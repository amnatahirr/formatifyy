import pdfplumber
from formatter.rules import detect_line_type
import re

def _is_likely_paragraph_break(line):
    """
    Determines if a line is a true paragraph break (empty or very minimal).
    Multiple consecutive spaces or truly empty lines indicate paragraph boundaries.
    """
    return not line or len(line.strip()) == 0

def _should_merge_with_next(current_line, next_line):
    """
    Determines if current_line should be merged with next_line to form a complete paragraph.
    
    Rules:
    - Don't merge if current line is a heading
    - Don't merge if current line ends with colon (e.g., "Following are:")
    - Don't merge if next line is a heading
    - Don't merge if next line starts with a bullet/number
    - Don't merge if current line is very short and ALL CAPS (likely a heading)
    - DO merge normal body text that spans multiple lines in the PDF
    """
    if not current_line or not next_line:
        return False
    
    current_stripped = current_line.strip()
    next_stripped = next_line.strip()
    
    if not current_stripped or not next_stripped:
        return False
    
    # Check if current line is a heading by looking at its characteristics
    current_type = detect_line_type(current_stripped, None)
    next_type = detect_line_type(next_stripped, current_type)
    
    # Don't merge headings with body text
    if current_type in ("heading1", "heading2", "heading3"):
        return False
    
    # Don't merge if current ends with colon (list intro)
    if current_stripped.endswith(":"):
        return False
    
    # Don't merge if next line is a heading
    if next_type in ("heading1", "heading2", "heading3"):
        return False
    
    # Don't merge if next line is a bullet or numbered item
    if next_type in ("bullet", "numbered"):
        return False
    
    # Don't merge if next line looks like a new heading (all caps, short)
    if next_stripped.isupper() and len(next_stripped.split()) <= 6:
        return False
    
    # If current ends with punctuation mid-sentence, merge with next
    if current_stripped.endswith((",", "-")):
        return True
    
    # If next line starts with lowercase (continuation), merge them
    if next_stripped[0].islower():
        return True
    
    return False

def parse_pdf(file_path):
    """
    Returns list of dicts: {"text": paragraph_text, "type": paragraph_type}
    
    Intelligently merges PDF lines into logical paragraphs by detecting:
    1. True paragraph breaks (empty lines)
    2. Heading boundaries
    3. List item boundaries
    4. Continuous body text spanning multiple PDF lines
    """
    with pdfplumber.open(file_path) as pdf:
        # Extract all text with line information
        raw_lines = []
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            # Split by lines but preserve line content
            for line in text.splitlines():
                raw_lines.append(line.strip())
    
    # Merge lines into logical paragraphs
    merged_paragraphs = []
    current_paragraph = ""
    
    i = 0
    while i < len(raw_lines):
        line = raw_lines[i]
        
        # Handle empty lines as paragraph breaks
        if _is_likely_paragraph_break(line):
            if current_paragraph.strip():
                merged_paragraphs.append(current_paragraph.strip())
                current_paragraph = ""
            i += 1
            continue
        
        # Start or continue building paragraph
        if not current_paragraph:
            current_paragraph = line
        else:
            # Check if we should merge with the next line
            if _should_merge_with_next(current_paragraph, line):
                current_paragraph += " " + line
            else:
                # Save current paragraph and start new one
                if current_paragraph.strip():
                    merged_paragraphs.append(current_paragraph.strip())
                current_paragraph = line
        
        i += 1
    
    # Don't forget the last paragraph
    if current_paragraph.strip():
        merged_paragraphs.append(current_paragraph.strip())
    
    # Now detect line types for each merged paragraph
    lines = []
    prev_type = None
    
    for para_text in merged_paragraphs:
        if para_text:
            line_type = detect_line_type(para_text, prev_type)
            lines.append({"text": para_text, "type": line_type})
            prev_type = line_type
    
    return lines
