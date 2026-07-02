# from pydantic import BaseModel, EmailStr
# from typing import Optional, List
# from datetime import datetime
 
# from pydantic import BaseModel
# from typing import Optional
 
# class UserCreate(BaseModel):
#     username: str
#     email: EmailStr
#     password: str
#     role: str = "student"
#     university_id: Optional[int] = None

# class UserResponse(BaseModel):
#     id: int
#     username: str
#     email: str
#     role: str
#     university_id: Optional[int]
#     created_at: datetime

# class ReferenceFormattingRule(BaseModel):
#     """
#     Sub-model embedded inside FormattingRule / formatting_rules JSON.
#     The admin configures this once per template; the formatter service reads
#     it every time a student uploads a document.
#     """
#     style: str = "APA"                 # "APA" | "IEEE" | "MLA"
#     font_name: str = "Times New Roman"
#     font_size: float = 12.0
#     line_spacing: float = 1.5          # multiplier
#     hanging_indent: float = 0.5        # inches
#     space_before: float = 0.0          # pt
#     space_after: float = 6.0           # pt
#     bold: bool = False
#     italic: bool = False
#     color: str = "#000000"             # hex
#     sort_alphabetically: bool = True
#     remove_duplicates: bool = True
#     make_urls_clickable: bool = True
#     mark_incomplete: bool = True
#     numbering_style: str = "numeric"
# class UserLoginResponse(BaseModel):
#     id: int
#     username: str
#     email: str
#     role: str
#     token: str

# class UniversityCreate(BaseModel):
#     name: str
#     country: str

# class UniversityResponse(BaseModel):
#     id: int
#     name: str
#     country: str

# # ─────────────────────────────────────────────────────────────────────────────
# # NEW: Structured required section (replaces plain List[str])
# # ─────────────────────────────────────────────────────────────────────────────
# class RequiredSection(BaseModel):
#     """
#     One entry in the template's required_sections list.

#     Example:
#         {"name": "Introduction", "order": 1, "required": true}
#     """
#     name: str
#     order: int          # 1-based position in the expected document order
#     required: bool = True  # True = must be present; False = optional but tracked

# # ─────────────────────────────────────────────────────────────────────────────

# class FormattingRule(BaseModel):
#     # Heading 1 styles
#     heading1_font: str = "Times New Roman"
#     heading1_size: int = 18
#     heading1_bold: bool = True
#     heading1_italic: bool = False
#     heading1_underline: bool = False
#     heading1_color: str = "#000000"
#     heading1_line_spacing: float = 1.0
#     heading1_space_before: float = 12.0
#     heading1_space_after: float = 6.0
    
#     # Heading 2 styles
#     heading2_font: str = "Times New Roman"
#     heading2_size: int = 16
#     heading2_bold: bool = True
#     heading2_italic: bool = False
#     heading2_underline: bool = False
#     heading2_color: str = "#000000"
#     heading2_line_spacing: float = 1.0
#     heading2_space_before: float = 10.0
#     heading2_space_after: float = 5.0
    
#     # Heading 3 styles
#     heading3_font: str = "Times New Roman"
#     heading3_size: int = 14
#     heading3_bold: bool = True
#     heading3_italic: bool = False
#     heading3_underline: bool = False
#     heading3_color: str = "#000000"
#     heading3_line_spacing: float = 1.0
#     heading3_space_before: float = 8.0
#     heading3_space_after: float = 4.0
    
#     # Heading 4 styles
#     heading4_font: str = "Times New Roman"
#     heading4_size: int = 12
#     heading4_bold: bool = False
#     heading4_italic: bool = False
#     heading4_underline: bool = False
#     heading4_color: str = "#000000"
#     heading4_line_spacing: float = 1.0
#     heading4_space_before: float = 6.0
#     heading4_space_after: float = 3.0
    
#     # Body text styles
#     body_font: str = "Times New Roman"
#     body_size: int = 12
#     body_color: str = "#000000"
#     body_line_spacing: float = 1.0
#     body_space_before: float = 0.0
#     body_space_after: float = 0.0
#     body_justified: bool = False
    
