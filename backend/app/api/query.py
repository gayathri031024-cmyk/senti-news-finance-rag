"""
Query API — Phase 4.

POST /api/query: given a document_id and a natural-language question,
reuses Phase 3's hybrid retrieval untouched (semantic_search +
keyword_search + hybrid_search — no duplicated retrieval logic), builds
a context block from the ranked chunks, sends it to the configured LLM
provider under the grounding rules in services/generation/prompts.py,
and returns the generated answer together with citations built directly
from the retrieved chunks.

If retrieval finds nothing, the LLM is never called: the endpoint
returns a fixed "not found in the document" answer with no sources.
This keeps "say clearly when the answer isn't in the document" a
guarantee of the retrieval step, not something left to the LLM to
remember to do.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import repository
from app.db.session import get_db
from app.models.document import DocumentStatus
from app.schemas.query import QueryRequest, QueryResponse, SourceCitation
from app.services.embeddings.factory import get_embedding_provider
from app.services.embeddings.openai_provider import EmbeddingProviderError
from app.services.generation.context_builder import build_context
from app.services.generation.prompts import SYSTEM_PROMPT, build_user_prompt
from app.services.llm.factory import get_llm_provider
from app.services.llm.openai_provider import LLMProviderError
from app.services.retrieval.hybrid import hybrid_search
from app.services.retrieval.keyword_search import keyword_search
from app.services.retrieval.vector_search import semantic_search

router = APIRouter(tags=["query"])
logger = logging.getLogger("sentinews.query")
settings = get_settings()

NOT_FOUND_ANSWER = (
    "I couldn't find information about this in the uploaded document. "
    "This question may be unrelated to the document's contents, or may "
    "not be covered by it."
)


@router.post("/query", response_model=QueryResponse)
def query(request: QueryRequest, db: Session = Depends(get_db)) -> QueryResponse:
    document = repository.get_document(db, request.document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    if document.status != DocumentStatus.PROCESSED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document is not ready for querying (status: {document.status.value}).",
        )

    try:
        embedding_provider = get_embedding_provider(settings)
        query_embedding = embedding_provider.embed_texts([request.question])[0]
    except EmbeddingProviderError as exc:
        logger.error("Embedding the question failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not embed the question: {exc}",
        ) from exc

    vector_results = semantic_search(db, request.document_id, query_embedding, top_k=settings.TOP_K)
    keyword_results = keyword_search(db, request.document_id, request.question, top_k=settings.TOP_K)

    ranked = hybrid_search(
        vector_results,
        keyword_results,
        vector_weight=settings.VECTOR_WEIGHT,
        keyword_weight=settings.KEYWORD_WEIGHT,
        k=settings.TOP_K,
    )

    if not ranked:
        return QueryResponse(answer=NOT_FOUND_ANSWER, sources=[])

    context = build_context(ranked)
    user_prompt = build_user_prompt(question=request.question, context=context)

    try:
        llm_provider = get_llm_provider(settings)
        answer = llm_provider.generate(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)
    except LLMProviderError as exc:
        logger.error("LLM generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM generation failed: {exc}",
        ) from exc

    return QueryResponse(
        answer=answer,
        sources=[
            SourceCitation(
                document_id=document.id,
                document_name=document.filename,
                page_number=c.page_number,
                chunk_id=c.chunk_id,
                relevance_score=round(c.hybrid_score, 4),
            )
            for c in ranked
        ],
    )
