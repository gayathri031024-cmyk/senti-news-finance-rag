"""
Document/chunk repository.

Isolates ORM/session usage so the API layer and the ingestion
processor don't touch SQLAlchemy directly, and so tests can monkeypatch
these functions instead of standing up a real database.
"""
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.chunk import DocumentChunk
from app.models.document import Document, DocumentStatus
from app.services.ingestion.chunker import Chunk


def create_document(db: Session, *, filename: str, file_type: str, file_size: int) -> Document:
    document = Document(
        filename=filename,
        file_type=file_type,
        file_size=file_size,
        status=DocumentStatus.UPLOADED,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def get_document(db: Session, document_id: uuid.UUID) -> Document | None:
    return db.get(Document, document_id)


def list_documents(db: Session) -> list[Document]:
    return list(db.scalars(select(Document).order_by(Document.created_at.desc())))


def update_document_status(
    db: Session,
    document: Document,
    status: DocumentStatus,
    *,
    error_message: str | None = None,
) -> Document:
    document.status = status
    document.error_message = error_message
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def bulk_create_chunks(db: Session, document_id: uuid.UUID, chunks: list[Chunk]) -> list[DocumentChunk]:
    """Returns the created rows (with generated ids) so the caller can
    immediately generate and attach embeddings without a second query."""
    rows = [
        DocumentChunk(
            document_id=document_id,
            chunk_index=chunk.chunk_index,
            page_number=chunk.page_number,
            section=chunk.section,
            content=chunk.content,
        )
        for chunk in chunks
    ]
    db.add_all(rows)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def bulk_set_embeddings(db: Session, chunk_embeddings: dict[uuid.UUID, list[float]]) -> None:
    for chunk_id, embedding in chunk_embeddings.items():
        db.execute(
            update(DocumentChunk).where(DocumentChunk.id == chunk_id).values(embedding=embedding)
        )
    db.commit()


def get_chunk_by_id(db: Session, chunk_id: uuid.UUID) -> DocumentChunk | None:
    return db.get(DocumentChunk, chunk_id)


def document_stats(db: Session, document_id: uuid.UUID) -> dict:
    """Chunk count and distinct page count for a document, in one query."""
    row = db.execute(
        select(
            func.count(DocumentChunk.id),
            func.count(func.distinct(DocumentChunk.page_number)),
        ).where(DocumentChunk.document_id == document_id)
    ).one()
    return {"chunk_count": row[0] or 0, "page_count": row[1] or 0}
