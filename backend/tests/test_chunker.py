import pytest

from app.services.ingestion.chunker import chunk_pages
from app.services.ingestion.pdf_parser import PageText


def test_chunk_creation_produces_sequential_indices():
    pages = [PageText(page_number=1, text="Sentence one. Sentence two. Sentence three.")]
    chunks = chunk_pages(pages, chunk_size=1000, chunk_overlap=100)

    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0


def test_long_page_splits_into_multiple_chunks_respecting_size():
    sentence = "This is a financial statement sentence with some numbers 123. "
    long_text = sentence * 40  # well over chunk_size
    pages = [PageText(page_number=1, text=long_text)]

    chunks = chunk_pages(pages, chunk_size=300, chunk_overlap=50)

    assert len(chunks) > 1
    for chunk in chunks:
        # Allow a little slack for the hard-split fallback path.
        assert len(chunk.content) <= 300 + 50


def test_overlap_is_present_between_consecutive_chunks():
    sentence = "Revenue grew by twelve percent this quarter across all segments. "
    long_text = sentence * 30
    pages = [PageText(page_number=1, text=long_text)]

    chunks = chunk_pages(pages, chunk_size=300, chunk_overlap=80)
    assert len(chunks) >= 2

    tail_of_first = chunks[0].content[-40:]
    assert tail_of_first[:20] in chunks[1].content or tail_of_first in chunks[1].content


def test_page_metadata_preserved_across_pages():
    pages = [
        PageText(page_number=1, text="Content on page one."),
        PageText(page_number=2, text="Content on page two."),
        PageText(page_number=5, text="Content on page five (non-contiguous)."),
    ]
    chunks = chunk_pages(pages, chunk_size=1000, chunk_overlap=100)

    page_numbers = [c.page_number for c in chunks]
    assert page_numbers == [1, 2, 5]


def test_empty_pages_produce_no_chunks():
    pages = [
        PageText(page_number=1, text="Real content here."),
        PageText(page_number=2, text=""),
        PageText(page_number=3, text="   "),
    ]
    chunks = chunk_pages(pages, chunk_size=1000, chunk_overlap=100)

    assert len(chunks) == 1
    assert chunks[0].page_number == 1


def test_avoids_extremely_tiny_trailing_chunks():
    sentence = "A reasonably long sentence about quarterly earnings performance. "
    text = sentence * 10 + "Tiny."
    pages = [PageText(page_number=1, text=text)]

    chunks = chunk_pages(pages, chunk_size=250, chunk_overlap=40)

    # The trailing "Tiny." fragment should have been merged, not left standalone.
    assert all(len(c.content) >= 40 for c in chunks)


def test_chunk_overlap_must_be_smaller_than_chunk_size():
    pages = [PageText(page_number=1, text="Some content.")]
    with pytest.raises(ValueError):
        chunk_pages(pages, chunk_size=100, chunk_overlap=100)


def test_document_relationship_via_chunk_index_ordering():
    """Chunks are produced in reading order — chunk_index increases
    monotonically across pages, which is what lets a document's
    chunks be reassembled in order."""
    pages = [
        PageText(page_number=1, text="Page one sentence one. Page one sentence two."),
        PageText(page_number=2, text="Page two sentence one. Page two sentence two."),
    ]
    chunks = chunk_pages(pages, chunk_size=40, chunk_overlap=10)

    indices = [c.chunk_index for c in chunks]
    assert indices == sorted(indices)
    assert indices == list(range(len(chunks)))
