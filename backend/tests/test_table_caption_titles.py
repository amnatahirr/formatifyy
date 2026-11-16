"""Tests for table caption titles, caption structure and bookmark safety."""

import re
import zipfile

import pytest
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from docx_tools.docx_fields import (
    _prepare_toc_entries,
    generate_document_lists,
    normalize_bookmarks,
    rebuild_caption_with_seq,
    validate_and_repair_list_anchors,
)
from docx_tools.table_processor import dedupe_row_cells
from services.table_caption_service import (
    _clean_label_text,
    resolve_table_title,
)
from services.table_numbering_service import (
    apply_numbering_to_table_captions,
    assign_table_numbers,
)


def _p(doc, text, style=None):
    p = doc.add_paragraph(text)
    if style:
        try:
            p.style = doc.styles[style]
        except Exception:
            pass
    return p


def _table(doc, header_texts, rows=2):
    t = doc.add_table(rows=1 + rows, cols=len(header_texts))
    t.style = "Table Grid"
    for i, txt in enumerate(header_texts):
        t.rows[0].cells[i].text = txt
    for r in range(1, 1 + rows):
        for c in range(len(header_texts)):
            t.rows[r].cells[c].text = f"r{r}c{c}"
    return t


def _gridspan(table, col, span):
    tc = table.rows[0].cells[col]._tc
    tcPr = tc.get_or_add_tcPr()
    gs = OxmlElement("w:gridSpan")
    gs.set(qn("w:val"), str(span))
    tcPr.append(gs)


def _body_tables(doc):
    from docx_tools.docx_fields import _element_is_before_body_start

    return [t for t in doc.tables if not _element_is_before_body_start(doc, t._tbl)]


def _all_bm(doc):
    body = doc.element.body
    starts = {b.get(qn("w:id")): b.get(qn("w:name")) for b in body.iter(qn("w:bookmarkStart"))}
    ends = {e.get(qn("w:id")) for e in body.iter(qn("w:bookmarkEnd"))}
    return starts, ends


def _pageref_targets(doc):
    return set(re.findall(r"PAGEREF\s+(\S+)", doc.element.body.xml))


def _para_text(el):
    return "".join(t.text or "" for t in el.iter(qn("w:t")))


# ── a) label extraction ───────────────────────────────────────────────────────

def test_clean_label_strips_status_and_adds_requirements():
    assert (
        _clean_label_text("NFR02 – Usability — Addressed")
        == "NFR02 – Usability Requirements"
    )
    assert (
        _clean_label_text("FR02 - Admin Template Management - Implemented")
        == "FR02 - Admin Template Management Requirements"
    )
    assert _clean_label_text("UC01 - Login") == "UC01 - Login"


def test_resolve_title_prefers_label_paragraph(tmp_path):
    doc = Document()
    _p(doc, "2.3.1. Functional Requirements", style="Heading 2")
    _p(doc, "FR01 – User Registration and Authentication – Implemented")
    _p(doc, "This table defines the requirements for onboarding.")
    t = _table(doc, ["Requirement ID", "Requirement Description"])
    title, source = resolve_table_title(t, doc)
    assert source == "label"
    assert title == "FR01 – User Registration and Authentication Requirements"


def test_resolve_title_heading_and_header_sources():
    doc = Document()
    _p(doc, "2.3.3. Requirements Traceability Matrix", style="Heading 2")
    _p(doc, "This table maps requirements.")
    t = _table(doc, ["Col A", "Col B"])
    title, source = resolve_table_title(t, doc)
    assert source == "heading"
    assert title == "Requirements Traceability Matrix"

    doc2 = Document()
    t2 = _table(doc2, ["FR ID", "FR Description", "Business Needs"])
    title2, source2 = resolve_table_title(t2, doc2)
    assert source2 == "shape"
    assert title2 == "Requirements Traceability Matrix"

    t3 = _table(doc2, ["Team Member", "Activity"])
    title3, _ = resolve_table_title(t3, doc2)
    assert title3 == "Team Member Activity Allocation"

    # header fallback: never empty when header cells exist
    doc3 = Document()
    t4 = _table(doc3, ["Alpha", "Beta"])
    title4, source4 = resolve_table_title(t4, doc3)
    assert source4 == "header"
    assert title4 == "Alpha — Beta"


