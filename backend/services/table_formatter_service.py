# """
# services/table_formatter_service.py
# =====================================
# Applies formatting to SELECTED tables in a DOCX file.

# Presets
# -------
#   academic      Bold header, shading, full borders, banded rows, TNR 12pt
#   professional  Bold header, full borders, no banding, Calibri 11pt
#   minimal       No shading, thin borders only, no banding

# The service never touches tables that are NOT in *selected_indices*.
# It always writes to a working-copy path (never the original).
# """

# from __future__ import annotations

# import copy
# import shutil
# import os
# from typing import Any, Dict, List, Optional

# from docx import Document
# from docx.shared import Pt, RGBColor
# from docx.enum.text import WD_ALIGN_PARAGRAPH
# from docx.oxml.ns import qn
# from docx.oxml import OxmlElement

# # ─────────────────────────────────────────────────────────────────────────────
# # Preset definitions
# # ─────────────────────────────────────────────────────────────────────────────

# PRESETS: Dict[str, Dict[str, Any]] = {
#     "academic": {
#         "font_name":        "Times New Roman",
#         "font_size":        12,
#         "header_bold":      True,
#         "header_bg":        "D6E4F0",      # light blue
#         "header_align":     "center",
#         "body_align":       "left",
#         "banded_rows":      True,
#         "band_color":       "F2F8FC",      # very light blue
#         "borders":          True,
#         "border_color":     "000000",
#         "border_size":      4,             # half-points (4 = 0.5pt)
#         "cell_padding_top": 60,            # twips
#         "cell_padding_bot": 60,
#         "cell_padding_lft": 108,
#         "cell_padding_rgt": 108,
#         "auto_fit":         True,
#         "center_table":     True,
#         "repeat_header":    True,
#     },
#     "professional": {
#         "font_name":        "Calibri",
#         "font_size":        11,
#         "header_bold":      True,
#         "header_bg":        "2E4057",      # dark navy
#         "header_align":     "center",
#         "body_align":       "left",
#         "banded_rows":      False,
#         "band_color":       None,
#         "borders":          True,
#         "border_color":     "2E4057",
#         "border_size":      6,             # 0.75 pt
#         "cell_padding_top": 80,
#         "cell_padding_bot": 80,
#         "cell_padding_lft": 120,
#         "cell_padding_rgt": 120,
#         "auto_fit":         True,
#         "center_table":     True,
#         "repeat_header":    True,
#     },
#     "minimal": {
#         "font_name":        "Arial",
#         "font_size":        11,
#         "header_bold":      False,
#         "header_bg":        None,
#         "header_align":     "left",
#         "body_align":       "left",
#         "banded_rows":      False,
#         "band_color":       None,
#         "borders":          True,
#         "border_color":     "AAAAAA",
#         "border_size":      2,             # 0.25 pt
#         "cell_padding_top": 40,
#         "cell_padding_bot": 40,
#         "cell_padding_lft": 80,
#         "cell_padding_rgt": 80,
#         "auto_fit":         True,
#         "center_table":     False,
#         "repeat_header":    False,
#     },
# }

# _ALIGN_MAP = {
#     "left":    WD_ALIGN_PARAGRAPH.LEFT,
#     "center":  WD_ALIGN_PARAGRAPH.CENTER,
#     "right":   WD_ALIGN_PARAGRAPH.RIGHT,
#     "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
# }

# W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


# # ─────────────────────────────────────────────────────────────────────────────
# # Public API
# # ─────────────────────────────────────────────────────────────────────────────

# class TableFormatterService:

#     def apply_table_formatting(
#         self,
#         source_path:      str,
#         output_path:      str,
#         selected_indices: List[int],
#         preset:           str = "academic",
#         custom_rules:     Optional[Dict[str, Any]] = None,
#     ) -> bool:
#         """
#         Copy *source_path* → *output_path*, then format only the tables
#         whose 0-based index is in *selected_indices*.

#         Returns True on success, False on failure.
#         """
#         try:
#             # Always write to output_path so original is never touched
#             if source_path != output_path:
#                 shutil.copy2(source_path, output_path)

#             rules = self._build_rules(preset, custom_rules)
#             doc   = Document(output_path)

#             for idx, table in enumerate(doc.tables):
#                 if idx not in selected_indices:
#                     continue
#                 self._format_table(table, rules, idx)

#             doc.save(output_path)
#             return True

#         except Exception as exc:
#             import traceback
#             print(f"[TableFormatter] ERROR: {traceback.format_exc()}")
#             return False

