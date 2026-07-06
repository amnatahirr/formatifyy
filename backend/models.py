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


class ImageBlock(BaseModel):
    """A single image extracted from the document."""
    image_id: str
    page_number: int
    base64: str = ""
    caption: str = ""


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


class UserLoginRequest(BaseModel):
    email: str
    password: str


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