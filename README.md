# SentiNews — Finance Research Assistant

SentiNews is a finance-focused RAG (Retrieval-Augmented Generation) application that lets users upload financial documents and ask questions grounded in the uploaded content.

The system extracts and cleans PDF text, creates page-scoped chunks, indexes them using both semantic and keyword search, retrieves relevant evidence, and generates answers with citations pointing back to the source document.

It is designed as a technically focused prototype demonstrating document ingestion, hybrid retrieval, grounded generation, citation traceability, and RAG evaluation. This repository is not a production system — it's built in phases so each layer can be verified before the next is added.

## What It Does

- Upload financial PDF documents
- Extract text page-by-page
- Clean and chunk financial content
- Preserve page-level source attribution
- Generate embeddings for semantic retrieval
- Perform PostgreSQL full-text keyword search
- Combine semantic and keyword retrieval using hybrid ranking
- Build grounded context from retrieved chunks
- Generate natural-language answers using a configurable LLM
- Return citations tied to actually retrieved document chunks
- Evaluate retrieval recall and citation traceability
- Provide a simple research interface for uploading documents and asking questions

## Architecture

```text
                    Financial PDF
                         │
                         ▼
                 PDF Validation
                         │
                         ▼
              Page-by-Page Extraction
                         │
                         ▼
                     Cleaning
                         │
                         ▼
             Sentence-Aware Chunking
                         │
                         ▼
                  PostgreSQL
                 ┌───────┴────────┐
                 │                │
                 ▼                ▼
            Embeddings         Full-Text
             pgvector           Search
                 │                │
                 └───────┬────────┘
                         ▼
                  Hybrid Retrieval
                         │
                         ▼
                  Ranked Chunks
                         │
                         ▼
                  Context Builder
                         │
                         ▼
                    LLM Provider
                         │
                         ▼
               Grounded Answer
                         │
                         ▼
                     Citations
```

## Phases