#     # ── Rule resolution ───────────────────────────────────────────────────────

#     def _build_rules(
#         self,
#         preset:       str,
#         custom_rules: Optional[Dict[str, Any]],
#     ) -> Dict[str, Any]:
#         base  = copy.deepcopy(PRESETS.get(preset, PRESETS["academic"]))
#         if custom_rules:
#             for k, v in custom_rules.items():
#                 if v is not None:
#                     base[k] = v
#         return base

#     # ── Core formatter ────────────────────────────────────────────────────────

#     def _format_table(
#         self,
#         table,
#         rules: Dict[str, Any],
#         table_idx: int,
#     ) -> None:
#         """Apply all formatting rules to a single python-docx Table object."""

#         tbl = table._tbl

#         # 1. Table-level alignment + auto-fit
#         self._set_table_properties(tbl, rules)

#         # 2. Borders
#         if rules.get("borders"):
#             self._apply_table_borders(tbl, rules)

#         # 3. Repeat header row on page break
#         if rules.get("repeat_header") and table.rows:
#             self._set_repeat_header(table.rows[0]._tr)

#         # 4. Per-row and per-cell formatting
#         for row_idx, row in enumerate(table.rows):
#             is_header = row_idx == 0
#             is_odd    = row_idx % 2 == 1

#             for cell in row.cells:
#                 self._format_cell(cell, rules, is_header, is_odd)

#     # ── Table-level XML ───────────────────────────────────────────────────────

#     def _set_table_properties(self, tbl, rules: Dict[str, Any]) -> None:
#         tblPr = self._get_or_create(tbl, f"{{{W_NS}}}tblPr")

#         # Center table
#         if rules.get("center_table"):
#             jc = self._get_or_create(tblPr, f"{{{W_NS}}}jc")
#             jc.set(qn("w:val"), "center")

#         # Auto-fit to window
#         if rules.get("auto_fit"):
#             tblW = self._get_or_create(tblPr, f"{{{W_NS}}}tblW")
#             tblW.set(qn("w:w"),    "5000")
#             tblW.set(qn("w:type"), "pct")   # 100% = 5000 fiftieths-of-a-percent

#             layout = self._get_or_create(tblPr, f"{{{W_NS}}}tblLayout")
#             layout.set(qn("w:type"), "autofit")

#     def _apply_table_borders(self, tbl, rules: Dict[str, Any]) -> None:
#         tblPr     = self._get_or_create(tbl, f"{{{W_NS}}}tblPr")
#         tblBorders = self._get_or_create(tblPr, f"{{{W_NS}}}tblBorders")

#         color = rules.get("border_color", "000000")
#         size  = str(rules.get("border_size", 4))   # half-points

#         for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
#             el = self._get_or_create(tblBorders, f"{{{W_NS}}}{side}")
#             el.set(qn("w:val"),   "single")
#             el.set(qn("w:sz"),    size)
#             el.set(qn("w:space"), "0")
#             el.set(qn("w:color"), color)

#     def _set_repeat_header(self, tr) -> None:
#         trPr = self._get_or_create(tr, f"{{{W_NS}}}trPr")
#         tblHeader = self._get_or_create(trPr, f"{{{W_NS}}}tblHeader")
#         tblHeader.set(qn("w:val"), "1")

#     # ── Cell-level formatting ─────────────────────────────────────────────────

#     def _format_cell(
#         self,
#         cell,
#         rules:     Dict[str, Any],
#         is_header: bool,
#         is_odd:    bool,
#     ) -> None:
#         tc = cell._tc

#         # Cell properties
#         tcPr = self._get_or_create(tc, f"{{{W_NS}}}tcPr")

#         # Padding
#         tcMar = self._get_or_create(tcPr, f"{{{W_NS}}}tcMar")
#         for side, key in (
#             ("top",    "cell_padding_top"),
#             ("bottom", "cell_padding_bot"),
#             ("left",   "cell_padding_lft"),
#             ("right",  "cell_padding_rgt"),
#         ):
#             el = self._get_or_create(tcMar, f"{{{W_NS}}}{side}")
#             el.set(qn("w:w"),    str(rules.get(key, 80)))
#             el.set(qn("w:type"), "dxa")

#         # Background shading
#         bg_color = None
#         if is_header and rules.get("header_bg"):
#             bg_color = rules["header_bg"]
#         elif not is_header and rules.get("banded_rows") and is_odd and rules.get("band_color"):
#             bg_color = rules["band_color"]

