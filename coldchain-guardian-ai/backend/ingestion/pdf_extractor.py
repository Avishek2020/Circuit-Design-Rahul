"""
PDF text extraction with per-page metadata and character-offset tracking.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf


# ── data classes ─────────────────────────────────────────────────────────────

@dataclass
class PageBlock:
    page_number: int    # 1-based
    text: str
    char_start: int     # offset in ExtractedDocument.full_text
    char_end: int


@dataclass
class ExtractedDocument:
    file_path: Path
    sop_number: str     # e.g. "SOP-001"
    sop_title: str      # e.g. "Temperature Monitoring and Control Procedures"
    pages: list[PageBlock]
    full_text: str

    def page_at_offset(self, offset: int) -> int:
        """Return 1-based page number that contains the given char offset."""
        for pb in self.pages:
            if pb.char_start <= offset < pb.char_end:
                return pb.page_number
        return self.pages[-1].page_number if self.pages else 1


# ── extraction ────────────────────────────────────────────────────────────────

_MULTI_NEWLINE = re.compile(r"\n{3,}")
_MULTI_SPACE   = re.compile(r"[ \t]{2,}")
_HEADER_NOISE  = re.compile(          # strip running header/footer lines
    r"ColdChain Guardian AI\s*\|.*\n|"
    r"CONFIDENTIAL.*\n|"
    r"© FrostGuard.*\n|"
    r"Page \d+\s*\n",
    re.IGNORECASE,
)


def _clean(text: str) -> str:
    text = _HEADER_NOISE.sub("\n", text)
    text = _MULTI_SPACE.sub(" ", text)
    text = _MULTI_NEWLINE.sub("\n\n", text)
    return text.strip()


def _parse_sop_meta(stem: str) -> tuple[str, str]:
    """
    'SOP-001_Temperature_Monitoring_Control'
    → ('SOP-001', 'Temperature Monitoring and Control')
    """
    parts = stem.split("_", 1)
    sop_number = parts[0]
    sop_title  = parts[1].replace("_", " ") if len(parts) > 1 else stem
    return sop_number, sop_title


def extract_pdf(path: Path) -> ExtractedDocument:
    """Extract all text from *path*, returning an ExtractedDocument."""
    doc = pymupdf.open(str(path))
    pages: list[PageBlock] = []
    text_parts: list[str] = []
    cursor = 0

    for i, page in enumerate(doc):
        raw  = page.get_text()
        text = _clean(raw)
        if text:
            text += "\n"
        char_start = cursor
        char_end   = cursor + len(text)
        pages.append(PageBlock(
            page_number=i + 1,
            text=text,
            char_start=char_start,
            char_end=char_end,
        ))
        text_parts.append(text)
        cursor = char_end

    doc.close()

    full_text           = "".join(text_parts)
    sop_number, sop_title = _parse_sop_meta(path.stem)

    # Prefer the actual title extracted from page 1 text (second non-empty line)
    page1_lines = [l.strip() for l in pages[0].text.splitlines() if l.strip()] if pages else []
    for line in page1_lines:
        if len(line) > 20 and not line.startswith("SOP-"):
            sop_title = line
            break

    return ExtractedDocument(
        file_path=path,
        sop_number=sop_number,
        sop_title=sop_title,
        pages=pages,
        full_text=full_text,
    )


def extract_directory(directory: Path) -> list[ExtractedDocument]:
    """Extract all PDFs found under *directory* (non-recursive)."""
    pdfs = sorted(directory.glob("*.pdf"))
    return [extract_pdf(p) for p in pdfs]
