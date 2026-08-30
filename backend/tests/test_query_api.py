import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.api.query as query_module
from app.main import app
from app.models.document import Document, DocumentStatus
from app.services.llm.openai_provider import LLMProviderError
from app.services.retrieval.types import RawResult

client = TestClient(app)


def _fake_document(status=DocumentStatus.PROCESSED, filename="HDFC_Bank_Q4FY26_Results.pdf") -> Document:
    doc = Document(filename=filename, file_type="application/pdf", file_size=100, status=status)
    doc.id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    doc.created_at = doc.updated_at = now
    return doc


class _FakeLLM:
    """Stand-in LLM used across tests so no real API call is ever made
    and the unit tests aren't dependent on LLM_PROVIDER/LLM_API_KEY."""

    def __init__(self, answer: str):
        self.answer = answer
        self.calls = []

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        return self.answer


class _FailingLLM:
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        raise LLMProviderError("simulated LLM outage")


def _patch_retrieval(monkeypatch, vector_results=None, keyword_results=None):
    monkeypatch.setattr(
        query_module, "semantic_search", lambda db, document_id, query_embedding, top_k: vector_results or []
    )
    monkeypatch.setattr(
        query_module, "keyword_search", lambda db, document_id, query_text, top_k: keyword_results or []
    )


# ---------------------------------------------------------------------------
# Grounded answers
# ---------------------------------------------------------------------------

