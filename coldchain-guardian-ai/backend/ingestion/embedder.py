"""
Embedding backends for TextChunk objects.

Production : OpenAIEmbedder  — text-embedding-3-small, 1536 dims
Development: MockEmbedder    — deterministic zero-ish vectors (no API key needed)

Usage:
    embedder = build_embedder()          # auto-picks based on OPENAI_API_KEY
    vectors  = embedder.embed(chunks)    # list[list[float]]
"""

from __future__ import annotations

import hashlib
import math
import os
import time
from abc import ABC, abstractmethod
from typing import Sequence

from backend.ingestion.chunker import TextChunk


EMBEDDING_DIM    = 1536    # OpenAI text-embedding-3-small
OPENAI_MODEL     = "text-embedding-3-small"
BATCH_SIZE       = 100     # OpenAI rate-limit-safe batch
RETRY_SLEEP_SECS = 5


# ── abstract base ─────────────────────────────────────────────────────────────

class EmbedderBase(ABC):
    dim: int = EMBEDDING_DIM

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per text."""

    def embed(self, chunks: Sequence[TextChunk]) -> list[list[float]]:
        """Embed all chunks in batches, returning vectors in the same order."""
        texts   = [c.text for c in chunks]
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start : start + BATCH_SIZE]
            vectors.extend(self.embed_batch(batch))
        return vectors


# ── OpenAI backend ────────────────────────────────────────────────────────────

class OpenAIEmbedder(EmbedderBase):
    def __init__(self, api_key: str | None = None):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError(
                "openai package not installed. Run: pip install openai"
            ) from exc
        self._client = OpenAI(api_key=api_key or os.environ["OPENAI_API_KEY"])

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        for attempt in range(3):
            try:
                resp = self._client.embeddings.create(
                    model=OPENAI_MODEL,
                    input=texts,
                    encoding_format="float",
                )
                return [item.embedding for item in resp.data]
            except Exception as exc:  # noqa: BLE001
                if attempt == 2:
                    raise
                print(f"  [embedder] retry {attempt + 1} after error: {exc}")
                time.sleep(RETRY_SLEEP_SECS * (attempt + 1))
        return []  # unreachable


# ── Mock backend (no API key required) ───────────────────────────────────────

class MockEmbedder(EmbedderBase):
    """
    Produces deterministic pseudo-random unit vectors derived from the
    SHA-256 hash of each text. Good enough for testing the pipeline without
    real similarity; replace with OpenAIEmbedder for production use.
    """

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            digest = hashlib.sha256(text.encode()).digest()
            # Expand digest to EMBEDDING_DIM floats via cyclic XOR
            raw = []
            for i in range(EMBEDDING_DIM):
                byte = digest[i % len(digest)] ^ (i >> 8)
                raw.append((byte / 127.5) - 1.0)
            # L2-normalise
            norm = math.sqrt(sum(x * x for x in raw)) or 1.0
            results.append([x / norm for x in raw])
        return results


# ── factory ───────────────────────────────────────────────────────────────────

def build_embedder(force_mock: bool = False) -> EmbedderBase:
    """Return the best available embedder.

    Uses OpenAIEmbedder when OPENAI_API_KEY is set and *force_mock* is False;
    otherwise falls back to MockEmbedder.
    """
    if not force_mock and os.environ.get("OPENAI_API_KEY"):
        try:
            embedder = OpenAIEmbedder()
            print("  [embedder] using OpenAI text-embedding-3-small")
            return embedder
        except Exception as exc:  # noqa: BLE001
            print(f"  [embedder] OpenAI unavailable ({exc}); falling back to mock")

    print("  [embedder] using MockEmbedder (deterministic pseudo-random vectors)")
    return MockEmbedder()
