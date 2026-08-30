"""
End-to-end ingestion test against a real Postgres + pgvector database.
Skipped by default — this sandbox has none. Run against a real Neon
(or local Docker) database with:

    RUN_DB_INTEGRATION_TESTS=1 pytest tests/test_ingestion_integration.py
"""
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db import repository
from app.models.document import DocumentStatus
from app.services.ingestion.processor import process_document
from tests.pdf_fixtures import make_pdf_bytes

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_DB_INTEGRATION_TESTS"),
    reason="Requires a live Postgres with pgvector and migrations applied. "
    "Set RUN_DB_INTEGRATION_TESTS=1 to enable.",
)


def test_full_pipeline_stores_document_and_chunks():
    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)

    pdf_bytes = make_pdf_bytes(
        ["Revenue grew 12% this quarter to $4,695 crore.", "Net profit margin improved to 18.3%."]
    )

    with Session() as db:
        document = repository.create_document(
            db, filename="integration_test.pdf", file_type="application/pdf", file_size=len(pdf_bytes)
        )
        document_id = document.id

    # Run the pipeline synchronously (this is what the background task calls).
    process_document(document_id, pdf_bytes)

    with Session() as db:
        document = repository.get_document(db, document_id)
        assert document is not None
        assert document.status == DocumentStatus.PROCESSED

        stats = repository.document_stats(db, document_id)
        assert stats["chunk_count"] > 0
        assert stats["page_count"] == 2
