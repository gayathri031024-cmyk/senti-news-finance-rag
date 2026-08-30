"""
Keyword search via PostgreSQL full-text search.

Uses the generated `content_tsv` column (see migration 0003) and
plainto_tsquery, which handles arbitrary user query text (including
multi-word financial phrases like "net interest income") without
requiring tsquery operator syntax from the caller. Score is ts_rank —
higher is more relevant, matching semantic_search's convention.
"""
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.retrieval.types import RawResult


def keyword_search(
    db: Session, document_id: uuid.UUID, query_text: str, top_k: int
) -> list[RawResult]:
    rows = db.execute(
        text(
            """
            SELECT id, page_number, content, section,
                   ts_rank(content_tsv, plainto_tsquery('english', :query_text)) AS score
            FROM document_chunks
            WHERE document_id = :document_id
              AND content_tsv @@ plainto_tsquery('english', :query_text)
            ORDER BY score DESC
            LIMIT :top_k
            """
        ),
        {"document_id": str(document_id), "query_text": query_text, "top_k": top_k},
    ).all()

    return [
        RawResult(
            chunk_id=row.id,
            source="keyword",
            score=float(row.score),
            page_number=row.page_number,
            content=row.content,
            section=row.section,
        )
        for row in rows
    ]
