"""
Document ingestion API.

POST /api/documents/upload  — validate, store, kick off background processing
GET  /api/documents          — list all documents with page/chunk counts
GET  /api/documents/{id}     — single document detail
"""
import logging
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import repository
from app.db.session import get_db
from app.models.document import DocumentStatus
from app.schemas.document import DocumentDetail, DocumentListItem, DocumentUploadResponse
from app.services.ingestion.processor import process_document

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger("sentinews.documents")
settings = get_settings()

_SAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_filename(raw_name: str) -> str:
    """
    Never trust a user-provided filename: strip any path components,
    then keep only a conservative character set. Falls back to a
    generic name if nothing usable remains.
    """
    name = Path(raw_name or "").name  # drops any directory traversal (../, etc.)
    name = _SAFE_FILENAME_CHARS.sub("_", name).strip("._") or "document"
    return name[:255]


def _validate_upload(file: UploadFile, file_bytes: bytes) -> None:
    is_pdf_type = (file.content_type or "").lower() == "application/pdf"
    is_pdf_ext = (file.filename or "").lower().endswith(".pdf")
    if not (is_pdf_type or is_pdf_ext):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted.",
        )

    if len(file_bytes) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    if len(file_bytes) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.MAX_FILE_SIZE_MB}MB limit.",
        )

    # Cheap magic-byte check — content-type headers are client-supplied
    # and easy to spoof, so don't rely on them alone.
    if not file_bytes.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File does not look like a valid PDF.",
        )


def _to_list_item(document, stats: dict) -> DocumentListItem:
    return DocumentListItem(
        id=document.id,
        filename=document.filename,
        file_type=document.file_type,
        file_size=document.file_size,
        status=document.status,
        page_count=stats["page_count"],
        chunk_count=stats["chunk_count"],
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    file_bytes = await file.read()
    _validate_upload(file, file_bytes)

    safe_name = _sanitize_filename(file.filename or "document.pdf")

    try:
        document = repository.create_document(
            db, filename=safe_name, file_type="application/pdf", file_size=len(file_bytes)
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to create document record")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save the document record. Please try again.",
        ) from exc

    # Persist the raw PDF to disk (uuid-based name — never the user's
    # filename) so later phases can re-process it if needed.
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    (upload_dir / f"{document.id}.pdf").write_bytes(file_bytes)

    document = repository.update_document_status(db, document, DocumentStatus.PROCESSING)
    background_tasks.add_task(process_document, document.id, file_bytes)

    return DocumentUploadResponse(id=document.id, filename=document.filename, status=document.status)


@router.get("", response_model=list[DocumentListItem])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentListItem]:
    documents = repository.list_documents(db)
    return [
        _to_list_item(doc, repository.document_stats(db, doc.id))
        for doc in documents
    ]


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(document_id: uuid.UUID, db: Session = Depends(get_db)) -> DocumentDetail:
    document = repository.get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    stats = repository.document_stats(db, document.id)
    return DocumentDetail(
        id=document.id,
        filename=document.filename,
        file_type=document.file_type,
        file_size=document.file_size,
        status=document.status,
        page_count=stats["page_count"],
        chunk_count=stats["chunk_count"],
        created_at=document.created_at,
        updated_at=document.updated_at,
        error_message=document.error_message,
    )
