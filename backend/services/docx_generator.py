from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.shared import OxmlElement
from docx.oxml.ns import qn
from formatter.rules import detect_line_type
from formatter.paragraph_formatter import paragraph_formatter

def set_page_size(doc, page_size='A4'):
    """
    Set the page size for the document.
    Supported sizes: Letter, Legal, A4, A3, Tabloid
    """
    page_dimensions = {
        'Letter': (Inches(8.5), Inches(11)),
        'Legal': (Inches(8.5), Inches(14)),
        'A4': (Inches(8.27), Inches(11.69)),
        'A3': (Inches(11.69), Inches(16.54)),
        'Tabloid': (Inches(11), Inches(17)),
    }
    
    if page_size not in page_dimensions:
        page_size = 'A4'  # Default to A4
    
    width, height = page_dimensions[page_size]
    
    # Access the first section (or create one if needed)
    section = doc.sections[0] if doc.sections else doc.add_section()
    
    # Set page width and height
    section.page_width = width
    section.page_height = height
    
    return doc

def generate_docx_from_formatted(formatted_content, output_path, template_rules=None, title=None):
    """
    Generates a DOCX file from pre-formatted content with template rules applied.
    formatted_content: dict with formatted paragraphs and metadata
    template_rules: dict with formatting rules from template
    title: document title (not added to document, used for filename only)
    """
    doc = Document()
    
    # Get complete formatting rules (with defaults)
    rules = paragraph_formatter.get_formatting_rules(template_rules)
    
    # Set page size from template
    page_size = rules.get('page_size', 'A4')
    doc = set_page_size(doc, page_size)
    
    # Set document margins from template
    paragraph_formatter.set_document_margins(doc, rules=rules)

    # Note: Title is NOT added to the document, only used for metadata

    # Add formatted content paragraphs
    for para in formatted_content.get("content", []):
        # HANDLE IMAGE 
        if para.get("image_path"):
            try:
                doc.add_picture(para["image_path"], width=Inches(5))
            except Exception as e:
                print("Image insert error:", e)
                continue
        text = para.get("text", "")
        formatting = para.get("formatting", {})
        style = para.get("style", "body")
        detected_type = para.get("detected_type", style)
        
        if not text.strip():
            continue

        # Apply formatting based on detected type
        if detected_type == "heading1":
            paragraph_formatter.add_heading(doc, text, level=1, rules=rules)
        elif detected_type == "heading2":
            paragraph_formatter.add_heading(doc, text, level=2, rules=rules)
        elif detected_type == "heading3":
            paragraph_formatter.add_heading(doc, text, level=3, rules=rules)
        elif detected_type == "heading4":
            paragraph_formatter.add_heading(doc, text, level=4, rules=rules)
        elif detected_type == "bullet":
            paragraph_formatter.add_bullet_point(doc, text, rules=rules, level=0)
        elif detected_type == "numbered":
            paragraph_formatter.add_numbered_item(doc, text, rules=rules, level=0)
        else:
            # Apply body paragraph with formatting
            paragraph_formatter.add_paragraph(doc, text, rules=rules)

    doc.save(output_path)


def generate_docx(parsed_lines, output_path, template_rules=None):
    """
    Generates a DOCX file from parsed lines with rules applied.
    parsed_lines: list of dicts {"text": line_text, "type": line_type}
    template_rules: dict with formatting rules
    """
    doc = Document()
    
    # Get complete formatting rules (with defaults)
    rules = paragraph_formatter.get_formatting_rules(template_rules)
    
    # Set page size from template
    page_size = rules.get('page_size', 'A4')
    doc = set_page_size(doc, page_size)
    
    # Set document margins from template
    paragraph_formatter.set_document_margins(doc, rules=rules)

    for item in parsed_lines:
        line = item["text"]
        line_type = item["type"]

        if line_type == "heading1":
            paragraph_formatter.add_heading(doc, line, level=1, rules=rules)
        elif line_type == "heading2":
            paragraph_formatter.add_heading(doc, line, level=2, rules=rules)
        elif line_type == "heading3":
            paragraph_formatter.add_heading(doc, line, level=3, rules=rules)
        elif line_type == "heading4":
            paragraph_formatter.add_heading(doc, line, level=4, rules=rules)
        elif line_type == "bullet":
            paragraph_formatter.add_bullet_point(doc, line, rules=rules, level=0)
        elif line_type == "numbered":
            paragraph_formatter.add_numbered_item(doc, line, rules=rules, level=0)
        else:  # paragraph
            paragraph_formatter.add_paragraph(doc, line, rules=rules)

    doc.save(output_path)
