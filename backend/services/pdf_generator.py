from fpdf import FPDF
from formatter.paragraph_formatter import paragraph_formatter

def hex_to_rgb(hex_color):
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def get_font_style(bold=False, italic=False, underline=False):
    """Return font style string for FPDF."""
    style = ''
    if bold:
        style += 'B'
    if italic:
        style += 'I'
    if underline:
        style += 'U'
    return style if style else ''

def map_font_to_fpdf(font_name):
    """
    Map common font names to FPDF built-in fonts.
    FPDF only supports: Helvetica, Times, Courier, Symbol, ZapfDingbats
    """
    if not font_name:
        return "Helvetica"
    
    font_lower = font_name.lower().strip()
    
    # Map to Helvetica (sans-serif)
    if any(name in font_lower for name in ["arial", "helvetica", "sans", "calibri", "verdana", "tahoma", "segoe"]):
        return "Helvetica"
    
    # Map to Times (serif)
    if any(name in font_lower for name in ["times", "roman", "serif", "georgia", "garamond", "cambria", "palatino"]):
        return "Times"
    
    # Map to Courier (monospace)
    if any(name in font_lower for name in ["courier", "mono", "consolas", "menlo", "monaco", "lucida console"]):
        return "Courier"
    
    # Default to Helvetica for any unknown font
    return "Helvetica"

def add_paragraph_to_pdf(pdf, text, config, page_width, rules):
    """
    Add a paragraph to PDF with proper wrapping and formatting.
    Uses multi_cell for intelligent text wrapping that respects paragraph boundaries.
    """
    # Helper function to convert points to mm
    def pt_to_mm(points):
        return points * 0.352778  # 1 point = 0.352778 mm
    
    # Helper function to calculate line height based on font size and spacing
    def get_pdf_height(multiplier, base_size=12):
        # Approximate: 1.0 spacing = 5mm for 12pt font
        # Scale based on font size
        return max(4, (5 * multiplier * base_size) / 12)
    
    # Set font and color - MAP THE FONT NAME
    font_style = get_font_style(config.get("bold", False), config.get("italic", False), config.get("underline", False))
    mapped_font = map_font_to_fpdf(config.get("font", "Arial"))
    pdf.set_font(mapped_font, font_style, size=config.get("size", 12))
    
    rgb = hex_to_rgb(config.get("color", "#000000"))
    pdf.set_text_color(*rgb)
    
    # Add space before paragraph
    space_before = config.get("space_before", 0)
    if space_before > 0:
        pdf.ln(pt_to_mm(space_before))
    
    line_height = get_pdf_height(config.get("line_spacing", 1.0), config.get("size", 12))
    
    # Use multi_cell for proper text wrapping that maintains paragraph cohesion
    # This ensures long paragraphs stay together instead of breaking awkwardly
    pdf.multi_cell(
        w=page_width,
        h=line_height,
        text=text,
        border=0,
        align='J',  # Justified alignment for professional look
        split_only=False
    )
    
    # Add space after paragraph
    space_after = config.get("space_after", 0)
    if space_after > 0:
        pdf.ln(pt_to_mm(space_after))
    else:
        # Add minimal spacing between paragraphs for visual separation
        pdf.ln(2)

