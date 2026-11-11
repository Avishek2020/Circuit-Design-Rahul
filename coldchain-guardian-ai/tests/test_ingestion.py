"""
Unit tests for Day 2 ingestion components.
Run: pytest tests/test_ingestion.py -v
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.ingestion.chunker import MIN_WORDS, chunk_document
from backend.ingestion.embedder import MockEmbedder
from backend.ingestion.pdf_extractor import extract_pdf

SOP_DIR = ROOT / "data" / "raw" / "sop_documents"
SOP_001 = SOP_DIR / "SOP-001_Temperature_Monitoring_Control.pdf"


# ── extraction ────────────────────────────────────────────────────────────────

def test_extract_pages():
    doc = extract_pdf(SOP_001)
    assert len(doc.pages) == 4
    assert doc.sop_number == "SOP-001"


def test_full_text_non_empty():
    doc = extract_pdf(SOP_001)
    assert len(doc.full_text) > 500


def test_page_offset_mapping():
    doc = extract_pdf(SOP_001)
    # First char should map to page 1
    assert doc.page_at_offset(0) == 1
    # Last char should map to page 4
    assert doc.page_at_offset(len(doc.full_text) - 1) == 4


def test_key_content_present():
    doc = extract_pdf(SOP_001)
    for keyword in ["HACCP", "Temperature Excursion", "Critical Limit", "Calibration"]:
        assert keyword in doc.full_text, f"Missing: {keyword}"


# ── chunking ──────────────────────────────────────────────────────────────────

def test_chunk_count():
    doc    = extract_pdf(SOP_001)
    chunks = chunk_document(doc)
    # We expect ~12 chunks from the 4-page SOP
    assert 8 <= len(chunks) <= 20


def test_chunk_word_counts():
    doc    = extract_pdf(SOP_001)
    chunks = chunk_document(doc)
    for c in chunks:
        assert c.word_count >= MIN_WORDS, (
            f"Chunk {c.chunk_index} '{c.section_title}' has only {c.word_count} words"
        )
        assert c.word_count <= 500, (
            f"Chunk {c.chunk_index} oversized at {c.word_count} words"
        )


def test_chunk_indices_sequential():
    doc    = extract_pdf(SOP_001)
    chunks = chunk_document(doc)
    for i, c in enumerate(chunks):
        assert c.chunk_index == i


def test_chunk_page_numbers():
    doc    = extract_pdf(SOP_001)
    chunks = chunk_document(doc)
    for c in chunks:
        assert 1 <= c.page_start <= len(doc.pages)


def test_no_empty_chunk_text():
    doc    = extract_pdf(SOP_001)
    chunks = chunk_document(doc)
    for c in chunks:
        assert c.text.strip(), f"Chunk {c.chunk_index} has empty text"


def test_section_titles_no_trailing_period():
    """Verify that no section title is a list item (which would end with '.')."""
    doc    = extract_pdf(SOP_001)
    chunks = chunk_document(doc)
    for c in chunks:
        assert not c.section_title.rstrip().endswith("."), (
            f"List item detected as section: {c.section_title!r}"
        )


def test_known_sections_present():
    doc    = extract_pdf(SOP_001)
    chunks = chunk_document(doc)
    titles = {c.section_title for c in chunks}
    for expected in [
        "1. Purpose", "3. Definitions",
        "7. Temperature Excursion Response Decision Tree",
        "9. Revision History",
    ]:
        assert expected in titles, f"Section not found: {expected!r}"


# ── embedding ─────────────────────────────────────────────────────────────────

def test_mock_embedder_shape():
    doc    = extract_pdf(SOP_001)
    chunks = chunk_document(doc)
    emb    = MockEmbedder()
    vecs   = emb.embed(chunks)
    assert len(vecs) == len(chunks)
    assert all(len(v) == 1536 for v in vecs)


def test_mock_embedder_deterministic():
    doc    = extract_pdf(SOP_001)
    chunks = chunk_document(doc)
    emb    = MockEmbedder()
    v1     = emb.embed(chunks)
    v2     = emb.embed(chunks)
    assert v1 == v2


def test_mock_embedder_unit_vectors():
    import math
    emb  = MockEmbedder()
    vecs = emb.embed_batch(["hello world"])
    norm = math.sqrt(sum(x * x for x in vecs[0]))
    assert abs(norm - 1.0) < 1e-6, f"Vector not unit-normalised (norm={norm:.6f})"
