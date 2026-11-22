"""Fast tests for the local grammar service (no model is loaded here)."""
from __future__ import annotations

import asyncio

import pytest

from functions import grammar_local as g


# ── spell-checker skip rules ────────────────────────────────────────────────

@pytest.mark.parametrize("word", [
    "RFID", "CNIC",            # ALL-CAPS acronyms
    "camelCase", "JavaScript", "iPhone",  # identifiers / CamelCase
    "user_id",                 # underscore
    "MP3", "v2", "1a",         # digits
    "of", "is",                # very short
    "Lahore",                  # capitalised mid-sentence (proper noun)
])
def test_skip_rules_skip(word):
    assert g.should_skip_word(word, is_sentence_start=False)


def test_skip_rules_whitelist_and_normal_words():
    assert g.should_skip_word("kinect", False, whitelist={"kinect"})
    assert not g.should_skip_word("sysem", False)
    assert not g.should_skip_word("Sysem", True)   # sentence start is still checked


def test_spell_ignores_urls_emails_and_flags_typos():
    issues = g.check(
        ["Visit www.exmaple.com or mail admin@exmaple.org for the sysem details."],
        use_model=False,
    )
    words = [i["original"] for i in issues]
    assert "sysem" in words
    assert not any("exmaple" in w for w in words)
    iss = next(i for i in issues if i["original"] == "sysem")
    assert iss["suggestion"] == "system"
    assert iss["source"] == "spell" and iss["grammar_type"] == "spelling"


# ── edit extraction ─────────────────────────────────────────────────────────

def test_edits_ignore_whitespace_quotes_and_ligatures():
    assert g.extract_edits("The system open my window .", "The system open my window.") == []
    assert g.extract_edits("The user’s profile is shown here.", "The user's profile is shown here.") == []
    assert g.extract_edits("The ﬁle is saved on the server.", "The file is saved on the server.") == []


def test_edits_drop_heavy_rewrite_and_empty():
    src = "The system open my profile window when I click it."
    assert g.extract_edits(src, "") is None
    assert g.extract_edits(src, "Clicking opens it.") is None          # length ratio
    assert g.extract_edits(src, "A user may want to see their own account page now.") is None  # similarity


def test_edits_word_level():
    edits = g.extract_edits("The system open my profile window.", "The system opens my profile window.")
    assert edits == [{"i1": 2, "i2": 3, "j1": 2, "j2": 3}]


# ── merge + classification ──────────────────────────────────────────────────

def _merge(src, model_out):
    spell = g.get_spell()
    toks = g.tokenize(src)
    hits = g._spell_hits_for(src, toks, spell)
    return g.merge_sentence(src, toks, hits, model_out, spell)


def test_merge_both_prefers_model_word():
    res = _merge("The sysem will display the post.", "The system will display the post.")
    assert len(res) == 1
    r = res[0]
    assert (r["original"], r["suggestion"], r["source"], r["grammar_type"]) == \
        ("sysem", "system", "both", "spelling")


def test_merge_model_nonword_falls_back_to_spell_candidate():
    res = _merge("The sysem will display the post.", "The sysxem will display the post.")
    assert len(res) == 1
    assert res[0]["suggestion"] == "system" and res[0]["source"] == "both"


def test_merge_keeps_spell_and_model_issues_at_different_places():
    res = _merge("The sysem open the profile page for users.",
                 "The sysem opens the profile page for users.")
    by_src = {r["source"]: r for r in res}
    assert by_src["spell"]["original"] == "sysem"
    assert by_src["model"]["original"] == "open" and by_src["model"]["suggestion"] == "opens"
    assert by_src["model"]["grammar_type"] == "grammar"


def test_merge_punctuation_and_insertion():
    res = _merge("After login the user sees the main dashboard.",
                 "After login, the user sees the main dashboard.")
    assert len(res) == 1
    r = res[0]
    assert r["grammar_type"] == "punctuation"
    assert r["original"] == "login" and r["suggestion"] == "login,"