#     # Bullet and numbered list styles
#     bullet_font: str = "Times New Roman"
#     bullet_size: int = 12
#     bullet_color: str = "#000000"
#     bullet_line_spacing: float = 1.0
#     bullet_indent: float = 0.5
#     bullet_space_before: float = 0.0
#     bullet_space_after: float = 0.0
#     bullet_type: str = "bullet"
    
#     # Numbered list styles
#     numbered_font: str = "Times New Roman"
#     numbered_size: int = 12
#     numbered_color: str = "#000000"
#     numbered_line_spacing: float = 1.0
#     numbered_indent: float = 0.5
#     numbered_space_before: float = 0.0
#     numbered_space_after: float = 0.0
#     numbered_style: str = "1,2,3"
    
#     # Document margins (in mm)
#     margin_top: float = 25.0
#     margin_bottom: float = 25.0
#     margin_left: float = 30.0
#     margin_right: float = 20.0
    
#     # Page settings
#     page_size: str = "A4"
#     line_number_enabled: bool = False
#     first_line_indent: float = 0.5
    
#     # Line spacing overrides
#     body_line_spacing_override: bool = False
#     heading1_line_spacing_override: bool = False
#     heading2_line_spacing_override: bool = False
#     heading3_line_spacing_override: bool = False
#     bullet_line_spacing_override: bool = False
#     numbered_line_spacing_override: bool = False
    
#     reference_rules: Optional[ReferenceFormattingRule] = None


# class TemplateCreate(BaseModel):
#     name: str
#     required_sections: List[RequiredSection] = []   # ← now structured
#     formatting_rules: FormattingRule


# class TemplateUpdate(BaseModel):
#     name: Optional[str] = None
#     required_sections: Optional[List[RequiredSection]] = None  # ← now structured
#     formatting_rules: Optional[FormattingRule] = None


# class TemplateResponse(BaseModel):
#     id: int
#     name: str
#     required_sections: List[RequiredSection]         # ← now structured
#     formatting_rules: FormattingRule
#     university_id: int
#     created_by: int
#     created_at: datetime

# class DocumentUpload(BaseModel):
#     template_id: int
#     filename: str

# class DocumentResponse(BaseModel):
#     id: int
#     filename: str
#     detected_sections: List[str]
#     missing_sections: List[str]
#     status: str
#     created_at: datetime

# class SectionSuggestion(BaseModel):
#     section_name: str
#     reason: str
#     suggested_content: str

# class ImageAnalysisResult(BaseModel):
#     is_safe: bool
#     confidence_score: float
#     warnings: Optional[List[str]] = None

# class DocumentUploadResponse(BaseModel):
#     id: int
#     filename: str
#     file_path: str
#     status: str
#     created_at: datetime

# class GoogleDriveFile(BaseModel):
#     id: str
#     name: str
#     mime_type: str
#     modified_time: str
#     file_size: Optional[int] = None

# class FileSyncStatus(BaseModel):
#     document_id: int
#     source: str
#     sync_status: str
#     google_drive_id: Optional[str] = None
#     local_path: Optional[str] = None
#     last_synced: Optional[datetime] = None

# class MobileUploadRequest(BaseModel):
#     session_id: str
#     filename: str
#     file_size: int
#     template_id: int

# class QRDownloadCreate(BaseModel):
#     document_id: int
#     file_type: str

# class QRDownloadStatus(BaseModel):
#     is_valid: bool
#     expires_at: datetime
#     used: bool
    

# class DocumentImage(BaseModel):
#     """Model for document images stored in database"""
#     id: int
#     document_id: int
#     image_path: str
#     image_filename: str
#     line_number: int
#     created_at: datetime

# class Config:
#     from_attributes = True
    
    
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any, Dict
from datetime import datetime

from pydantic import BaseModel
from typing import Optional


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str = "student"
    university_id: Optional[int] = None

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    university_id: Optional[int]
    created_at: datetime

