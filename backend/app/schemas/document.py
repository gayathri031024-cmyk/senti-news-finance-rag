import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentStatus


class DocumentUploadResponse(BaseModel):
    """Returned immediately by POST /api/documents/upload."""
    id: uuid.UUID
    filename: str
    status: DocumentStatus


class DocumentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    file_type: str
    file_size: int
    status: DocumentStatus
    page_count: int
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class DocumentDetail(DocumentListItem):
    error_message: str | None = None
