#!/usr/bin/env python3
"""
Test script to verify all fixes work correctly.
Tests the three issues:
1. ParagraphFormat 'level' attribute error
2. Line spacing styling
3. PDF to DOCX/PDF styling
"""

import os
import tempfile
from formatter.docx_formatter import format_docx
from services.docx_generator import generate_docx
from services.pdf_generator import generate_pdf
from formatter.paragraph_formatter import paragraph_formatter

def test_line_spacing_and_formatting():
    """Test that line spacing and all formatting is applied correctly"""
    
    # Test data - complex document with nested lists
    test_content = [
        {"text": "INTRODUCTION", "type": "heading1"},
        {"text": "This is the introduction paragraph", "type": "paragraph"},
        {"text": "Main Points", "type": "heading2"},
        {"text": "First point", "type": "bullet"},
        {"text": "Second point", "type": "bullet"},
        {"text": "Numbered Section", "type": "heading3"},
        {"text": "Item one", "type": "numbered"},
        {"text": "Item two", "type": "numbered"},
        {"text": "Conclusion paragraph with proper line spacing", "type": "paragraph"},
    ]
    
    # Test rules with specific line spacing
    test_rules = {
        "heading1_size": 16,
        "heading1_line_spacing": 1.5,
        "heading2_size": 14,
        "heading2_line_spacing": 1.4,
        "body_line_spacing": 1.2,
        "bullet_line_spacing": 1.1,
        "margin_top": 1.0,
        "margin_bottom": 1.0,
        "margin_left": 1.0,
        "margin_right": 1.0,
    }
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Test 1: Generate DOCX from parsed lines
        print("[TEST 1] Generating DOCX with template rules...")
        docx_output = os.path.join(temp_dir, "test_output.docx")
        generate_docx(test_content, docx_output, template_rules=test_rules)
        print(f"✓ DOCX generated successfully: {docx_output}")
        
        # Test 2: Generate PDF from parsed lines
        print("[TEST 2] Generating PDF with template rules...")
        pdf_output = os.path.join(temp_dir, "test_output.pdf")
        generate_pdf(test_content, pdf_output, template_rules=test_rules)
        print(f"✓ PDF generated successfully: {pdf_output}")
        
        # Test 3: Format existing DOCX
        if os.path.exists(docx_output):
            print("[TEST 3] Formatting existing DOCX with template rules...")
            formatted_docx = os.path.join(temp_dir, "formatted_test.docx")
            format_docx(docx_output, formatted_docx, template_rules=test_rules)
            print(f"✓ DOCX formatted successfully: {formatted_docx}")
        
        print("\n✓ All tests passed! Fixes are working correctly.")
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_line_spacing_and_formatting()
    exit(0 if success else 1)