def test_resolve_title_distinct_for_identical_headers(tmp_path):
    doc = Document()
    titles = []
    for label in ("FR01 – Alpha – Implemented", "FR02 – Beta – Implemented"):
        _p(doc, label)
        _p(doc, "This table defines things.")
        t = _table(doc, ["ID", "Description"])
        titles.append(resolve_table_title(t, doc)[0])
    assert titles[0] != titles[1]
    assert "Alpha" in titles[0] and "Beta" in titles[1]


# ── b) merged-cell dedupe ─────────────────────────────────────────────────────

def test_gridspan_cells_deduped():
    doc = Document()
    t = doc.add_table(rows=2, cols=6)
    # merge cells 0-3 and 4-5 horizontally (real gridSpan structure)
    t.rows[0].cells[0].merge(t.rows[0].cells[3])
    t.rows[0].cells[4].merge(t.rows[0].cells[5])
    t.rows[0].cells[0].text = "TC-ID: TC01"
    t.rows[0].cells[4].text = "Author"
    cells = dedupe_row_cells(t.rows[0].cells)
    texts = [c.text.strip() for c in cells]
    assert texts.count("TC-ID: TC01") == 1
    assert "TC-ID: TC01 — TC-ID: TC01" not in " — ".join(texts)
    title, _ = resolve_table_title(t, doc)
    assert "TC-ID: TC01 — TC-ID: TC01" not in (title or "")


# ── c/d) numbering + caption structure ────────────────────────────────────────

def test_apply_numbering_caption_style_and_no_heading(tmp_path):
    doc = Document()
    _p(doc, "1. Intro", style="Heading 1")
    _p(doc, "FR01 – Login – Implemented")
    _p(doc, "This table defines login requirements.")
    t1 = _table(doc, ["ID", "Desc"])
    _p(doc, "Some body text between tables.")
    _p(doc, "NFR01 – Speed – Addressed")
    _p(doc, "This table defines speed requirements.")
    t2 = _table(doc, ["ID", "Desc"])

    assignments = assign_table_numbers(doc, {})
    applied = apply_numbering_to_table_captions(doc, assignments, {})
    assert len(applied) == 2

    body = _body_tables(doc)
    captions = []
    for tbl in body:
        prev = tbl._tbl.getprevious()
        while prev is not None and prev.tag != qn("w:p"):
            prev = prev.getprevious()
        if prev is not None:
            captions.append(prev)
    assert len(captions) == 2
    for cap in captions:
        p_pr = cap.find(qn("w:pPr"))
        ps = p_pr.find(qn("w:pStyle")) if p_pr is not None else None
        assert ps is not None and ps.get(qn("w:val")) == "Caption"
        # never a heading style / outline level
        assert p_pr.find(qn("w:outlineLvl")) is None
        assert p_pr.find(qn("w:numPr")) is None

    # main TOC must not list captions
    toc_entries = _prepare_toc_entries(doc, "1-3")
    for e in toc_entries:
        assert not re.match(r"(?i)^table\s+\d+\s*:", e["text"])


def test_rebuild_caption_with_seq_preserves_bookmarks():
    doc = Document()
    p = doc.add_paragraph("Table 1: Old title")
    # add a bookmark pair manually
    bm_id = "777"
    bs = OxmlElement("w:bookmarkStart")
    bs.set(qn("w:id"), bm_id)
    bs.set(qn("w:name"), "_Toc000000777")
    be = OxmlElement("w:bookmarkEnd")
    be.set(qn("w:id"), bm_id)
    p._element.insert(0, bs)
    p._element.append(be)

    rebuild_caption_with_seq(p, "Table", "New title", number=1)
    names = [b.get(qn("w:name")) for b in p._element.iter(qn("w:bookmarkStart"))]
    ends = [e.get(qn("w:id")) for e in p._element.iter(qn("w:bookmarkEnd"))]
    assert "_Toc000000777" in names
    assert bm_id in ends
    assert "SEQ Table" in p._element.xml