def generate_pdf(parsed_lines, output_path, template_rules=None):
    """
    Generates a PDF from parsed lines with rules applied.
    parsed_lines: list of dicts {"text": line_text, "type": line_type}
    template_rules: dict with formatting rules from template
    """
    # Get complete formatting rules (with defaults)
    rules = paragraph_formatter.get_formatting_rules(template_rules)
    
    # Set page size from template
    page_size = rules.get('page_size', 'A4')
    page_sizes = {
        'Letter': ('L', 'Letter'),
        'Legal': ('L', 'Legal'),
        'A4': ('A4', 'A4'),
        'A3': ('A3', 'A3'),
        'Tabloid': (11 * 25.4, 17 * 25.4),  # Width and height in mm
    }
    
    # Initialize PDF with appropriate page size
    if page_size in ['Letter', 'Legal', 'A4', 'A3']:
        pdf = FPDF(format=page_sizes[page_size][1])
    else:
        pdf = FPDF(format='A4')  # Default fallback
    
    pdf.add_page()
    
    # Set page margins from template
    spacing_unit = rules.get("spacing_unit", "in")
    margin_top = paragraph_formatter._to_inches(rules.get("margin_top", 1.0), spacing_unit) * 25.4
    margin_bottom = paragraph_formatter._to_inches(rules.get("margin_bottom", 1.0), spacing_unit) * 25.4
    margin_left = paragraph_formatter._to_inches(rules.get("margin_left", 1.0), spacing_unit) * 25.4
    margin_right = paragraph_formatter._to_inches(rules.get("margin_right", 1.0), spacing_unit) * 25.4
    
    pdf.set_auto_page_break(auto=True, margin=margin_bottom)
    pdf.set_margins(margin_left, margin_top, margin_right)

    # Map the default font
    default_font = map_font_to_fpdf(rules.get("body_font", "Arial"))
    pdf.set_font(default_font, size=rules.get("body_size", 12))

    # Get the actual usable page width - use the left/right margins for proper calculation
    # FPDF measures from edge to edge, so subtract both margins
    page_width = pdf.w - margin_left - margin_right

    # Get all formatting from template - ALL FONTS ARE MAPPED
    heading1_config = {
        "font": rules.get("heading1_font", "Arial"),
        "size": rules.get("heading1_size", 16),
        "bold": rules.get("heading1_bold", True),
        "italic": rules.get("heading1_italic", False),
        "underline": rules.get("heading1_underline", False),
        "color": rules.get("heading1_color", "#000000"),
        "line_spacing": rules.get("heading1_line_spacing", 1.0),
        "space_before": rules.get("heading1_space_before", 12.0),
        "space_after": rules.get("heading1_space_after", 6.0),
    }
    
    heading2_config = {
        "font": rules.get("heading2_font", "Arial"),
        "size": rules.get("heading2_size", 14),
        "bold": rules.get("heading2_bold", True),
        "italic": rules.get("heading2_italic", False),
        "underline": rules.get("heading2_underline", False),
        "color": rules.get("heading2_color", "#000000"),
        "line_spacing": rules.get("heading2_line_spacing", 1.0),
        "space_before": rules.get("heading2_space_before", 10.0),
        "space_after": rules.get("heading2_space_after", 5.0),
    }
    
    heading3_config = {
        "font": rules.get("heading3_font", "Arial"),
        "size": rules.get("heading3_size", 13),
        "bold": rules.get("heading3_bold", True),
        "italic": rules.get("heading3_italic", False),
        "underline": rules.get("heading3_underline", False),
        "color": rules.get("heading3_color", "#000000"),
        "line_spacing": rules.get("heading3_line_spacing", 1.0),
        "space_before": rules.get("heading3_space_before", 8.0),
        "space_after": rules.get("heading3_space_after", 4.0),
    }
    
    body_config = {
        "font": rules.get("body_font", "Arial"),
        "size": rules.get("body_size", 12),
        "color": rules.get("body_color", "#000000"),
        "line_spacing": rules.get("body_line_spacing", 1.0),
        "space_before": rules.get("body_space_before", 0.0),
        "space_after": rules.get("body_space_after", 0.0),
    }
    
    bullet_config = {
        "font": rules.get("bullet_font", "Arial"),
        "size": rules.get("bullet_size", 12),
        "color": rules.get("bullet_color", "#000000"),
        "line_spacing": rules.get("bullet_line_spacing", 1.0),
        "space_before": rules.get("bullet_space_before", 0.0),
        "space_after": rules.get("bullet_space_after", 0.0),
    }
    
    numbered_config = {
        "font": rules.get("numbered_font", "Arial"),
        "size": rules.get("numbered_size", 12),
        "color": rules.get("numbered_color", "#000000"),
        "line_spacing": rules.get("numbered_line_spacing", 1.0),
        "space_before": rules.get("numbered_space_before", 0.0),
        "space_after": rules.get("numbered_space_after", 0.0),
    }
    
    for item in parsed_lines:
        text = str(item["text"])
        line_type = item["type"]

        if line_type == "heading1":
            add_paragraph_to_pdf(pdf, text, heading1_config, page_width, rules)
            
        elif line_type == "heading2":
            add_paragraph_to_pdf(pdf, text, heading2_config, page_width, rules)
            
        elif line_type == "heading3":
            add_paragraph_to_pdf(pdf, text, heading3_config, page_width, rules)
            
        elif line_type == "bullet":
            # Add bullet prefix and render
            bullet_text = "• " + text
            add_paragraph_to_pdf(pdf, bullet_text, bullet_config, page_width, rules)
            
        elif line_type == "numbered":
            add_paragraph_to_pdf(pdf, text, numbered_config, page_width, rules)
            
        else:  # paragraph
            config = body_config
            add_paragraph_to_pdf(pdf, text, config, page_width, rules)

    # Reset text color to black before saving
    pdf.set_text_color(0, 0, 0)
    pdf.output(output_path)