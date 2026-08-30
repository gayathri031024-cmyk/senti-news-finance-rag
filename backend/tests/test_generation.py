import uuid

from app.services.generation.context_builder import build_context
from app.services.generation.prompts import SYSTEM_PROMPT, build_user_prompt
from app.services.retrieval.types import Candidate


def _candidate(content, page=1, section=None):
    return Candidate(
        chunk_id=uuid.uuid4(),
        page_number=page,
        content=content,
        section=section,
        vector_score=0.9,
        keyword_score=0.5,
        hybrid_score=0.7,
    )


def test_build_context_includes_page_and_content():
    candidates = [_candidate("Net profit rose to Rs. 17,000 crore.", page=5, section="Profitability")]
    context = build_context(candidates)
    assert "Page 5" in context
    assert "Profitability" in context
    assert "Net profit rose to Rs. 17,000 crore." in context


def test_build_context_joins_multiple_chunks_distinctly():
    candidates = [
        _candidate("First chunk content.", page=1),
        _candidate("Second chunk content.", page=2),
    ]
    context = build_context(candidates)
    assert "First chunk content." in context
    assert "Second chunk content." in context
    assert context.index("First chunk content.") < context.index("Second chunk content.")


def test_build_context_empty_list_returns_empty_string():
    assert build_context([]) == ""


def test_system_prompt_states_grounding_rules():
    lowered = SYSTEM_PROMPT.lower()
    assert "only" in lowered
    assert "not present" in lowered or "not found" in lowered or "could not be found" in lowered
    assert "fabricate" in lowered or "invent" in lowered


def test_user_prompt_includes_question_and_context():
    prompt = build_user_prompt(question="What was the GNPA?", context="[Page 3]\nGNPA was 1.2%.")
    assert "What was the GNPA?" in prompt
    assert "GNPA was 1.2%." in prompt


def test_user_prompt_handles_empty_context_explicitly():
    prompt = build_user_prompt(question="What was the GNPA?", context="")
    assert "no relevant excerpts" in prompt.lower()
