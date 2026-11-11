"""
Shared pytest fixtures and DB availability detection.
Tests marked @pytest.mark.db are skipped when PostgreSQL is unreachable.
"""

import pytest


def _db_available() -> bool:
    try:
        from backend.db.connection import get_engine
        from sqlalchemy import text
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


DB_AVAILABLE = _db_available()

requires_db = pytest.mark.skipif(
    not DB_AVAILABLE,
    reason="PostgreSQL not reachable — skipping DB-dependent test",
)
