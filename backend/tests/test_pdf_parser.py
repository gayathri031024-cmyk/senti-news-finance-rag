import pytest

from app.services.ingestion.pdf_parser import PdfExtractionError, extract_pdf_pages
from tests.pdf_fixtures import make_blank_pdf_bytes, make_pdf_bytes


def test_extracts_text_per_page():
    pdf_bytes = make_pdf_bytes(["First page content.", "Second page content."])
    result = extract_pdf_pages(pdf_bytes)

    assert result.page_count == 2
    assert len(result.pages) == 2
    assert "First page" in result.pages[0].text
    assert "Second page" in result.pages[1].text


def test_page_numbers_are_1_indexed_and_in_order():
    pdf_bytes = make_pdf_bytes(["Page A", "Page B", "Page C"])
    result = extract_pdf_pages(pdf_bytes)

    assert [p.page_number for p in result.pages] == [1, 2, 3]


def test_handles_empty_pages_without_crashing():
    pdf_bytes = make_pdf_bytes(["Some content", "", "More content"])
    result = extract_pdf_pages(pdf_bytes)

    assert result.page_count == 3
    assert result.pages[1].text == ""
    # Overall document still has extractable text (pages 1 and 3).
    assert result.has_extractable_text is True


def test_scanned_pdf_with_no_text_is_flagged():
    pdf_bytes = make_blank_pdf_bytes(page_count=2)
    result = extract_pdf_pages(pdf_bytes)

    assert result.page_count == 2
    assert result.has_extractable_text is False


def test_malformed_pdf_raises_extraction_error():
    with pytest.raises(PdfExtractionError):
        extract_pdf_pages(b"this is not a pdf file at all")


def test_empty_bytes_raises_extraction_error():
    with pytest.raises(PdfExtractionError):
        extract_pdf_pages(b"")