- **Phase 1 — Foundation (complete):** React + FastAPI + PostgreSQL + pgvector wired end-to-end, with a `GET /api/health` endpoint and a bare documents table.
- **Phase 2 — Financial Document Ingestion (complete):** upload a PDF, validate it, extract text page-by-page, clean it, chunk it, and store the chunks in PostgreSQL.
- **Phase 3 — Hybrid Retrieval (complete):** embed chunks, store vectors in pgvector, add PostgreSQL full-text search, and combine both into ranked hybrid retrieval over a document's chunks.
- **Phase 4 — RAG Generation (complete):** turn the ranked chunks from Phase 3 into a grounded, cited natural-language answer via a configurable LLM provider — `POST /api/query`.
- **Phase 5 — Research Interface (complete):** a two-column UI — document upload/selection on the left, a question/answer panel with source citations on the right.
- **Phase 6 — Evaluation (this phase):** a measured evaluation of retrieval recall, citation accuracy, and an honest attempt at an unsupported-question check. See [Phase 6 — Evaluation](#phase-6--evaluation) below.

**Not yet implemented:** reranking, chat/multi-turn conversation, authentication, or any multi-user functionality. Those are later phases.

## Phase 2 — Financial Document Ingestion

### Pipeline

```
PDF Upload
    │  POST /api/documents/upload
    ▼
Validation
    │  PDF extension/MIME + magic bytes, size limit, safe filename
    ▼
Page-by-page Extraction
    │  services/ingestion/pdf_parser.py (pypdf)
    ▼
Cleaning
    │  services/ingestion/cleaner.py — whitespace + repeated header/footer
    │  removal; numbers, %, currency symbols untouched
    ▼
Chunking
    │  services/ingestion/chunker.py — sentence-aware, page-scoped,
    │  configurable CHUNK_SIZE / CHUNK_OVERLAP
    ▼
PostgreSQL
     documents (status) + document_chunks (page_number, chunk_index, content)
```

The Document row is created and returned to the caller immediately (`status: "processing"`); extraction/cleaning/chunking run afterward as a FastAPI background task. This keeps the upload request fast without introducing a separate task queue, which is out of scope for a prototype of this size.

### Supported file type & size limit

PDF only, validated three ways: file extension, `Content-Type` header, and a magic-byte check (`%PDF-` at the start of the file) — headers alone are client-supplied and easy to spoof. Default size limit is 25MB (`MAX_FILE_SIZE_MB`).

### API endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/documents/upload` | Upload a PDF; returns id, filename, status |
| GET | `/api/documents` | List all documents with page/chunk counts |
| GET | `/api/documents/{id}` | Single document detail, incl. `error_message` if failed |

### Processing statuses

`uploaded → processing → processed | failed`.

A document only reaches `failed` with an `error_message` explaining why (malformed PDF, no extractable text/scanned PDF, or an unexpected error) — it never gets stuck in `processing`; the pipeline's outer error handler guarantees a terminal status is always written.

### Chunking strategy & defaults

`CHUNK_SIZE=1200`, `CHUNK_OVERLAP=200` (characters). 1200 characters (~200–250 words) is enough to hold a paragraph or a small financial table together as one coherent unit for later retrieval, without being so large that a chunk mixes multiple unrelated topics. 200 characters of overlap (~15–20%) keeps a sentence that falls right on a chunk boundary from losing its surrounding context.

Chunks never span multiple pages. Each chunk belongs to exactly one `page_number`. This trades a small amount of chunk-size uniformity (a page ending mid-thought produces a shorter final chunk) for chunk-to-page attribution that's always exact — the main ask of this phase.

Splitting prefers sentence/paragraph boundaries (via a regex on `. ! ?` + whitespace and blank lines) over mid-sentence cuts. A single sentence longer than `CHUNK_SIZE` (rare, but dense tables can produce this) falls back to a hard split rather than being left oversized. A trailing fragment shorter than ~120 characters is merged into the previous chunk instead of being stored as a near-empty chunk.

Lightweight section detection: if a page's first non-empty line looks like a heading (short, no terminal punctuation), it's stored as `section` on that page's chunks. No further structure detection.

### Cleaning

Whitespace is normalized (collapsed blank lines, collapsed runs of spaces, trimmed trailing whitespace). Lines that repeat verbatim across most pages (e.g. "Confidential", a running report title) are detected and stripped as headers/footers. Numbers, %, ₹/$/other currency symbols, and financial terminology are never touched by cleaning — only whitespace and identified repeated lines are removed.

## Phase 3 — Hybrid Retrieval

### Pipeline

```
User Question
      │
      ├──────────────┬──────────────┐
      ▼                              ▼
semantic_search()              keyword_search()
pgvector cosine (<=>)          PostgreSQL FTS (tsvector/GIN)
      │                              │
      └──────────────┬───────────────┘
                      ▼
        retrieve_candidates → deduplicate
              → normalize_scores → combine_scores
                      → rank → top_k
                      │
                      ▼
              Ranked chunks (no LLM, no generated answer)
```

Chunk embeddings are generated automatically at the end of ingestion (`services/ingestion/processor.py`), right after chunks are stored — no separate step needed. A chunk that fails to embed (e.g. no `EMBEDDING_API_KEY` configured for `openai`) keeps `embedding = NULL` and simply won't surface in vector search; keyword search still works over it. This is a deliberate choice so a Phase 3 embedding problem never breaks Phase 2's ingestion guarantee (a document that extracts and chunks successfully still reaches `processed`).

### Embedding provider

Configurable via `EMBEDDING_PROVIDER`:

- **`local` (default)** — a dependency-free, deterministic embedding using the "hashing trick" (feature hashing, as in scikit-learn's `HashingVectorizer`): stopwords removed, remaining tokens hashed to a fixed-size vector, L2-normalized. No API key, no network call, no model download. Limitation: this is word-overlap, not learned semantics — it has no notion of synonyms or paraphrase (e.g. "how much did the bank lend" won't match "advances" the way a trained model would). It exists purely so the retrieval architecture (storage, indexing, cosine similarity, hybrid combination) can be built and tested without external dependencies. Financial queries in this domain are often keyword-heavy already (ratio names, line items, abbreviations like "GNPA"), which is why this stand-in still produces sensible top-1 results in practice (see verification below) — but it is not a substitute for real semantic search.
- **`openai`** — calls OpenAI's `/v1/embeddings` endpoint directly (no SDK dependency), requesting `EMBEDDING_DIMENSIONS` explicitly so output size always matches the pgvector column regardless of which `text-embedding-3-*` model is configured. Requires `EMBEDDING_API_KEY`. This is the path for real semantic search quality.

Both implement the same `embed_texts(list[str]) -> list[list[float]]` interface (`services/embeddings/base.py`), so swapping providers is a one-variable change — no code changes needed.

### pgvector storage

`document_chunks.embedding` is a `vector(384)` column (migration 0003), with an HNSW index on cosine distance (`vector_cosine_ops`). HNSW was chosen over ivfflat for this prototype because it needs no training/"lists" tuning step and performs reasonably without a representative data sample present at index-build time — ivfflat's clustering quality depends on that, which doesn't fit a demo where documents are uploaded incrementally.

`EMBEDDING_DIMENSIONS` must match whatever the configured model actually outputs. The column's dimension is fixed at migration time — switching to a differently-sized model later means writing a new migration (`ALTER COLUMN embedding TYPE vector(N)`), not just changing the env var.

### PostgreSQL full-text search

`document_chunks.content_tsv` is a generated column (`GENERATED ALWAYS AS (to_tsvector('english', content)) STORED`), indexed with GIN. Keyword search uses `plainto_tsquery('english', ...)` so arbitrary user query text (including multi-word phrases like "net interest income") works without requiring tsquery operator syntax from the caller, ranked with `ts_rank`.

### Hybrid ranking

`services/retrieval/hybrid.py` implements the pipeline as six pure, independently-testable functions, run in this order:

1. `retrieve_candidates()` — concatenate vector + keyword hits
2. `deduplicate()` — merge into one `Candidate` per `chunk_id`
3. `normalize_scores()` — min-max normalize vector/keyword scores independently
4. `combine_scores()` — weighted sum: `hybrid = VECTOR_WEIGHT·vec + KEYWORD_WEIGHT·kw`
5. `rank()` — sort descending by `hybrid_score`
6. `top_k()` — truncate to `TOP_K`

A chunk found by only one method gets 0.0 (post-normalization) for the other — it wasn't judged relevant by that method, not indeterminate. Vector and keyword scores are normalized separately before combining, since cosine similarity and `ts_rank` are on unrelated scales.

Weight reasoning (`VECTOR_WEIGHT=0.6`, `KEYWORD_WEIGHT=0.4`): financial questions in this domain are often precise — exact ratio names, line-item labels, abbreviations ("GNPA", "NIM") — where a literal keyword match is a strong, reliable signal. But queries are also often phrased differently from how the document states it, where only semantic similarity finds the right chunk. A 0.6/0.4 split leans toward semantic recall as the primary driver while keeping keyword strong enough to matter. This is not tuned against a labeled relevance eval set — it's a reasoned starting point, which is exactly why it's an environment variable rather than a constant.

### Configuration

New in Phase 3 (`backend/.env.example`):

```
EMBEDDING_PROVIDER=local        # "local" or "openai"
EMBEDDING_MODEL=local-hashing-v1
EMBEDDING_API_KEY=
EMBEDDING_DIMENSIONS=384
VECTOR_WEIGHT=0.6
KEYWORD_WEIGHT=0.4
TOP_K=5
```

### Retrieval API

`POST /api/retrieval/search`

Request:

```json
{
  "document_id": "5a63dc44-405c-4243-b44f-b2e3e857ad55",
  "query": "What was the net interest income?"
}
```

Response:

```json
{
  "query": "What was the net interest income?",
  "document_id": "5a63dc44-405c-4243-b44f-b2e3e857ad55",
  "vector_weight": 0.6,
  "keyword_weight": 0.4,
  "results": [
    {
      "chunk_id": "…",
      "page_number": 8,
      "section": "Full-Year Income Statement FY26",
      "content": "Full-Year Income Statement FY26 Standalone P&L figures...",
      "vector_score": 1.0,
      "keyword_score": 1.0,
      "hybrid_score": 1.0
    }
  ]
}
```

The response is self-contained for debugging/demo purposes — it echoes the query and the weights used alongside every chunk's individual vector/keyword/hybrid scores and page number, so retrieval quality can be inspected without cross-referencing server config. Returns 404 if the document doesn't exist, 409 if it hasn't finished processing yet (`status != "processed"`).

## Phase 4 — RAG Generation

### Pipeline

```
Question
    │
    ▼
Hybrid Retrieval (Phase 3, reused as-is — semantic_search + keyword_search + hybrid_search)
    │
    ▼
Relevant Chunks (ranked Candidates)
    │
    ▼
Context Builder (services/generation/context_builder.py)
    │
    ▼
LLM (configurable provider, services/llm/)
    │
    ▼
Grounded Answer + Citations
```

`POST /api/query` does not duplicate any retrieval logic — it imports and calls the same `semantic_search`, `keyword_search`, and `hybrid_search` functions Phase 3's `/api/retrieval/search` uses, unmodified. Phase 3's endpoint and tests were left untouched.

If retrieval returns no candidates at all, the LLM is never called — the endpoint immediately returns a fixed "not found in the document" answer with an empty sources list. This makes "say clearly when the answer isn't in the document" a property of the retrieval step for the no-context case, not something the model has to remember to do unprompted every time.

### LLM provider

Configurable via `LLM_PROVIDER`, following the exact same swappable-provider pattern as Phase 3's `EMBEDDING_PROVIDER` (`services/llm/base.py` defines the `LLMProvider` interface; `services/llm/factory.py` selects an implementation):

- **`local` (default)** — a dependency-free, no-API-key placeholder (`services/llm/local_provider.py`). It does not read the retrieved context and does not generate a real answer; it returns a fixed string saying so. It exists only so the whole pipeline (retrieval → context → prompt → response → citations) can be wired up and demoed with zero external dependencies, mirroring the role `EMBEDDING_PROVIDER=local` plays for embeddings. It must never be used as evidence that grounding/anti-hallucination behavior works — see "What's verified" below.
- **`openai`** — calls OpenAI's `/v1/chat/completions` endpoint directly (no SDK dependency), with `temperature=0` since this is a grounded-answer task over fixed context, not creative writing. Requires `LLM_API_KEY`.

### Prompting & grounding rules

`services/generation/prompts.py` holds the system prompt sent with every request, instructing the model to: answer only from the provided context; never invent figures, dates, or facts; never reference a page/citation beyond what's in the context; explicitly say when the answer isn't present rather than guessing (including for off-document questions, e.g. predictions or unrelated topics); and clearly label any calculation/inference (e.g. a computed percentage change) as distinct from a fact stated directly in the document.

Critically, citations are never parsed out of the model's text. `schemas/query.py`'s `SourceCitation` list is built directly from the `Candidate` objects Phase 3's `hybrid_search()` actually returned — document name, page number, chunk ID, and hybrid relevance score. If the model's answer text mentions a page number, that mention is untrusted prose; the citations the API returns always come from real retrieval, so a citation can never be invented (see `test_query_only_cites_actually_retrieved_chunks` in `tests/test_query_api.py`).

### Query API

`POST /api/query`

Request:

```json
{
  "document_id": "5a63dc44-405c-4243-b44f-b2e3e857ad55",
  "question": "What was the bank's net interest income?"
}
```

Response:

```json
{
  "answer": "The Net Interest Income (NII) for Q4FY26 was Rs. 21,000 crore, as reported on page 4.",
  "sources": [
    {
      "document_id": "5a63dc44-405c-4243-b44f-b2e3e857ad55",
      "document_name": "HDFC_Bank_Q4FY26_Results.pdf",
      "page_number": 4,
      "chunk_id": "…",
      "relevance_score": 0.91
    }
  ]
}
```

Status codes: 404 document not found, 409 document not yet processed, 502 if the embedding call or the LLM call fails, 422 for a malformed request (missing/empty question, invalid document_id).

### Configuration

New in Phase 4 (`backend/.env.example`):

```
LLM_PROVIDER=local              # "local" (placeholder, no key) or "openai"
LLM_MODEL=local-echo-v1
LLM_API_KEY=
```

Phase 4 reuses `TOP_K`, `VECTOR_WEIGHT`, and `KEYWORD_WEIGHT` from Phase 3 as-is for retrieval — there is no separate Phase 4 retrieval configuration to keep in sync.

### What's verified vs. what needs live LLM testing

This phase was built and tested without a live OpenAI API key available in this environment. To be precise about what that does and doesn't prove:

**Verified** (offline, mocked/local — pytest, 78 tests, all passing, no regressions to the 57 Phase 1–3 tests):

- `POST /api/query` request/response shape, status codes (200/404/409/422/502), and citation fields.
- Retrieval integration: `/api/query` calls Phase 3's `semantic_search`/`keyword_search`/`hybrid_search` unmodified and passes their results into the context builder.
- Citations always come from actually-retrieved chunks, never from the (mocked) LLM's text — even when the mocked LLM text names a different page.
- The "no retrieval hits → fixed not-found answer, LLM never called" path (covers the mechanism behind the unsupported-question requirement, e.g. "Who will win the 2030 Indian elections?", when retrieval genuinely returns nothing).
- LLM failure handling (502) when the provider raises an error.
- Context builder and prompt template content (pure unit tests).
- The `local` and `openai` LLM providers instantiate correctly and the local provider makes no network call.

**NOT yet verified** — requires a real `LLM_API_KEY` and a live database, which weren't available in this environment:

- That a real LLM, given the actual retrieved HDFC Bank chunks, produces a correct, non-hallucinated answer to the seven financial questions in the Phase 4 spec (NII, net profit, GNPA, NNPA, advances, provisions, reasons for profit growth).
- That a real LLM correctly declines to answer when retrieval returns some (irrelevant) context for an off-topic question, as opposed to the always-safe "zero retrieval hits" path already verified.
- End-to-end curl verification against the live Neon database (see "Real PDF verification" below) with `LLM_PROVIDER=openai` and a real key.

To complete live verification (once you have an `LLM_API_KEY`):

```bash
# in backend/.env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini      # or another chat-completion model you have access to
LLM_API_KEY=sk-...
```

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"document_id": "<id-from-upload>", "question": "What was the net interest income?"}'

curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"document_id": "<id-from-upload>", "question": "Who will win the 2030 Indian elections?"}'
```

Check that the first returns the real NII figure with a citation pointing at the correct page, and the second either says the information isn't in the document, or if some tangentially related chunk was retrieved, still declines to answer the actual question rather than speculating.

## Stack

| Layer | Technology |
|---|---|
| Frontend | React, TypeScript, Vite, Tailwind CSS v4 |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy, Alembic, pypdf |
| Database | PostgreSQL + pgvector |
| Local infra | Docker Compose (database only — backend/frontend run locally) |

## Project layout

```
sentinews/
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── health.py
│   │   │   ├── documents.py          # upload / list / detail
│   │   │   ├── retrieval.py          # POST /api/retrieval/search
│   │   │   └── query.py              # POST /api/query (Phase 4)
│   │   ├── core/config.py            # chunking, upload, embedding, hybrid-ranking, LLM settings
│   │   ├── db/
│   │   │   ├── session.py
│   │   │   └── repository.py         # all DB access for documents/chunks
│   │   ├── models/
│   │   │   ├── document.py
│   │   │   └── chunk.py              # + embedding vector, content_tsv (Phase 3)
│   │   ├── schemas/{health,document,retrieval,query}.py
│   │   └── services/
│   │       ├── ingestion/
│   │       │   ├── pdf_parser.py
│   │       │   ├── cleaner.py
│   │       │   ├── chunker.py
│   │       │   └── processor.py      # orchestrates ingestion + embedding generation
│   │       ├── embeddings/
│   │       │   ├── base.py           # EmbeddingProvider interface
│   │       │   ├── local_provider.py # dependency-free hashing embedding
│   │       │   ├── openai_provider.py
│   │       │   └── factory.py
│   │       ├── retrieval/
│   │       │   ├── types.py          # RawResult, Candidate
│   │       │   ├── vector_search.py  # pgvector cosine search
│   │       │   ├── keyword_search.py # PostgreSQL FTS
│   │       │   └── hybrid.py         # 6-stage hybrid ranking pipeline
│   │       ├── llm/                  # Phase 4
│   │       │   ├── base.py           # LLMProvider interface
│   │       │   ├── local_provider.py # no-op / no-API-key placeholder
│   │       │   ├── openai_provider.py
│   │       │   └── factory.py
│   │       └── generation/           # Phase 4
│   │           ├── context_builder.py  # ranked Candidates -> LLM context text
│   │           └── prompts.py           # system prompt (grounding rules) + user prompt template
│   ├── alembic/versions/
│   │   ├── 0001_initial_documents_table.py
│   │   ├── 0002_phase2_document_chunks.py
│   │   └── 0003_phase3_hybrid_retrieval.py
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.tsx
│       ├── components/{StatusBadge,DocumentUpload,DocumentList}.tsx
│       └── lib/{api,documentsApi,useHealth}.ts
└── sample_data/
    └── HDFC_Bank_Q4FY26_Results.pdf   # real-figure verification PDF, see below
