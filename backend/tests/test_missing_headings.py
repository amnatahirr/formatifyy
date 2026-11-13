"""
Tests for the Missing Headings feature:

- missing_sections.splice_ghost_blocks (pure block splicing)
- POST /api/documents/add-missing-heading/{id} endpoint behaviour
- analyze response missing_headings keys + missing_section issue filtering

Uses a temp SQLite DB and temp docx files; never touches formatify.db.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault("SUPER_ADMIN_KEY", "super_secret_master_key_here")
os.environ.setdefault("JWT_SECRET", "formatify_dev_jwt_secret_change_me")
os.environ.setdefault("PLAGIARISM_ENABLE_WEB", "false")
os.environ.setdefault("PLAGIARISM_LLM_PATTERNS", "false")
if not os.environ.get("FORMATIFY_ENC_KEY"):
    from cryptography.fernet import Fernet

    os.environ["FORMATIFY_ENC_KEY"] = Fernet.generate_key().decode()

from fastapi import HTTPException  # noqa: E402


def _precreate_templates_with_org_id(database) -> None:
    """Same workaround as tests_full/conftest.py for the init_db seed-order bug."""
    conn = database.get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS universities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            country TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'student',
            university_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (university_id) REFERENCES universities(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            university_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            required_sections TEXT,
            formatting_rules TEXT,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            org_id INTEGER DEFAULT 1,
            FOREIGN KEY (university_id) REFERENCES universities(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
        """
    )
    conn.commit()
    conn.close()


REQUIRED_SECTIONS = [
    {"name": "Introduction", "order": 1, "required": True, "heading_level": 1},
    {"name": "Methodology", "order": 2, "required": True, "heading_level": 1},
    {"name": "Results", "order": 3, "required": True, "heading_level": 1},
    {"name": "Conclusion", "order": 4, "required": True, "heading_level": 1},
]

FORMATTING_RULES = {
    "heading1_font": "Times New Roman",
    "heading1_size": 16,
    "heading1_bold": True,
    "body_font": "Times New Roman",
    "body_size": 11,
    "body_line_spacing": 1.5,
}


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("missing_headings")
    db_path = tmp / "test_formatify.db"
    upload = tmp / "uploads"
    (upload / "working").mkdir(parents=True)
    (upload / "analysis").mkdir(parents=True)
    outputs = tmp / "outputs"
    outputs.mkdir()

    import database

    database.DATABASE_URL = str(db_path)
    _precreate_templates_with_org_id(database)
    database.init_db()

    import main as main_mod

    main_mod.UPLOAD_DIR = str(upload)
    main_mod.OUTPUT_DIR = str(outputs)
    main_mod.ANALYSIS_CACHE_DIR = str(upload / "analysis")
    database.DATABASE_URL = str(db_path)

    # Source docx: has Introduction + Conclusion; Methodology + Results missing.
    from docx import Document

    src = tmp / "source.docx"
    d = Document()
    d.add_heading("Introduction", level=1)
    d.add_paragraph("This report introduces the project scope and motivation.")
    d.add_paragraph("It also states the research questions clearly.")
    d.add_heading("Conclusion", level=1)
    d.add_paragraph("The project achieved its stated objectives.")
    d.save(str(src))

    # Seed template + document rows.
    conn = database.get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users ORDER BY id LIMIT 1")
    user_id = int(cur.fetchone()["id"])
    cur.execute(
        """
        INSERT INTO templates
            (university_id, name, description, required_sections, formatting_rules, created_by)
        VALUES (1, 'MH Test Template', 'test', ?, ?, ?)
        """,
        (json.dumps(REQUIRED_SECTIONS), json.dumps(FORMATTING_RULES), user_id),
    )
    template_id = int(cur.lastrowid)
    cur.execute(
        """
        INSERT INTO documents
            (user_id, template_id, filename, file_path, status)
        VALUES (?, ?, ?, ?, 'completed')
        """,
        (user_id, template_id, "source.docx", str(src)),
    )
    document_id = int(cur.lastrowid)
    conn.commit()
    conn.close()

    return SimpleNamespace(
        main=main_mod,
        database=database,
        tmp=tmp,
        upload=upload,
        user_id=user_id,
        template_id=template_id,
        document_id=document_id,
        src=src,
    )


# ---------------------------------------------------------------------------
# splice_ghost_blocks (pure)
# ---------------------------------------------------------------------------

