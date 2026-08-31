# SentiNews — Finance Research Assistant

> Finance-focused RAG application for asking grounded questions about uploaded financial documents.

**Live Demo:** https://senti-news-finance-rag-1.onrender.com/

**Backend API:**https://senti-news-finance-rag.onrender.com/docs

**GitHub:** https://github.com/gayathri031024-cmyk/senti-news-finance-rag

SentiNews is a finance-focused RAG (Retrieval-Augmented Generation) application that lets users upload financial documents and ask questions grounded in the uploaded content.

The system extracts and cleans PDF text, creates page-scoped chunks, indexes them using both semantic and keyword search, retrieves relevant evidence, and generates answers with citations pointing back to the source document.

It is a technically focused prototype demonstrating document ingestion, hybrid retrieval, grounded generation, citation traceability, and RAG evaluation. It is not a production system — there's no authentication, multi-user support, or production-scale infrastructure — but every layer of the pipeline is real, tested, and independently verifiable.

## What It Does

- Upload financial PDF documents
- Extract text page-by-page
- Clean and chunk financial content
- Preserve page-level source attribution
- Generate embeddings for semantic retrieval
- Perform PostgreSQL full-text keyword search
- Combine semantic and keyword retrieval using hybrid ranking
- Build grounded context from retrieved chunks
- Generate natural-language answers using Groq as the LLM provider
- Return citations tied to actually retrieved document chunks
- Evaluate retrieval recall and citation traceability
- Provide a simple research interface for uploading documents and asking questions

## Live Demo

The deployed application can be used to:

1. Upload a financial PDF.
2. Wait for the document status to become `Processed`.
3. Select the uploaded document.
4. Ask a financial question.
5. Receive a grounded answer with source citations.

### Example

Sample document:

`HDFC_Bank_Q4FY26_Results.pdf`

Example questions:

- What was HDFC Bank's net profit?
- What was the net interest income for Q4 FY26?
- What was the GNPA ratio as of March 2026?
- What was the capital adequacy ratio as of March 2026?
- How did provisions change quarter-on-quarter in Q4 FY26?

The answer is generated from retrieved document context, and the API returns the source document, page number, chunk ID, and relevance score for the retrieved evidence.

## Architecture

```
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
                    Groq LLM
                         │
                         ▼
               Grounded Answer
                         │
                         ▼
                     Citations
```

## Key Technical Features

### Document Ingestion

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

The Document row is created and returned to the caller immediately (status: `processing`); extraction/cleaning/chunking run afterward as a FastAPI background task. This keeps the upload request fast without introducing a separate task queue, which is out of scope for a prototype of this size.

**Supported file type & size limit:** PDF only, validated three ways: file extension, Content-Type header, and a magic-byte check (`%PDF-` at the start of the file) — headers alone are client-supplied and easy to spoof. Default size limit is 25MB (`MAX_FILE_SIZE_MB`).

**Processing statuses:** `uploaded → processing → processed | failed`. A document only reaches `failed` with an `error_message` explaining why (malformed PDF, no extractable text/scanned PDF, or an unexpected error) — it never gets stuck in `processing`; the pipeline's outer error handler guarantees a terminal status is always written.

**Chunking strategy & defaults:** `CHUNK_SIZE=1200`, `CHUNK_OVERLAP=200` (characters). 1200 characters (~200–250 words) is enough to hold a paragraph or a small financial table together as one coherent unit for later retrieval, without being so large that a chunk mixes multiple unrelated topics. 200 characters of overlap (~15–20%) keeps a sentence that falls right on a chunk boundary from losing its surrounding context.

Chunks never span multiple pages. Each chunk belongs to exactly one `page_number`. This trades a small amount of chunk-size uniformity (a page ending mid-thought produces a shorter final chunk) for chunk-to-page attribution that's always exact.