```

## Setup

### 1. Database

Either Docker Compose (`docker compose up -d db`, using the root `.env.example`), or a managed provider like Neon — see `backend/.env.example` for the `DATABASE_URL` format either way.

### 2. Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head        # applies 0001 -> 0002 -> 0003: documents, document_chunks,
                             # updated status enum, embedding vector column, tsvector column
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open the printed local URL — you'll see the connection status badge from Phase 1, plus the "Upload Financial Document" panel and document list from Phase 2. Phase 3 (retrieval) has no frontend yet — use the API directly (see "Retrieval API" above) or the interactive docs at `http://localhost:8000/docs`.

## Running tests

```bash
cd backend
source .venv/bin/activate
pytest -v
```

78 tests total (57 from Phase 1–3, unchanged, + 21 new in Phase 4). Parser, cleaner, chunker, embeddings, hybrid-ranking, LLM-provider, and generation (context builder/prompts) tests run against generated PDFs and plain Python data — no database or external API needed. API tests (`test_documents_api.py`, `test_retrieval_api.py`, `test_query_api.py`) monkeypatch the repository/search/LLM layer for the same reason. All tests are deterministic — the local embedding provider (hashing-based) and local LLM provider (placeholder, see Phase 4 above) are the defaults, never a real network call, so test runs never depend on `EMBEDDING_API_KEY`/`LLM_API_KEY` being set or on external API availability/cost. Three tests are skipped unless a real database is available:

```bash
RUN_DB_INTEGRATION_TESTS=1 pytest tests/test_db.py -k live
RUN_DB_INTEGRATION_TESTS=1 pytest tests/test_ingestion_integration.py
RUN_DB_INTEGRATION_TESTS=1 pytest tests/test_retrieval_integration.py
```

Frontend build/type-check:

```bash
cd frontend
npm run build
```

## Real PDF verification

`sample_data/HDFC_Bank_Q4FY26_Results.pdf` is a 9-page PDF built from real, current HDFC Bank Q4 FY26 figures (net interest income, PAT, GNPA/NNPA, deposits, EPS, capital adequacy, etc.), sourced from the bank's own investor-relations earnings presentation. It's a generated PDF rather than a scan of the original filing (see the Phase 2 completion report for why), but every figure in it is real and it exercises the same dense, tabular financial content the pipeline is meant to handle.

To verify ingestion (Phase 2) against your own database:

```bash
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@sample_data/HDFC_Bank_Q4FY26_Results.pdf"
```

Then check status and stats:

```bash
curl http://localhost:8000/api/documents/<id-from-response>
```

Once status is `"processed"`, query Postgres directly to confirm chunks — and, as of Phase 3, embeddings — landed correctly:

```sql
SELECT id, filename, status, error_message FROM documents;

SELECT document_id, COUNT(*) AS chunk_count, COUNT(DISTINCT page_number) AS page_count
FROM document_chunks
GROUP BY document_id;

SELECT chunk_index, page_number, section,
       (embedding IS NOT NULL) AS has_embedding,
       left(content, 80) AS preview
FROM document_chunks
WHERE document_id = '<id>'
ORDER BY chunk_index;
```

