"""
Hybrid retrieval pipeline.

retrieve_candidates() -> deduplicate() -> normalize_scores()
    -> combine_scores() -> rank() -> top_k()

Each stage is a pure function over plain dataclasses (no DB, no I/O),
so each is independently unit-testable and the whole pipeline can be
run in tests without a database.

Weight reasoning (VECTOR_WEIGHT / KEYWORD_WEIGHT, default 0.6 / 0.4):
financial questions in this domain are often precise — exact ratio
names, line-item labels, abbreviations like "GNPA" or "NIM" — where a
literal keyword match is a strong, reliable signal that shouldn't be
diluted. But queries are also often phrased differently from how the
document states it (e.g. "how much did the bank lend out" vs.
"advances"), where only semantic similarity finds the right chunk. A
0.6/0.4 split leans toward semantic recall as the primary driver while
keeping keyword match strong enough to matter — not tuned against a
labeled eval set, just a reasoned starting point. Both are configurable
via environment variables specifically so they can be tuned later
against real query/relevance data.
"""
from app.services.retrieval.types import Candidate, RawResult


def retrieve_candidates(
    vector_results: list[RawResult], keyword_results: list[RawResult]
) -> list[RawResult]:
    """Stage 1: simple concatenation — no merging yet."""
    return [*vector_results, *keyword_results]


def deduplicate(candidates: list[RawResult]) -> list[Candidate]:
    """
    Stage 2: merge raw hits into one Candidate per chunk_id. A chunk
    found by both methods gets both scores; a chunk found by only one
    method has None for the other (handled explicitly in normalize_scores,
    not silently treated as zero here).
    """
    merged: dict = {}
    for result in candidates:
        if result.chunk_id not in merged:
            merged[result.chunk_id] = Candidate(
                chunk_id=result.chunk_id,
                page_number=result.page_number,
                content=result.content,
                section=result.section,
            )
        candidate = merged[result.chunk_id]
        if result.source == "vector":
            candidate.vector_score = result.score
        elif result.source == "keyword":
            candidate.keyword_score = result.score
    return list(merged.values())


def _min_max_normalize(values: list[float]) -> dict[int, float]:
    """Returns {index: normalized_value} for a list, 0..1 range.
    A constant list (all equal, including a single value) normalizes
    to 1.0 for every entry — treated as equally relevant rather than
    arbitrarily zeroed out."""
    if not values:
        return {}
    lo, hi = min(values), max(values)
    if hi == lo:
        return {i: 1.0 for i in range(len(values))}
    return {i: (v - lo) / (hi - lo) for i, v in enumerate(values)}


def normalize_scores(candidates: list[Candidate]) -> list[Candidate]:
    """
    Stage 3: min-max normalize vector and keyword scores independently
    (they're on unrelated scales — cosine similarity vs. ts_rank), so
    Stage 4 can combine them meaningfully. A chunk missing one score
    type gets 0.0 for that type after normalization — it simply wasn't
    found relevant by that method, not indeterminate.
    """
    vector_indices = [i for i, c in enumerate(candidates) if c.vector_score is not None]
    keyword_indices = [i for i, c in enumerate(candidates) if c.keyword_score is not None]

    vector_norm = _min_max_normalize([candidates[i].vector_score for i in vector_indices])
    keyword_norm = _min_max_normalize([candidates[i].keyword_score for i in keyword_indices])

    for pos, idx in enumerate(vector_indices):
        candidates[idx].vector_score = vector_norm[pos]
    for pos, idx in enumerate(keyword_indices):
        candidates[idx].keyword_score = keyword_norm[pos]

    for candidate in candidates:
        if candidate.vector_score is None:
            candidate.vector_score = 0.0
        if candidate.keyword_score is None:
            candidate.keyword_score = 0.0

    return candidates


def combine_scores(
    candidates: list[Candidate], vector_weight: float, keyword_weight: float
) -> list[Candidate]:
    """Stage 4: weighted sum of the (already normalized) scores."""
    for candidate in candidates:
        candidate.hybrid_score = (
            vector_weight * (candidate.vector_score or 0.0)
            + keyword_weight * (candidate.keyword_score or 0.0)
        )
    return candidates


def rank(candidates: list[Candidate]) -> list[Candidate]:
    """Stage 5: sort by hybrid_score, descending."""
    return sorted(candidates, key=lambda c: c.hybrid_score, reverse=True)


def top_k(candidates: list[Candidate], k: int) -> list[Candidate]:
    """Stage 6."""
    return candidates[:k]


def hybrid_search(
    vector_results: list[RawResult],
    keyword_results: list[RawResult],
    vector_weight: float,
    keyword_weight: float,
    k: int,
) -> list[Candidate]:
    """Runs the full pipeline in order — the orchestrator the API uses."""
    candidates = retrieve_candidates(vector_results, keyword_results)
    candidates = deduplicate(candidates)
    candidates = normalize_scores(candidates)
    candidates = combine_scores(candidates, vector_weight, keyword_weight)
    candidates = rank(candidates)
    return top_k(candidates, k)
