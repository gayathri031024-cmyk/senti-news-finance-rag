import uuid

from app.services.retrieval.hybrid import (
    combine_scores,
    deduplicate,
    hybrid_search,
    normalize_scores,
    rank,
    retrieve_candidates,
    top_k,
)
from app.services.retrieval.types import Candidate, RawResult


def _raw(chunk_id, source, score, page=1):
    return RawResult(
        chunk_id=chunk_id, source=source, score=score, page_number=page,
        content=f"content for {chunk_id}", section=None,
    )


def test_retrieve_candidates_concatenates_both_lists():
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    vector_results = [_raw(c1, "vector", 0.9)]
    keyword_results = [_raw(c2, "keyword", 0.5)]

    combined = retrieve_candidates(vector_results, keyword_results)
    assert len(combined) == 2


def test_deduplicate_merges_chunk_found_by_both_methods():
    c1 = uuid.uuid4()
    candidates = retrieve_candidates(
        [_raw(c1, "vector", 0.9)],
        [_raw(c1, "keyword", 0.7)],
    )
    merged = deduplicate(candidates)

    assert len(merged) == 1
    assert merged[0].vector_score == 0.9
    assert merged[0].keyword_score == 0.7


def test_deduplicate_keeps_chunks_found_by_only_one_method_separate():
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    candidates = retrieve_candidates(
        [_raw(c1, "vector", 0.9)],
        [_raw(c2, "keyword", 0.7)],
    )
    merged = deduplicate(candidates)

    assert len(merged) == 2
    by_id = {c.chunk_id: c for c in merged}
    assert by_id[c1].vector_score == 0.9
    assert by_id[c1].keyword_score is None
    assert by_id[c2].keyword_score == 0.7
    assert by_id[c2].vector_score is None


def test_normalize_scores_min_max_to_0_1_range():
    candidates = [
        Candidate(chunk_id=uuid.uuid4(), page_number=1, content="a", section=None, vector_score=0.2),
        Candidate(chunk_id=uuid.uuid4(), page_number=2, content="b", section=None, vector_score=0.8),
        Candidate(chunk_id=uuid.uuid4(), page_number=3, content="c", section=None, vector_score=0.5),
    ]
    normalized = normalize_scores(candidates)

    assert normalized[0].vector_score == 0.0  # was the minimum
    assert normalized[1].vector_score == 1.0  # was the maximum
    assert 0.0 < normalized[2].vector_score < 1.0


def test_normalize_scores_fills_missing_score_with_zero():
    candidates = [
        Candidate(chunk_id=uuid.uuid4(), page_number=1, content="a", section=None, vector_score=0.5),
    ]
    normalized = normalize_scores(candidates)

    assert normalized[0].keyword_score == 0.0


def test_normalize_scores_constant_values_all_become_one():
    """A tie shouldn't be arbitrarily zeroed — all-equal values are
    all equally relevant, not all irrelevant."""
    candidates = [
        Candidate(chunk_id=uuid.uuid4(), page_number=1, content="a", section=None, vector_score=0.5),
        Candidate(chunk_id=uuid.uuid4(), page_number=2, content="b", section=None, vector_score=0.5),
    ]
    normalized = normalize_scores(candidates)

    assert all(c.vector_score == 1.0 for c in normalized)


def test_combine_scores_applies_weights():
    candidates = [
        Candidate(
            chunk_id=uuid.uuid4(), page_number=1, content="a", section=None,
            vector_score=1.0, keyword_score=0.0,
        ),
    ]
    combined = combine_scores(candidates, vector_weight=0.6, keyword_weight=0.4)

    assert combined[0].hybrid_score == 0.6


def test_rank_orders_descending_by_hybrid_score():
    candidates = [
        Candidate(chunk_id=uuid.uuid4(), page_number=1, content="a", section=None, hybrid_score=0.2),
        Candidate(chunk_id=uuid.uuid4(), page_number=2, content="b", section=None, hybrid_score=0.9),
        Candidate(chunk_id=uuid.uuid4(), page_number=3, content="c", section=None, hybrid_score=0.5),
    ]
    ranked = rank(candidates)

    assert [c.hybrid_score for c in ranked] == [0.9, 0.5, 0.2]


def test_top_k_truncates():
    candidates = [
        Candidate(chunk_id=uuid.uuid4(), page_number=i, content="x", section=None, hybrid_score=1.0)
        for i in range(10)
    ]
    assert len(top_k(candidates, 3)) == 3


def test_hybrid_search_end_to_end_ranks_dual_hit_highest():
    c1, c2, c3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    vector_results = [_raw(c1, "vector", 0.9), _raw(c2, "vector", 0.5)]
    keyword_results = [_raw(c1, "keyword", 0.8), _raw(c3, "keyword", 0.4)]

    results = hybrid_search(
        vector_results, keyword_results, vector_weight=0.6, keyword_weight=0.4, k=5
    )

    assert results[0].chunk_id == c1  # found by both methods -> ranks first
    assert len(results) == 3  # 3 unique chunks across both result sets


def test_hybrid_search_respects_top_k():
    vector_results = [_raw(uuid.uuid4(), "vector", 0.9 - i * 0.1) for i in range(5)]
    results = hybrid_search(vector_results, [], vector_weight=0.6, keyword_weight=0.4, k=2)

    assert len(results) == 2