class ReferenceFormattingRule(BaseModel):
    """
    Sub-model embedded inside FormattingRule / formatting_rules JSON.
    The admin configures this once per template; the formatter service reads
    it every time a student uploads a document.
    """
    style: str = "APA"                 # "APA" | "IEEE" | "MLA"
    font_name: str = "Times New Roman"
    font_size: float = 12.0
    line_spacing: float = 1.5          # multiplier
    hanging_indent: float = 0.5        # inches
    space_before: float = 0.0          # pt
    space_after: float = 6.0           # pt
    bold: bool = False
    italic: bool = False
    color: str = "#000000"             # hex
    sort_alphabetically: bool = True
    remove_duplicates: bool = True
    make_urls_clickable: bool = True
    mark_incomplete: bool = True
    numbering_style: str = "numeric"


# ─────────────────────────────────────────────────────────────────────────────
# NEW: Table style sub-model
# ─────────────────────────────────────────────────────────────────────────────
class TableStyle(BaseModel):
    """
    Table formatting settings saved by admin in the template.
    Applied automatically to all tables detected in a user's uploaded document.
    """
    font_name: str = "Times New Roman"
    font_size: int = 12
    header_bold: bool = True
    header_bg: str = "D6E4F0"          # hex, no leading #
    header_align: str = "center"       # left | center | right | justify
    body_align: str = "left"
    banded_rows: bool = True
    band_color: str = "F2F8FC"         # hex, no leading #
    borders: bool = True
    border_color: str = "000000"       # hex, no leading #
    border_size: int = 4               # half-points (4 = 0.5pt)
    cell_padding_top: int = 60         # twips
    cell_padding_bot: int = 60
    cell_padding_lft: int = 108
    cell_padding_rgt: int = 108
    center_table: bool = True
    auto_fit: bool = True
    repeat_header: bool = True


class UserLoginResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    token: str

class UniversityCreate(BaseModel):
    name: str
    country: str

class UniversityResponse(BaseModel):
    id: int
    name: str
    country: str

# ─────────────────────────────────────────────────────────────────────────────
# Structured required section (replaces plain List[str])
# ─────────────────────────────────────────────────────────────────────────────
class RequiredSection(BaseModel):
    """
    One entry in the template's required_sections list.

    Example:
        {"name": "Introduction", "order": 1, "required": true}
    """
    name: str
    order: int          # 1-based position in the expected document order
    required: bool = True  # True = must be present; False = optional but tracked

# ─────────────────────────────────────────────────────────────────────────────