#         if bg_color:
#             shd = self._get_or_create(tcPr, f"{{{W_NS}}}shd")
#             shd.set(qn("w:val"),   "clear")
#             shd.set(qn("w:color"), "auto")
#             shd.set(qn("w:fill"), bg_color)
#         else:
#             # Remove any existing shading
#             existing_shd = tcPr.find(f"{{{W_NS}}}shd")
#             if existing_shd is not None:
#                 tcPr.remove(existing_shd)

#         # Per-paragraph (text) formatting inside cell
#         align_key  = "header_align" if is_header else "body_align"
#         align_str  = rules.get(align_key, "left")
#         wd_align   = _ALIGN_MAP.get(align_str, WD_ALIGN_PARAGRAPH.LEFT)
#         bold       = is_header and rules.get("header_bold", True)
#         font_name  = rules.get("font_name", "Times New Roman")
#         font_size  = rules.get("font_size", 12)

#         for para in cell.paragraphs:
#             para.paragraph_format.alignment = wd_align

#             for run in para.runs:
#                 run.bold          = bold
#                 run.font.name     = font_name
#                 run.font.size     = Pt(font_size)

#                 # Header text color — white on dark backgrounds
#                 if is_header and rules.get("header_bg"):
#                     bg = rules["header_bg"]
#                     # Luminance check — if dark bg, use white text
#                     try:
#                         r = int(bg[0:2], 16)
#                         g = int(bg[2:4], 16)
#                         b = int(bg[4:6], 16)
#                         lum = 0.299*r + 0.587*g + 0.114*b
#                         if lum < 128:
#                             run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
#                         else:
#                             run.font.color.rgb = RGBColor(0x00, 0x00, 0x00)
#                     except Exception:
#                         pass
#                 else:
#                     run.font.color.rgb = RGBColor(0x00, 0x00, 0x00)

#     # ── XML helper ────────────────────────────────────────────────────────────

#     @staticmethod
#     def _get_or_create(parent, tag: str):
#         """Find child with *tag* or create it as first child."""
#         el = parent.find(tag)
#         if el is None:
#             # Extract local name from {namespace}localname format
#             if "}" in tag:
#                 local_name = tag.split("}")[-1]
#             else:
#                 local_name = tag
            
#             # Create element using the prefix format directly (w: for Word namespace)
#             # OxmlElement expects 'w:localname' format, not a namespace URI format
#             el = OxmlElement("w:" + local_name)
#             parent.insert(0, el)
#         return el


# # ─────────────────────────────────────────────────────────────────────────────
# # Singleton
# # ─────────────────────────────────────────────────────────────────────────────

# table_formatter_service = TableFormatterService()




"""
services/table_formatter_service.py
=====================================
Applies formatting to SELECTED tables in a DOCX file.
Includes a fix for Style Hierarchy to ensure Template fonts (e.g., Calibri)
override User's manual formatting (e.g., Times New Roman).
"""

from __future__ import annotations

import copy
import shutil
import os
from typing import Any, Dict, List, Optional

from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# ─────────────────────────────────────────────────────────────────────────────
# Preset definitions
# ─────────────────────────────────────────────────────────────────────────────

PRESETS: Dict[str, Dict[str, Any]] = {
    "academic": {
        "font_name":        "Times New Roman",
        "font_size":        12,
        "header_bold":      True,
        "header_bg":        "D6E4F0",      # light blue
        "header_align":     "center",
        "body_align":       "left",
        "banded_rows":      True,
        "band_color":       "F2F8FC",      # very light blue
        "borders":          True,
        "border_color":     "000000",
        "border_size":      4,             # half-points (4 = 0.5pt)
        "cell_padding_top": 60,            # twips
        "cell_padding_bot": 60,
        "cell_padding_lft": 108,
        "cell_padding_rgt": 108,
        "auto_fit":         True,
        "center_table":     True,
        "repeat_header":    True,
    },
    "professional": {
        "font_name":        "Calibri",
        "font_size":        11,
        "header_bold":      True,
        "header_bg":        "2E4057",      # dark navy
        "header_align":     "center",
        "body_align":       "left",
        "banded_rows":      False,
        "band_color":       None,
        "borders":          True,
        "border_color":     "2E4057",
        "border_size":      6,             # 0.75 pt
        "cell_padding_top": 80,
        "cell_padding_bot": 80,
        "cell_padding_lft": 120,
        "cell_padding_rgt": 120,
        "auto_fit":         True,
        "center_table":     True,
        "repeat_header":    True,
    },
    "minimal": {
        "font_name":        "Arial",
        "font_size":        11,
        "header_bold":      False,
        "header_bg":        None,
        "header_align":     "left",
        "body_align":       "left",
        "banded_rows":      False,
        "band_color":       None,
        "borders":          True,
        "border_color":     "AAAAAA",
        "border_size":      2,             # 0.25 pt
        "cell_padding_top": 40,
        "cell_padding_bot": 40,
        "cell_padding_lft": 80,
        "cell_padding_rgt": 80,
        "auto_fit":         True,
        "center_table":     False,
        "repeat_header":    False,
    },
}

