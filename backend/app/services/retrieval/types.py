"""
Shared dataclasses for the hybrid retrieval pipeline.

RawResult: one hit from a single retrieval method (vector or keyword),
before merging. Candidate: one chunk after merging, holding whichever
scores it has (a chunk found by only one method has None for the other).
"""
import uuid
from dataclasses import dataclass


@dataclass
class RawResult:
    chunk_id: uuid.UUID
    source: str  # "vector" | "keyword"
    score: float
    page_number: int
    content: str
    section: str | None


@dataclass
class Candidate:
    chunk_id: uuid.UUID
    page_number: int
    content: str
    section: str | None
    vector_score: float | None = None
    keyword_score: float | None = None
    hybrid_score: float = 0.0