Splitting prefers sentence/paragraph boundaries (via a regex on `. ! ?` + whitespace and blank lines) over mid-sentence cuts. A single sentence longer than `CHUNK_SIZE` (rare, but dense tables can produce this) falls back to a hard split rather than being left oversized. A trailing fragment shorter than ~120 characters is merged into the previous chunk instead of being stored as a near-empty chunk.

Lightweight section detection: if a page's first non-empty line looks like a heading (short, no terminal punctuation), it's stored as `section` on that page's chunks.

**Cleaning:** Whitespace is normalized (collapsed blank lines, collapsed runs of spaces, trimmed trailing whitespace). Lines that repeat verbatim across most pages (e.g. "Confidential", a running report title) are detected and stripped as headers/footers. Numbers, %, ₹/$/other currency symbols, and financial terminology are never touched by cleaning — only whitespace and identified repeated lines are removed.

### Hybrid Retrieval

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

Chunk embeddings are generated automatically at the end of ingestion (`services/ingestion/processor.py`), right after chunks are stored — no separate step needed. A chunk that fails to embed (e.g. no `EMBEDDING_API_KEY` configured for a remote provider) keeps `embedding = NULL` and simply won't surface in vector search; keyword search still works over it. This is a deliberate choice so an embedding problem never breaks the ingestion guarantee — a document that extracts and chunks successfully still reaches `processed`.

**Embedding provider** — configurable via `EMBEDDING_PROVIDER`:

- **local (default)** — a dependency-free, deterministic embedding using the "hashing trick" (feature hashing, as in scikit-learn's `HashingVectorizer`): stopwords removed, remaining tokens hashed to a fixed-size vector, L2-normalized. No API key, no network call, no model download. Limitation: this is word-overlap, not learned semantics — it has no notion of synonyms or paraphrase (e.g. "how much did the bank lend" won't match "advances" the way a trained model would). It exists purely so the retrieval architecture (storage, indexing, cosine similarity, hybrid combination) can be built and tested without external dependencies. Financial queries in this domain are often keyword-heavy already (ratio names, line items, abbreviations like "GNPA"), which is why this stand-in still produces sensible top-1 results in practice (see Verification below) — but it is not a substitute for real semantic search.
- **openai** — calls OpenAI's `/v1/embeddings` endpoint directly (no SDK dependency), requesting `EMBEDDING_DIMENSIONS` explicitly so output size always matches the pgvector column regardless of which `text-embedding-3-*` model is configured. Requires `EMBEDDING_API_KEY`. This is the path for real semantic search quality.

Both implement the same `embed_texts(list[str]) -> list[list[float]]` interface (`services/embeddings/base.py`), so swapping providers is a one-variable change — no code changes needed.

**pgvector storage:** `document_chunks.embedding` is a `vector(384)` column, with an HNSW index on cosine distance (`vector_cosine_ops`). HNSW was chosen over ivfflat because it needs no training/"lists" tuning step and performs reasonably without a representative data sample present at index-build time — ivfflat's clustering quality depends on that, which doesn't fit a system where documents are uploaded incrementally.

`EMBEDDING_DIMENSIONS` must match whatever the configured model actually outputs. The column's dimension is fixed at migration time — switching to a differently-sized model later means writing a new migration (`ALTER COLUMN embedding TYPE vector(N)`), not just changing the env var.

**PostgreSQL full-text search:** `document_chunks.content_tsv` is a generated column (`GENERATED ALWAYS AS (to_tsvector('english', content)) STORED`), indexed with GIN. Keyword search uses `plainto_tsquery('english', ...)` so arbitrary user query text (including multi-word phrases like "net interest income") works without requiring tsquery operator syntax from the caller, ranked with `ts_rank`.

**Hybrid ranking:** `services/retrieval/hybrid.py` implements the pipeline as six pure, independently-testable functions, run in this order:

1. `retrieve_candidates()` — concatenate vector + keyword hits
2. `deduplicate()` — merge into one Candidate per chunk_id
3. `normalize_scores()` — min-max normalize vector/keyword scores independently
4. `combine_scores()` — weighted sum: `hybrid = VECTOR_WEIGHT·vec + KEYWORD_WEIGHT·kw`
5. `rank()` — sort descending by hybrid_score
6. `top_k()` — truncate to `TOP_K`

