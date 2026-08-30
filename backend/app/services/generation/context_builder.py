"""
Context builder — Phase 4.

Formats the chunks already ranked by Phase 3's hybrid_search() into a
single text block the LLM reads as its source of truth. Deliberately a
pure function over plain data (no DB, no I/O) so it's independently
unit-testable, same as hybrid.py's stages.

Each chunk is labeled with its page number so the model can naturally
refer to "page N" in its answer — but the API's citation list (see
schemas/query.py) is built directly from the retrieved Candidate
objects, never parsed out of the model's text. That's what guarantees
a citation can never be fabricated: it either came from an actually
retrieved chunk, or it doesn't appear at all.
"""
from app.services.retrieval.types import Candidate

_CHUNK_SEPARATOR = "\n\n---\n\n"


def build_context(candidates: list[Candidate]) -> str:
    blocks = []
    for candidate in candidates:
        section_label = f" | Section: {candidate.section}" if candidate.section else ""
        blocks.append(
            f"[Page {candidate.page_number}{section_label}]\n{candidate.content}"
        )
    return _CHUNK_SEPARATOR.join(blocks)
