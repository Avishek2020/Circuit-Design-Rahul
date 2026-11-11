"""
Document ingestion pipeline — Day 2.

Usage:
  # dry run (no DB needed):
  python -m backend.ingestion.pipeline --dry-run

  # full run (requires PostgreSQL + pgvector):
  python -m backend.ingestion.pipeline

  # re-ingest from scratch:
  python -m backend.ingestion.pipeline --reset

  # verbose dry run (prints chunk text snippets):
  python -m backend.ingestion.pipeline --dry-run --verbose
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# ── path setup so this can be run as `python -m backend.ingestion.pipeline`
#    from the project root ──────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]  # coldchain-guardian-ai/
sys.path.insert(0, str(ROOT))

from backend.ingestion.chunker    import TextChunk, chunk_documents
from backend.ingestion.embedder   import build_embedder
from backend.ingestion.pdf_extractor import extract_directory

SOP_DIR = ROOT / "data" / "raw" / "sop_documents"


# ── helpers ───────────────────────────────────────────────────────────────────

def _print_chunk_table(chunks: list[TextChunk], verbose: bool) -> None:
    print(f"\n{'IDX':>4}  {'SOP':<8} {'SECTION':<45} {'WDS':>4}  {'PG':>2}")
    print("─" * 72)
    for c in chunks:
        sec = c.section_title[:43] + ".." if len(c.section_title) > 45 else c.section_title
        print(f"  {c.chunk_index:>3}  {c.sop_number:<8} {sec:<45} {c.word_count:>4}  {c.page_start:>2}")
        if verbose:
            snippet = c.text[:160].replace("\n", " ")
            print(f"       ↳ {snippet}…")
    print()


def _store_chunks(chunks: list[TextChunk], vectors: list[list[float]], reset: bool) -> None:
    from backend.db.connection import (
        create_hnsw_index, create_tables, db_session, enable_pgvector,
    )
    from backend.models.document import DocumentChunk

    with db_session() as session:
        enable_pgvector(session)

    create_tables()

    with db_session() as session:
        if reset:
            deleted = session.query(DocumentChunk).delete()
            print(f"  [db] reset: removed {deleted} existing rows")

        rows = []
        for chunk, vec in zip(chunks, vectors):
            rows.append(DocumentChunk(
                source_file   = chunk.source_file,
                sop_number    = chunk.sop_number,
                sop_title     = chunk.sop_title,
                section_title = chunk.section_title,
                chunk_index   = chunk.chunk_index,
                sub_index     = chunk.sub_index,
                page_start    = chunk.page_start,
                text          = chunk.text,
                word_count    = chunk.word_count,
                embedding     = vec,
            ))
        session.bulk_save_objects(rows)

    create_hnsw_index()
    print(f"  [db] inserted {len(rows)} rows + HNSW index ready")


# ── main ──────────────────────────────────────────────────────────────────────

def run(dry_run: bool = False, reset: bool = False,
        verbose: bool = False, force_mock: bool = False) -> None:

    print("\nColdChain Guardian AI – Document Ingestion Pipeline")
    print("=" * 55)

    # 1. Extract
    print(f"\n[1/3] Extracting PDFs from {SOP_DIR.relative_to(ROOT)} …")
    t0 = time.perf_counter()
    docs = extract_directory(SOP_DIR)
    if not docs:
        print("  No PDFs found. Run `python data/generate_sops.py` first.")
        return
    for d in docs:
        total_words = sum(len(p.text.split()) for p in d.pages)
        print(f"  {d.sop_number}  pages={len(d.pages)}  words≈{total_words}  "
              f"file={d.file_path.name}")
    print(f"  Extracted {len(docs)} document(s) in {time.perf_counter()-t0:.2f}s")

    # 2. Chunk
    print("\n[2/3] Chunking …")
    t1 = time.perf_counter()
    chunks = chunk_documents(docs)
    sop_counts: dict[str, int] = {}
    for c in chunks:
        sop_counts[c.sop_number] = sop_counts.get(c.sop_number, 0) + 1
    for sop, n in sorted(sop_counts.items()):
        print(f"  {sop}  →  {n} chunks")
    print(f"  Total {len(chunks)} chunks in {time.perf_counter()-t1:.3f}s")

    if verbose:
        _print_chunk_table(chunks, verbose=True)
    else:
        _print_chunk_table(chunks, verbose=False)

    # 3. Embed
    print("[3/3] Generating embeddings …")
    t2 = time.perf_counter()
    embedder = build_embedder(force_mock=force_mock)
    vectors  = embedder.embed(chunks)
    assert len(vectors) == len(chunks)
    print(f"  {len(vectors)} vectors × {len(vectors[0])} dims "
          f"in {time.perf_counter()-t2:.2f}s")

    # 4. Store (or skip)
    if dry_run:
        print("\n  [dry-run] skipping database write")
    else:
        print("\n[+] Storing in PostgreSQL …")
        _store_chunks(chunks, vectors, reset=reset)

    print("\n" + "=" * 55)
    print(f"Done. {len(chunks)} chunks, {len(docs)} documents.")
    if dry_run:
        print("Re-run without --dry-run to write to PostgreSQL.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest SOP PDFs into the ColdChain Guardian AI vector store."
    )
    parser.add_argument("--dry-run",    action="store_true",
                        help="Extract and embed but skip DB write")
    parser.add_argument("--reset",      action="store_true",
                        help="Delete all existing chunks before inserting")
    parser.add_argument("--verbose",    action="store_true",
                        help="Print chunk text snippets")
    parser.add_argument("--force-mock", action="store_true",
                        help="Use mock embedder even if OPENAI_API_KEY is set")
    args = parser.parse_args()
    run(
        dry_run    = args.dry_run,
        reset      = args.reset,
        verbose    = args.verbose,
        force_mock = args.force_mock,
    )


if __name__ == "__main__":
    main()
