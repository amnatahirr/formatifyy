import re
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class DetectedBullet:
    """Represents a detected bullet/list item"""
    text: str
    index: int  # Index in document blocks
    confidence: float  # 0.0 - 1.0 confidence score
    reason: str  # Why it was detected as a bullet


class BulletDetectionService:
    """Service to detect content that should be formatted as bullets"""
    
    def __init__(self):
        # Common bullet patterns
        self.bullet_patterns = [
            r'^\s*[-•*]\s+',  # Standard bullets
            r'^\s*\d+\.\s+',  # Numbered lists
            r'^\s*[a-zA-Z]\)\s+',  # Letter lists
            r'^\s*[a-zA-Z]\.\s+',  # Letter with period
        ]
        
        # Keywords that suggest list context
        self.list_context_keywords = [
            'following', 'below', 'includes', 'consists of', 'contains',
            'such as', 'examples', 'list', 'steps', 'requirements',
            'features', 'benefits', 'include:', 'followed by:', 'as follows:'
        ]
        
        # Min/max length for list items
        self.min_bullet_length = 3
        self.max_bullet_length = 200
        self._marker_pattern = re.compile(
            r'^\s*(?:[•○■▪\-*→»–]+|\(?\d+[.)]|\(?[a-zA-Z][.)]|\(?[ivxlcdmIVXLCDM]+[.)])\s+\S'
        )
    
    def detect_bullets_in_blocks(self, blocks: List[Dict[str, Any]]) -> List[DetectedBullet]:
        """
        Detect bullets from a list of document blocks.
        
        Args:
            blocks: List of document blocks with type, text, and metadata
            
        Returns:
            List of DetectedBullet objects
        """
        detected = []
        
        for i, block in enumerate(blocks):
            if block.get('type') not in ['paragraph', 'list_item']:
                continue
            
            text = block.get('text', '').strip()
            if not text:
                continue
            
            # Skip headings and other block types
            if len(text) < self.min_bullet_length:
                continue
            
            # Check for existing list items
            if block.get('type') == 'list_item':
                detected.append(DetectedBullet(
                    text=text,
                    index=i,
                    confidence=0.95,
                    reason="Already marked as list_item"
                ))
                continue

            # Skip paragraphs that look like section headings — they should
            # never be treated as list items regardless of pattern matching.
            if block.get('type') == 'heading' or self._is_heading_like(text):
                continue

            # Score the paragraph for bullet likelihood
            score, reason = self._score_for_bullets(text, blocks, i)

            if score > 0.4:  # Lowered threshold — split items score ~0.5
                detected.append(DetectedBullet(
                    text=text,
                    index=i,
                    confidence=score,
                    reason=reason
                ))
        
        return detected
    
    def _is_heading_like(self, text: str) -> bool:
        """
        Return True if the text looks like a section heading rather than a
        list item. Headings should never be shown as bullet candidates.
        """
        # Numbered headings: "1. Introduction", "2. Background", etc.
        if re.match(r'^\d+[.)\s]\s*[A-Z]', text):
            return True
        # ALL-CAPS short lines
        if text.isupper() and len(text.split()) <= 8:
            return True
        # Title-case short lines (≤ 6 words, no sentence punctuation)
        words = text.split()
        if (len(words) <= 6
                and not text.endswith(('.', '?', '!', ':'))
                and all(w[0].isupper() for w in words if w)):
            return True
        return False

    def _score_for_bullets(self, text: str, blocks: List[Dict[str, Any]], index: int) -> tuple[float, str]:
        """
        Score text to determine if it should be a bullet.
        Returns (score, reason)
        """
        score = 0.0
        reasons = []
        
        # Check for bullet patterns in text
        for pattern in self.bullet_patterns:
            if re.match(pattern, text):
                score += 0.4
                reasons.append("matches_bullet_pattern")
                break
        if self._marker_pattern.match(text):
            score += 0.35
            reasons.append("matches_extended_marker")
        
        # Check length - short items are more likely bullets
        if len(text) < 100:
            score += 0.2
            reasons.append("short_length")
        elif len(text) > 200:
            score -= 0.2
            reasons.append("long_length")
        
        # Check context — look at previous block.
        # Headings are intentionally excluded: "3. Steps for Writing..." contains
        # "steps" as a keyword but that heading should NOT make the next prose
        # sentence ("Writing a good assignment...") look like a list item.
        if index > 0:
            prev_block    = blocks[index - 1]
            prev_text_raw = prev_block.get('text', '')
            prev_text     = prev_text_raw.lower()
            prev_is_heading = (
                prev_block.get('type') == 'heading' or
                self._is_heading_like(prev_text_raw)
            )

            if not prev_is_heading:
                # Check if previous block suggests a list context
                for keyword in self.list_context_keywords:
                    if keyword in prev_text:
                        score += 0.3
                        reasons.append(f"list_context_keyword:{keyword}")
                        break

                # Check if previous block ends with colon
                if prev_text.rstrip().endswith(':'):
                    score += 0.25
                    reasons.append("prev_ends_with_colon")

            # Neighbour is already detected as list item → strong signal
            # (applies even after a heading — continuation of a list)
            if prev_block.get('type') == 'list_item':
                score += 0.3
                reasons.append("neighbour_is_list_item")
        
        # Check for keywords suggesting item-like content
        item_keywords = ['include', 'support', 'provide', 'ensure', 'maintain', 'improve']
        text_lower = text.lower()
        for keyword in item_keywords:
            if keyword in text_lower:
                score += 0.1
                reasons.append(f"item_keyword:{keyword}")
                break
        
        # Penalize paragraphs that look like prose
        if len(text.split()) > 20:
            words = text.split()
            avg_word_length = sum(len(w) for w in words) / len(words)
            if avg_word_length > 7:  # Longer words suggest prose
                score -= 0.15
                reasons.append("prose_likely")
        
        # Cap score at 1.0
        score = min(1.0, max(0.0, score))
        reason = ", ".join(reasons) if reasons else "no_signals"
        
        return score, reason
    
    def group_consecutive_bullets(self, detected: List[DetectedBullet]) -> List[List[DetectedBullet]]:
        """
        Group consecutive detected bullets together (to identify lists).
        
        Returns:
            List of bullet groups
        """
        if not detected:
            return []
        detected_sorted = sorted(detected, key=lambda d: d.index)
        groups: List[List[DetectedBullet]] = []
        current_group: List[DetectedBullet] = [detected_sorted[0]]

        for i in range(1, len(detected_sorted)):
            prev = detected_sorted[i - 1]
            cur = detected_sorted[i]

            # Keep list continuity with a small tolerance for one skipped block.
            if cur.index - prev.index <= 2:
                current_group.append(cur)
                continue

            if len(current_group) >= 2:
                groups.append(current_group)
            current_group = [cur]

        if len(current_group) >= 2:
            groups.append(current_group)

        return groups