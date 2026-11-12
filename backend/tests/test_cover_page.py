"""
test_cover_page.py — Tests for cover page rendering.

Verifies:
  (a) full data cover
  (b) no co-supervisor
  (c) no logo
  - correct paragraph order and text
  - no bullets / numbering / ListParagraph styles
  - no raw Jinja tags ({{ or {%)
"""
from __future__ import annotations

import io
import os
import sys

import pytest
from docx import Document
from docx.oxml.ns import qn

# Ensure backend is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import FrontmatterContext, FrontmatterMember
from frontmatter.frontmatter_generator import (
    render_cover_page,
    scaffold_templates,
)


@pytest.fixture(autouse=True, scope="module")
def _ensure_templates():
    """Make sure the cover template exists (scaffold if missing)."""
    scaffold_templates()


def _cover_paragraphs(ctx: FrontmatterContext) -> list[str]:
    """Render a cover and return non-empty paragraph texts (in order)."""
    cover_bytes = render_cover_page(ctx)
    doc = Document(io.BytesIO(cover_bytes))
    return [
        (p.text or "").strip()
        for p in doc.paragraphs
        if (p.text or "").strip()
    ]


def _cover_doc(ctx: FrontmatterContext) -> Document:
    cover_bytes = render_cover_page(ctx)
    return Document(io.BytesIO(cover_bytes))


def _has_numbering(doc: Document) -> list[str]:
    """Return paragraph texts that have <w:numPr> (list numbering) or List styles."""
    bad = []
    for p in doc.paragraphs:
        pPr = p._element.find(qn("w:pPr"))
        has_num = pPr is not None and pPr.find(qn("w:numPr")) is not None
        style_name = (p.style.name if p.style else "") or ""
        is_list_style = "list" in style_name.lower()
        if has_num or is_list_style:
            bad.append((p.text or "").strip())
    return bad


def _has_jinja_tags(doc: Document) -> list[str]:
    """Return paragraph texts that still contain raw Jinja tags."""
    bad = []
    for p in doc.paragraphs:
        t = p.text or ""
        if "{{" in t or "{%" in t:
            bad.append(t.strip())
    return bad


# ── Fixtures ──────────────────────────────────────────────────────────────────

FULL_CTX = FrontmatterContext(
    project_title="Smart Traffic System",
    university_name="COMSATS University Islamabad",
    department="Computer Science",
    session="Fall 2026",
    logo_path=None,  # logo tested separately
    members=[
        FrontmatterMember(name="Alice", reg_no="FA20-BSE-001", email=None),
        FrontmatterMember(name="Bob", reg_no="FA20-BSE-002", email=None),
    ],
    supervisor_name="Dr. Ahmed",
    cosupervisor_name="Dr. Khan",
    domains=[],
    signature_path=None,
)

NO_COSUPERVISOR_CTX = FrontmatterContext(
    project_title="Smart Traffic System",
    university_name="COMSATS University Islamabad",
    department="Computer Science",
    session="Fall 2026",
    logo_path=None,
    members=[
        FrontmatterMember(name="Alice", reg_no="FA20-BSE-001", email=None),
    ],
    supervisor_name="Dr. Ahmed",
    cosupervisor_name="",  # empty
    domains=[],
    signature_path=None,
)

NO_LOGO_CTX = FrontmatterContext(
    project_title="Smart Traffic System",
    university_name="COMSATS University Islamabad",
    department="Computer Science",
    session="Fall 2026",
    logo_path="/nonexistent/logo.png",  # file does not exist
    members=[
        FrontmatterMember(name="Alice", reg_no="FA20-BSE-001", email=None),
    ],
    supervisor_name="Dr. Ahmed",
    cosupervisor_name="",
    domains=[],
    signature_path=None,
)


# ── (a) Full data ────────────────────────────────────────────────────────────

