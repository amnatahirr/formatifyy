import os
import tempfile
from docx import Document
from docx.shared import Pt
from ML.predictor import predict_line_type
from formatter.paragraph_formatter import paragraph_formatter
from services.document_parser import parser as doc_parser
from services.docx_generator import set_page_size


def format_line_with_colon(
    p,
    line,
    font_size=11,
    bold=False,
    append_colon=False
):
    """
    Adds a line to paragraph `p` with text before ':' bolded.
    If append_colon=True, a colon is added at the end of the line.
    """

    if append_colon and not line.endswith(":"):
        line += ":"

    if ":" in line:
        parts = line.split(":", 1)
        bold_text = parts[0].strip() + ":"
        normal_text = parts[1].strip()

        run_bold = p.add_run(bold_text + " ")
        run_bold.bold = True
        run_bold.font.size = Pt(font_size)

        run_normal = p.add_run(normal_text)
        run_normal.bold = bold
        run_normal.font.size = Pt(font_size)

    else:
        run = p.add_run(line)
        run.bold = bold
        run.font.size = Pt(font_size)


def format_docx(input_path: str, output_path: str, template_rules: dict = None):
    """
    Core formatting logic with template rules.
    Reads original DOCX and writes a new formatted DOCX using template rules.
    
    Args:
        input_path: Path to input DOCX file
        output_path: Path to output DOCX file
        template_rules: Dictionary with formatting rules from template
    """

    try:
        doc = Document(input_path)
    except Exception as e:
        print(f"[v0] Error opening input document: {str(e)}")
        raise
    
    new_doc = Document()
    
    # Use provided template rules or defaults
    rules = paragraph_formatter.get_formatting_rules(template_rules)
    
    # Set page size from template
    page_size = rules.get('page_size', 'A4')
    new_doc = set_page_size(new_doc, page_size)
    
    # Set margins from template
    paragraph_formatter.set_document_margins(new_doc, rules=rules)

    # Extract non-empty lines
    lines = [
        para.text.strip()
        for para in doc.paragraphs
        if para.text.strip() != ""
    ]

    i = 0
    in_list_context = False  # Track if we're in a list context

    while i < len(lines):
        try:
            line = lines[i]
            line_type, confidence = predict_line_type(line)
            # ---------- HEADING 1 / 2 / 3 / 4 ----------
            if line_type in ["heading1", "heading2", "heading3", "heading4"]:
                level_map = {
                    "heading1": 1,
                    "heading2": 2,
                    "heading3": 3,
                    "heading4": 4
                }
                level = level_map.get(line_type, 1)
                paragraph_formatter.add_heading(new_doc, line, level=level, rules=rules)
                # Check if this is a list indicator (e.g., "Following are the content:")
                if any(indicator in line for indicator in ["Following are", "Below are", "Items:", "Points:", "includes:"]):
                    in_list_context = True
                else:
                    in_list_context = False
                prev_type = line_type
                i += 1
                continue

            # ---------- BULLET LIST ----------
            if line_type == "bullet":
                list_level = 0
                while i < len(lines) and predict_line_type(lines[i][0]) == "bullet":
                    clean_line = lines[i].lstrip(" -•*")
                    # Detect indentation level
                    original_line = lines[i]
                    indent_count = len(original_line) - len(original_line.lstrip())
                    list_level = indent_count // 4  # 4 spaces per level
                    paragraph_formatter.add_bullet_point(new_doc, clean_line, rules=rules, bold=False, level=list_level)
                    prev_type = "bullet"
                    i += 1
                continue

            # ---------- NUMBERED LIST ----------
            if line_type == "numbered":
                list_level = 0
                while i < len(lines) and predict_line_type(lines[i][0]) == "numbered":
                    line_to_process = lines[i]
                    # Remove numbering prefix (1., 2., a), b), etc.)
                    import re
                    clean_line = re.sub(r'^[\d\w]+[.\)]\s+', '', line_to_process)
                    # Detect indentation level
                    indent_count = len(line_to_process) - len(line_to_process.lstrip())
                    list_level = indent_count // 4  # 4 spaces per level
                    paragraph_formatter.add_numbered_item(new_doc, clean_line, rules=rules, level=list_level)
                    prev_type = "numbered"
                    i += 1
                continue

            # ---------- NORMAL PARAGRAPH OR IMPLICIT BULLET ----------
            # If we're in list context and this looks like a list item, treat as bullet
            if in_list_context and line_type == "paragraph":
                words = line.split()
                # Check if it looks like a list item (short, simple phrase like "This is amna")
                if 2 <= len(words) <= 8 and len(line) < 100:
                    paragraph_formatter.add_bullet_point(new_doc, line, rules=rules, level=0)
                    prev_type = "bullet"
                    i += 1
                    continue
            
            paragraph_formatter.add_paragraph(new_doc, line, rules=rules)
            in_list_context = False  # Exit list context on substantial paragraph
            prev_type = "paragraph"
            i += 1
            
        except Exception as e:
            print(f"[v0] Error processing line {i}: {str(e)}")
            # Skip problematic lines and continue
            i += 1
            continue

    try:
        new_doc.save(output_path)
    except Exception as e:
        print(f"[v0] Error saving output document: {str(e)}")
        raise


def apply_formatting(input_path: str, template_rules: dict = None) -> str:
    """
    Wrapper used by export API.
    Takes original DOCX path and optional template rules,
    returns formatted DOCX path.
    
    Args:
        input_path: Path to original DOCX file
        template_rules: Optional template formatting rules
    """

    temp_dir = tempfile.mkdtemp()
    output_path = os.path.join(temp_dir, "formatted.docx")

    format_docx(input_path, output_path, template_rules=template_rules)

    return output_path


def apply_template_headings(docx_path: str, detected_headings: list, output_path: str):
    """
    Sets specific paragraphs to Word 'Heading X' styles.
    
    Args:
        docx_path: Path to input DOCX
        detected_headings: List of dicts [{"para_index": 5, "heading_level": 1}, ...]
        output_path: Path to save result
    """
    from docx import Document
    doc = Document(docx_path)
    
    for h in detected_headings:
        idx = h.get("para_index")
        lvl = h.get("heading_level", 1)
        
        if idx is not None and 0 <= idx < len(doc.paragraphs):
            para = doc.paragraphs[idx]
            # Set the built-in Word style name
            try:
                para.style = f"Heading {lvl}"
            except Exception as e:
                print(f"[apply_template_headings] Style Heading {lvl} error: {e}")
                
    doc.save(output_path)
