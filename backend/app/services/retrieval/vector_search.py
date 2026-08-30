"""
Vector similarity search via pgvector.

Uses the `<=>` cosine-distance operator (pgvector). Score returned is
cosine similarity (1 - distance) — higher is more similar, matching
the convention used by keyword_search's ts_rank score.
"""
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.retrieval.types import RawResult


def semantic_search(
    db: Session, document_id: uuid.UUID, query_embedding: list[float], top_k: int
) -> list[RawResult]:
    """
    Only considers chunks that already have an embedding (a chunk can
    briefly exist without one between creation and the embedding step).
    """
    rows = db.execute(
        text(
            """
            SELECT id, page_number, content, section,
                   1 - (embedding <=> :query_embedding) AS score
            FROM document_chunks
            WHERE document_id = :document_id
              AND embedding IS NOT NULL
            ORDER BY embedding <=> :query_embedding
            LIMIT :top_k
            """
        ),
        {
            "document_id": str(document_id),
            "query_embedding": str(query_embedding),
            "top_k": top_k,
        },
    ).all()

    return [
        RawResult(
            chunk_id=row.id,
            source="vector",
            score=float(row.score),
            page_number=row.page_number,
            content=row.content,
            section=row.section,
        )
        for row in rows
    ]
