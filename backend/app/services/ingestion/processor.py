"""
Ingestion pipeline orchestrator.

Runs after the upload endpoint has already created the Document row
and returned a response. Executes as a FastAPI BackgroundTask, so it
needs its own DB session (the request-scoped one is already closed).
"""
import logging
import uuid

from app.core.config import get_settings
from app.db import repository
from app.db.session import SessionLocal
from app.models.document import DocumentStatus
from app.services.embeddings.factory import get_embedding_provider
from app.services.ingestion.chunker import chunk_pages
from app.services.ingestion.cleaner import clean_pages
from app.services.ingestion.pdf_parser import PdfExtractionError, extract_pdf_pages

logger = logging.getLogger("sentinews.ingestion")


def process_document(document_id: uuid.UUID, file_bytes: bytes) -> None:
    """
    Full pipeline: extract -> clean -> chunk -> store. Updates the
    document's status at each terminal outcome. Never raises — any
    failure is caught, logged, and reflected in the document's status
    and error_message so the document never gets stuck in "processing".
    """
    settings = get_settings()
    db = SessionLocal()
    try:
        document = repository.get_document(db, document_id)
        if document is None:
            logger.error("process_document: document %s not found", document_id)
            return

        try:
            extraction = extract_pdf_pages(file_bytes)
        except PdfExtractionError as exc:
            logger.error("Extraction failed for document %s: %s", document_id, exc)
            repository.update_document_status(
                db, document, DocumentStatus.FAILED, error_message=str(exc)
            )
            return

        if not extraction.has_extractable_text:
            message = (
                "No extractable text found on any page — this looks like a "
                "scanned/image-only PDF. OCR is not supported in this phase."
            )
            logger.warning("Document %s: %s", document_id, message)
            repository.update_document_status(
                db, document, DocumentStatus.FAILED, error_message=message
            )
            return

        cleaned_pages = clean_pages(extraction.pages)
        chunks = chunk_pages(
            cleaned_pages,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )

        if not chunks:
            message = "Extraction succeeded but produced no usable chunks."
            logger.warning("Document %s: %s", document_id, message)
            repository.update_document_status(
                db, document, DocumentStatus.FAILED, error_message=message
            )
            return

        created_chunks = repository.bulk_create_chunks(db, document_id, chunks)

        # Embedding generation is a Phase 3 enhancement on top of Phase 2's
        # extract/clean/chunk/store contract — a failure here (e.g. no
        # EMBEDDING_API_KEY configured) does not fail the document. Chunks
        # simply keep embedding = NULL; keyword search still works over
        # them, semantic_search just won't return them (see vector_search.py).
        try:
            provider = get_embedding_provider(settings)
            embeddings = provider.embed_texts([chunk.content for chunk in created_chunks])
            repository.bulk_set_embeddings(
                db, {chunk.id: embedding for chunk, embedding in zip(created_chunks, embeddings)}
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "Embedding generation failed for document %s — chunks stored without "
                "embeddings; keyword search still works, semantic search will not.",
                document_id,
            )

        repository.update_document_status(db, document, DocumentStatus.PROCESSED)
        logger.info(
            "Document %s processed: %d pages, %d chunks",
            document_id, extraction.page_count, len(chunks),
        )

    except Exception as exc:  # noqa: BLE001 - last-resort guard so status never gets stuck
        logger.exception("Unexpected error processing document %s", document_id)
        try:
            document = repository.get_document(db, document_id)
            if document is not None:
                repository.update_document_status(
                    db, document, DocumentStatus.FAILED, error_message=f"Unexpected error: {exc}"
                )
        except Exception:  # noqa: BLE001 - avoid masking the original error
            logger.exception("Also failed to record failure status for document %s", document_id)
    finally:
        db.close()
