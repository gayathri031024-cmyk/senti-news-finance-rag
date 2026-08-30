import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.api.documents as documents_module
from app.main import app
from app.models.document import Document, DocumentStatus
from tests.pdf_fixtures import make_pdf_bytes

client = TestClient(app)


def _fake_document(**overrides) -> Document:
    doc = Document(
        filename=overrides.get("filename", "test.pdf"),
        file_type="application/pdf",
        file_size=overrides.get("file_size", 1234),
        status=overrides.get("status", DocumentStatus.UPLOADED),
    )
    doc.id = overrides.get("id", uuid.uuid4())
    doc.error_message = overrides.get("error_message")
    now = datetime.now(timezone.utc)
    doc.created_at = overrides.get("created_at", now)
    doc.updated_at = overrides.get("updated_at", now)
    return doc


def test_upload_valid_pdf_returns_processing_status(monkeypatch):
    created = _fake_document(status=DocumentStatus.UPLOADED)

    monkeypatch.setattr(documents_module.repository, "create_document", lambda db, **kw: created)
    monkeypatch.setattr(
        documents_module.repository,
        "update_document_status",
        lambda db, doc, status, **kw: _fake_document(id=doc.id, status=status),
    )
    # Don't actually touch disk or spawn real background work in this test.
    monkeypatch.setattr(documents_module.Path, "mkdir", lambda *a, **kw: None)
    monkeypatch.setattr(documents_module.Path, "write_bytes", lambda *a, **kw: None)

    pdf_bytes = make_pdf_bytes(["Some financial content here."])
    response = client.post(
        "/api/documents/upload",
        files={"file": ("HDFC_Q1_Results.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "test.pdf"  # comes from our faked repository return
    assert body["status"] == "processing"


def test_upload_rejects_non_pdf_file():
    response = client.post(
        "/api/documents/upload",
        files={"file": ("notes.txt", b"just some text", "text/plain")},
    )
    assert response.status_code == 400


def test_upload_rejects_oversized_file(monkeypatch):
    monkeypatch.setattr(documents_module.settings, "MAX_FILE_SIZE_MB", 0)  # 0 MB limit -> anything is "too big"
    pdf_bytes = make_pdf_bytes(["content"])

    response = client.post(
        "/api/documents/upload",
        files={"file": ("big.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 413


def test_upload_rejects_malformed_pdf_bytes():
    response = client.post(
        "/api/documents/upload",
        files={"file": ("broken.pdf", b"not actually a pdf", "application/pdf")},
    )
    # Fails magic-byte validation (doesn't start with %PDF-)
    assert response.status_code == 400


def test_upload_rejects_empty_file():
    response = client.post(
        "/api/documents/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert response.status_code == 400


def test_list_documents_returns_stats(monkeypatch):
    doc = _fake_document(filename="HDFC_Q1_Results.pdf", status=DocumentStatus.PROCESSED)

    monkeypatch.setattr(documents_module.repository, "list_documents", lambda db: [doc])
    monkeypatch.setattr(
        documents_module.repository,
        "document_stats",
        lambda db, doc_id: {"page_count": 9, "chunk_count": 9},
    )

    response = client.get("/api/documents")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["filename"] == "HDFC_Q1_Results.pdf"
    assert body[0]["status"] == "processed"
    assert body[0]["page_count"] == 9
    assert body[0]["chunk_count"] == 9


def test_get_document_detail_found(monkeypatch):
    doc = _fake_document(status=DocumentStatus.PROCESSED)

    monkeypatch.setattr(documents_module.repository, "get_document", lambda db, doc_id: doc)
    monkeypatch.setattr(
        documents_module.repository,
        "document_stats",
        lambda db, doc_id: {"page_count": 3, "chunk_count": 5},
    )

    response = client.get(f"/api/documents/{doc.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(doc.id)
    assert body["chunk_count"] == 5


def test_get_document_detail_not_found(monkeypatch):
    monkeypatch.setattr(documents_module.repository, "get_document", lambda db, doc_id: None)

    response = client.get(f"/api/documents/{uuid.uuid4()}")
    assert response.status_code == 404


def test_get_document_invalid_id_returns_422():
    response = client.get("/api/documents/not-a-valid-uuid")
    assert response.status_code == 422
