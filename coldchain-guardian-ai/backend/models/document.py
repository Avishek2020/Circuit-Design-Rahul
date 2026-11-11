"""
SQLAlchemy model for the document_chunks table (pgvector-backed).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Column, DateTime, Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase

try:
    from pgvector.sqlalchemy import Vector
    _VECTOR_AVAILABLE = True
except ImportError:
    _VECTOR_AVAILABLE = False


EMBEDDING_DIM = 1536


class Base(DeclarativeBase):
    pass


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_file   = Column(String(255),  nullable=False, index=True)
    sop_number    = Column(String(20),   nullable=False, index=True)
    sop_title     = Column(String(512))
    section_title = Column(String(512))
    chunk_index   = Column(Integer,      nullable=False)
    sub_index     = Column(Integer,      nullable=False, default=0)
    page_start    = Column(Integer)
    text          = Column(Text,         nullable=False)
    word_count    = Column(Integer)
    embedding     = Column(
        Vector(EMBEDDING_DIM) if _VECTOR_AVAILABLE else Text,
        nullable=True,
    )
    created_at    = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentChunk {self.sop_number} "
            f"§{self.section_title!r} chunk={self.chunk_index}>"
        )
