import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.api.retrieval as retrieval_module
from app.main import app
from app.models.document import Document, DocumentStatus
from app.services.retrieval.types import RawResult

client = TestClient(app)


def _fake_document(status=DocumentStatus.PROCESSED) -> Document:
    doc = Document(filename="test.pdf", file_type="application/pdf", file_size=100, status=status)
    doc.id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    doc.created_at = doc.updated_at = now
    return doc


def test_search_returns_ranked_results(monkeypatch):
    doc = _fake_document()
    chunk_id = uuid.uuid4()

    monkeypatch.setattr(retrieval_module.repository, "get_document", lambda db, doc_id: doc)
    monkeypatch.setattr(
        retrieval_module,
        "semantic_search",
        lambda db, document_id, query_embedding, top_k: [
            RawResult(chunk_id=chunk_id, source="vector", score=0.8, page_number=3, content="NII content", section="Income")
        ],
    )
    monkeypatch.setattr(
        retrieval_module,
        "keyword_search",
        lambda db, document_id, query_text, top_k: [
            RawResult(chunk_id=chunk_id, source="keyword", score=0.6, page_number=3, content="NII content", section="Income")
        ],
    )

    response = client.post(
        "/api/retrieval/search",
        json={"document_id": str(doc.id), "query": "What was the net interest income?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "What was the net interest income?"
    assert len(body["results"]) == 1
    result = body["results"][0]
    assert result["chunk_id"] == str(chunk_id)
    assert result["page_number"] == 3
    assert "vector_score" in result
    assert "keyword_score" in result
    assert "hybrid_score" in result


def test_search_document_not_found(monkeypatch):
    monkeypatch.setattr(retrieval_module.repository, "get_document", lambda db, doc_id: None)

    response = client.post(
        "/api/retrieval/search",
        json={"document_id": str(uuid.uuid4()), "query": "anything"},
    )
    assert response.status_code == 404


def test_search_document_not_yet_processed(monkeypatch):
    doc = _fake_document(status=DocumentStatus.PROCESSING)
    monkeypatch.setattr(retrieval_module.repository, "get_document", lambda db, doc_id: doc)

    response = client.post(
        "/api/retrieval/search",
        json={"document_id": str(doc.id), "query": "anything"},
    )
    assert response.status_code == 409


def test_search_rejects_empty_query(monkeypatch):
    doc = _fake_document()
    monkeypatch.setattr(retrieval_module.repository, "get_document", lambda db, doc_id: doc)

    response = client.post(
        "/api/retrieval/search",
        json={"document_id": str(doc.id), "query": ""},
    )
    assert response.status_code == 422


def test_search_no_results_returns_empty_list(monkeypatch):
    doc = _fake_document()
    monkeypatch.setattr(retrieval_module.repository, "get_document", lambda db, doc_id: doc)
    monkeypatch.setattr(retrieval_module, "semantic_search", lambda *a, **k: [])
    monkeypatch.setattr(retrieval_module, "keyword_search", lambda *a, **k: [])

    response = client.post(
        "/api/retrieval/search",
        json={"document_id": str(doc.id), "query": "something with no matches"},
    )
    assert response.status_code == 200
    assert response.json()["results"] == []
