"""initial: enable pgvector, create documents table

Revision ID: 0001
Revises:
Create Date: 2026-08-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

document_status = postgresql.ENUM(
    "pending", "processing", "ready", "failed",
    name="document_status",
)


def upgrade() -> None:
    # Enable pgvector now so later phases can add vector columns
    # without another extension-management migration.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # create_table() below creates the ENUM type implicitly as part of
    # the column definition — no separate .create() call needed.
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("file_type", sa.String(length=64), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            document_status,
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("documents")
    document_status.drop(op.get_bind(), checkfirst=True)
    # Extension is left in place intentionally — other objects/phases
    # may depend on it; dropping it is an explicit, separate action.
