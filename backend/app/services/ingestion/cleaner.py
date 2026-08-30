"""
Text cleaning.

Normalizes whitespace and strips obviously repeated headers/footers
without touching the financial content itself — numbers, percentages,
currency symbols, and financial terms must survive unchanged.
"""
import re
from collections import Counter

from app.services.ingestion.pdf_parser import PageText

# A run of 3+ blank lines collapses to one blank line (paragraph break).
_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")
# Runs of horizontal whitespace (spaces/tabs, not newlines) collapse to one space.
_EXCESS_SPACES = re.compile(r"[ \t]{2,}")
# Trailing whitespace at the end of a line.
_TRAILING_WS = re.compile(r"[ \t]+\n")

# A candidate header/footer line: short, and appears on most pages.
_MAX_HEADER_FOOTER_LEN = 80
_HEADER_FOOTER_MIN_PAGE_FRACTION = 0.6


def _normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _TRAILING_WS.sub("\n", text)
    text = _EXCESS_SPACES.sub(" ", text)
    text = _EXCESS_BLANK_LINES.sub("\n\n", text)
    return text.strip()


def _find_repeated_lines(pages: list[PageText]) -> set[str]:
    """
    Lines that appear (verbatim, after stripping) on most pages are
    almost always a running header/footer (e.g. "Classification -
    Confidential", a report title, a page-number line) rather than
    content, and are safe to drop as pure noise.
    """
    if len(pages) < 3:
        # Too few pages to tell a real repeated header from coincidence.
        return set()

    line_page_counts: Counter[str] = Counter()
    for page in pages:
        seen_this_page: set[str] = set()
        for raw_line in page.text.splitlines():
            line = raw_line.strip()
            if not line or len(line) > _MAX_HEADER_FOOTER_LEN:
                continue
            if line not in seen_this_page:
                line_page_counts[line] += 1
                seen_this_page.add(line)

    threshold = max(2, int(len(pages) * _HEADER_FOOTER_MIN_PAGE_FRACTION))
    return {line for line, count in line_page_counts.items() if count >= threshold}


def clean_pages(pages: list[PageText]) -> list[PageText]:
    """
    Clean each page's text. Never touches digits, currency symbols
    (₹, $, %, etc.), or financial terminology — only whitespace and
    lines identified as repeated headers/footers across the document.
    """
    repeated_lines = _find_repeated_lines(pages)

    cleaned: list[PageText] = []
    for page in pages:
        lines = [
            line for line in page.text.splitlines()
            if line.strip() not in repeated_lines
        ]
        text = _normalize_whitespace("\n".join(lines))
        cleaned.append(PageText(page_number=page.page_number, text=text))
    return cleaned
