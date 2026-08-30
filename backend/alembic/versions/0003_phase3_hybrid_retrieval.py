"""phase 3: embedding vector column, tsvector generated column, indexes

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# Must match Settings.EMBEDDING_DIMENSIONS. pgvector columns have a fixed
# dimension — switching embedding models to a different output size
# requires a new migration (ALTER COLUMN ... TYPE vector(N)), not just an
# env var change. See README for the reasoning.
EMBEDDING_DIMENSIONS = 384


def upgrade() -> None:
    # --- Vector column for semantic search ---
    op.execute(
        f"ALTER TABLE document_chunks ADD COLUMN embedding vector({EMBEDDING_DIMENSIONS})"
    )

    # HNSW index for cosine-distance ANN search. Chosen over ivfflat for
    # a prototype at this scale: no training step / "lists" tuning needed,
    # and it performs well without a representative sample of data present
    # at index-build time (ivfflat's clustering quality depends on that).
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding_hnsw "
        "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
    )

    # --- Generated tsvector column for keyword (full-text) search ---
    op.execute(
        "ALTER TABLE document_chunks "
        "ADD COLUMN content_tsv tsvector "
        "GENERATED ALWAYS AS (to_tsvector('english', content)) STORED"
    )
    op.execute(
        "CREATE INDEX ix_document_chunks_content_tsv "
        "ON document_chunks USING gin (content_tsv)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_content_tsv")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS content_tsv")

    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding")
