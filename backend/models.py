"""
models.py — Pydantic data models for the Formatify analysis pipeline.

Defines the exact JSON contract expected by the Flutter frontend.
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════════
# DOCUMENT MODEL — output of the ingestion/parser layer
# ═══════════════════════════════════════════════════════════════════════════════

class ParagraphBlock(BaseModel):
    """A single paragraph extracted from the document."""
    paragraph_id: str
    page_number: int
    heading_context: str = ""
    style: str = "Normal"
    text: str = ""
    font_size: Optional[float] = None
    bold: Optional[bool] = None
    style_name: Optional[str] = None
    numbering_prefix: Optional[str] = None
    prev_blank: bool = False
    next_blank: bool = False


class ImageBlock(BaseModel):
    """A single image extracted from the document."""
    image_id: str
    page_number: int
    base64: str = ""
    caption: str = ""
    # Paragraph that embeds the image (e.g. "p12") — used for before/after relevance.
    paragraph_id: str = ""


class DocumentModel(BaseModel):
    """Structured representation of the entire uploaded document."""
    filename: str = ""
    total_pages: int = 0
    paragraphs: List[ParagraphBlock] = Field(default_factory=list)
    images: List[ImageBlock] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH MODEL — output of the batching layer
# ═══════════════════════════════════════════════════════════════════════════════

class Batch(BaseModel):
    """A batch of pages sent to the AI functions for analysis."""
    batch_index: int
    page_start: int
    page_end: int
    paragraphs: List[ParagraphBlock] = Field(default_factory=list)
    images: List[ImageBlock] = Field(default_factory=list)
    context_paragraphs: List[ParagraphBlock] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# ISSUE MODEL — individual issue found by any AI function
# ═══════════════════════════════════════════════════════════════════════════════

class Issue(BaseModel):
    """
    A single issue detected by one of the six analysis functions.
    Fields are a superset — each function populates only the fields it needs.
    """
    function: str = ""
    type: str = ""
    severity: str = "minor"
    paragraph_id: str = ""
    image_id: str = ""
    page: int = 0
    reason: str = ""
    suggestion: str = ""
    explanation: str = ""
    original: str = ""
    current_heading: str = ""
    content_belongs_to: str = ""
    text_preview: str = ""
    verdict: str = ""
    confidence: float = 0.0
    # Local vision extras
    ethics_category: str = ""
    similarity: float = 0.0
    surrounding_text: str = ""
    # Heading / list classification provenance
    source: str = ""  # matched | inferred | missing | list_detection_prepass | ...
    heading_level: Optional[int] = None
    matched_template_heading: Optional[str] = None
    needs_review: bool = False
    list_detection: str = ""
    para_indices: List[int] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# STATISTICS — summary stats for the analysis report
# ═══════════════════════════════════════════════════════════════════════════════

class Stats(BaseModel):
    total_issues: int = 0
    grammar_issues: int = 0
    formatting_issues: int = 0
    image_ethics_issues: int = 0
    image_relevance_issues: int = 0
    para_relevance_issues: int = 0
    plagiarism_issues: int = 0
    major_issues: int = 0
    minor_issues: int = 0
    avg_formatting_compliance: float = 0.0
    avg_plagiarism_risk: float = 0.0


class DocumentInfo(BaseModel):
    filename: str = ""
    total_pages: int = 0
    total_paragraphs: int = 0
    total_images: int = 0
    total_batches: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# ANALYSIS REPORT — top-level response returned to the Flutter frontend
# ═══════════════════════════════════════════════════════════════════════════════

class AnalysisReport(BaseModel):
    """The complete JSON response returned by POST /analyze."""
    issues: List[Issue] = Field(default_factory=list)
    stats: Stats = Field(default_factory=Stats)
    document_info: Optional[DocumentInfo] = None
# ═══════════════════════════════════════════════════════════════════════════════
# AUTH & TEMPLATE CRUD MODELS — for signup, login and admin settings
# ═══════════════════════════════════════════════════════════════════════════════

class UserSignupRequest(BaseModel):
    username: str
    email: str
    password: str
    university_id: Optional[int] = 1
    department_id: int
    current_semester: int


class UserLoginRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    user_id: int
    current_password: str
    new_password: str


class TemplateCreateRequest(BaseModel):
    name: str
    description: str = ""
    required_sections: List[Any] = Field(default_factory=list)
    formatting_rules: Dict[str, Any] = Field(default_factory=dict)


class TemplateUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    required_sections: Optional[List[Any]] = None
    formatting_rules: Optional[Dict[str, Any]] = None


# ═══════════════════════════════════════════════════════════════════════════════
# FRONTMATTER — cover page / project-details detection & generation
# ═══════════════════════════════════════════════════════════════════════════════

class FrontmatterMember(BaseModel):
    """One group member. reg_no / email are optional in the minimal schema."""
    name: str = ""
    reg_no: Optional[str] = None
    email: Optional[str] = None


class DetectionResult(BaseModel):
    """Result of hybrid cover / project-info page detection on a DOCX."""
    cover_page_present: bool = False
    info_page_present: bool = False
    cover_confidence: float = 0.0
    info_confidence: float = 0.0
    confidence: float = 0.0
    reasoning: str = ""
    used_llm: bool = False
    cover_signals: List[str] = Field(default_factory=list)
    info_signals: List[str] = Field(default_factory=list)


class FrontmatterContext(BaseModel):
    """Assembled data ready for cover / project-info DOCX templates."""
    project_title: str = ""
    university_name: str = ""
    department: str = ""
    session: str = ""
    logo_path: Optional[str] = None
    members: List[FrontmatterMember] = Field(default_factory=list)
    supervisor_name: str = ""
    cosupervisor_name: str = ""
    domains: List[str] = Field(default_factory=list)
    signature_path: Optional[str] = None


class FrontmatterGenerateRequest(BaseModel):
    """Optional overrides sent with POST .../frontmatter/generate."""
    group_id: Optional[int] = None
    domains: Optional[List[str]] = None
    signature_path: Optional[str] = None
    generate_cover: Optional[bool] = None
    generate_info: Optional[bool] = None