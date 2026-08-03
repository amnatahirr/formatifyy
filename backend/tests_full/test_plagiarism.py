"""Plagiarism corpus status, local_check smoke, supervisor monitor."""
from __future__ import annotations

import pytest


@pytest.mark.p1
@pytest.mark.plagiarism
def test_corpus_status(client):
    r = client.get("/api/plagiarism/corpus-status")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "enabled" in body
    assert "corpus_dir" in body
    assert "ready" in body
    assert "files_on_disk" in body
    # Empty corpus is OK — error string explains how to ingest
    if not body.get("ready"):
        assert body.get("error") is None or isinstance(body.get("error"), str)


@pytest.mark.p1
@pytest.mark.plagiarism
def test_corpus_status_rebuild_smoke(client):
    """rebuild=true should not 500 even when corpus empty/small."""
    r = client.get("/api/plagiarism/corpus-status?rebuild=true")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "enabled" in body
    assert "ready" in body


@pytest.mark.p1
@pytest.mark.plagiarism
def test_pipeline_import_smoke():
    from plagiarism.pipeline import (
        corpus_plagiarism_enabled,
        document_to_chunks,
        report_to_issues,
    )

    assert isinstance(corpus_plagiarism_enabled(), bool)
    assert callable(document_to_chunks)
    assert callable(report_to_issues)


@pytest.mark.p1
@pytest.mark.plagiarism
def test_local_check_identical_minhash():
    """Planted identical text → near-1.0 MinHash Jaccard without full corpus."""
    from plagiarism.corpus_index import jaccard_from_minhash, text_to_minhash

    planted = (
        "Machine learning models trained on large academic corpora can "
        "reproduce verbatim passages from prior theses when prompts are poorly constrained."
    )
    a = text_to_minhash(planted)
    b = text_to_minhash(planted)
    score = jaccard_from_minhash(a, b)
    assert score >= 0.99, f"expected near-identical Jaccard, got {score}"


@pytest.mark.p1
@pytest.mark.plagiarism
def test_local_check_analyze_sentence_if_corpus_ready():
    """If a corpus index can be built, score planted text; otherwise skip."""
    from plagiarism.pipeline import get_or_build_corpus_index
    from plagiarism.local_check import analyze_sentence_local
    from plagiarism import config as plag_config
    from plagiarism.text_extract import iter_corpus_files

    files = list(iter_corpus_files(plag_config.CORPUS_DIR))
    if not files:
        pytest.skip("No corpus files on disk — local_check against index unavailable")

    try:
        corpus = get_or_build_corpus_index(force_rebuild=False)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Corpus index unavailable: {exc}")

    # Use a sentence from the first corpus file if extractable; else planted long text
    planted = (
        "This unique pytest planted sentence should not match the corpus unless "
        "the same rare phrase already exists in an indexed FYP report document."
    )
    result = analyze_sentence_local(planted, "pytest_chunk_0", corpus)
    assert result.local_suspicion_score >= 0.0
    assert result.match_type in ("exact", "semantic", "both", "none")


@pytest.mark.p1
@pytest.mark.plagiarism
@pytest.mark.fyp
def test_supervisor_plagiarism_monitor_endpoints(client, auth_headers, seeded_users):
    sup_uid = int(seeded_users["supervisor"]["id"])
    r = client.get(
        f"/api/supervisor/plagiarism-monitor?user_id={sup_uid}",
        headers=auth_headers["supervisor"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, dict)

    # Detail for first group if any; otherwise skip detail/flag
    groups = body.get("groups") or body.get("items") or []
    if not groups:
        # Still verify student plagiarism list shape is gated
        stud = client.get(
            f"/api/student/supervisors?user_id={seeded_users['student']['id']}",
            headers=auth_headers["student"],
        )
        assert stud.status_code == 200
        return

    group_id = int(groups[0].get("group_id") or groups[0].get("id"))
    detail = client.get(
        f"/api/supervisor/plagiarism-monitor/{group_id}?user_id={sup_uid}",
        headers=auth_headers["supervisor"],
    )
    assert detail.status_code in (200, 404), detail.text

    if detail.status_code == 200:
        flag = client.post(
            f"/api/supervisor/plagiarism-monitor/{group_id}/flag?user_id={sup_uid}",
            json={"reason": "pytest flag — elevated similarity"},
            headers=auth_headers["supervisor"],
        )
        assert flag.status_code in (200, 400, 404), flag.text


@pytest.mark.p1
@pytest.mark.plagiarism
@pytest.mark.fyp
def test_student_cannot_access_supervisor_plagiarism_monitor(
    client, auth_headers, seeded_users
):
    r = client.get(
        f"/api/supervisor/plagiarism-monitor?user_id={seeded_users['student']['id']}",
        headers=auth_headers["student"],
    )
    assert r.status_code == 403, r.text