A chunk found by only one method gets 0.0 (post-normalization) for the other — it wasn't judged relevant by that method, not indeterminate. Vector and keyword scores are normalized separately before combining, since cosine similarity and ts_rank are on unrelated scales.

**Weight reasoning** (`VECTOR_WEIGHT=0.6`, `KEYWORD_WEIGHT=0.4`): financial questions in this domain are often precise — exact ratio names, line-item labels, abbreviations ("GNPA", "NIM") — where a literal keyword match is a strong, reliable signal. But queries are also often phrased differently from how the document states it, where only semantic similarity finds the right chunk. A 0.6/0.4 split leans toward semantic recall as the primary driver while keeping keyword strong enough to matter. This is not tuned against a labeled relevance eval set — it's a reasoned starting point, which is exactly why it's an environment variable rather than a constant.

### LLM Generation

The live application uses **Groq** for grounded answer generation.

The model receives the retrieved document context and the user's question and is instructed to: answer only from the supplied evidence; never invent figures, dates, or facts; never reference a page/citation beyond what's in the context; explicitly say when the answer isn't present rather than guessing (including for off-document questions, e.g. predictions or unrelated topics); and clearly label any calculation/inference (e.g. a computed percentage change) as distinct from a fact stated directly in the document. The system prompt encoding these rules lives in `services/generation/prompts.py`.

Configuration:

```env
LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-120b
LLM_API_KEY=<your-groq-api-key>
```

The API key is supplied through the deployment environment and is not committed to the repository.

Provider implementations follow the same swappable-provider pattern used for embeddings (`services/llm/base.py` defines the `LLMProvider` interface; `services/llm/factory.py` selects an implementation):

- **local (default)** — a dependency-free, no-API-key placeholder (`services/llm/local_provider.py`). It does not read the retrieved context and does not generate a real answer; it returns a fixed string saying so. It exists only so the whole pipeline (retrieval → context → prompt → response → citations) can be wired up and demoed with zero external dependencies. It must never be used as evidence that grounding/anti-hallucination behavior works — see Verification below.
- **groq** — calls Groq's OpenAI-compatible chat completions endpoint directly (no SDK dependency), with `temperature=0` since this is a grounded-answer task over fixed context, not creative writing. Requires `LLM_API_KEY`.

If retrieval returns no candidates at all, the LLM is never called — the endpoint immediately returns a fixed "not found in the document" answer with an empty sources list. This makes "say clearly when the answer isn't in the document" a property of the retrieval step for the no-context case, not something the model has to remember to do unprompted every time.

### Citation Traceability

Citations are never parsed out of the model's text. `schemas/query.py`'s `SourceCitation` list is built directly from the `Candidate` objects the hybrid retrieval layer actually returned — document name, page number, chunk ID, and hybrid relevance score. If the model's answer text mentions a page number, that mention is untrusted prose; the citations the API returns always come from real retrieval, so a citation can never be invented (see `test_query_only_cites_actually_retrieved_chunks` in `tests/test_query_api.py`).

### Research Interface

The frontend (`frontend/src/App.tsx`) is a two-column layout:

- **Left column:** `DocumentUpload` and `DocumentList`, selectable — clicking a processed document makes it the active document for the research panel. Documents still processing or failed are shown but not selectable.
- **Right column:** `QueryPanel` — a question input, submit button, loading state, the generated answer, and a `SourceList` showing each cited source's document name, page number, and relevance score.

Error states covered: empty question (validated client-side before the request is sent), backend unreachable or a failed query (surfaced as an inline error message), and no document selected (the panel explains what to do instead of showing an empty form). No PDF viewer or highlight-on-click is built — out of scope for now.

## Evaluation

