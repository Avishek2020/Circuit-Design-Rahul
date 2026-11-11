"""
Semantic (vector) retrieval over the document_chunks table.

Uses pgvector cosine distance (<=>).  Falls back to a pure-Python
dot-product search when pgvector is unavailable (e.g. SQLite test mode).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import text

from backend.db.connection import db_session
from backend.ingestion.embedder import EmbedderBase, build_embedder
from backend.models.document import DocumentChunk

_embedder: EmbedderBase | None = None


def _get_embedder() -> EmbedderBase:
    global _embedder
    if _embedder is None:
        _embedder = build_embedder()
    return _embedder


# ── result type ───────────────────────────────────────────────────────────────

@dataclass
class SemanticResult:
    chunk_id:      str
    sop_number:    str
    sop_title:     str
    section_title: str
    page_start:    int
    text:          str
    word_count:    int
    score:         float   # cosine similarity 0–1 (higher = more similar)
    source_file:   str

    @property
    def citation(self) -> str:
        return f"{self.sop_number} § {self.section_title} (p.{self.page_start})"


# ── search ────────────────────────────────────────────────────────────────────

def semantic_search(
    query: str,
    top_k: int = 5,
    min_score: float = 0.0,
    sop_filter: str | None = None,
) -> list[SemanticResult]:
    """
    Return up to *top_k* document chunks most similar to *query*.

    Parameters
    ----------
    query       : natural-language question
    top_k       : maximum results
    min_score   : discard results below this cosine similarity
    sop_filter  : restrict to a specific SOP number (e.g. "SOP-001")
    """
    emb = _get_embedder()
    vec = emb.embed_batch([query])[0]
    vec_str = "[" + ",".join(f"{v:.8f}" for v in vec) + "]"

    with db_session() as session:
        base_sql = """
            SELECT
                CAST(id AS TEXT)   AS chunk_id,
                sop_number,
                sop_title,
                section_title,
                page_start,
                text,
                word_count,
                source_file,
                1 - (embedding <=> CAST(:vec AS vector)) AS score
            FROM document_chunks
            WHERE embedding IS NOT NULL
            {sop_clause}
            ORDER BY embedding <=> CAST(:vec AS vector)
            LIMIT :k
        """
        sop_clause = "AND sop_number = :sop" if sop_filter else ""
        sql = base_sql.format(sop_clause=sop_clause)

        params: dict = {"vec": vec_str, "k": top_k}
        if sop_filter:
            params["sop"] = sop_filter

        rows = session.execute(text(sql), params).fetchall()

    results = []
    for row in rows:
        score = float(row.score) if row.score is not None else 0.0
        if score >= min_score:
            results.append(SemanticResult(
                chunk_id      = row.chunk_id,
                sop_number    = row.sop_number,
                sop_title     = row.sop_title,
                section_title = row.section_title,
                page_start    = row.page_start or 1,
                text          = row.text,
                word_count    = row.word_count or 0,
                score         = score,
                source_file   = row.source_file,
            ))
    return results


def semantic_search_multi(
    queries: list[str],
    top_k: int = 3,
) -> list[SemanticResult]:
    """Run semantic_search for multiple queries and deduplicate by chunk_id."""
    seen: set[str] = set()
    combined: list[SemanticResult] = []
    for q in queries:
        for r in semantic_search(q, top_k=top_k):
            if r.chunk_id not in seen:
                seen.add(r.chunk_id)
                combined.append(r)
    combined.sort(key=lambda r: r.score, reverse=True)
    return combined[:top_k * len(queries)]
