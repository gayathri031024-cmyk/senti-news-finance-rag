"""
Chunking.

Splits each page's cleaned text into overlapping chunks, trying to
break on sentence/paragraph boundaries rather than mid-sentence.

Design choice: chunks never span multiple pages. Each chunk belongs
to exactly one page_number. This keeps "page-aware" simple and exact
(the spec's main ask for this phase) at the cost of occasionally
producing a short trailing chunk at a page boundary — an acceptable
trade for correctness over maximal chunk-size uniformity. See README
for the reasoning.
"""
import re
from dataclasses import dataclass

from app.services.ingestion.pdf_parser import PageText

# Split on sentence-ish boundaries: '.', '!', '?' followed by whitespace,
# or a blank line (paragraph break). Keeps the delimiter with the sentence.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9₹$])|\n\s*\n")

# A chunk shorter than this (and not the only content on its page) gets
# merged into the previous chunk instead of standing alone.
_MIN_CHUNK_CHARS = 120


@dataclass
class Chunk:
    chunk_index: int
    page_number: int
    content: str
    section: str | None = None


def _split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(text) if p.strip()]
    return parts if parts else ([text.strip()] if text.strip() else [])


def _guess_section(text: str) -> str | None:
    """
    Lightweight section detection: if the page's first non-empty line
    looks like a heading (short, no terminal punctuation, e.g. "STANDALONE
    Income statement"), use it as the section label. Deliberately simple —
    the spec asks not to overbuild this.
    """
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if 0 < len(first_line) <= 100 and not first_line.endswith((".", ",", ";")):
        return first_line
    return None


def _chunk_page_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """
    Greedily pack sentences into chunks up to chunk_size characters,
    carrying the trailing chunk_overlap characters of context into the
    next chunk. Falls back to a hard character split only for a single
    sentence longer than chunk_size (rare, but tables can produce this).
    """
    sentences = _split_sentences(text)
    if not sentences:
        return []

    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence

        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)
            # Carry the tail of the previous chunk forward as overlap.
            overlap_text = current[-chunk_overlap:] if chunk_overlap > 0 else ""
            current = f"{overlap_text} {sentence}".strip()
        else:
            current = sentence

        # A single sentence longer than chunk_size (e.g. a dense table row)
        # gets hard-split rather than left oversized.
        while len(current) > chunk_size:
            chunks.append(current[:chunk_size])
            current = current[chunk_size - chunk_overlap:]

    if current:
        chunks.append(current)

    # Merge a too-small trailing chunk into the previous one rather than
    # storing a near-empty fragment.
    if len(chunks) > 1 and len(chunks[-1]) < _MIN_CHUNK_CHARS:
        chunks[-2] = f"{chunks[-2]} {chunks[-1]}".strip()
        chunks.pop()

    return chunks


def chunk_pages(pages: list[PageText], chunk_size: int, chunk_overlap: int) -> list[Chunk]:
    """
    Chunk every page's text. Empty pages produce no chunks. Chunk
    indices are assigned sequentially across the whole document so
    they reflect reading order.
    """
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    all_chunks: list[Chunk] = []
    index = 0
    for page in pages:
        if not page.text.strip():
            continue
        section = _guess_section(page.text)
        for piece in _chunk_page_text(page.text, chunk_size, chunk_overlap):
            all_chunks.append(
                Chunk(chunk_index=index, page_number=page.page_number, content=piece, section=section)
            )
            index += 1
    return all_chunks
