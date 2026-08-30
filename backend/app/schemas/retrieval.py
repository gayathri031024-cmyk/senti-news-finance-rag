import uuid

from pydantic import BaseModel, Field


class RetrievalSearchRequest(BaseModel):
    document_id: uuid.UUID
    query: str = Field(min_length=1, max_length=2000)


class RetrievedChunk(BaseModel):
    chunk_id: uuid.UUID
    page_number: int
    section: str | None
    content: str
    vector_score: float
    keyword_score: float
    hybrid_score: float


class RetrievalSearchResponse(BaseModel):
    """Includes the query and weighting configuration alongside the
    results, so a response is self-contained for debugging/demoing
    without needing to cross-reference server config."""
    query: str
    document_id: uuid.UUID
    vector_weight: float
    keyword_weight: float
    results: list[RetrievedChunk]
