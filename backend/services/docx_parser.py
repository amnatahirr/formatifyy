from docx import Document
from formatter.rules import detect_line_type

def parse_docx_with_line_numbers(file_path):
    """
    Returns list of dicts: {"text": line_text, "type": line_type, "line": line_number}
    Preserves line numbers for accurate image placement
    """
    lines = []
    doc = Document(file_path)
    prev_type = None
    line_number = 1
    
    # Parse regular paragraphs
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            line_type = detect_line_type(text, prev_type)
            lines.append({
                "text": text, 
                "type": line_type,
                "line": line_number
            })
            prev_type = line_type
            line_number += 1
    
    # Parse tables (if any)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    text = para.text.strip()
                    if text:
                        line_type = detect_line_type(text, prev_type)
                        lines.append({
                            "text": text, 
                            "type": line_type,
                            "line": line_number
                        })
                        prev_type = line_type
                        line_number += 1
    
    return lines


def parse_docx(file_path):
    """
    Original function for backward compatibility
    Returns list of dicts: {"text": line_text, "type": line_type}
    """
    lines_with_numbers = parse_docx_with_line_numbers(file_path)
    # Remove line numbers for backward compatibility
    return [{"text": item["text"], "type": item["type"]} for item in lines_with_numbers]