"""
One-time database setup script.

Creates the `coldchain` database, enables the pgvector extension,
and creates all application tables.

Requirements:
  - PostgreSQL 16+ running locally
  - psycopg2-binary installed
  - DATABASE_URL in .env or environment

Usage:
  python scripts/setup_db.py

For a fresh PostgreSQL install you may need to create the database first:
  psql -U postgres -c "CREATE DATABASE coldchain;"
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from backend.db.connection import (
    create_hnsw_index,
    create_tables,
    db_session,
    enable_pgvector,
    get_engine,
)


def main() -> None:
    print("ColdChain Guardian AI – Database Setup")
    print("=" * 45)

    engine = get_engine()
    print(f"  Connecting to: {engine.url!r}")

    try:
        with db_session() as session:
            enable_pgvector(session)
            print("  [ok] pgvector extension enabled")
    except Exception as exc:
        print(f"  [error] Could not enable pgvector: {exc}")
        print("  Make sure pgvector is installed: https://github.com/pgvector/pgvector")
        sys.exit(1)

    create_tables()
    print("  [ok] Tables created (or already exist)")

    # Verify
    with db_session() as session:
        result = session.execute(
            text("SELECT COUNT(*) FROM document_chunks")
        ).scalar()
        print(f"  [ok] document_chunks table accessible — {result} rows")

    print("\nDatabase ready. Run the ingestion pipeline:")
    print("  python -m backend.ingestion.pipeline")


if __name__ == "__main__":
    main()
