"""
Test PDF fixtures, generated on the fly with fpdf2 so tests don't
depend on a checked-in binary file.
"""
import io

from fpdf import FPDF


def make_pdf_bytes(pages: list[str]) -> bytes:
    """Build a simple multi-page PDF where each string is one page's text."""
    pdf = FPDF()
    pdf.set_font("Helvetica", size=12)
    for page_text in pages:
        pdf.add_page()
        if page_text:
            pdf.multi_cell(0, 8, page_text)
    return bytes(pdf.output())


def make_blank_pdf_bytes(page_count: int = 1) -> bytes:
    """A PDF with real pages but no text on any of them (simulates a scan)."""
    pdf = FPDF()
    for _ in range(page_count):
        pdf.add_page()
    return bytes(pdf.output())