def test_query_returns_grounded_answer_with_citations(monkeypatch):
    doc = _fake_document()
    chunk_id = uuid.uuid4()

    monkeypatch.setattr(query_module.repository, "get_document", lambda db, doc_id: doc)
    _patch_retrieval(
        monkeypatch,
        vector_results=[
            RawResult(chunk_id=chunk_id, source="vector", score=0.9, page_number=4,
                      content="Net Interest Income (NII) for Q4FY26 was Rs. 21,000 crore.", section="Financial Highlights"),
        ],
        keyword_results=[
            RawResult(chunk_id=chunk_id, source="keyword", score=0.7, page_number=4,
                      content="Net Interest Income (NII) for Q4FY26 was Rs. 21,000 crore.", section="Financial Highlights"),
        ],
    )

    fake_llm = _FakeLLM("The Net Interest Income (NII) for Q4FY26 was Rs. 21,000 crore, per page 4.")
    monkeypatch.setattr(query_module, "get_llm_provider", lambda settings: fake_llm)

    response = client.post(
        "/api/query",
        json={"document_id": str(doc.id), "question": "What was the net interest income?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == fake_llm.answer
    assert len(body["sources"]) == 1
    source = body["sources"][0]
    assert source["chunk_id"] == str(chunk_id)
    assert source["page_number"] == 4
    assert source["document_id"] == str(doc.id)
    assert source["document_name"] == doc.filename
    assert "relevance_score" in source

    # The LLM must have actually been given the retrieved context, not
    # asked to answer with no grounding material.
    assert len(fake_llm.calls) == 1
    assert "21,000 crore" in fake_llm.calls[0]["user_prompt"]
    assert "net interest income" in fake_llm.calls[0]["user_prompt"].lower()


def test_query_only_cites_actually_retrieved_chunks(monkeypatch):
    """Citations must come from retrieval, never be invented — even if
    the (mocked) LLM text references a different page."""
    doc = _fake_document()
    chunk_id = uuid.uuid4()

    monkeypatch.setattr(query_module.repository, "get_document", lambda db, doc_id: doc)
    _patch_retrieval(
        monkeypatch,
        vector_results=[
            RawResult(chunk_id=chunk_id, source="vector", score=0.9, page_number=6,
                      content="Gross NPA ratio stood at 1.2%.", section="Asset Quality"),
        ],
    )

    fake_llm = _FakeLLM("According to page 99, GNPA was 1.2%.")  # LLM text is untrusted for citations
    monkeypatch.setattr(query_module, "get_llm_provider", lambda settings: fake_llm)

    response = client.post(
        "/api/query",
        json={"document_id": str(doc.id), "question": "What was the GNPA?"},
    )

    assert response.status_code == 200
    sources = response.json()["sources"]
    assert len(sources) == 1
    # The citation reflects the real retrieved page (6), not the
    # fabricated page mentioned in the LLM's own text (99).
    assert sources[0]["page_number"] == 6
    assert sources[0]["chunk_id"] == str(chunk_id)


# ---------------------------------------------------------------------------
# Unsupported / unanswerable questions
# ---------------------------------------------------------------------------

def test_query_with_no_retrieval_hits_returns_not_found_without_calling_llm(monkeypatch):
    """When retrieval finds nothing (e.g. an off-document question like
    an election prediction), the endpoint must say so and must not
    call the LLM at all -- this guarantees the "not in the document"
    behavior rather than leaving it up to the model to remember.

    NOTE: this only tests the *no-context* path. Whether a real LLM
    correctly declines to answer when *some* (irrelevant) context *is*
    retrieved still requires live verification against a real
    LLM_PROVIDER=openai — see README."""
    doc = _fake_document()
    monkeypatch.setattr(query_module.repository, "get_document", lambda db, doc_id: doc)
    _patch_retrieval(monkeypatch, vector_results=[], keyword_results=[])

    llm_calls = []

    def _get_llm_provider(settings):
        llm_calls.append(1)
        return _FakeLLM("should not be reached")

    monkeypatch.setattr(query_module, "get_llm_provider", _get_llm_provider)

    response = client.post(
        "/api/query",
        json={"document_id": str(doc.id), "question": "Who will win the 2030 Indian elections?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sources"] == []
    assert "couldn't find" in body["answer"].lower() or "not found" in body["answer"].lower()
    assert llm_calls == []  # LLM was never invoked


# ---------------------------------------------------------------------------
# Document validation
# ---------------------------------------------------------------------------

def test_query_document_not_found(monkeypatch):
    monkeypatch.setattr(query_module.repository, "get_document", lambda db, doc_id: None)

    response = client.post(
        "/api/query",
        json={"document_id": str(uuid.uuid4()), "question": "anything"},
    )
    assert response.status_code == 404


def test_query_document_not_yet_processed(monkeypatch):
    doc = _fake_document(status=DocumentStatus.PROCESSING)
    monkeypatch.setattr(query_module.repository, "get_document", lambda db, doc_id: doc)

    response = client.post(
        "/api/query",
        json={"document_id": str(doc.id), "question": "anything"},
    )
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# LLM failure
# ---------------------------------------------------------------------------

def test_query_llm_failure_returns_502(monkeypatch):
    doc = _fake_document()
    chunk_id = uuid.uuid4()
    monkeypatch.setattr(query_module.repository, "get_document", lambda db, doc_id: doc)
    _patch_retrieval(
        monkeypatch,
        vector_results=[
            RawResult(chunk_id=chunk_id, source="vector", score=0.9, page_number=2,
                      content="Provisions for the quarter were Rs. 1,500 crore.", section=None),
        ],
    )
    monkeypatch.setattr(query_module, "get_llm_provider", lambda settings: _FailingLLM())

    response = client.post(
        "/api/query",
        json={"document_id": str(doc.id), "question": "What were the provisions?"},
    )

    assert response.status_code == 502


# ---------------------------------------------------------------------------
# Malformed requests
# ---------------------------------------------------------------------------

def test_query_rejects_empty_question(monkeypatch):
    doc = _fake_document()
    monkeypatch.setattr(query_module.repository, "get_document", lambda db, doc_id: doc)

    response = client.post(
        "/api/query",
        json={"document_id": str(doc.id), "question": ""},
    )
    assert response.status_code == 422


def test_query_rejects_missing_document_id():
    response = client.post("/api/query", json={"question": "What was the net profit?"})
    assert response.status_code == 422


def test_query_rejects_invalid_document_id_format():
    response = client.post(
        "/api/query",
        json={"document_id": "not-a-uuid", "question": "What was the net profit?"},
    )
    assert response.status_code == 422


def test_query_rejects_missing_question_field():
    response = client.post("/api/query", json={"document_id": str(uuid.uuid4())})
    assert response.status_code == 422