class TestFullDataCover:
    def test_paragraph_order(self):
        texts = _cover_paragraphs(FULL_CTX)
        # Expected order: university, department, (logo omitted), title,
        # "Final Year Project Report", "Session: Fall 2026",
        # "Submitted by:", member lines, "Supervisor: Dr. Ahmed",
        # "Co-Supervisor: Dr. Khan"
        assert "COMSATS University Islamabad" in texts
        assert "Computer Science" in texts
        assert "Smart Traffic System" in texts
        assert "Final Year Project Report" in texts
        assert "Session: Fall 2026" in texts
        assert "Submitted by:" in texts
        assert "Supervisor: Dr. Ahmed" in texts
        assert "Co-Supervisor: Dr. Khan" in texts

        # Check order: university before title before FYP
        uni_idx = texts.index("COMSATS University Islamabad")
        dept_idx = texts.index("Computer Science")
        title_idx = texts.index("Smart Traffic System")
        fyp_idx = texts.index("Final Year Project Report")
        session_idx = texts.index("Session: Fall 2026")
        sub_idx = texts.index("Submitted by:")
        sup_idx = texts.index("Supervisor: Dr. Ahmed")
        cosup_idx = texts.index("Co-Supervisor: Dr. Khan")

        assert uni_idx < dept_idx < title_idx < fyp_idx < session_idx < sub_idx < sup_idx < cosup_idx

    def test_member_lines(self):
        texts = _cover_paragraphs(FULL_CTX)
        assert "Alice (FA20-BSE-001)" in texts
        assert "Bob (FA20-BSE-002)" in texts

        # Members are between "Submitted by:" and "Supervisor: Dr. Ahmed"
        sub_idx = texts.index("Submitted by:")
        alice_idx = texts.index("Alice (FA20-BSE-001)")
        bob_idx = texts.index("Bob (FA20-BSE-002)")
        sup_idx = texts.index("Supervisor: Dr. Ahmed")
        assert sub_idx < alice_idx < bob_idx < sup_idx

    def test_no_bullets(self):
        doc = _cover_doc(FULL_CTX)
        numbered = _has_numbering(doc)
        assert numbered == [], f"Cover paragraphs have list numbering / list style: {numbered}"

    def test_no_jinja_tags(self):
        doc = _cover_doc(FULL_CTX)
        bad = _has_jinja_tags(doc)
        assert bad == [], f"Cover has raw Jinja tags: {bad}"


# ── (b) No co-supervisor ──────────────────────────────────────────────────────

class TestNoCosupervisor:
    def test_cosupervisor_omitted(self):
        texts = _cover_paragraphs(NO_COSUPERVISOR_CTX)
        assert not any("Co-Supervisor" in t for t in texts), (
            f"Co-Supervisor line should be omitted: {texts}"
        )
        # Supervisor still present
        assert "Supervisor: Dr. Ahmed" in texts

    def test_no_bullets(self):
        doc = _cover_doc(NO_COSUPERVISOR_CTX)
        numbered = _has_numbering(doc)
        assert numbered == [], f"Cover paragraphs have list numbering / list style: {numbered}"

    def test_no_jinja_tags(self):
        doc = _cover_doc(NO_COSUPERVISOR_CTX)
        bad = _has_jinja_tags(doc)
        assert bad == [], f"Cover has raw Jinja tags: {bad}"


# ── (c) No logo ───────────────────────────────────────────────────────────────

class TestNoLogo:
    def test_logo_paragraph_removed(self):
        texts = _cover_paragraphs(NO_LOGO_CTX)
        # No empty line where logo would be; university and title still present
        assert "COMSATS University Islamabad" in texts
        assert "Smart Traffic System" in texts
        # No blank lines
        assert "" not in texts

    def test_no_jinja_tags(self):
        doc = _cover_doc(NO_LOGO_CTX)
        bad = _has_jinja_tags(doc)
        assert bad == [], f"Cover has raw Jinja tags: {bad}"

    def test_no_bullets(self):
        doc = _cover_doc(NO_LOGO_CTX)
        numbered = _has_numbering(doc)
        assert numbered == [], f"Cover paragraphs have list numbering / list style: {numbered}"