# ── sentence handling + fallback ────────────────────────────────────────────

def test_short_sentences_headings_and_code_are_skipped():
    assert not g.is_checkable("Use Case Diagram")
    assert not g.is_checkable("The sysem works.")                    # < 4 words
    assert not g.is_checkable("if (x == 1) { return foo(); } else bar;")
    assert g.is_checkable("post Condition User Viewed numbers.")


def test_offsets_point_into_original_paragraph():
    para = "First sentence is fine here.  The  sysem will display the post."
    issues = g.check([para], use_model=False)
    assert len(issues) == 1
    i = issues[0]
    assert para[i["char_start"]:i["char_end"]] == i["original"] == "sysem"
    assert i["sentence_index"] == 1


def test_span_grows_until_unique_in_paragraph():
    para = "The sysem shows a list. Then the sysem saves the new list."
    issues = g.check([para], use_model=False)
    assert len(issues) == 2
    for i in issues:
        assert para.count(i["original"]) == 1
        assert para[i["char_start"]:i["char_end"]] == i["original"]
        assert "system" in i["suggestion"]


def test_model_crash_falls_back_to_spell(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("model exploded")
    monkeypatch.setattr(g._MODEL, "correct", boom)
    issues = g.check(["The sysem will display the post."], use_model=True)
    assert [i["source"] for i in issues] == ["spell"]


def test_check_grammar_keeps_schema_and_multiple_issues(monkeypatch):
    from functions.grammar import check_grammar
    from models import Batch, ParagraphBlock
    from pipeline.aggregator import aggregate
    from models import DocumentModel

    monkeypatch.setenv("GRAMMAR_USE_MODEL", "false")
    p = ParagraphBlock(paragraph_id="p3", page_number=2,
                       text="The sysem shows the dashbord to every user.")
    h = ParagraphBlock(paragraph_id="p4", page_number=2, style="Heading 1",
                       text="Sysem Archtecture Overview Of The Whole Thing")
    raw = asyncio.run(check_grammar(None, Batch(batch_index=0, page_start=2, page_end=2,
                                                paragraphs=[p, h])))
    # heading paragraph is spell-checked too (every capitalised word)
    assert {(r["paragraph_id"], r["original"]) for r in raw} == {
        ("p3", "sysem"), ("p3", "dashbord"), ("p4", "Sysem"), ("p4", "Archtecture")}
    for r in raw:
        assert r["function"] == "grammar" and r["type"] == "grammar"
        assert r["page"] == 2
        assert r["suggestion"] and r["reason"]
    report = aggregate(raw, DocumentModel(paragraphs=[p, h]), total_batches=1)
    grammar = [i for i in report.issues if i.function == "grammar"]
    assert len(grammar) == 4 and report.stats.grammar_issues == 4


# ── headings / short lines: spell-check only ────────────────────────────────

def test_heading_and_label_lines_are_spell_checked():
    issues = g.check(["Abstractttttttt:", "1. Introductionn", "Muhammad Ali Jinnah"], use_model=False)
    found = {(i["unit_index"], i["original"], i["suggestion"]) for i in issues}
    assert found == {(0, "Abstractttttttt", "Abstract"), (1, "Introductionn", "Introduction")}


def test_short_lines_never_reach_the_model(monkeypatch):
    seen = []

    def fake_correct(sentences, batch_size=8, progress=None):
        seen.extend(sentences)
        return list(sentences)

    monkeypatch.setattr(g._MODEL, "correct", fake_correct)
    g.check(["Abstractttttttt:", "The system shows the full list of users."], use_model=True)
    g.check(["The system shows the full list of users."], use_model=True, spell_only_units=[0])
    assert seen == ["The system shows the full list of users."]


def test_repeated_letter_typo_gets_a_candidate():
    spell = g.get_spell()
    assert spell.candidate("abstractttttttt") == "abstract"
    assert spell.candidate("Sooooftware") == "Software"
