"""phase 2: document_chunks table, updated status enum, error_message

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1. Replace the document_status enum with the Phase 2 values ---
    # Old: pending, processing, ready, failed
    # New: uploaded, processing, processed, failed
    op.execute("ALTER TYPE document_status RENAME TO document_status_old")
    op.execute("CREATE TYPE document_status AS ENUM ('uploaded', 'processing', 'processed', 'failed')")

    op.execute("ALTER TABLE documents ALTER COLUMN status DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE documents
        ALTER COLUMN status TYPE document_status
        USING (
            CASE status::text
                WHEN 'pending' THEN 'uploaded'
                WHEN 'processing' THEN 'processing'
                WHEN 'ready' THEN 'processed'
                WHEN 'failed' THEN 'failed'
            END
        )::document_status
        """
    )
    op.execute("ALTER TABLE documents ALTER COLUMN status SET DEFAULT 'uploaded'")
    op.execute("DROP TYPE document_status_old")

    # --- 2. Add error_message to documents ---
    op.add_column("documents", sa.Column("error_message", sa.Text(), nullable=True))

    # --- 3. Create document_chunks ---
    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(length=512), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_document_chunks_document_id", "document_chunks", ["document_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")

    op.drop_column("documents", "error_message")

    op.execute("ALTER TYPE document_status RENAME TO document_status_new")
    op.execute("CREATE TYPE document_status AS ENUM ('pending', 'processing', 'ready', 'failed')")
    op.execute("ALTER TABLE documents ALTER COLUMN status DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE documents
        ALTER COLUMN status TYPE document_status
        USING (
            CASE status::text
                WHEN 'uploaded' THEN 'pending'
                WHEN 'processing' THEN 'processing'
                WHEN 'processed' THEN 'ready'
                WHEN 'failed' THEN 'failed'
            END
        )::document_status
        """
    )
    op.execute("ALTER TABLE documents ALTER COLUMN status SET DEFAULT 'pending'")
    op.execute("DROP TYPE document_status_new")
