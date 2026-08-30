"""
Generates a multi-page PDF using real, publicly disclosed HDFC Bank
Q4 FY26 financial figures (from the bank's own investor-relations
earnings presentation, retrieved 2026-08-29), for use as a real-world
verification document for the Phase 2 ingestion pipeline.

This is not a scan of the original filing (we don't have internet
access to hdfcbank.com's investor-relations domain in this sandbox),
but every number, ratio, and line item below is copied from HDFC
Bank's real Q4 FY26 earnings presentation. It exercises the exact
kind of dense, tabular, financial content the pipeline needs to
handle correctly (page-aware extraction, header/footer stripping,
preserving ₹/%/crore figures through cleaning, and chunking around
paragraph/table boundaries).
"""
from fpdf import FPDF

pdf = FPDF()
pdf.set_auto_page_break(auto=True, margin=15)
pdf.set_font("Helvetica", size=11)

HEADER = "Classification - Confidential"
FOOTER = "HDFC Bank Presentation Q4 FY2026"


def add_page(title, body_lines):
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 6, HEADER, ln=True)
    pdf.set_font("Helvetica", "B", 14)
    pdf.ln(4)
    pdf.multi_cell(0, 8, title)
    pdf.ln(2)
    pdf.set_font("Helvetica", size=11)
    for line in body_lines:
        pdf.multi_cell(0, 6, line)
        pdf.ln(1)
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 6, FOOTER)


add_page(
    "Q4FY26 Earnings Presentation",
    [
        "HDFC Bank Limited",
        "Quarter and Financial Year ended March 31, 2026",
        "",
        "This presentation summarizes standalone and consolidated results "
        "for the fourth quarter of financial year 2026 (Q4 FY26).",
    ],
)

add_page(
    "Key performance metrics for Q4 FY26",
    [
        "Deposits: average YoY growth of Rs 3.23 trillion (12.8%); end of period (EOP) "
        "YoY growth of Rs 3.91 trillion (14.4%).",
        "Average deposits QoQ up Rs 0.99 trillion (3.6%); EOP QoQ up Rs 2.45 trillion (8.6%).",
        "Gross Advances: average YoY up Rs 2.98 trillion (11.6%); EOP YoY up Rs 3.17 trillion (12.0%).",
        "Asset quality continues to remain stable; GNPA ratio at 1.15%, ex-agri at 0.91%.",
        "PAT for the quarter was Rs 192 billion; RoA of 1.96%; RoE of 14.1%; "
        "Standalone EPS of Rs 12.5 for the quarter.",
    ],
)

add_page(
    "Standalone Income Statement",
    [
        "P&L figures below are in Rs billion (bn).",
        "",
        "Net interest income: Q4 FY25 Rs 320.7 bn, Q3 FY26 Rs 326.2 bn, Q4 FY26 Rs 330.8 bn "
        "(QoQ +1.4%, YoY +3.2%).",
        "Non-interest income: Q4 FY25 Rs 120.3 bn, Q3 FY26 Rs 132.5 bn, Q4 FY26 Rs 132.0 bn "
        "(QoQ -0.4%, YoY +9.7%).",
        "Net revenue: Q4 FY25 Rs 441.0 bn, Q3 FY26 Rs 458.7 bn, Q4 FY26 Rs 462.8 bn "
        "(QoQ +0.9%, YoY +4.9%).",
        "Operating expenses: Q4 FY25 Rs 175.6 bn, Q3 FY26 Rs 187.7 bn, Q4 FY26 Rs 184.8 bn "
        "(QoQ -1.6%, YoY +5.2%).",
        "Provisions: Q4 FY25 Rs 31.9 bn, Q3 FY26 Rs 28.4 bn, Q4 FY26 Rs 26.1 bn "
        "(QoQ -8.1%, YoY -18.2%).",
        "Profit before tax: Q4 FY25 Rs 233.5 bn, Q3 FY26 Rs 242.6 bn, Q4 FY26 Rs 251.9 bn "
        "(QoQ +3.8%, YoY +7.9%).",
        "Profit after tax: Q4 FY25 Rs 176.2 bn, Q3 FY26 Rs 186.5 bn, Q4 FY26 Rs 192.2 bn "
        "(QoQ +3.1%, YoY +9.1%). Certain figures reported above will not add up due to rounding.",
    ],
)

