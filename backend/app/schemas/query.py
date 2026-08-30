import uuid

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    document_id: uuid.UUID
    question: str = Field(min_length=1, max_length=2000)


class SourceCitation(BaseModel):
    """Built directly from a chunk that was actually retrieved by Phase
    3's hybrid_search() — never from anything the LLM says, so a
    citation can never point at a page/chunk that wasn't really used."""

    document_id: uuid.UUID
    document_name: str
    page_number: int
    chunk_id: uuid.UUID
    relevance_score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceCitation]