def _blk(pid, type_="paragraph", text=""):
    return {"paragraph_id": pid, "type": type_, "text": text, "page": 1}


def test_splice_one_missing_before_anchor():
    from missing_sections import splice_ghost_blocks

    blocks = [_blk("p0"), _blk("p1"), _blk("p2")]
    previews = [{
        "name": "Methodology", "level": 1, "issue_id": "missing_heading_methodology",
        "insert_before_paragraph_id": "p1", "position": "before",
        "placeholder_text": "[Add your Methodology content here]",
    }]
    out = splice_ghost_blocks(blocks, previews)
    assert [b["type"] for b in out] == ["paragraph", "ghost_heading", "paragraph", "paragraph"]
    ghost = out[1]
    assert ghost["is_placeholder"] is True
    assert ghost["text"] == "Methodology"
    assert ghost["level"] == 1
    assert ghost["issue_id"] == "missing_heading_methodology"
    assert ghost["style"] == "Heading 1"
    # input list untouched
    assert all(b["type"] == "paragraph" for b in blocks)


def test_splice_two_adjacent_keep_template_order():
    from missing_sections import splice_ghost_blocks

    blocks = [_blk("p0"), _blk("p5")]
    previews = [
        {"name": "Methodology", "level": 1, "issue_id": "i1",
         "insert_before_paragraph_id": "p5", "position": "before"},
        {"name": "Results", "level": 1, "issue_id": "i2",
         "insert_before_paragraph_id": "p5", "position": "before"},
    ]
    out = splice_ghost_blocks(blocks, previews)
    ghosts = [b for b in out if b["type"] == "ghost_heading"]
    assert [g["text"] for g in ghosts] == ["Methodology", "Results"]
    # both before p5
    idx_p5 = next(i for i, b in enumerate(out) if b["paragraph_id"] == "p5")
    assert out[idx_p5 - 2]["text"] == "Methodology"
    assert out[idx_p5 - 1]["text"] == "Results"


def test_splice_at_end_goes_before_images():
    from missing_sections import splice_ghost_blocks

    blocks = [
        _blk("p0"), _blk("p1"),
        {"paragraph_id": "", "type": "image", "text": "", "image_index": 0},
    ]
    previews = [{"name": "Conclusion", "level": 2, "issue_id": "i9",
                 "insert_before_paragraph_id": None, "position": "end"}]
    out = splice_ghost_blocks(blocks, previews)
    types = [b["type"] for b in out]
    assert types == ["paragraph", "paragraph", "ghost_heading", "image"]
    assert out[2]["style"] == "Heading 2"


def test_splice_no_previews_returns_blocks():
    from missing_sections import splice_ghost_blocks

    blocks = [_blk("p0")]
    assert splice_ghost_blocks(blocks, []) == blocks
    assert splice_ghost_blocks(blocks, None) == blocks


# ---------------------------------------------------------------------------
# add-missing-heading endpoint
# ---------------------------------------------------------------------------

def _call(coro):
    return asyncio.run(coro)


def test_missing_sections_detection_on_working_copy(env):
    """Sanity: detection on the source docx finds Methodology + Results."""
    from missing_sections import build_previews, detect_missing_sections

    info = detect_missing_sections(str(env.src), REQUIRED_SECTIONS)
    assert info["reliable"] is True
    names = [m["name"] for m in info["missing"]]
    assert names == ["Methodology", "Results"]
    previews = build_previews(info)
    assert all(p["issue_id"].startswith("missing_heading_") for p in previews)


def test_add_missing_heading_with_content(env):
    main = env.main
    result = _call(main.add_missing_heading_endpoint(
        env.document_id,
        env.user_id,
        {"section_name": "Methodology", "content": "First paragraph.\n\nSecond paragraph."},
    ))
    assert result["status"] == "success"
    assert result["inserted"] is True
    assert result["message"]

    # Working copy now contains heading + two body paragraphs in order.
    from docx import Document

    doc = Document(result["working_copy"])
    texts = [p.text for p in doc.paragraphs]
    styles = [p.style.name for p in doc.paragraphs]
    i_intro = texts.index("Introduction")
    i_meth = texts.index("Methodology")
    i_conc = texts.index("Conclusion")
    assert i_intro < i_meth < i_conc
    assert styles[i_meth].startswith("Heading")
    # body paragraphs immediately after the heading
    assert texts[i_meth + 1] == "First paragraph."
    assert texts[i_meth + 2] == "Second paragraph."

    # Response carries ghost-spliced blocks + updated missing list.
    mh_names = [m["name"] for m in result["missing_headings"]]
    assert mh_names == ["Results"]
    ghost_texts = [b["text"] for b in result["document_blocks"] if b["type"] == "ghost_heading"]
    assert ghost_texts == ["Results"]

    # Second call is idempotent.
    again = _call(main.add_missing_heading_endpoint(
        env.document_id,
        env.user_id,
        {"section_name": "Methodology", "content": "ignored"},
    ))
    assert again["inserted"] is False
    assert "already has a matching heading" in again["message"]


