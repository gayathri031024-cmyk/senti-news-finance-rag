"""
PDF text extraction.

Extracts text page-by-page (never as one flat string) using pypdf.
Deliberately narrow scope: no OCR, no layout reconstruction, no table
detection — just reliable per-page text with clear failure signals.
"""
import io
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PdfExtractionError(Exception):
    """Raised when a PDF cannot be parsed at all (malformed / not a PDF)."""


@dataclass
class PageText:
    page_number: int  # 1-indexed, matches how a human would cite the page
    text: str


@dataclass
class ExtractionResult:
    pages: list[PageText]
    page_count: int

    @property
    def has_extractable_text(self) -> bool:
        """
        False for scanned/image-only PDFs where every page came back
        empty. Callers should treat that as a failure, not success —
        OCR is out of scope for this phase.
        """
        return any(page.text.strip() for page in self.pages)


def extract_pdf_pages(file_bytes: bytes) -> ExtractionResult:
    """
    Extract text from every page of a PDF.

    Raises PdfExtractionError for malformed/unreadable files. Returns
    an ExtractionResult even when pages are empty — callers decide
    whether "no extractable text" counts as a processing failure
    (it should, per Phase 2 spec: don't pretend a scanned PDF worked).
    """
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except Exception as exc:  # pypdf raises varied exception types for bad input
        raise PdfExtractionError(f"Could not read PDF: {exc}") from exc

    if reader.is_encrypted:
        # Try an empty-password decrypt (common for "restricted" but not
        # actually password-protected exports); if that fails, surface it.
        try:
            reader.decrypt("")
        except Exception as exc:  # noqa: BLE001
            raise PdfExtractionError(f"PDF is encrypted and could not be opened: {exc}") from exc

    pages: list[PageText] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001 - a single bad page shouldn't kill the batch
            text = ""
        pages.append(PageText(page_number=index, text=text))

    if not pages:
        raise PdfExtractionError("PDF has no pages")

    return ExtractionResult(pages=pages, page_count=len(pages))