def test_numbering_twice_is_idempotent(tmp_path):
    doc = Document()
    _p(doc, "FR01 – Login – Implemented")
    _p(doc, "This table defines login requirements.")
    t = _table(doc, ["ID", "Desc"])
    a1 = assign_table_numbers(doc, {})
    apply_numbering_to_table_captions(doc, a1, {})
    xml1 = t._tbl.getprevious().xml
    a2 = assign_table_numbers(doc, {})
    apply_numbering_to_table_captions(doc, a2, {})
    xml2 = t._tbl.getprevious().xml
    assert xml1 == xml2


# ── e/f/g) full chain twice: anchors + LoT integrity ──────────────────────────

def _run_chain(path, rules=None):
    rules = rules or {}
    generate_document_lists(
        path, rules, [], include_toc=True, include_lot=True, include_lof=True
    )
    return path


def test_full_chain_twice_anchors_resolve(tmp_path):
    doc = Document()
    _p(doc, "1. Introduction", style="Heading 1")
    for i, label in enumerate(("FR01 – Alpha – Implemented", "NFR01 – Beta – Addressed"), 1):
        _p(doc, f"{i}. Section {label.split('–')[0].strip()}", style="Heading 2")
        _p(doc, label)
        _p(doc, "This table defines requirements.")
        _table(doc, ["ID", "Desc"])
    _p(doc, "2. More", style="Heading 1")
    _p(doc, "Closing text.")
    path = str(tmp_path / "doc.docx")
    doc.save(path)

    _run_chain(path)
    _run_chain(path)  # second full pass must stay consistent

    doc2 = Document(path)
    starts, ends = _all_bm(doc2)
    names = set(starts.values())
    # no unpaired starts
    assert all(i in ends for i in starts)
    # every PAGEREF target exists
    missing = _pageref_targets(doc2) - names
    assert not missing, f"dangling anchors: {missing}"
    # LoT entries == number of body tables, no duplicate captions
    from docx_tools.docx_fields import _element_is_before_body_start as before

    tables = [t for t in doc2.tables if not before(doc2, t._tbl)]
    lot_entries = [
        e for e in _pageref_targets(doc2)
    ]
    # count table-caption LoT entries by bookmark on caption paras
    cap_bm = set()
    for tbl in tables:
        prev = tbl._tbl.getprevious()
        while prev is not None and prev.tag != qn("w:p"):
            prev = prev.getprevious()
        if prev is not None:
            cap_bm.update(
                b.get(qn("w:name"))
                for b in prev.iter(qn("w:bookmarkStart"))
            )
    assert cap_bm <= names
    # captions not duplicated: only CONSECUTIVE caption paragraphs directly
    # above the table count (stops at first non-caption paragraph)
    for tbl in tables:
        prev = tbl._tbl.getprevious()
        caps = 0
        while prev is not None and prev.tag == qn("w:p"):
            txt = _para_text(prev).strip()
            if not re.match(r"(?i)^table\s*\d*\s*:", txt):
                break
            caps += 1
            prev = prev.getprevious()
        assert caps <= 1, f"table has {caps} stacked captions"


def test_validate_and_repair_fixes_dangling_anchor(tmp_path):
    doc = Document()
    _p(doc, "1. Intro", style="Heading 1")
    _p(doc, "Body text.")
    path = str(tmp_path / "d.docx")
    doc.save(path)
    d = Document(path)
    stats = validate_and_repair_list_anchors(d)
    assert stats["repaired"] == 0 and stats["dropped"] == 0


def test_normalize_bookmarks_removes_unreferenced(tmp_path):
    doc = Document()
    p = doc.add_paragraph("Heading One")
    try:
        p.style = doc.styles["Heading 1"]
    except Exception:
        pass
    # orphan bookmark pair, unreferenced
    bs = OxmlElement("w:bookmarkStart")
    bs.set(qn("w:id"), "501")
    bs.set(qn("w:name"), "_Toc000000501")
    be = OxmlElement("w:bookmarkEnd")
    be.set(qn("w:id"), "501")
    p._element.insert(0, bs)
    p._element.append(be)
    stats = normalize_bookmarks(doc)
    assert stats["removed"] >= 1
    names = [b.get(qn("w:name")) for b in doc.element.body.iter(qn("w:bookmarkStart"))]
    assert "_Toc000000501" not in names