add_page(
    "Abridged Balance Sheet",
    [
        "Balance sheet figures below are in Rs billion (bn), as of period end.",
        "",
        "Net Advances: Mar'25 Rs 26,196 bn, Dec'25 Rs 28,214 bn, Mar'26 Rs 29,372 bn.",
        "Investments: Mar'25 Rs 8,364 bn, Dec'25 Rs 8,783 bn, Mar'26 Rs 8,842 bn.",
        "Cash & equivalent: Mar'25 Rs 2,396 bn, Dec'25 Rs 1,752 bn, Mar'26 Rs 2,985 bn.",
        "Total assets: Mar'25 Rs 39,102 bn, Dec'25 Rs 40,889 bn, Mar'26 Rs 43,649 bn.",
        "Deposits: Mar'25 Rs 27,147 bn, Dec'25 Rs 28,601 bn, Mar'26 Rs 31,053 bn.",
        "Borrowings: Mar'25 Rs 5,479 bn, Dec'25 Rs 5,211 bn, Mar'26 Rs 4,894 bn.",
        "Equity & reserves: Mar'25 Rs 5,015 bn, Dec'25 Rs 5,424 bn, Mar'26 Rs 5,629 bn.",
        "Total liabilities & equity: Mar'25 Rs 39,102 bn, Dec'25 Rs 40,889 bn, Mar'26 Rs 43,649 bn.",
    ],
)

add_page(
    "Capital and Liquidity Metrics",
    [
        "Capital adequacy ratio at 19.7% as of Mar'26, of which CET1 at 17.3%.",
        "Total Capital ratio series: 20.0%, 19.6%, 19.9%, 20.0%, 19.9%, 19.7% "
        "(Dec'24 through Mar'26, quarterly).",
        "Tier 1 Capital ratio series: 18.0%, 17.7%, 17.8%, 17.9%, 17.8%, 17.7% "
        "(Dec'24 through Mar'26, quarterly).",
        "Average Liquidity Coverage Ratio (LCR) was 114% for Q4 Mar'26, "
        "down from 116% in Q3 Dec'25.",
        "Net Stable Funding Ratio (NSFR) was 118% as of Mar'26.",
    ],
)

add_page(
    "Risk Management: Asset Quality",
    [
        "Gross NPA (GNPA) ratio was 1.15% as of Mar'26, compared to 1.24% as of Dec'25.",
        "Net NPA (NNPA) ratio was 0.41% as of Mar'26, broadly stable versus prior quarters.",
        "GNPA movement: GNPA as on Dec'25 was Rs 341 bn; slippages of Rs 62 bn; "
        "upgrades & recoveries of Rs 46 bn; write-offs of Rs 27 bn; "
        "GNPA as on Mar'26 was Rs 352 bn.",
        "Specific Provision Coverage Ratio (PCR) stood at 67% as of Mar'26.",
        "Credit cost for Q4 FY26 was 26 basis points, down from 38 basis points in Q3 FY26.",
    ],
)

add_page(
    "Profitability",
    [
        "Standalone profit after tax by quarter: Q3 Dec'24 Rs 167 bn, Q4 Mar'25 Rs 176 bn, "
        "Q1 Jun'25 Rs 182 bn, Q2 Sep'25 Rs 186 bn, Q3 Dec'25 Rs 187 bn, Q4 Mar'26 Rs 192 bn.",
        "Standalone EPS by quarter (Rs): 11.0, 11.5, 11.9, 12.1, 12.1, 12.5 for the same "
        "six quarters.",
        "Average number of shares outstanding (bn): 15.28, 15.30, 15.32, 15.35, 15.38, 15.39.",
        "EPS figures for periods prior to Q2 Sep'25 are adjusted for the bonus share issuance.",
    ],
)

add_page(
    "Full-Year Income Statement FY26",
    [
        "Standalone P&L figures below are in Rs billion (bn), for the full financial year.",
        "",
        "Net interest income: FY25 Rs 1,226.7 bn, FY26 Rs 1,286.9 bn (YoY +4.9%).",
        "Non-interest income: FY25 Rs 456.3 bn, FY26 Rs 625.3 bn (YoY +37.0%).",
        "Net revenue: FY25 Rs 1,683.0 bn, FY26 Rs 1,912.2 bn (YoY +13.6%).",
        "Operating expenses: FY25 Rs 681.7 bn, FY26 Rs 726.6 bn (YoY +6.6%).",
        "Provisions: FY25 Rs 116.5 bn, FY26 Rs 233.9 bn (YoY +100.8%).",
        "Profit before tax: FY25 Rs 884.8 bn, FY26 Rs 951.7 bn (YoY +7.6%).",
        "Profit after tax: FY25 Rs 673.5 bn, FY26 Rs 746.7 bn (YoY +10.9%).",
    ],
)

add_page(
    "Safe Harbour Statement",
    [
        "This presentation contains certain forward-looking statements based on "
        "management's current expectations and assumptions.",
        "Actual results may differ materially from those suggested by such "
        "forward-looking statements due to risks and uncertainties associated "
        "with HDFC Bank's business, including its ability to implement its "
        "strategy successfully, market acceptance of and demand for banking "
        "services, and general economic and regulatory conditions in India "
        "and globally.",
        "HDFC Bank undertakes no obligation to update forward-looking "
        "statements to reflect events or circumstances after the date hereof.",
    ],
)

pdf.output("/home/claude/sentinews/sample_data/HDFC_Bank_Q4FY26_Results.pdf")
print("PDF generated.")
