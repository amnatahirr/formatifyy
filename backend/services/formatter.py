from typing import Dict, List
from datetime import datetime

class FormattingEngine:
    """Apply formatting rules to documents"""
    
    def __init__(self):
        self.default_rules = {
            "font_family": "Times New Roman",
            "heading_size": 16,
            "body_size": 12,
            "line_spacing": 1.5,
            "margins": {
                "top": 1.0,
                "bottom": 1.0,
                "left": 1.0,
                "right": 1.0
            }
        }
    
    def apply_formatting(
        self,
        parsed_content: Dict,
        formatting_rules: Dict
    ) -> Dict:
        """Apply formatting rules to parsed content"""
        
        formatted = {
            "metadata": {
                "formatted_at": datetime.now().isoformat(),
                "formatting_rules": formatting_rules
            },
            "content": []
        }
        
        for para in parsed_content.get("paragraphs", []):
            formatted_para = self._format_paragraph(para, formatting_rules)
            formatted["content"].append(formatted_para)
        
        return formatted
    
    def _format_paragraph(self, para: Dict, rules: Dict) -> Dict:
        """Format individual paragraph based on detected type and rules"""
        text = para["text"]
        detected_type = para.get("detected_type", para.get("style", "paragraph"))
        
        # Determine style based on detected type
        if detected_type in ["heading1", "heading2", "heading3"]:
            style = "heading"
        elif detected_type in ["bullet", "numbered"]:
            style = "list"
        else:
            style = "body"
        
        # Get appropriate font size and styling
        if detected_type == "heading1":
            font_size = rules.get("heading1_size", 18)
            font = rules.get("heading1_font", "Times New Roman")
            bold = rules.get("heading1_bold", True)
            italic = rules.get("heading1_italic", False)
            underline = rules.get("heading1_underline", False)
            line_spacing = rules.get("heading1_line_spacing", 1.5)
        elif detected_type == "heading2":
            font_size = rules.get("heading2_size", 16)
            font = rules.get("heading2_font", "Times New Roman")
            bold = rules.get("heading2_bold", True)
            italic = rules.get("heading2_italic", False)
            underline = rules.get("heading2_underline", False)
            line_spacing = rules.get("heading2_line_spacing", 1.5)
        elif detected_type == "heading3":
            font_size = rules.get("heading3_size", 14)
            font = rules.get("heading3_font", "Times New Roman")
            bold = rules.get("heading3_bold", True)
            italic = rules.get("heading3_italic", False)
            underline = rules.get("heading3_underline", False)
            line_spacing = rules.get("heading3_line_spacing", 1.5)
        elif detected_type in ["bullet", "numbered"]:
            font_size = rules.get("bullet_size", 12)
            font = rules.get("bullet_font", "Times New Roman")
            bold = False
            italic = False
            underline = False
            line_spacing = rules.get("bullet_line_spacing", 1.5)
        else:
            font_size = rules.get("body_size", 12)
            font = rules.get("body_font", "Times New Roman")
            bold = False
            italic = False
            underline = False
            line_spacing = rules.get("body_line_spacing", 1.5)
        
        formatted_para = {
            "text": text,
            "style": style,
            "detected_type": detected_type,
            "formatting": {
                "font": font,
                "size": font_size,
                "bold": bold,
                "italic": italic,
                "underline": underline,
                "line_spacing": line_spacing,
                "alignment": rules.get("alignment", "left")
            }
        }
        
        return formatted_para
    
    def _get_style(self, para: Dict, rules: Dict) -> str:
        """Determine paragraph style from detected type"""
        detected_type = para.get("detected_type", para.get("style", ""))
        if detected_type.startswith("heading") or para.get("is_bold"):
            return "heading"
        elif detected_type in ["bullet", "numbered"]:
            return "list"
        return "body"
    
    def _get_font_size(self, para: Dict, rules: Dict) -> int:
        """Get font size based on paragraph type"""
        detected_type = para.get("detected_type", para.get("style", ""))
        
        if detected_type == "heading1":
            return rules.get("heading1_size", 18)
        elif detected_type == "heading2":
            return rules.get("heading2_size", 14)
        elif detected_type == "heading3":
            return rules.get("heading3_size", 12)
        elif detected_type in ["bullet", "numbered"]:
            return rules.get("list_item_size", 11)
        else:
            return rules.get("body_size", 11)
    
    def validate_formatting(self, formatted_content: Dict) -> Dict:
        """Validate formatted content against rules"""
        issues = []
        warnings = []
        
        for para in formatted_content.get("content", []):
            # Check for consistent formatting
            if para["style"] == "heading" and para["formatting"]["size"] < 14:
                issues.append(f"Heading too small: '{para['text']}'")
            
            if len(para["text"]) > 200 and para["style"] == "heading":
                warnings.append(f"Heading too long: '{para['text']}'")
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings
        }

# Singleton instance
formatter = FormattingEngine()