To verify retrieval (Phase 3):

```bash
curl -X POST http://localhost:8000/api/retrieval/search \
  -H "Content-Type: application/json" \
  -d '{"document_id": "<id-from-above>", "query": "What was the net interest income?"}'
```

Try it with a few different financial questions — e.g. "What is the GNPA ratio?", "What is the capital adequacy ratio?" — and check that the top-ranked chunk's `page_number`/`content` actually answers the question.

To verify RAG generation (Phase 4) — requires `LLM_PROVIDER=openai` and a real `LLM_API_KEY` in `backend/.env` for a real answer; with the default `LLM_PROVIDER=local` you'll get the placeholder text instead (see Phase 4 → "What's verified" above for exactly what has and hasn't been confirmed this way):

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"document_id": "<id-from-above>", "question": "What was the net profit?"}'
```

(`documents` doesn't store page/chunk counts directly — they're computed from `document_chunks` at query time, which is what `GET /api/documents` and `GET /api/documents/{id}` do.)

## Configuration

All configuration is read from environment variables — nothing is hardcoded; `.env` files are gitignored. Full list (`backend/.env.example`):

```
# Phase 2 — ingestion
CHUNK_SIZE=1200
CHUNK_OVERLAP=200
MAX_FILE_SIZE_MB=25
UPLOAD_DIR=storage/uploads

