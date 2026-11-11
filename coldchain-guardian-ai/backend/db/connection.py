"""
SQLAlchemy engine and session factory.
Reads DATABASE_URL from environment / .env file.
"""

from __future__ import annotations

import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

_DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://user:password@localhost:5432/coldchain",
)

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            _DATABASE_URL,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            echo=False,
        )
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal


@contextmanager
def db_session() -> Session:
    Session = get_session_factory()
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def enable_pgvector(session: Session) -> None:
    """Create the pgvector extension if it doesn't exist."""
    session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    session.commit()


def create_tables() -> None:
    """Create all tables (safe to run multiple times)."""
    from backend.models.document import Base
    Base.metadata.create_all(get_engine())


def create_hnsw_index() -> None:
    """Create HNSW index on embedding column for fast cosine similarity search."""
    with db_session() as session:
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS document_chunks_embedding_hnsw
            ON document_chunks
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """))