_ALIGN_MAP = {
    "left":    WD_ALIGN_PARAGRAPH.LEFT,
    "center":  WD_ALIGN_PARAGRAPH.CENTER,
    "right":   WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


class TableFormatterService:

    def apply_table_formatting(
        self,
        source_path:      str,
        output_path:      str,
        selected_indices: List[int],
        preset:           str = "academic",
        custom_rules:     Optional[Dict[str, Any]] = None,
    ) -> bool:
        try:
            if source_path != output_path:
                shutil.copy2(source_path, output_path)

            rules = self._build_rules(preset, custom_rules)
            doc   = Document(output_path)

            for idx, table in enumerate(doc.tables):
                if idx not in selected_indices:
                    continue
                self._format_table(table, rules, idx)

            doc.save(output_path)
            return True

        except Exception as exc:
            import traceback
            print(f"[TableFormatter] ERROR: {traceback.format_exc()}")
            return False

    def fill_table_cell(
        self,
        docx_path: str,
        table_index: int,
        row_1based: int,
        col_1based: int,
        text: str,
    ) -> bool:
        """
        Write *text* into a specific table cell and save back to *docx_path*.
        Table index is 0-based; row/col are 1-based for readability.
        """
        try:
            doc = Document(docx_path)
            if table_index < 0 or table_index >= len(doc.tables):
                return False

            r = row_1based - 1
            c = col_1based - 1
            if r < 0 or c < 0:
                return False

            table = doc.tables[table_index]

            # python-docx Table.cell handles internal grid; may raise IndexError
            cell = table.cell(r, c)
            cell.text = text

            doc.save(docx_path)
            return True
        except Exception:
            import traceback
            print(f"[TableFillCell] ERROR: {traceback.format_exc()}")
            return False

    def _build_rules(
        self,
        preset:       str,
        custom_rules: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        base = copy.deepcopy(PRESETS.get(preset, PRESETS["academic"]))
        if custom_rules:
            for k, v in custom_rules.items():
                if v is not None:
                    base[k] = v
        return base

    def _format_table(
        self,
        table,
        rules: Dict[str, Any],
        table_idx: int,
    ) -> None:
        tbl = table._tbl

        self._set_table_properties(tbl, rules)

        if rules.get("borders"):
            self._apply_table_borders(tbl, rules)

        if rules.get("repeat_header") and table.rows:
            self._set_repeat_header(table.rows[0]._tr)

        for row_idx, row in enumerate(table.rows):
            is_header = row_idx == 0
            is_odd    = row_idx % 2 == 1
            for cell in row.cells:
                self._format_cell(cell, rules, is_header, is_odd)

    def _set_table_properties(self, tbl, rules: Dict[str, Any]) -> None:
        tblPr = self._get_or_create(tbl, f"{{{W_NS}}}tblPr")
        if rules.get("center_table"):
            jc = self._get_or_create(tblPr, f"{{{W_NS}}}jc")
            jc.set(qn("w:val"), "center")

        if rules.get("auto_fit"):
            tblW = self._get_or_create(tblPr, f"{{{W_NS}}}tblW")
            tblW.set(qn("w:w"),    "5000")
            tblW.set(qn("w:type"), "pct") 
            layout = self._get_or_create(tblPr, f"{{{W_NS}}}tblLayout")
            layout.set(qn("w:type"), "autofit")

    def _apply_table_borders(self, tbl, rules: Dict[str, Any]) -> None:
        tblPr     = self._get_or_create(tbl, f"{{{W_NS}}}tblPr")
        tblBorders = self._get_or_create(tblPr, f"{{{W_NS}}}tblBorders")
        color = rules.get("border_color", "000000")
        size  = str(rules.get("border_size", 4))

        for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
            el = self._get_or_create(tblBorders, f"{{{W_NS}}}{side}")
            el.set(qn("w:val"),   "single")
            el.set(qn("w:sz"),    size)
            el.set(qn("w:space"), "0")
            el.set(qn("w:color"), color)

    def _set_repeat_header(self, tr) -> None:
        trPr = self._get_or_create(tr, f"{{{W_NS}}}trPr")
        tblHeader = self._get_or_create(trPr, f"{{{W_NS}}}tblHeader")
        tblHeader.set(qn("w:val"), "1")

    def _format_cell(
        self,
        cell,
        rules:     Dict[str, Any],
        is_header: bool,
        is_odd:    bool,
    ) -> None:
        tc = cell._tc
        tcPr = self._get_or_create(tc, f"{{{W_NS}}}tcPr")

        # Padding
        tcMar = self._get_or_create(tcPr, f"{{{W_NS}}}tcMar")
        for side, key in (("top", "cell_padding_top"), ("bottom", "cell_padding_bot"), 
                          ("left", "cell_padding_lft"), ("right", "cell_padding_rgt")):
            el = self._get_or_create(tcMar, f"{{{W_NS}}}{side}")
            el.set(qn("w:w"),    str(rules.get(key, 80)))
            el.set(qn("w:type"), "dxa")

        # Background shading
        bg_color = None
        if is_header and rules.get("header_bg"):
            bg_color = rules["header_bg"]
        elif not is_header and rules.get("banded_rows") and is_odd and rules.get("band_color"):
            bg_color = rules["band_color"]

        if bg_color:
            shd = self._get_or_create(tcPr, f"{{{W_NS}}}shd")
            shd.set(qn("w:val"),   "clear")
            shd.set(qn("w:color"), "auto")
            shd.set(qn("w:fill"),  bg_color)
        else:
            existing_shd = tcPr.find(f"{{{W_NS}}}shd")
            if existing_shd is not None:
                tcPr.remove(existing_shd)

        # Paragraph Formatting
        align_key  = "header_align" if is_header else "body_align"
        wd_align   = _ALIGN_MAP.get(rules.get(align_key, "left"), WD_ALIGN_PARAGRAPH.LEFT)
        bold       = is_header and rules.get("header_bold", True)
        font_name  = rules.get("font_name", "Times New Roman")
        font_size  = rules.get("font_size", 12)

        for para in cell.paragraphs:
            para.paragraph_format.alignment = wd_align
            for run in para.runs:
                # --- CRITICAL FIX: Clear legacy direct formatting ---
                # Setting to None forces the run to forget its previous manual font settings
                run.font.name = None
                run.font.size = None
                
                # Apply Template Settings
                run.bold      = bold
                run.font.name = font_name
                run.font.size = Pt(font_size)
                self._force_run_font_family(run, font_name)

                # Text contrast logic
                if is_header and rules.get("header_bg"):
                    bg = rules["header_bg"]
                    try:
                        r, g, b = int(bg[0:2], 16), int(bg[2:4], 16), int(bg[4:6], 16)
                        lum = 0.299*r + 0.587*g + 0.114*b
                        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF) if lum < 128 else RGBColor(0, 0, 0)
                    except: pass
                else:
                    run.font.color.rgb = RGBColor(0, 0, 0)

    @staticmethod
    def _force_run_font_family(run, font_name: str) -> None:
        """
        Word can keep showing a different font (e.g. Calibri) if only run.font.name
        is set. Force-set the underlying w:rFonts mappings so the run strictly
        uses the requested font across ascii/hAnsi/eastAsia/cs.
        """
        try:
            r = run._element
            rPr = r.get_or_add_rPr()
            rFonts = rPr.find(qn("w:rFonts"))
            if rFonts is None:
                rFonts = OxmlElement("w:rFonts")
                rPr.insert(0, rFonts)

            # Set all common script mappings
            rFonts.set(qn("w:ascii"),   font_name)
            rFonts.set(qn("w:hAnsi"),   font_name)
            rFonts.set(qn("w:eastAsia"), font_name)
            rFonts.set(qn("w:cs"),      font_name)
        except Exception:
            # Non-fatal: fall back to python-docx run.font.name
            pass

    @staticmethod
    def _get_or_create(parent, tag: str):
        el = parent.find(tag)
        if el is None:
            local_name = tag.split("}")[-1] if "}" in tag else tag
            el = OxmlElement("w:" + local_name)
            parent.insert(0, el)
        return el

table_formatter_service = TableFormatterService()