class FormattingRule(BaseModel):
    # Heading 1 styles
    heading1_font: str = "Times New Roman"
    heading1_size: int = 18
    heading1_bold: bool = True
    heading1_italic: bool = False
    heading1_underline: bool = False
    heading1_color: str = "#000000"
    heading1_line_spacing: float = 1.0
    heading1_space_before: float = 12.0
    heading1_space_after: float = 6.0

    # Heading 2 styles
    heading2_font: str = "Times New Roman"
    heading2_size: int = 16
    heading2_bold: bool = True
    heading2_italic: bool = False
    heading2_underline: bool = False
    heading2_color: str = "#000000"
    heading2_line_spacing: float = 1.0
    heading2_space_before: float = 10.0
    heading2_space_after: float = 5.0

    # Heading 3 styles
    heading3_font: str = "Times New Roman"
    heading3_size: int = 14
    heading3_bold: bool = True
    heading3_italic: bool = False
    heading3_underline: bool = False
    heading3_color: str = "#000000"
    heading3_line_spacing: float = 1.0
    heading3_space_before: float = 8.0
    heading3_space_after: float = 4.0

    # Heading 4 styles
    heading4_font: str = "Times New Roman"
    heading4_size: int = 12
    heading4_bold: bool = False
    heading4_italic: bool = False
    heading4_underline: bool = False
    heading4_color: str = "#000000"
    heading4_line_spacing: float = 1.0
    heading4_space_before: float = 6.0
    heading4_space_after: float = 3.0

    # Body text styles
    body_font: str = "Times New Roman"
    body_size: int = 12
    body_color: str = "#000000"
    body_line_spacing: float = 1.0
    body_space_before: float = 0.0
    body_space_after: float = 0.0
    body_justified: bool = False

    # Bullet and numbered list styles
    bullet_font: str = "Times New Roman"
    bullet_size: int = 12
    bullet_color: str = "#000000"
    bullet_line_spacing: float = 1.0
    bullet_indent: float = 0.5
    bullet_space_before: float = 0.0
    bullet_space_after: float = 0.0
    bullet_type: str = "bullet"

    # Numbered list styles
    numbered_font: str = "Times New Roman"
    numbered_size: int = 12
    numbered_color: str = "#000000"
    numbered_line_spacing: float = 1.0
    numbered_indent: float = 0.5
    numbered_space_before: float = 0.0
    numbered_space_after: float = 0.0
    numbered_style: str = "1,2,3"

    # Document margins (in mm)
    spacing_unit: str = "mm"  # mm | cm | in
    margin_top: float = 25.0
    margin_bottom: float = 25.0
    margin_left: float = 30.0
    margin_right: float = 20.0

    # Page settings
    page_size: str = "A4"
    line_number_enabled: bool = False
    first_line_indent: float = 0.5

    # Line spacing overrides
    body_line_spacing_override: bool = False
    heading1_line_spacing_override: bool = False
    heading2_line_spacing_override: bool = False
    heading3_line_spacing_override: bool = False
    bullet_line_spacing_override: bool = False
    numbered_line_spacing_override: bool = False

    # Reference rules sub-object
    reference_rules: Optional[ReferenceFormattingRule] = None

    # ── TABLE STYLE (NEW) ────────────────────────────────────────────────────
    # Using Optional[TableStyle] so existing templates without this field
    # deserialise cleanly (defaults to None, not a validation error).
    table_style: Optional[TableStyle] = None

    # ── Extra safety net ─────────────────────────────────────────────────────
    # Allow any extra fields sent by the Flutter client that are not yet
    # modelled here. They will be silently preserved in the DB via the
    # admin router's dict-based merge logic instead of being stripped.
    model_config = {"extra": "allow"}


class TemplateCreate(BaseModel):
    name: str
    required_sections: List[RequiredSection] = []
    formatting_rules: FormattingRule


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    required_sections: Optional[List[RequiredSection]] = None
    formatting_rules: Optional[FormattingRule] = None


class TemplateResponse(BaseModel):
    id: int
    name: str
    required_sections: List[RequiredSection]
    formatting_rules: FormattingRule
    university_id: int
    created_by: int
    created_at: datetime

class DocumentUpload(BaseModel):
    template_id: int
    filename: str

class DocumentResponse(BaseModel):
    id: int
    filename: str
    detected_sections: List[str]
    missing_sections: List[str]
    status: str
    created_at: datetime

class SectionSuggestion(BaseModel):
    section_name: str
    reason: str
    suggested_content: str

class ImageAnalysisResult(BaseModel):
    is_safe: bool
    confidence_score: float
    warnings: Optional[List[str]] = None

class DocumentUploadResponse(BaseModel):
    id: int
    filename: str
    file_path: str
    status: str
    created_at: datetime

class GoogleDriveFile(BaseModel):
    id: str
    name: str
    mime_type: str
    modified_time: str
    file_size: Optional[int] = None

class FileSyncStatus(BaseModel):
    document_id: int
    source: str
    sync_status: str
    google_drive_id: Optional[str] = None
    local_path: Optional[str] = None
    last_synced: Optional[datetime] = None

class MobileUploadRequest(BaseModel):
    session_id: str
    filename: str
    file_size: int
    template_id: int

class QRDownloadCreate(BaseModel):
    document_id: int
    file_type: str

class QRDownloadStatus(BaseModel):
    is_valid: bool
    expires_at: datetime
    used: bool


class DocumentImage(BaseModel):
    """Model for document images stored in database"""
    id: int
    document_id: int
    image_path: str
    image_filename: str
    line_number: int
    created_at: datetime

class Config:
    from_attributes = True
 