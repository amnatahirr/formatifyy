"""Pydantic models for the VC module."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""
    template_id: int


class JoinProjectRequest(BaseModel):
    invite_code: str


class InviteMemberRequest(BaseModel):
    email: str


class CommitRequest(BaseModel):
    content: str
    message: str = ""


class RollbackRequest(BaseModel):
    commit_id: int


class ResolveConflictRequest(BaseModel):
    resolution_content: str


class ConflictVariant(BaseModel):
    author_id: int
    author_name: str
    content: str
    commit_id: int
    version_number: int
    created_at: str


class MergeConflictResponse(BaseModel):
    id: int
    conflict_type: str
    section_id: Optional[str] = None
    section_name: Optional[str] = None
    related_section_id: Optional[str] = None
    related_section_name: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    status: str
    resolution_content: Optional[str] = None


class SectionState(BaseModel):
    section_id: str
    section_name: str
    template_order: int
    heading_level: int = 1
    latest_content: str = ""
    latest_version: int = 0
    latest_author: str = ""
    latest_updated_at: Optional[str] = None
    commit_count: int = 0


class CommitRecord(BaseModel):
    id: int
    section_id: str
    author_id: int
    author_name: str
    version_number: int
    content: str
    commit_type: str
    parent_commit_id: Optional[int] = None
    message: str = ""
    created_at: str