def test_add_missing_heading_empty_content_placeholder(env):
    main = env.main
    result = _call(main.add_missing_heading_endpoint(
        env.document_id,
        env.user_id,
        {"section_name": "Results", "content": ""},
    ))
    assert result["inserted"] is True

    from docx import Document

    doc = Document(result["working_copy"])
    texts = [p.text for p in doc.paragraphs]
    i_res = texts.index("Results")
    assert texts[i_res + 1] == "[Add your Results content here]"
    assert result["missing_headings"] == []


def test_add_missing_heading_unknown_section_400(env):
    main = env.main
    with pytest.raises(HTTPException) as exc:
        _call(main.add_missing_heading_endpoint(
            env.document_id, env.user_id,
            {"section_name": "Not A Section", "content": "x"},
        ))
    assert exc.value.status_code == 400


def test_add_missing_heading_other_user_404(env):
    main = env.main
    with pytest.raises(HTTPException) as exc:
        _call(main.add_missing_heading_endpoint(
            env.document_id, env.user_id + 9999,
            {"section_name": "Methodology", "content": "x"},
        ))
    assert exc.value.status_code == 404


def test_missing_headings_get_endpoint(env):
    main = env.main
    state = main.missing_headings_endpoint(env.document_id, env.user_id)
    assert state["status"] == "success"
    assert state["missing_headings"] == []  # all added by earlier tests
    assert isinstance(state["document_blocks"], list)


# ---------------------------------------------------------------------------
# analyze response
# ---------------------------------------------------------------------------

def test_analyze_response_missing_headings(env, monkeypatch):
    main = env.main

    async def fake_run_analysis(**kwargs):
        return {"issues": [], "stats": {}}

    async def fake_ai_client():
        raise RuntimeError("no AI in tests")

    monkeypatch.setattr(main, "_run_analysis", fake_run_analysis)
    monkeypatch.setattr(main, "_get_ai_client", fake_ai_client)
    monkeypatch.setattr(main, "sync_analysis_to_project_members", lambda *a, **k: None)

    # Fresh document still missing Methodology + Results? Earlier tests added
    # them to the working copy, but analyze force-rebuilds from the upload,
    # so both are missing again.
    result = asyncio.run(main.analyze_document_endpoint(env.document_id, env.user_id))

    assert "missing_headings" in result
    assert result["missing_headings_reliable"] is True
    names = [m["name"] for m in result["missing_headings"]]
    assert names == ["Methodology", "Results"]
    for m in result["missing_headings"]:
        assert set(m) >= {
            "issue_id", "name", "level", "optional",
            "insert_before_paragraph_id", "position", "placeholder_text",
        }

    # Ghost blocks spliced into document_blocks.
    ghosts = [b for b in result["document_blocks"] if b["type"] == "ghost_heading"]
    assert [g["text"] for g in ghosts] == ["Methodology", "Results"]
    assert all(g["is_placeholder"] for g in ghosts)

    # No missing_section issues anywhere in the issues lists.
    for key in ("issues", "content_issues", "style_issues"):
        assert not [
            i for i in result[key]
            if (i.get("type") or "").lower() == "missing_section"
        ], key

    # template_heading_matches unchanged — still reports missing rows.
    missing_matches = [
        m for m in result["template_heading_matches"]
        if m.get("source") == "missing"
    ]
    assert len(missing_matches) >= 2

    # Cached analysis json carries the new keys.
    cache = Path(env.upload) / "analysis" / f"doc_{env.document_id}.json"
    # analyze endpoint itself does not write the cache (worker does), so just
    # verify the response is JSON-serializable.
    json.dumps(result, default=str)
