"""
DocumentChunk model.

Stores the output of the ingestion pipeline: page-aware, cleaned text
chunks, plus (Phase 3) an embedding vector and a generated tsvector
column for hybrid retrieval.
"""
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.db.session import Base

_EMBEDDING_DIM = get_settings().EMBEDDING_DIMENSIONS


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("ix_document_chunks_document_id", "document_id"),
        # Declared here (not just created via raw SQL in migration 0003)
        # so `alembic check`/autogenerate see these as already-modeled
        # and don't propose dropping them on the next revision.
        Index(
            "ix_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index(
            "ix_document_chunks_content_tsv",
            "content_tsv",
            postgresql_using="gin",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Phase 3 — populated by the ingestion pipeline after chunk creation,
    # so it's nullable (a chunk briefly exists without an embedding).
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(_EMBEDDING_DIM), nullable=True
    )
    # Generated column (DB-computed, see migration 0003). `Computed(...)`
    # tells SQLAlchemy this value is produced by Postgres, not the app —
    # it's excluded from INSERT/UPDATE and fetched back via RETURNING.
    # Without this marker SQLAlchemy sends an explicit NULL for it on
    # every insert, which Postgres rejects for GENERATED ALWAYS columns.
    content_tsv: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', content)", persisted=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
