"""
End-to-end retrieval test against a real Postgres + pgvector database.
Skipped by default. Run against a real Neon (or local Docker) database
with migrations applied:

    RUN_DB_INTEGRATION_TESTS=1 pytest tests/test_retrieval_integration.py
"""
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db import repository
from app.services.embeddings.factory import get_embedding_provider
from app.services.ingestion.processor import process_document
from app.services.retrieval.hybrid import hybrid_search
from app.services.retrieval.keyword_search import keyword_search
from app.services.retrieval.vector_search import semantic_search
from tests.pdf_fixtures import make_pdf_bytes

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_DB_INTEGRATION_TESTS"),
    reason="Requires a live Postgres with pgvector and migrations applied. "
    "Set RUN_DB_INTEGRATION_TESTS=1 to enable.",
)


def test_hybrid_search_retrieves_relevant_chunk():
    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)

    pdf_bytes = make_pdf_bytes(
        [
            "Net interest income grew 3.2 percent year over year to Rs 330.8 billion.",
            "GNPA ratio was 1.15 percent as of March 2026, an improvement from 1.24 percent.",
            "The bank opened new branches across twelve cities during the quarter.",
        ]
    )

    with Session() as db:
        document = repository.create_document(
            db, filename="retrieval_integration.pdf", file_type="application/pdf",
            file_size=len(pdf_bytes),
        )
        document_id = document.id

    process_document(document_id, pdf_bytes)

    with Session() as db:
        provider = get_embedding_provider(settings)
        query_embedding = provider.embed_texts(["What was the net interest income?"])[0]

        vector_results = semantic_search(db, document_id, query_embedding, top_k=settings.TOP_K)
        keyword_results = keyword_search(
            db, document_id, "net interest income", top_k=settings.TOP_K
        )
        ranked = hybrid_search(
            vector_results, keyword_results,
            vector_weight=settings.VECTOR_WEIGHT,
            keyword_weight=settings.KEYWORD_WEIGHT,
            k=settings.TOP_K,
        )

        assert len(ranked) > 0
        assert "net interest income" in ranked[0].content.lower()