# Phase 3 — embeddings + hybrid retrieval
EMBEDDING_PROVIDER=local        # "local" or "openai"
EMBEDDING_MODEL=local-hashing-v1
EMBEDDING_API_KEY=
EMBEDDING_DIMENSIONS=384
VECTOR_WEIGHT=0.6
KEYWORD_WEIGHT=0.4
TOP_K=5

# Phase 4 — RAG generation
LLM_PROVIDER=local              # "local" (placeholder, no key) or "openai"
LLM_MODEL=local-echo-v1
LLM_API_KEY=
```

Uploaded PDFs are stored under `backend/storage/uploads/<document-id>.pdf` (gitignored) so a later phase could re-process a document without re-uploading it.

## Phase 5 — Research Interface

The frontend (`frontend/src/App.tsx`) is a two-column layout:

- **Left column:** `DocumentUpload` (unchanged from Phase 2) and `DocumentList`, now selectable — clicking a processed document makes it the active document for the research panel. Documents still processing or failed are shown but not selectable.
- **Right column:** `QueryPanel` — a question input, submit button, loading state, the generated answer, and a `SourceList` showing each cited source's document name, page number, and relevance score.

Error states covered: empty question (validated client-side before the request is sent), backend unreachable or a failed query (surfaced as an inline error message), and no document selected (the panel explains what to do instead of showing an empty form). No PDF viewer or highlight-on-click was built — out of scope per the Phase 5 brief.

## Phase 6 — Evaluation

### Methodology

`backend/eval/dataset.json` holds 22 questions written against the sample document (`sample_data/HDFC_Bank_Q4FY26_Results.pdf`), with the expected source page recorded for each grounded question. 19 questions are grounded (factual numbers, financial metrics, comparisons within the document, one "why" explanation) and 3 are deliberately unanswerable from the document (a future election, a live stock price, ESG initiatives — none of which appear in a Q4 results deck).

`backend/eval/evaluate_rag.py` runs each question against a live backend and measures:

- **Retrieval Recall@K** — does the expected page appear among the top-K chunks `POST /api/retrieval/search` returns? (K = the server's configured `TOP_K`, 5 by default.)
- **Citation Accuracy** — for every chunk cited in a `POST /api/query` answer, was that chunk actually part of that question's retrieval results? This catches fabricated citations — a cited `chunk_id` that doesn't trace back to a real retrieval hit would fail this check.
- **Unsupported-question proxy** — the top hybrid retrieval score for each unanswerable question, checked against a low-confidence threshold.

Run it yourself:

```bash
cd backend
python eval/evaluate_rag.py --base-url http://localhost:8000
```

### Results (measured, this run)

- **Retrieval Recall@5:** 84.2% (16/19)
- **Citation Accuracy:** 100.0% (95/95 citations traced to real retrieved chunks)
- **Unsupported Questions — Retrieval Confidence Proxy:** 0/3 scored below the 0.15 threshold

The 3 misses on Recall@5 were all questions whose expected page (2) holds several closely related numbers (GNPA, PAT, RoA, RoE, EPS) — the hybrid ranker sometimes preferred a page with a stronger keyword match on a different phrasing of the same metric instead.

### A limitation worth being upfront about

The unsupported-question proxy is not meaningful in the default configuration. All three unsupported questions returned the exact same hybrid score (0.600), which means the local, deterministic hashing embedding (`EMBEDDING_PROVIDER=local`) isn't discriminating between "this question relates to the document" and "this question doesn't" — it's a placeholder for exercising the pipeline shape, not a real semantic signal. Getting a real unsupported-question measurement requires two things this repo intentionally stops short of by default: `EMBEDDING_PROVIDER=openai` for real semantic embeddings, and `LLM_PROVIDER=openai` so the model itself can decline to answer instead of returning a canned string. Do not present the 0/3 "confident" result as "the system doesn't know when it doesn't know" — it means the opposite: with local providers, this prototype currently can't tell.

### Limitations of this evaluation

- 22 questions over a single 9-page synthetic sample document — not a production-scale or externally validated benchmark.
- Recall@K is judged on page-level overlap, not chunk-level precision.
- Citation Accuracy checks traceability (a citation points to a real chunk from that question's retrieval), not whether the citation is the best possible source — a looser bar than full groundedness verification.
- No inter-annotator agreement or external review of the expected answers — they were derived directly from the source PDF text.

## Phase 7 — Finalization

### Final verification checklist

**Functionality** — all verified against a live local Postgres+pgvector instance (not mocks):

- [x] Upload works (`POST /api/documents/upload`)
- [x] PDF processing works (9/9 pages extracted from the sample PDF)
- [x] Chunking works (page number + section preserved per chunk)
- [x] Embeddings work (384-dim vectors written to `document_chunks.embedding`)
- [x] pgvector works (HNSW cosine-similarity index, confirmed via `\d document_chunks`)
- [x] PostgreSQL FTS works (generated tsvector column + GIN index)
- [x] Hybrid retrieval works (`POST /api/retrieval/search`, correct top-ranked chunk on multiple test queries)
- [x] LLM pipeline works (`POST /api/query` — retrieval → context → prompt → answer → citations; real prose answers require `LLM_PROVIDER=openai` and a key)
- [x] Citations work (100% of cited chunks traced back to a real retrieval hit — see Phase 6)
- [x] Frontend works (builds clean, two-column research UI, calls the real API)

**Engineering**

- [x] Clean architecture (`api/` `core/` `db/` `models/` `schemas/` `services/` separation, unchanged from Phase 1)
- [x] Environment variables (no secrets hardcoded in application code — see note below on `.env`)
- [x] Error handling (upload validation, processing-failure status, empty-question/backend-unreachable states in the UI)
- [x] Tests (78 passed, 3 skipped — the 3 are OpenAI-provider tests that need a real API key)
- [x] Evaluation (Phase 6 — Recall@5 84.2%, Citation Accuracy 100%, documented honestly including the retrieval-confidence-proxy limitation)
- [x] Documentation (this README)

**Scope** — confirmed NOT present, matching the brief:

- [x] No authentication / multi-user platform
- [x] No voice
- [x] No complex/financial-analytics dashboard
- [x] No complete NotebookLM clone
- [x] No unnecessary microservices or production-scale infrastructure

### Issues found and fixed during finalization

1. **Leaked credential:** `backend/.env` (committed inside the working copy, not `.env.example`) contained a live Neon Postgres connection string with a real password. Removed from active use; this password must be rotated before the repo is shared, since it was sitting in plaintext in an uploaded archive.
2. **No `.gitignore` existed anywhere in the project.** Without one, `git add .` would have committed the leaked `.env`, `node_modules/`, the Python `venv/`, and uploaded user PDFs. Added a root `.gitignore` covering all of these.
3. **Ingestion bug:** the `DocumentChunk.content_tsv` column is a Postgres `GENERATED ALWAYS` column (see migration 0003), but the SQLAlchemy model mapped it as a normal nullable column — every insert therefore sent an explicit `NULL` for it, which Postgres rejects for generated columns. Every upload silently got stuck in `processing` forever. Fixed by marking the column `Computed(...)` in the ORM model, so SQLAlchemy excludes it from INSERT/UPDATE and fetches the DB-computed value back via `RETURNING`.
4. **Migration/model drift:** the HNSW (embedding) and GIN (content_tsv) indexes were created via raw SQL in migration 0003 but never declared on the SQLAlchemy model. `alembic check` flagged this — the next `alembic revision --autogenerate` would have proposed dropping both indexes. Fixed by declaring them in `DocumentChunk.__table_args__`; `alembic check` now reports no pending changes.
5. **Frontend `node_modules` were platform-specific** (built for a different OS) and failed to run. Reinstalled clean — not a code issue, just an artifact of the delivered archive.

None of these were caught by the existing 78-test suite, since it exercises the app through mocked/unit-level boundaries rather than a real Postgres instance with real generated columns and real indexes — worth keeping in mind: passing tests here means the code logic is right, not that the database interaction is right. Consider adding at least one integration test that runs a real upload against a real Postgres+pgvector instance in CI, if that's feasible before the demo.

## What's next (not part of this repo's scope)

- Add a real integration test (upload → ingest → embed → retrieve) against a live Postgres+pgvector instance in CI, since the current suite only exercises mocked/unit-level boundaries.
- Re-run the Phase 6 evaluation with `EMBEDDING_PROVIDER=openai` and `LLM_PROVIDER=openai` to get a meaningful unsupported-question measurement and real end-to-end answer quality numbers.
- Build a Phase 3 retrieval frontend (currently API-only) and consider a PDF viewer with highlight-on-click, both explicitly out of scope so far.
- Reranking, multi-turn chat, and authentication remain unimplemented and are candidates for future phases.
