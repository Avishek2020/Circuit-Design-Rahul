"""
Section-aware text chunker for SOP documents.

Strategy:
  1. Detect numbered section / subsection headers via regex.
  2. Treat each section as a logical unit; split oversized sections at
     paragraph boundaries with a 50-word sliding overlap.
  3. Attach source metadata to every chunk.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Optional

from backend.ingestion.pdf_extractor import ExtractedDocument


# ── config ────────────────────────────────────────────────────────────────────

MAX_WORDS     = 400   # hard cap per chunk
OVERLAP_WORDS = 50    # overlap between consecutive sub-chunks
MIN_WORDS     = 30    # merge chunks smaller than this into the previous one

# Matches genuine section and subsection headers.
#
# Top-level:   "1. Purpose"                      → "N. Title"
# Subsections: "5.1 Approved Sensor Systems"     → "N.M Title" (no trailing period)
#
# The `\s*$` end-of-line anchor rejects long numbered list items
# ("1. Verify refrigeration unit has pre-cooled to within…")
# because those exceed 60 characters after the number prefix.
#
# Pattern breakdown:
#   (\d+(?:\.\d+)*)   – section number, e.g. "1", "5.1", "6.2"
#   (?:\.)?           – optional trailing period (top-level sections only)
#   [ \t]+            – one or more spaces/tabs
#   ([A-Z][^\n\r]{3,60}) – title: capital letter + 3-60 more non-newline chars
#   \s*$              – nothing else on this line
_SECTION_RE = re.compile(
    r"^(\d+(?:\.\d+)*)(?:\.)?[ \t]+([A-Z][^\n\r]{3,60})\s*$",
    re.MULTILINE,
)


# ── data class ────────────────────────────────────────────────────────────────

@dataclass
class TextChunk:
    chunk_id:      str
    source_file:   str
    sop_number:    str
    sop_title:     str
    section_title: str
    chunk_index:   int          # global 0-based index within the document
    sub_index:     int          # 0 = first sub-chunk of this section
    page_start:    int          # 1-based page where this chunk begins
    text:          str
    word_count:    int

    # Convenience: full label used as context header in prompts
    @property
    def label(self) -> str:
        return f"{self.sop_number} § {self.section_title}"


# ── helpers ───────────────────────────────────────────────────────────────────

def _word_count(text: str) -> int:
    return len(text.split())


def _split_paragraphs(text: str, max_words: int, overlap: int) -> list[str]:
    """Split *text* into chunks of at most *max_words*, preferring paragraph
    boundaries, with *overlap* words of trailing context carried forward."""
    paragraphs = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]
    chunks: list[str] = []
    current_parts: list[str] = []
    current_words = 0

    for para in paragraphs:
        pw = _word_count(para)
        if current_words + pw > max_words and current_parts:
            chunks.append("\n\n".join(current_parts))
            # carry last *overlap* words forward
            tail = " ".join(" ".join(current_parts).split()[-overlap:])
            current_parts = [tail] if tail else []
            current_words = _word_count(tail)
        current_parts.append(para)
        current_words += pw

    if current_parts:
        chunks.append("\n\n".join(current_parts))
    return chunks or [text]


# ── public API ────────────────────────────────────────────────────────────────

def chunk_document(doc: ExtractedDocument) -> list[TextChunk]:
    """Return a flat list of TextChunk objects for one extracted document."""
    text   = doc.full_text
    matches = list(_SECTION_RE.finditer(text))

    # Filter out numbered list items that happen to be short:
    # real section titles never end with a period.
    matches = [m for m in matches if not m.group(2).rstrip().endswith(".")]

    if not matches:
        # No headers found — treat whole document as one chunk
        return [TextChunk(
            chunk_id      = str(uuid.uuid4()),
            source_file   = doc.file_path.name,
            sop_number    = doc.sop_number,
            sop_title     = doc.sop_title,
            section_title = "Full Document",
            chunk_index   = 0,
            sub_index     = 0,
            page_start    = 1,
            text          = text.strip(),
            word_count    = _word_count(text),
        )]

    chunks: list[TextChunk] = []
    global_idx = 0

    for i, match in enumerate(matches):
        sec_num   = match.group(1)
        sec_head  = match.group(2).strip()
        # Strip trailing header noise (page number artifacts from PDF footer)
        sec_head  = re.sub(r"\s*\d+\s*$", "", sec_head).strip()
        # Top-level sections ("1") get "1. Title"; subsections ("5.1") get "5.1 Title"
        sep       = ". " if "." not in sec_num else " "
        sec_title = f"{sec_num}{sep}{sec_head}"

        start  = match.start()
        end    = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body   = text[start:end].strip()
        page_s = doc.page_at_offset(start)

        sub_texts = (
            _split_paragraphs(body, MAX_WORDS, OVERLAP_WORDS)
            if _word_count(body) > MAX_WORDS
            else [body]
        )

        for sub_i, sub_text in enumerate(sub_texts):
            chunks.append(TextChunk(
                chunk_id      = str(uuid.uuid4()),
                source_file   = doc.file_path.name,
                sop_number    = doc.sop_number,
                sop_title     = doc.sop_title,
                section_title = sec_title,
                chunk_index   = global_idx,
                sub_index     = sub_i,
                page_start    = page_s,
                text          = sub_text,
                word_count    = _word_count(sub_text),
            ))
            global_idx += 1

    # Merge sub-threshold chunks into their predecessor
    merged: list[TextChunk] = []
    for chunk in chunks:
        if merged and chunk.word_count < MIN_WORDS:
            prev = merged[-1]
            merged[-1] = TextChunk(
                chunk_id      = prev.chunk_id,
                source_file   = prev.source_file,
                sop_number    = prev.sop_number,
                sop_title     = prev.sop_title,
                section_title = prev.section_title,
                chunk_index   = prev.chunk_index,
                sub_index     = prev.sub_index,
                page_start    = prev.page_start,
                text          = prev.text + "\n\n" + chunk.text,
                word_count    = prev.word_count + chunk.word_count,
            )
        else:
            merged.append(chunk)

    # Re-sequence chunk_index after merging
    for i, c in enumerate(merged):
        c.chunk_index = i

    return merged


def chunk_documents(docs: list[ExtractedDocument]) -> list[TextChunk]:
    all_chunks: list[TextChunk] = []
    for doc in docs:
        all_chunks.extend(chunk_document(doc))
    return all_chunks
