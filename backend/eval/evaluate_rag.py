"""
Phase 6 — RAG Evaluation.

Runs the evaluation dataset (eval/dataset.json) against a running instance
of the SentiNews Finance RAG backend and reports measured metrics:

  * Retrieval Recall@K       — does the expected page appear in the top-K
                                 retrieved chunks for each grounded question?
  * Citation Accuracy        — does every chunk_id cited in a /api/query
                                 answer correspond to a real chunk that was
                                 actually retrieved for that document (never
                                 a fabricated citation)?
  * Unsupported Questions    — a confidence proxy for whether the retrieval
                                 layer signals "no good evidence" on
                                 questions the document cannot answer.

IMPORTANT — honest scope of this script:
This prototype ships with LLM_PROVIDER=local by default (see backend
README), which returns a fixed placeholder string rather than a real
generated answer. Recall@K and Citation Accuracy are measured on the
retrieval layer and are meaningful regardless of LLM provider. The
"unsupported question" check, however, can only truly be evaluated at the
*answer* level with a real LLM (LLM_PROVIDER=openai) — with the local
provider this script instead reports the retrieval-confidence proxy
(top hybrid score) and labels it as such. Do not read the local-provider
numbers as "the LLM correctly refused" — they are not that.

Usage:
    python evaluate_rag.py [--base-url http://localhost:8000] [--top-k 5]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import httpx

DATASET_PATH = Path(__file__).parent / "dataset.json"

# Below this hybrid score, we treat retrieval as "no confident evidence" —
# used only for the unsupported-question proxy check, not for grounded
# questions.
UNSUPPORTED_SCORE_THRESHOLD = 0.15


def load_dataset() -> dict[str, Any]:
    with DATASET_PATH.open() as f:
        return json.load(f)


def find_document_id(client: httpx.Client, filename: str) -> str:
    resp = client.get("/api/documents")
    resp.raise_for_status()
    for doc in resp.json():
        if doc["filename"] == filename and doc["status"] == "processed":
            return doc["id"]
    raise SystemExit(
        f"No processed document named '{filename}' found. "
        f"Upload it via POST /api/documents/upload first."
    )


def run_retrieval(
    client: httpx.Client, document_id: str, question: str, top_k: int
) -> list[dict[str, Any]]:
    # The retrieval API returns results at the server's configured TOP_K
    # (see backend/.env); this script's --top-k flag documents/labels the
    # value used for Recall@K rather than overriding it per-request.
    resp = client.post(
        "/api/retrieval/search",
        json={"document_id": document_id, "query": question},
    )
    resp.raise_for_status()
    return resp.json()["results"]


def run_query(client: httpx.Client, document_id: str, question: str) -> dict[str, Any]:
    resp = client.post(
        "/api/query", json={"document_id": document_id, "question": question}
    )
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the SentiNews RAG pipeline")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    dataset = load_dataset()
    questions = dataset["questions"]
    grounded = [q for q in questions if q["type"] != "unsupported"]
    unsupported = [q for q in questions if q["type"] == "unsupported"]

    client = httpx.Client(base_url=args.base_url, timeout=30.0)

    try:
        document_id = find_document_id(client, dataset["document_filename"])
    except httpx.ConnectError:
        print(f"Could not connect to backend at {args.base_url}. Is it running?")
        sys.exit(1)

    # --- Retrieval Recall@K + Citation Accuracy (grounded questions) -----
    recall_hits = 0
    citation_checks = 0
    citation_ok = 0
    per_question_rows: list[str] = []

    for q in grounded:
        retrieved = run_retrieval(client, document_id, q["question"], args.top_k)
        retrieved_pages = {r["page_number"] for r in retrieved}
        retrieved_chunk_ids = {r["chunk_id"] for r in retrieved}
        hit = q["expected_page"] in retrieved_pages
        recall_hits += int(hit)

        query_result = run_query(client, document_id, q["question"])
        sources = query_result["sources"]
        # Fabricated citation = a cited chunk_id that wasn't actually part
        # of that same question's retrieval results.
        for src in sources:
            citation_checks += 1
            if src["chunk_id"] in retrieved_chunk_ids:
                citation_ok += 1

        per_question_rows.append(
            f"  [{'HIT ' if hit else 'MISS'}] {q['id']}: {q['question']} "
            f"(expected p.{q['expected_page']}, retrieved pages {sorted(retrieved_pages)})"
        )

    recall_at_k = recall_hits / len(grounded) if grounded else 0.0
    citation_accuracy = citation_ok / citation_checks if citation_checks else 0.0

    # --- Unsupported-question proxy check ---------------------------------
    unsupported_rows: list[str] = []
    unsupported_low_confidence = 0
    for q in unsupported:
        retrieved = run_retrieval(client, document_id, q["question"], args.top_k)
        top_score = max((r["hybrid_score"] for r in retrieved), default=0.0)
        low_confidence = top_score < UNSUPPORTED_SCORE_THRESHOLD
        unsupported_low_confidence += int(low_confidence)
        unsupported_rows.append(
            f"  [{'LOW-CONF' if low_confidence else 'confident'}] "
            f"{q['id']}: {q['question']} (top hybrid score {top_score:.3f})"
        )

    # --- Report -------------------------------------------------------------
    print("RAG Evaluation")
    print("-" * 40)
    print(f"Document: {dataset['document_filename']}")
    print(f"Questions: {len(questions)} ({len(grounded)} grounded, {len(unsupported)} unsupported)")
    print()
    print(f"Retrieval Recall@{args.top_k}: {recall_at_k * 100:.1f}% ({recall_hits}/{len(grounded)})")
    for row in per_question_rows:
        print(row)
    print()
    print(f"Citation Accuracy: {citation_accuracy * 100:.1f}% ({citation_ok}/{citation_checks} citations traced to real retrieved chunks)")
    print()
    print(
        f"Unsupported Questions — Retrieval Confidence Proxy "
        f"(NOT an LLM-refusal measurement — see script docstring): "
        f"{unsupported_low_confidence}/{len(unsupported)} scored below "
        f"the {UNSUPPORTED_SCORE_THRESHOLD} hybrid-score threshold"
    )
    for row in unsupported_rows:
        print(row)


if __name__ == "__main__":
    main()
