"""
checker/perfect_content_checker.py
ULTRA-AGGRESSIVE VERSION - Guaranteed to catch Abstract ↔ Proposed Solution swaps
"""

import os
import re
import json
import pickle
import logging
import numpy as np
from typing import List, Dict, Any, Optional, Set, Tuple
from collections import defaultdict, Counter
from dataclasses import dataclass
import hashlib

logger = logging.getLogger(__name__)

@dataclass
class SectionSignature:
    heading: str
    keywords: Set[str]
    patterns: List[re.Pattern]
    tense_pattern: str
    bullet_point_ratio: float
    first_person_ratio: float
    future_tense_ratio: float

class PerfectContentChecker:
    """
    ULTRA-AGGRESSIVE CHECKER - Uses multiple strategies to catch swaps
    """
    
    def __init__(self, model_dir: str = "checker/models"):
        self.model_dir = model_dir
        os.makedirs(model_dir, exist_ok=True)
        
        # Load YOUR trained model
        self.trained_model = None
        self.trained_model_available = False
        self._load_trained_model()
        
        # Initialize signatures with STRONG definitions
        self.signatures = {}
        self._initialize_strong_signatures()
        
        logger.info(f"✅ Ultra-Aggressive Checker initialized")
        logger.info(f"   - Your trained model: {'✅ AVAILABLE' if self.trained_model_available else '❌ NOT AVAILABLE'}")
        logger.info(f"   - Pre-defined signatures: {len(self.signatures)}")
    
    def _load_trained_model(self):
        """Load YOUR trained model"""
        model_path = os.path.join(os.path.dirname(__file__), "content_classifier.pkl")
        if os.path.exists(model_path):
            try:
                with open(model_path, 'rb') as f:
                    self.trained_model = pickle.load(f)
                self.trained_model_available = True
                logger.info(f"✅ Loaded YOUR trained model")
            except Exception as e:
                logger.warning(f"❌ Failed to load trained model: {e}")
    
    def _initialize_strong_signatures(self):
        """Initialize with VERY STRONG signatures for Abstract and Proposed Solution"""
        
        # ABSTRACT signature - what ABSTRACT should look like
        self.signatures['Abstract'] = SectionSignature(
            heading='Abstract',
            keywords={
                # Abstract keywords - summary, overview, brief
                'presents', 'paper', 'study', 'research', 'investigates', 'examines',
                'explores', 'analyzes', 'discusses', 'reports', 'describes',
                'summary', 'overview', 'brief', 'concise', 'outline',
                'this paper', 'this study', 'this research', 'this work'
            },
            patterns=[],
            tense_pattern='present',  # Abstracts use present tense
            bullet_point_ratio=0.1,   # Abstracts rarely have bullet points
            first_person_ratio=0.2,    # Abstracts use "this paper" not "we will"
            future_tense_ratio=0.1     # Abstracts don't talk about future
        )
        
        # PROPOSED SOLUTION signature - what PROPOSED SOLUTION should look like
        self.signatures['Proposed Solution'] = SectionSignature(
            heading='Proposed Solution',
            keywords={
                # Proposed Solution keywords - future, implementation, features
                'proposed', 'system', 'will', 'shall', 'developed', 'implemented',
                'features', 'functionality', 'module', 'component', 'interface',
                'backend', 'frontend', 'database', 'api', 'user', 'admin',
                'allows', 'enables', 'provides', 'includes', 'offers',
                'we propose', 'our solution', 'the system', 'the application'
            },
            patterns=[],
            tense_pattern='future',  # Proposed solutions use future tense
            bullet_point_ratio=0.3,   # Proposed solutions often have bullet points
            first_person_ratio=0.4,    # Proposed solutions use "we will"
            future_tense_ratio=0.5     # Proposed solutions talk about future
        )
        
        # Add other common sections
        self.signatures['Introduction'] = SectionSignature(
            heading='Introduction',
            keywords={'introduction', 'background', 'context', 'motivation', 'problem'},
            patterns=[],
            tense_pattern='present',
            bullet_point_ratio=0.05,
            first_person_ratio=0.1,
            future_tense_ratio=0.05
        )
        
        self.signatures['Background'] = SectionSignature(
            heading='Background',
            keywords={'background', 'history', 'context', 'previous', 'existing'},
            patterns=[],
            tense_pattern='past',
            bullet_point_ratio=0.05,
            first_person_ratio=0.05,
            future_tense_ratio=0.0
        )
        
        self.signatures['Problem Statement'] = SectionSignature(
            heading='Problem Statement',
            keywords={'problem', 'issue', 'challenge', 'difficulty', 'lack', 'absence'},
            patterns=[],
            tense_pattern='present',
            bullet_point_ratio=0.1,
            first_person_ratio=0.05,
            future_tense_ratio=0.0
        )
        
        self.signatures['Expected Outcomes'] = SectionSignature(
            heading='Expected Outcomes',
            keywords={'expected', 'outcomes', 'benefits', 'gains', 'results', 'impact'},
            patterns=[],
            tense_pattern='future',
            bullet_point_ratio=0.5,
            first_person_ratio=0.2,
            future_tense_ratio=0.6
        )
        
        self.signatures['Related Work'] = SectionSignature(
            heading='Related Work',
            keywords={'related', 'work', 'existing', 'previous', 'research', 'study', 'paper', 'author'},
            patterns=[],
            tense_pattern='past',
            bullet_point_ratio=0.1,
            first_person_ratio=0.0,
            future_tense_ratio=0.0
        )
    
    @staticmethod
    def sections_from_blocks(blocks: List[Dict]) -> List[Dict]:
        """Convert blocks to sections"""
        sections = []
        current_heading = None
        current_content = []
        
        for block in blocks:
            block_type = block.get('type', 'paragraph')
            text = block.get('text', '').strip()
            
            if not text:
                continue
            
            if block_type == 'heading':
                if current_heading and current_content:
                    sections.append({
                        'heading': current_heading,
                        'content': ' '.join(current_content).strip()
                    })
                current_heading = text
                current_content = []
            else:
                if current_heading:
                    current_content.append(text)
        
        if current_heading and current_content:
            sections.append({
                'heading': current_heading,
                'content': ' '.join(current_content).strip()
            })
        
        return sections
    
    def check_section(self, heading: str, content: str, context: Dict = None) -> Optional[Dict]:
        """
        ULTRA-AGGRESSIVE check for content mismatch
        """
        if len(content) < 50:
            return None
        
        # Normalize heading
        canonical = self._resolve_heading(heading)
        if canonical not in self.signatures:
            return None
        
        # Get signature for this heading
        expected_sig = self.signatures[canonical]
        
        # Analyze the actual content
        actual_sig = self._analyze_content(content)
        
        # Calculate mismatch scores using MULTIPLE methods
        scores = []
        reasons = []
        
        # 1. KEYWORD MISMATCH SCORE
        keyword_score, keyword_reason = self._check_keywords(content, canonical, expected_sig)
        scores.append(keyword_score)
        if keyword_reason:
            reasons.append(keyword_reason)
        
        # 2. TENSE MISMATCH SCORE
        tense_score, tense_reason = self._check_tense(content, expected_sig)
        scores.append(tense_score)
        if tense_reason:
            reasons.append(tense_reason)
        
        # 3. BULLET POINT MISMATCH SCORE
        bullet_score, bullet_reason = self._check_bullet_points(content, expected_sig)
        scores.append(bullet_score)
        if bullet_reason:
            reasons.append(bullet_reason)
        
        # 4. FIRST PERSON MISMATCH SCORE
        first_person_score, first_person_reason = self._check_first_person(content, expected_sig)
        scores.append(first_person_score)
        if first_person_reason:
            reasons.append(first_person_reason)
        
        # 5. FUTURE TENSE MISMATCH SCORE
        future_score, future_reason = self._check_future_tense(content, expected_sig)
        scores.append(future_score)
        if future_reason:
            reasons.append(future_reason)
        
        # 6. TRAINED MODEL SCORE (if available)
        if self.trained_model_available:
            model_score, model_reason = self._check_trained_model(heading, content)
            scores.append(model_score * 2)  # Double weight for trained model
            if model_reason:
                reasons.append(model_reason)
        
        # Calculate final mismatch score (average of all scores)
        final_score = sum(scores) / len(scores) if scores else 0
        
        # MUCH LOWER THRESHOLD - 0.3 means 30% mismatch is enough to flag
        if final_score > 0.3:
            # Find which section this content actually belongs to
            best_match = self._find_best_match(content, canonical)
            
            return {
                'type': 'content_mismatch',
                'severity': 'error' if final_score > 0.6 else 'warning',
                'code': 'CONTENT_MISMATCH',
                'heading': heading,
                'canonical_heading': canonical,
                'best_match_heading': best_match,
                'confidence': round(min(final_score, 1.0), 2),
                'detection': 'ultra_aggressive',
                'detectors_used': reasons,
                'mismatch_score': round(final_score, 2),
                'message': self._generate_message(heading, canonical, best_match, reasons, final_score),
                'suggestions': self._generate_suggestions(canonical, best_match)
            }
        
        return None
    
    def _check_keywords(self, content: str, canonical: str, expected_sig: SectionSignature) -> Tuple[float, str]:
        """Check if keywords match expected section"""
        content_lower = content.lower()
        
        # Define STRONG keyword sets for each section
        abstract_keywords = {'presents', 'paper', 'study', 'research', 'summary', 'overview', 'brief'}
        proposed_keywords = {'proposed', 'system', 'will', 'developed', 'implemented', 'features', 'module', 'interface', 'allows', 'enables'}
        
        if canonical == 'Abstract':
            # Count Abstract keywords (should be high)
            abstract_count = sum(1 for kw in abstract_keywords if kw in content_lower)
            # Count Proposed Solution keywords (should be low)
            proposed_count = sum(1 for kw in proposed_keywords if kw in content_lower)
            
            if proposed_count > abstract_count:
                score = min(proposed_count / max(abstract_count, 1), 1.0)
                return score, f"Found {proposed_count} proposed-solution keywords but only {abstract_count} abstract keywords"
            
        elif canonical == 'Proposed Solution':
            # Count Proposed Solution keywords (should be high)
            proposed_count = sum(1 for kw in proposed_keywords if kw in content_lower)
            # Count Abstract keywords (should be low)
            abstract_count = sum(1 for kw in abstract_keywords if kw in content_lower)
            
            if abstract_count > proposed_count:
                score = min(abstract_count / max(proposed_count, 1), 1.0)
                return score, f"Found {abstract_count} abstract keywords but only {proposed_count} proposed-solution keywords"
        
        return 0.0, ""
    
    def _check_tense(self, content: str, expected_sig: SectionSignature) -> Tuple[float, str]:
        """Check tense usage"""
        future_indicators = ['will', 'shall', 'going to', 'proposed', 'aims', 'intends', 'plans']
        past_indicators = ['was', 'were', 'had', 'developed', 'implemented', 'tested', 'found']
        present_indicators = ['is', 'are', 'has', 'have', 'presents', 'describes', 'shows']
        
        content_lower = content.lower()
        
        future_count = sum(content_lower.count(w) for w in future_indicators)
        past_count = sum(content_lower.count(w) for w in past_indicators)
        present_count = sum(content_lower.count(w) for w in present_indicators)
        
        total = future_count + past_count + present_count
        if total == 0:
            return 0.0, ""
        
        future_ratio = future_count / total
        present_ratio = present_count / total
        past_ratio = past_count / total
        
        if expected_sig.heading == 'Abstract':
            # Abstract should be mostly present tense
            if future_ratio > 0.2:
                return 0.8, f"Abstract has {future_ratio:.0%} future tense (should be <20%)"
            if past_ratio > 0.3:
                return 0.6, f"Abstract has {past_ratio:.0%} past tense"
                
        elif expected_sig.heading == 'Proposed Solution':
            # Proposed Solution should be mostly future tense
            if present_ratio > 0.5:
                return 0.7, f"Proposed Solution has {present_ratio:.0%} present tense (should be future)"
            if past_ratio > 0.3:
                return 0.6, f"Proposed Solution has {past_ratio:.0%} past tense"
        
        return 0.0, ""
    
    def _check_bullet_points(self, content: str, expected_sig: SectionSignature) -> Tuple[float, str]:
        """Check bullet point usage"""
        bullet_count = len(re.findall(r'^[•\-*]\s', content, re.MULTILINE))
        
        if expected_sig.heading == 'Abstract' and bullet_count > 3:
            return 0.9, f"Abstract has {bullet_count} bullet points (should have few or none)"
        elif expected_sig.heading == 'Proposed Solution' and bullet_count < 2:
            return 0.5, f"Proposed Solution has only {bullet_count} bullet points (should have several)"
        
        return 0.0, ""
    
    def _check_first_person(self, content: str, expected_sig: SectionSignature) -> Tuple[float, str]:
        """Check first person usage"""
        first_person = len(re.findall(r'\b(I|we|our|my)\b', content, re.IGNORECASE))
        
        if expected_sig.heading == 'Abstract' and first_person > 2:
            return 0.7, f"Abstract uses '{first_person}' first-person pronouns (should be impersonal)"
        elif expected_sig.heading == 'Proposed Solution' and first_person < 1:
            return 0.4, f"Proposed Solution lacks first-person pronouns (should use 'we will')"
        
        return 0.0, ""
    
    def _check_future_tense(self, content: str, expected_sig: SectionSignature) -> Tuple[float, str]:
        """Check future tense usage"""
        future_words = ['will', 'shall', 'going to', 'proposed', 'aims', 'intends', 'plans', 'future']
        content_lower = content.lower()
        
        future_count = sum(content_lower.count(w) for w in future_words)
        
        if expected_sig.heading == 'Abstract' and future_count > 3:
            return 0.8, f"Abstract uses '{future_count}' future-tense words (should describe what IS, not what WILL BE)"
        elif expected_sig.heading == 'Proposed Solution' and future_count < 2:
            return 0.5, f"Proposed Solution lacks future-tense words (should describe what WILL BE implemented)"
        
        return 0.0, ""
    
    def _check_trained_model(self, heading: str, content: str) -> Tuple[float, str]:
        """Use your trained model"""
        try:
            # Need embedder - if not available, return 0
            from sentence_transformers import SentenceTransformer
            embedder = SentenceTransformer('all-MiniLM-L6-v2')
            
            text = f"{heading} [SEP] {content[:512]}"
            vec = embedder.encode([text], convert_to_numpy=True)
            prob = self.trained_model.predict_proba(vec)[0]
            
            # prob[0] = wrong_placement probability
            return prob[0], f"Trained model confidence: {prob[0]:.0%}"
        except:
            return 0.0, ""
    
    def _find_best_match(self, content: str, current_heading: str) -> str:
        """Find which section this content actually belongs to"""
        content_lower = content.lower()
        
        # Check against all signatures
        best_match = None
        best_score = 0
        
        for heading, sig in self.signatures.items():
            if heading == current_heading:
                continue
            
            # Count keyword matches
            matches = sum(1 for kw in sig.keywords if kw in content_lower)
            score = matches / max(len(sig.keywords), 1)
            
            if score > best_score and score > 0.2:
                best_score = score
                best_match = heading
        
        return best_match
    
    def _resolve_heading(self, heading: str) -> str:
        """Normalize heading"""
        heading = re.sub(r'^\d+[\.\d]*\s*', '', heading.strip())
        heading = re.sub(r'[:\-]+$', '', heading)
        heading = re.sub(r'#+\s*', '', heading)
        
        # Map common variations
        heading_lower = heading.lower()
        if 'abstract' in heading_lower:
            return 'Abstract'
        if 'proposed' in heading_lower or 'solution' in heading_lower:
            return 'Proposed Solution'
        if 'introduction' in heading_lower:
            return 'Introduction'
        if 'background' in heading_lower:
            return 'Background'
        if 'problem' in heading_lower:
            return 'Problem Statement'
        if 'expected' in heading_lower or 'outcome' in heading_lower:
            return 'Expected Outcomes'
        if 'related' in heading_lower or 'literature' in heading_lower:
            return 'Related Work'
        
        return heading
    
    def _generate_message(self, heading: str, canonical: str, best_match: str, reasons: List[str], score: float) -> str:
        """Generate message"""
        confidence = "highly likely" if score > 0.7 else "likely"
        
        if best_match:
            return (f"⚠️ It is {confidence} that the content under '{heading}' actually belongs to '{best_match}'. "
                   f"Reasons: {'; '.join(reasons[:2])}")
        else:
            return (f"⚠️ The content under '{heading}' doesn't match what's expected for a '{canonical}' section. "
                   f"Reasons: {'; '.join(reasons[:2])}")
    
    def _generate_suggestions(self, canonical: str, best_match: str) -> List[str]:
        """Generate suggestions"""
        suggestions = []
        if best_match:
            suggestions.append(f"Move this content to the '{best_match}' section")
            
            if best_match == 'Abstract' and canonical == 'Proposed Solution':
                suggestions.append("The Abstract should be a brief summary, not describe system features")
            elif best_match == 'Proposed Solution' and canonical == 'Abstract':
                suggestions.append("The Proposed Solution should describe what you WILL build, not summarize the whole project")
        
        suggestions.append("Review the document structure")
        return suggestions
    
    def _analyze_content(self, content: str) -> Dict:
        """Analyze content features"""
        content_lower = content.lower()
        
        # Count features
        future_count = sum(content_lower.count(w) for w in ['will', 'shall', 'going to', 'proposed'])
        bullet_count = len(re.findall(r'^[•\-*]\s', content, re.MULTILINE))
        first_person = len(re.findall(r'\b(I|we|our|my)\b', content, re.IGNORECASE))
        
        return {
            'future_count': future_count,
            'bullet_count': bullet_count,
            'first_person': first_person
        }


# ============================================================================
# Factory function
# ============================================================================

def create_perfect_checker(model_dir: str = "checker/models") -> PerfectContentChecker:
    """Create ultra-aggressive checker"""
    return PerfectContentChecker(model_dir)