"""Unit tests for image relevance surrounding-context extraction (no CLIP)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import Batch, ImageBlock, ParagraphBlock
from functions.image_relevance import surrounding_context_for_image


def _batch(paras, img):
    return Batch(
        batch_index=0,
        page_start=1,
        page_end=1,
        paragraphs=paras,
        images=[img],
    )


def test_before_after_context():
    paras = [
        ParagraphBlock(
            paragraph_id="p0",
            page_number=1,
            heading_context="Introduction",
            style="Heading 1",
            text="Introduction",
        ),
        ParagraphBlock(
            paragraph_id="p1",
            page_number=1,
            heading_context="Introduction",
            style="Normal",
            text="This chapter discusses neural network architectures for vision.",
        ),
        ParagraphBlock(
            paragraph_id="p2",
            page_number=1,
            heading_context="Introduction",
            style="Normal",
            text="",  # image para (empty text)
        ),
        ParagraphBlock(
            paragraph_id="p3",
            page_number=1,
            heading_context="Introduction",
            style="Normal",
            text="Figure 1: Architecture diagram",
        ),
        ParagraphBlock(
            paragraph_id="p4",
            page_number=1,
            heading_context="Introduction",
            style="Normal",
            text="The convolutional layers extract hierarchical features from images.",
        ),
    ]
    img = ImageBlock(
        image_id="img0",
        page_number=1,
        base64="x",
        paragraph_id="p2",
    )
    ctx = surrounding_context_for_image(_batch(paras, img), img)
    assert "neural network" in ctx["before"].lower()
    assert "convolutional" in ctx["after"].lower()
    assert "Figure 1" not in ctx["after"]  # caption skipped
    assert ctx["heading"] == "Introduction"
    print("PASS: surrounding_context_for_image before/after")


def test_missing_empty_image_paragraph_uses_index_split():
    """Real DOCX path: empty image paras are omitted; image still has pN id."""
    paras = [
        ParagraphBlock(
            paragraph_id="p10",
            page_number=1,
            heading_context="Proposed Solution",
            style="Normal",
            text="Voice command recognition accuracy of at least 90 percent.",
        ),
        ParagraphBlock(
            paragraph_id="p20",
            page_number=1,
            heading_context="Proposed Solution",
            style="Normal",
            text="Zero formatting loss on export to Word documents.",
        ),
        ParagraphBlock(
            paragraph_id="p30",
            page_number=1,
            heading_context="Methodology",
            style="Normal",
            text="We evaluated the agile model using a flow diagram approach.",
        ),
    ]
    flowers = ImageBlock(
        image_id="img1",
        page_number=1,
        base64="x",
        paragraph_id="p15",  # missing empty para between p10 and p20
    )
    agile = ImageBlock(
        image_id="img2",
        page_number=1,
        base64="x",
        paragraph_id="p25",  # between p20 and p30
    )
    ctx_f = surrounding_context_for_image(_batch(paras, flowers), flowers)
    ctx_a = surrounding_context_for_image(_batch(paras, agile), agile)
    assert "Voice command" in ctx_f["before"]
    assert "Zero formatting" in ctx_f["after"]
    assert "Zero formatting" in ctx_a["before"]
    assert "agile model" in ctx_a["after"].lower()
    # Critical: different images must not share identical mid-page context
    assert ctx_f["before"] != ctx_a["before"] or ctx_f["after"] != ctx_a["after"]
    print("PASS: missing empty image paragraph uses index split")


if __name__ == "__main__":
    test_before_after_context()
    test_missing_empty_image_paragraph_uses_index_split()