Measured against 22 questions over the 9-page HDFC Bank Q4 FY26 sample document (`backend/eval/dataset.json`), with the expected source page recorded for each grounded question. 19 questions are grounded (factual numbers, financial metrics, comparisons within the document, one "why" explanation) and 3 are deliberately unanswerable from the document (a future election, a live stock price, ESG initiatives — none of which appear in a Q4 results deck).

`backend/eval/evaluate_rag.py` runs each question against a live backend and measures:

- **Retrieval Recall@K** — does the expected page appear among the top-K chunks `POST /api/retrieval/search` returns? (K = the server's configured `TOP_K`, 5 by default.)
- **Citation Accuracy** — for every chunk cited in a `POST /api/query` answer, was that chunk actually part of that question's retrieval results? This catches fabricated citations — a cited chunk_id that doesn't trace back to a real retrieval hit would fail this check.
- **Unsupported-question proxy** — the top hybrid retrieval score for each unanswerable question, checked against a low-confidence threshold.

Run it yourself:

```bash
cd backend
python eval/evaluate_rag.py --base-url http://localhost:8000
```

### Evaluation Results

- **Retrieval Recall@5:** 84.2% (16/19)
- **Citation Accuracy:** 100.0% (95/95 citations traced to real retrieved chunks)

The evaluation also includes 3 deliberately unsupported questions. The current evaluation shows that the local hashing-based embedding provider is not reliable enough for measuring out-of-domain confidence: all 3 unsupported questions received a hybrid score of 0.600. Therefore, this result is **not presented as evidence of reliable hallucination detection**.

The application uses Groq for live answer generation, while local deterministic embeddings remain the default retrieval configuration for this prototype.

The 3 misses on Recall@5 were all questions whose expected page (2) holds several closely related numbers (GNPA, PAT, RoA, RoE, EPS) — the hybrid ranker sometimes preferred a page with a stronger keyword match on a different phrasing of the same metric instead.

A limitation worth being upfront about: the unsupported-question proxy is not meaningful in the default configuration. All three unsupported questions returned the exact same hybrid score (0.600), which means the local, deterministic hashing embedding (`EMBEDDING_PROVIDER=local`) isn't discriminating between "this question relates to the document" and "this question doesn't" — it's a placeholder for exercising the pipeline shape, not a real semantic signal. Getting a real unsupported-question measurement requires real semantic embeddings (`EMBEDDING_PROVIDER=openai`) and a live LLM that can decline to answer instead of returning a canned string. The 0/3 "confident" result should not be read as "the system knows when it doesn't know" — it means the opposite: with the local embedding provider, this prototype currently can't tell.

Other limitations of this evaluation: 22 questions over a single 9-page synthetic sample document is not a production-scale or externally validated benchmark; Recall@K is judged on page-level overlap, not chunk-level precision; Citation Accuracy checks traceability (a citation points to a real chunk from that question's retrieval), not whether the citation is the best possible source; and there was no inter-annotator agreement or external review of the expected answers — they were derived directly from the source PDF text.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React, TypeScript, Vite, Tailwind CSS v4 |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy, Alembic, pypdf |
| Database | PostgreSQL + pgvector |
| LLM | Groq (OpenAI-compatible chat completions API) |
| Local infra | Docker Compose (database only — backend/frontend run locally) |

## Project Structure

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
│   │   │   └── query.py              # POST /api/query
│   │   ├── core/config.py            # chunking, upload, embedding, hybrid-ranking, LLM settings
│   │   ├── db/
│   │   │   ├── session.py
│   │   │   └── repository.py         # all DB access for documents/chunks
│   │   ├── models/
│   │   │   ├── document.py
│   │   │   └── chunk.py              # + embedding vector, content_tsv
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
│   │       ├── llm/
│   │       │   ├── base.py           # LLMProvider interface
│   │       │   ├── local_provider.py # no-op / no-API-key placeholder
│   │       │   ├── groq_provider.py
│   │       │   └── factory.py
│   │       └── generation/
│   │           ├── context_builder.py  # ranked Candidates -> LLM context text
│   │           └── prompts.py           # system prompt (grounding rules) + user prompt template
│   ├── alembic/versions/
│   │   ├── 0001_initial_documents_table.py
│   │   ├── 0002_document_chunks.py
│   │   └── 0003_hybrid_retrieval.py
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
alembic upgrade head        # applies documents, document_chunks, status enum,
                             # embedding vector column, tsvector column
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open the printed local URL — you'll see the connection status badge, the "Upload Financial Document" panel, and the document list on the left, and the research/query panel on the right. Retrieval can also be exercised directly via the API (see the API section below) or the interactive docs at `http://localhost:8000/docs`.

## Configuration

All configuration is read from environment variables — nothing is hardcoded; `.env` files are gitignored. Full list (`backend/.env.example`):

```env
# Ingestion
CHUNK_SIZE=1200
CHUNK_OVERLAP=200
MAX_FILE_SIZE_MB=25
UPLOAD_DIR=storage/uploads

# Embeddings + hybrid retrieval
EMBEDDING_PROVIDER=local        # "local" or "openai"
EMBEDDING_MODEL=local-hashing-v1
EMBEDDING_API_KEY=
EMBEDDING_DIMENSIONS=384
VECTOR_WEIGHT=0.6
KEYWORD_WEIGHT=0.4
TOP_K=5

# RAG generation
LLM_PROVIDER=local              # "local" (placeholder, no key) or "groq"
LLM_MODEL=local-echo-v1
LLM_API_KEY=
```

To enable live generation, set:

```env
LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-120b
LLM_API_KEY=<your-groq-api-key>
```

The key itself is supplied through the `LLM_API_KEY` environment variable at runtime and is never checked into the repository or written into this README.

Uploaded PDFs are stored under `backend/storage/uploads/<document-id>.pdf` (gitignored) so a document can be re-processed later without re-uploading it.

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/documents/upload` | Upload a PDF; returns id, filename, status |
| GET | `/api/documents` | List all documents with page/chunk counts |
| GET | `/api/documents/{id}` | Single document detail, incl. error_message if failed |
| POST | `/api/retrieval/search` | Run hybrid retrieval over a document, no generation |
| POST | `/api/query` | Retrieval + grounded generation with citations |

**POST /api/retrieval/search**

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

The response is self-contained for debugging purposes — it echoes the query and the weights used alongside every chunk's individual vector/keyword/hybrid scores and page number, so retrieval quality can be inspected without cross-referencing server config. Returns 404 if the document doesn't exist, 409 if it hasn't finished processing yet (`status != "processed"`).

**POST /api/query**

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

`POST /api/query` does not duplicate any retrieval logic — it imports and calls the same `semantic_search`, `keyword_search`, and `hybrid_search` functions `/api/retrieval/search` uses, unmodified.

## Verification

### Automated tests

```bash
cd backend
source .venv/bin/activate
pytest -v
```

78 tests total. Parser, cleaner, chunker, embeddings, hybrid-ranking, LLM-provider, and generation (context builder/prompts) tests run against generated PDFs and plain Python data — no database or external API needed. API tests (`test_documents_api.py`, `test_retrieval_api.py`, `test_query_api.py`) monkeypatch the repository/search/LLM layer for the same reason. All tests are deterministic — the local embedding provider (hashing-based) and local LLM provider (placeholder) are the defaults, never a real network call, so test runs never depend on `EMBEDDING_API_KEY`/`LLM_API_KEY` being set or on external API availability/cost. 3 tests are skipped unless a real Groq API key is configured, and 3 more are skipped unless a real database is available:

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

What's verified (offline, mocked/local):

- `POST /api/query` request/response shape, status codes (200/404/409/422/502), and citation fields.
- Retrieval integration: `/api/query` calls `semantic_search`/`keyword_search`/`hybrid_search` unmodified and passes their results into the context builder.
- Citations always come from actually-retrieved chunks, never from the (mocked) LLM's text — even when the mocked LLM text names a different page.
- The "no retrieval hits → fixed not-found answer, LLM never called" path (covers the mechanism behind the unsupported-question requirement, e.g. "Who will win the 2030 Indian elections?", when retrieval genuinely returns nothing).
- LLM failure handling (502) when the provider raises an error.
- Context builder and prompt template content (pure unit tests).
- The local and groq LLM providers instantiate correctly and the local provider makes no network call.

What requires a live Groq API key and a live database to verify end-to-end:

- That Groq, given the actual retrieved HDFC Bank chunks, produces a correct, non-hallucinated answer to representative financial questions (NII, net profit, GNPA, NNPA, advances, provisions, reasons for profit growth).
- That Groq correctly declines to answer when retrieval returns some (irrelevant) context for an off-topic question, as opposed to the always-safe "zero retrieval hits" path already verified.
- End-to-end curl verification against a live database with `LLM_PROVIDER=groq` and a real key.

To run live verification:

```bash
# in backend/.env
LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-120b
LLM_API_KEY=<your Groq API key>
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

### Real PDF verification

`sample_data/HDFC_Bank_Q4FY26_Results.pdf` is a 9-page PDF built from real, current HDFC Bank Q4 FY26 figures (net interest income, PAT, GNPA/NNPA, deposits, EPS, capital adequacy, etc.), sourced from the bank's own investor-relations earnings presentation. It's a generated PDF rather than a scan of the original filing, but every figure in it is real and it exercises the same dense, tabular financial content the pipeline is meant to handle.

```bash
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@sample_data/HDFC_Bank_Q4FY26_Results.pdf"

curl http://localhost:8000/api/documents/<id-from-response>
```

Once status is `processed`, query Postgres directly to confirm chunks and embeddings landed correctly:

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

Try retrieval with a few different financial questions — e.g. "What is the GNPA ratio?", "What is the capital adequacy ratio?" — and check that the top-ranked chunk's `page_number`/`content` actually answers the question.

## Limitations

**Functional scope:** no authentication or multi-user support, no voice interface, no financial-analytics dashboard, no PDF viewer or highlight-on-click, no reranking, and no multi-turn/chat conversation. All of these are deliberate scope cuts for a focused prototype rather than oversights.

**Evaluation scope:** the retrieval-recall and citation-accuracy numbers above are measured against a single 9-page synthetic sample document with 22 hand-written questions — informative, but not a production-scale or externally validated benchmark. The unsupported-question confidence proxy is not a reliable out-of-domain detector under the default local embedding provider; treat it as a demonstration of the mechanism, not evidence that the system reliably knows what it doesn't know.

**Implementation notes:**

- Secrets are never hardcoded in application code and `.env` files are gitignored; `backend/.env.example` documents every variable without real values.
- `document_chunks.content_tsv` is a Postgres `GENERATED ALWAYS` column; the ORM model marks it `Computed(...)` so SQLAlchemy excludes it from inserts/updates and reads the database-computed value back instead of sending an explicit value.
- The HNSW (embedding) and GIN (content_tsv) indexes are declared directly on the SQLAlchemy model (`DocumentChunk.__table_args__`) so the ORM and the migrations stay in sync — `alembic check` reports no pending schema drift.
- The test suite (78 tests) exercises the application through mocked/unit-level boundaries; it validates code logic but not real Postgres behavior (generated columns, indexes). The `RUN_DB_INTEGRATION_TESTS=1` suites cover that gap when a real database is available.

## What's Next

- Add integration tests (upload → ingest → embed → retrieve) against a live Postgres+pgvector instance in CI, since the default suite only exercises mocked/unit-level boundaries.
- Re-run the evaluation with `EMBEDDING_PROVIDER=openai` and a live Groq key to get a meaningful unsupported-question measurement and real end-to-end answer-quality numbers.
- Build a dedicated retrieval frontend view (currently API-only for raw retrieval) and consider a PDF viewer with highlight-on-click.
- Reranking, multi-turn chat, and authentication remain unimplemented and are candidates for future work.
