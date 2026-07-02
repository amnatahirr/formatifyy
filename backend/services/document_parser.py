import os
import io
import uuid
from typing import List, Dict, Tuple
from docx import Document
from PIL import Image
import re
import spacy
from lxml import etree

# Load spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Downloading spaCy model...")
    os.system("python -m spacy download en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

# XML namespaces used in docx
NS = {
    "a":   "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "r":   "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "w":   "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp":  "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}


class DocumentParser:
    def __init__(self):
        self.nlp = nlp

    def parse_docx(self, file_path: str) -> Dict:
        """Parse DOCX file and extract structured content with heading and list detection"""
        doc = Document(file_path)

        parsed_content = {
            "paragraphs": [],
            "tables": [],
            "images": [],
            "headings": [],
            "lists": []
        }

        for para in doc.paragraphs:
            if para.text.strip():
                style = para.style.name if para.style else "Normal"
                is_bold = any(run.bold for run in para.runs)
                is_italic = any(run.italic for run in para.runs)
                is_underline = any(run.underline for run in para.runs)

                para_data = {
                    "text": para.text,
                    "style": style,
                    "is_bold": is_bold,
                    "is_italic": is_italic,
                    "is_underline": is_underline,
                    "font_size": self._get_font_size(para),
                    "level": para.style.base_style.base_style.name if para.style else None,
                    "is_list": self._is_list_item(para),
                    "list_level": self._get_list_level(para)
                }

                parsed_content["paragraphs"].append(para_data)

        # Extract tables
        for table in doc.tables:
            table_data = []
            for row in table.rows:
                row_data = [cell.text for cell in row.cells]
                table_data.append(row_data)
            parsed_content["tables"].append(table_data)

        # Extract images with surrounding context
        parsed_content["images"] = self.extract_images_with_context(file_path)

        return parsed_content

    def _get_font_size(self, para) -> int:
        """Extract font size from paragraph"""
        for run in para.runs:
            if run.font.size:
                return int(run.font.size.pt)
        return 12

    def _is_list_item(self, para) -> bool:
        """Check if paragraph is a list item"""
        if not para.style:
            return False

        style_name = para.style.name.lower()
        text = para.text.strip()

        if "list" in style_name or "bullet" in style_name:
            return True

        if text and text[0] in ["-", "*", "•"]:
            return True

        return False

    def _get_list_level(self, para) -> int:
        """Get the list level (nesting depth) of a paragraph"""
        if not para.style:
            return 0

        try:
            indent = para.paragraph_format.left_indent
            if indent:
                return max(0, int(indent.inches / 0.5))
        except:
            pass

        return 0

    def detect_sections(self, parsed_content: Dict) -> List[str]:
        """Detect section headings using heuristics and NLP"""
        detected_sections = []

        for para in parsed_content["paragraphs"]:
            text = para["text"].strip()
            is_heading = self._is_heading(para, text)

            if is_heading:
                detected_sections.append(text)

        return detected_sections

    def detect_heading_level(self, para: Dict) -> int:
        """Detect heading level (1, 2, or 3) from paragraph properties."""
        style_name = str(para.get("style", "")).lower()

        if "heading 1" in style_name or "heading1" in style_name:
            return 1
        if "heading 2" in style_name or "heading2" in style_name:
            return 2
        if "heading 3" in style_name or "heading3" in style_name:
            return 3

        font_size = para.get("font_size", 12)
        if font_size >= 18:
            return 1
        elif font_size >= 14:
            return 2
        else:
            return 3

    def _is_heading(self, para: Dict, text: str) -> bool:
        """Determine if paragraph is a heading using multiple rules."""
        if "Heading" in str(para["style"]):
            return True

        text_stripped = text.strip()
        if text_stripped.isupper() and len(text_stripped.split()) <= 6:
            return True

        if para["font_size"] and para["font_size"] >= 14:
            return True

        if para["is_bold"] and len(text) < 100 and len(text.split()) <= 8:
            if len(text.split()) <= 5:
                return True

        if self._is_title_case(text) and len(text.split()) <= 8:
            if text[0].isupper() and not text.endswith('.'):
                return True

        if para["is_underline"] and len(text) < 100 and len(text.split()) <= 8:
            return True

        if para["is_bold"] and para["is_italic"] and len(text) < 100:
            return True

        return False

    def _is_title_case(self, text: str) -> bool:
        """Check if text appears to be in title case"""
        words = text.split()
        if len(words) < 2:
            return False

        uppercase_words = sum(1 for word in words if word and word[0].isupper())
        return uppercase_words >= len(words) * 0.6

    # ══════════════════════════════════════════════════════════════════════
    # IMAGE EXTRACTION — FIXED
    # ══════════════════════════════════════════════════════════════════════

    def _get_rel_id_from_element(self, element) -> str | None:
        """
        Extract r:embed rId from any XML element — tries 4 different
        approaches to handle all docx image embedding styles.

        Approach 1: lxml namespace-aware attribute lookup (most reliable)
        Approach 2: regex on serialized XML string (fallback)
        Approach 3: XPath on pic:blipFill (another common location)
        Approach 4: Any attribute ending in :embed
        """
        r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

        # ── Approach 1: lxml namespace-aware search ───────────────────
        try:
            # Search all descendants for r:embed attribute
            for elem in element.iter():
                embed = elem.get(f"{{{r_ns}}}embed")
                if embed and embed.startswith("rId"):
                    return embed
        except Exception:
            pass

        # ── Approach 2: regex on raw XML string ───────────────────────
        try:
            raw_xml = etree.tostring(element, encoding="unicode")
            match = re.search(r'r:embed="(rId\d+)"', raw_xml)
            if match:
                return match.group(1)
            # Also try without namespace prefix (some generators omit it)
            match = re.search(r':embed="(rId\d+)"', raw_xml)
            if match:
                return match.group(1)
        except Exception:
            pass

        # ── Approach 3: XPath on blip element ────────────────────────
        try:
            blip_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
            blips = element.findall(f".//{{{blip_ns}}}blip")
            for blip in blips:
                embed = blip.get(f"{{{r_ns}}}embed")
                if embed:
                    return embed
        except Exception:
            pass

        return None

    def extract_images_with_context(self, file_path: str) -> List[Dict]:
        """
        Extract ALL images from a docx and return context dicts.

        WHY THE OLD CODE FAILED:
        ─────────────────────────
        Old code only searched para.runs → run._element.xml with a basic
        regex. Many docx images are embedded in:
          • <w:drawing> directly inside <w:p> (not inside a <w:r>)
          • <mc:AlternateContent> wrapper elements
          • Anchored (floating) drawings, not inline ones

        NEW APPROACH:
        ─────────────
        1. Save ALL images from doc.part.rels ONCE, keyed by rId
        2. For each paragraph, search the ENTIRE paragraph XML tree
           (not just runs) using 4 different methods to find r:embed
        3. Track used rIds to guarantee zero duplicates
        4. Also scan tables — images can be inside table cells

        Returns
        -------
        List of dicts: [{image_path, heading, before_text, after_text}]
        """
        doc = Document(file_path)
        results = []
        os.makedirs("uploads", exist_ok=True)

        # ── Step 1: Save ALL unique images once, keyed by rId ────────
        saved_images: Dict[str, str] = {}
        for rel_id, rel in doc.part.rels.items():
            if "image" in rel.target_ref:
                try:
                    img_bytes = rel.target_part.blob
                    save_path = f"uploads/{uuid.uuid4()}.png"
                    Image.open(io.BytesIO(img_bytes)).save(save_path)
                    saved_images[rel_id] = save_path
                except Exception:
                    continue

        

        # ── Step 2: Walk ALL paragraphs (including those in tables) ──
        # Build a flat list: (paragraph_element, paragraph_index, source)
        # source = "body" | "table"

        all_paras = []  # list of python-docx Paragraph objects in order

        # Body paragraphs
        for para in doc.paragraphs:
            all_paras.append(para)

        # Table cell paragraphs (images can be inside tables)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        all_paras.append(para)

        # ── Step 3: Match each paragraph to its image rId ─────────────
        used_rel_ids: set = set()   # ← prevents duplicates
        last_heading = ""

        for i, para in enumerate(all_paras):

            # Track nearest heading
            try:
                if para.style and para.style.name.startswith("Heading"):
                    last_heading = para.text.strip()
            except Exception:
                pass

            # Check if this paragraph contains an image at all
            para_xml_str = etree.tostring(para._element, encoding="unicode")
            has_image = (
                "graphic"  in para_xml_str or
                "drawing"  in para_xml_str or
                "blipFill" in para_xml_str or
                "imagedata" in para_xml_str.lower()
            )

            if not has_image:
                continue

            # Try to extract rId from paragraph's full XML tree
            image_rel_id = self._get_rel_id_from_element(para._element)

        

            if not image_rel_id:
                continue

            if image_rel_id not in saved_images:
                
                continue

            # ✅ Skip duplicate — same rId already processed
            if image_rel_id in used_rel_ids:
                
                continue

            used_rel_ids.add(image_rel_id)

            # Build context from surrounding paragraphs
            before_parts = [
                all_paras[j].text.strip()
                for j in range(max(0, i - 2), i)
                if all_paras[j].text.strip()
            ]
            before_text = " ".join(before_parts)

            after_text = ""
            if i + 1 < len(all_paras):
                after_text = all_paras[i + 1].text.strip()

            results.append({
                "image_path":  saved_images[image_rel_id],
                "heading":     last_heading,
                "before_text": before_text,
                "after_text":  after_text,
            })

       
        return results

    # ── Backwards compatible alias ────────────────────────────────────
    def extract_images(self, file_path: str) -> List[Dict]:
        """Alias for extract_images_with_context (backwards compatibility)."""
        return self.extract_images_with_context(file_path)


# Singleton instance
parser = DocumentParser()