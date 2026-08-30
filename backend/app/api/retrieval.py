"""
Retrieval API — Phase 3.

POST /api/retrieval/search: given a document_id and a natural-language
query, runs vector search + keyword search over that document's chunks
and returns a hybrid-ranked top-K. No LLM, no generated answer — this
endpoint proves retrieval quality, nothing more (see Phase 3 spec).
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import repository
from app.db.session import get_db
from app.models.document import DocumentStatus
from app.schemas.retrieval import RetrievalSearchRequest, RetrievalSearchResponse, RetrievedChunk
from app.services.embeddings.factory import get_embedding_provider
from app.services.embeddings.openai_provider import EmbeddingProviderError
from app.services.retrieval.hybrid import hybrid_search
from app.services.retrieval.keyword_search import keyword_search
from app.services.retrieval.vector_search import semantic_search

router = APIRouter(prefix="/retrieval", tags=["retrieval"])
logger = logging.getLogger("sentinews.retrieval")
settings = get_settings()


@router.post("/search", response_model=RetrievalSearchResponse)
def search(request: RetrievalSearchRequest, db: Session = Depends(get_db)) -> RetrievalSearchResponse:
    document = repository.get_document(db, request.document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    if document.status != DocumentStatus.PROCESSED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document is not ready for search (status: {document.status.value}).",
        )

    try:
        provider = get_embedding_provider(settings)
        query_embedding = provider.embed_texts([request.query])[0]
    except EmbeddingProviderError as exc:
        logger.error("Embedding the query failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not embed the search query: {exc}",
        ) from exc

    vector_results = semantic_search(db, request.document_id, query_embedding, top_k=settings.TOP_K)
    keyword_results = keyword_search(db, request.document_id, request.query, top_k=settings.TOP_K)

    ranked = hybrid_search(
        vector_results,
        keyword_results,
        vector_weight=settings.VECTOR_WEIGHT,
        keyword_weight=settings.KEYWORD_WEIGHT,
        k=settings.TOP_K,
    )

    return RetrievalSearchResponse(
        query=request.query,
        document_id=request.document_id,
        vector_weight=settings.VECTOR_WEIGHT,
        keyword_weight=settings.KEYWORD_WEIGHT,
        results=[
            RetrievedChunk(
                chunk_id=c.chunk_id,
                page_number=c.page_number,
                section=c.section,
                content=c.content,
                vector_score=c.vector_score or 0.0,
                keyword_score=c.keyword_score or 0.0,
                hybrid_score=c.hybrid_score,
            )
            for c in ranked
        ],
    )
