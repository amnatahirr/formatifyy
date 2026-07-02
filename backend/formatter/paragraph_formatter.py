"""
Paragraph Formatting Module for Formatify - Dynamic Template-Based Formatting

Applies formatting rules from templates dynamically.
All hardcoded styles have been removed in favor of template-driven formatting.
"""

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from typing import Optional, Dict


class ParagraphFormatter:
    """Handles all paragraph-level formatting using dynamic template rules"""
    
    # A4 Paper specifications (constants only)
    PAPER_WIDTH = Inches(8.27)  # 210mm
    PAPER_HEIGHT = Inches(11.7)  # 297mm
    
    def __init__(self):
        """Initialize the paragraph formatter"""
        pass

    @staticmethod
    def _to_inches(value, unit: str = "in"):
        """Convert spacing/margin numeric value from selected unit to inches."""
        try:
            numeric = float(value)
        except (ValueError, TypeError):
            return 0.0

        normalized_unit = (unit or "in").lower()
        if normalized_unit in ("in", "inch", "inches"):
            return numeric
        if normalized_unit == "cm":
            return numeric / 2.54
        if normalized_unit == "mm":
            return numeric / 25.4
        return numeric
    
    def _get_default_rules(self) -> Dict:
        """Get default formatting rules when no template provided"""
        return {
            "heading1_font": "Times New Roman",
            "heading1_size": 16,
            "heading1_bold": True,
            "heading1_line_spacing": 1.5,
            "heading1_space_before": 12.0,
            "heading1_space_after": 6.0,
            "heading2_font": "Times New Roman",
            "heading2_size": 14,
            "heading2_bold": True,
            "heading2_line_spacing": 1.5,
            "heading2_space_before": 10.0,
            "heading2_space_after": 5.0,
            "heading3_font": "Times New Roman",
            "heading3_size": 13,
            "heading3_bold": True,
            "heading3_line_spacing": 1.5,
            "heading3_space_before": 8.0,
            "heading3_space_after": 4.0,
            "heading4_font": "Times New Roman",
            "heading4_size": 12,
            "heading4_bold": False,
            "heading4_line_spacing": 1.5,
            "heading4_space_before": 6.0,
            "heading4_space_after": 3.0,
            "body_font": "Times New Roman",
            "body_size": 11,
            "body_line_spacing": 1.0,
            "body_space_before": 0.0,
            "body_space_after": 6.0,
            "bullet_font": "Times New Roman",
            "bullet_size": 12,
            "bullet_line_spacing": 1.0,
            "bullet_indent": 0.5,
            "bullet_space_before": 0.0,
            "bullet_space_after": 6.0,
            "margin_top": 1.0,
            "margin_bottom": 1.0,
            "margin_left": 1.0,
            "margin_right": 1.0,
        }
    
    def get_formatting_rules(self, template_rules: Optional[Dict] = None) -> Dict:
        """
        Get formatting rules from template or use defaults.
        
        Args:
            template_rules: Template formatting rules dictionary
            
        Returns:
            Dictionary with all formatting specifications
        """
        if not template_rules:
            return self._get_default_rules()
        
        # CRITICAL: Start with defaults, then override with template values
        # This ensures all required keys exist, but user values take precedence
        rules = self._get_default_rules()
        
        # Only update with non-None template values to preserve user choices
        for key, value in template_rules.items():
            if value is not None:
                rules[key] = value
                
        
        return rules
    
    def set_document_margins(self, document, rules: Optional[Dict] = None):
        """
        Set document margins from template rules.
        
        Args:
            document: python-docx Document object
            rules: Formatting rules dictionary with margin specifications
        """
        if not rules:
            rules = self._get_default_rules()
        
        spacing_unit = rules.get("spacing_unit", "in")
        margin_top = self._to_inches(rules.get("margin_top", 1.0), spacing_unit)
        margin_bottom = self._to_inches(rules.get("margin_bottom", 1.0), spacing_unit)
        margin_left = self._to_inches(rules.get("margin_left", 1.0), spacing_unit)
        margin_right = self._to_inches(rules.get("margin_right", 1.0), spacing_unit)
        
        
        
        # Ensure margins are reasonable (convert mm to inches if needed, cap at 2.5")
        # This prevents text width from becoming too narrow
        def clamp_margin(value):
            try:
                val = float(value)
                # Cap margins to prevent narrow text width
                return max(0.25, min(val, 2.5))
            except (ValueError, TypeError):
                return 1.0
        
        margin_top = clamp_margin(margin_top)
        margin_bottom = clamp_margin(margin_bottom)
        margin_left = clamp_margin(margin_left)
        margin_right = clamp_margin(margin_right)
        
        
        
        try:
            sections = document.sections
            for section in sections:
                section.top_margin = Inches(margin_top)
                section.bottom_margin = Inches(margin_bottom)
                section.left_margin = Inches(margin_left)
                section.right_margin = Inches(margin_right)
                
        except Exception as e:
            print(f"[v0] Error applying margins: {str(e)}")
    
    def set_paragraph_spacing(self, paragraph, space_before=0, space_after=6, line_spacing=1.0):
        """
        Set paragraph spacing.
        
        Args:
            paragraph: python-docx paragraph object
            space_before: Space before paragraph in points
            space_after: Space after paragraph in points
            line_spacing: Line spacing multiplier
        """
        try:
            paragraph_format = paragraph.paragraph_format
            
            # Convert to float if string - CRITICAL: Handle 0 values correctly
            try:
                # Use "is not None" instead of truthiness to preserve 0 values
                space_before = float(space_before) if space_before is not None else 0
                space_after = float(space_after) if space_after is not None else 6
                line_spacing = float(line_spacing) if line_spacing is not None else 1.0
            except (ValueError, TypeError):
                space_before = 0
                space_after = 6
                line_spacing = 1.0
            
            # Apply spacing - Pt() expects points (1/72 inch)
            paragraph_format.space_before = Pt(space_before)
            paragraph_format.space_after = Pt(space_after)
            paragraph_format.line_spacing = line_spacing
            
            
        except Exception as e:
            print(f"[v0] Warning: Could not set paragraph spacing: {str(e)}")
    
    def set_font_properties(self, run, font_size=None, bold=False, italic=False, 
                           underline=False, color=None, font_name=None):
        """Set font properties for a text run."""
        if font_name:
            run.font.name = font_name
        if font_size:
            run.font.size = Pt(font_size)
        run.font.bold = bold
        run.font.italic = italic
        run.font.underline = underline
        
        # Handle color - convert hex to RGB
        if color:
            try:
                # Remove '#' if present and convert hex to RGB
                hex_color = color.lstrip('#')
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
                run.font.color.rgb = RGBColor(r, g, b)
            except (ValueError, IndexError) as e:
                # If color parsing fails, use black
                run.font.color.rgb = RGBColor(0, 0, 0)
    
    def add_heading(self, document, text, level=1, rules: Optional[Dict] = None):
        """
        Add a formatted heading to document using template rules.
        
        Args:
            document: python-docx Document object
            text: Heading text
            level: Heading level (1, 2, or 3)
            rules: Formatting rules dictionary
        """
        if not rules:
            rules = self._get_default_rules()
        
        heading = document.add_heading(text, level=level)
        
        # Get properties from rules based on level
        if level == 1:
            font_size = rules.get("heading1_size", 16)
            font_name = rules.get("heading1_font", "Times New Roman")
            bold = rules.get("heading1_bold", True)
            italic = rules.get("heading1_italic", False)
            underline = rules.get("heading1_underline", False)
            color = rules.get("heading1_color", "#000000")
            line_spacing = rules.get("heading1_line_spacing", 1.5)
            space_before = rules.get("heading1_space_before", 12.0)
            space_after = rules.get("heading1_space_after", 6.0)
            
        elif level == 2:
            font_size = rules.get("heading2_size", 14)
            font_name = rules.get("heading2_font", "Times New Roman")
            bold = rules.get("heading2_bold", True)
            italic = rules.get("heading2_italic", False)
            underline = rules.get("heading2_underline", False)
            color = rules.get("heading2_color", "#000000")
            line_spacing = rules.get("heading2_line_spacing", 1.5)
            space_before = rules.get("heading2_space_before", 10.0)
            space_after = rules.get("heading2_space_after", 5.0)
            
        elif level == 3:
            font_size = rules.get("heading3_size", 13)
            font_name = rules.get("heading3_font", "Times New Roman")
            bold = rules.get("heading3_bold", True)
            italic = rules.get("heading3_italic", False)
            underline = rules.get("heading3_underline", False)
            color = rules.get("heading3_color", "#000000")
            line_spacing = rules.get("heading3_line_spacing", 1.5)
            space_before = rules.get("heading3_space_before", 8.0)
            space_after = rules.get("heading3_space_after", 4.0)
           
        else:  # level 4
            font_size = rules.get("heading4_size", 12)
            font_name = rules.get("heading4_font", "Times New Roman")
            bold = rules.get("heading4_bold", False)
            italic = rules.get("heading4_italic", False)
            underline = rules.get("heading4_underline", False)
            color = rules.get("heading4_color", "#000000")
            line_spacing = rules.get("heading4_line_spacing", 1.5)
            space_before = rules.get("heading4_space_before", 6.0)
            space_after = rules.get("heading4_space_after", 3.0)
           
        
        # Apply formatting to all runs
        for run in heading.runs:
            self.set_font_properties(
                run,
                font_size=font_size,
                bold=bold,
                italic=italic,
                underline=underline,
                color=color,
                font_name=font_name
            )
        
        # Set paragraph spacing
        self.set_paragraph_spacing(heading, space_before=space_before, space_after=space_after, line_spacing=line_spacing)
        
        return heading
    
    def add_paragraph(self, document, text, rules: Optional[Dict] = None):
        """
        Add a formatted paragraph to document using template rules.
        
        Args:
            document: python-docx Document object
            text: Paragraph text
            rules: Formatting rules dictionary
        """
        if not rules:
            rules = self._get_default_rules()
        
        para = document.add_paragraph(text)
        
        font_size = rules.get("body_size", 11)
        font_name = rules.get("body_font", "Times New Roman")
        color = rules.get("body_color", "#000000")
        line_spacing = rules.get("body_line_spacing", 1.0)
        space_before = rules.get("body_space_before", 0.0)
        space_after = rules.get("body_space_after", 6.0)
        spacing_unit = rules.get("spacing_unit", "in")
        first_line_indent = self._to_inches(rules.get("first_line_indent", 0.5), spacing_unit)
        justified = rules.get("body_justified", True)
        
       
        
        for run in para.runs:
            self.set_font_properties(
                run,
                font_size=font_size,
                font_name=font_name,
                color=color
            )
        
        # Apply first line indent
        try:
            para.paragraph_format.first_line_indent = Inches(first_line_indent)
        except Exception as e:
            print(f"[v0] Warning: Could not set first line indent: {str(e)}")
        
        # Apply justification if enabled
        if justified:
            para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        
        # Apply spacing - CRITICAL: space_before and space_after are in points
        self.set_paragraph_spacing(para, space_before=space_before, space_after=space_after, line_spacing=line_spacing)
        
        return para
    
    def add_bullet_point(self, document, text, rules: Optional[Dict] = None, bold=False, level=0):
        """
        Add a formatted bullet point to document using template rules.
        
        Args:
            document: python-docx Document object
            text: Bullet point text
            rules: Formatting rules dictionary
            bold: Whether to make text bold
            level: Nesting level (0 for first level, 1 for sub-bullets, etc)
        """
        if not rules:
            rules = self._get_default_rules()
        
        bullet_type = rules.get("bullet_type", "bullet")
        
        # Select bullet style based on type and level
        if bullet_type == "dash":
            style = 'List Bullet' if level == 0 else 'List Bullet 2'
            prefix = "– "
        elif bullet_type == "asterisk":
            style = 'List Bullet' if level == 0 else 'List Bullet 2'
            prefix = "* "
        else:  # default bullet
            style = 'List Bullet' if level == 0 else 'List Bullet 2'
            prefix = "• "
        
        bullet = document.add_paragraph(text, style=style)
        
        # Set nesting level safely
        try:
            bullet.paragraph_format.level = level
        except Exception as e:
            print(f"[v0] Warning: Could not set bullet level: {str(e)}")
        
        font_size = rules.get("bullet_size", 12)
        font_name = rules.get("bullet_font", "Times New Roman")
        color = rules.get("bullet_color", "#000000")
        line_spacing = rules.get("bullet_line_spacing", 1.0)
        space_before = rules.get("bullet_space_before", 0.0)
        space_after = rules.get("bullet_space_after", 6.0)
        
        # FIX: Control bullet indent to prevent character-level wrapping
        # Default indent should be reasonable (0.25" to 0.5" per level)
        spacing_unit = rules.get("spacing_unit", "in")
        bullet_indent = self._to_inches(rules.get("bullet_indent", 0.25), spacing_unit)
        safe_indent = min(bullet_indent, 0.5)  # Cap maximum indent at 0.5" to prevent narrow text width
        
        try:
            bullet.paragraph_format.left_indent = Inches(safe_indent + (level * 0.25))
        except Exception as e:
            print(f"[v0] Warning: Could not set bullet indent: {str(e)}")
        
        for run in bullet.runs:
            self.set_font_properties(
                run,
                font_size=font_size,
                font_name=font_name,
                bold=bold,
                color=color
            )
        
        self.set_paragraph_spacing(bullet, space_before=space_before, space_after=space_after, line_spacing=line_spacing)
        
        return bullet
    
    def add_numbered_item(self, document, text, rules: Optional[Dict] = None, level=0):
        """
        Add a formatted numbered list item to document using template rules.
        
        Args:
            document: python-docx Document object
            text: Item text
            rules: Formatting rules dictionary
            level: Nesting level (0 for first level, 1 for sub-items, etc)
        """
        if not rules:
            rules = self._get_default_rules()
        
        numbered_style = rules.get("numbered_style", "1,2,3")
        
        # Select numbering style
        if numbered_style == "A,B,C":
            style = 'List Number' if level == 0 else 'List Number 2'
        elif numbered_style == "a,b,c":
            style = 'List Number' if level == 0 else 'List Number 2'
        elif numbered_style == "i,ii,iii":
            style = 'List Number' if level == 0 else 'List Number 2'
        else:  # default "1,2,3"
            style = 'List Number' if level == 0 else 'List Number 2'
        
        item = document.add_paragraph(text, style=style)
        
        # Set nesting level safely
        try:
            item.paragraph_format.level = level
        except Exception as e:
            print(f"[v0] Warning: Could not set numbered item level: {str(e)}")
        
        font_size = rules.get("numbered_size", 12)
        font_name = rules.get("numbered_font", "Times New Roman")
        color = rules.get("numbered_color", "#000000")
        line_spacing = rules.get("numbered_line_spacing", 1.0)
        space_before = rules.get("numbered_space_before", 0.0)
        space_after = rules.get("numbered_space_after", 6.0)
        
        # FIX: Control numbered list indent to prevent character-level wrapping
        # Default indent should be reasonable (0.25" to 0.5" per level)
        spacing_unit = rules.get("spacing_unit", "in")
        numbered_indent = self._to_inches(rules.get("numbered_indent", 0.25), spacing_unit)
        safe_indent = min(numbered_indent, 0.5)  # Cap maximum indent at 0.5" to prevent narrow text width
        
        try:
            item.paragraph_format.left_indent = Inches(safe_indent + (level * 0.25))
        except Exception as e:
            print(f"[v0] Warning: Could not set numbered item indent: {str(e)}")
        
        for run in item.runs:
            self.set_font_properties(
                run,
                font_size=font_size,
                font_name=font_name,
                color=color
            )
        
        self.set_paragraph_spacing(item, space_before=space_before, space_after=space_after, line_spacing=line_spacing)
        
        return item


# Global formatter instance
paragraph_formatter = ParagraphFormatter()
