from app.services.ingestion.cleaner import clean_pages
from app.services.ingestion.pdf_parser import PageText


def test_normalizes_excess_whitespace():
    pages = [PageText(page_number=1, text="Line one.\n\n\n\n\nLine two.   has   extra   spaces.")]
    cleaned = clean_pages(pages)

    assert "\n\n\n" not in cleaned[0].text
    assert "   " not in cleaned[0].text


def test_preserves_financial_values():
    text = "Net profit rose to \u20b9 4,695 crore, up 12.2% YoY, EPS of $1.23."
    pages = [PageText(page_number=1, text=text)]
    cleaned = clean_pages(pages)

    assert "\u20b9 4,695 crore" in cleaned[0].text
    assert "12.2%" in cleaned[0].text
    assert "$1.23" in cleaned[0].text


def test_strips_lines_repeated_across_most_pages():
    header = "Classification - Confidential"
    pages = [
        PageText(page_number=i, text=f"{header}\nUnique content for page {i}.")
        for i in range(1, 6)
    ]
    cleaned = clean_pages(pages)

    for page in cleaned:
        assert header not in page.text
    assert "Unique content for page 3." in cleaned[2].text


def test_does_not_strip_lines_that_only_appear_once():
    pages = [
        PageText(page_number=1, text="Shared header\nPage one unique line."),
        PageText(page_number=2, text="Shared header\nPage two unique line."),
        PageText(page_number=3, text="A line that only appears on page three."),
    ]
    cleaned = clean_pages(pages)

    assert "A line that only appears on page three." in cleaned[2].text


def test_few_pages_does_not_trigger_header_stripping():
    """With fewer than 3 pages there's not enough signal to call
    something a repeated header — it should be left alone."""
    pages = [
        PageText(page_number=1, text="Short line\nMore content."),
        PageText(page_number=2, text="Short line\nOther content."),
    ]
    cleaned = clean_pages(pages)

    assert "Short line" in cleaned[0].text
    assert "Short line" in cleaned[1].text
