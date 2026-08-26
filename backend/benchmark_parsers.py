"""
benchmark_parsers.py — Day 1: compare PDF parsers on the income-statement page.

ROLE
  Side-by-side quality check BEFORE building the ingestion pipeline.
  Grade: column headers, cell alignment, hierarchy, footnotes, negatives in ().

PIPELINE POSITION
  Standalone experiment. Winner (pymupdf4llm here) feeds parse.py.

HOW TO RUN
  cd backend   # or any cwd — PDF path is resolved from this file
  python benchmark_parsers.py

NOTE
  Docling commented out: high RAM + Windows console Unicode issues on full PDFs.
"""

import pdfplumber
import pymupdf4llm
from pathlib import Path
# from docling.document_converter import DocumentConverter
# Docling removed: heavy on RAM (layout models) and full-PDF output is too large /
# fails to print cleanly in the Windows console (UnicodeEncodeError).

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "data" / "raw" / "nvda_FY2026.pdf"
PAGE = 53  # Consolidated Statements of Income — confirm manually in the PDF viewer

# 1) pdfplumber — coordinate-based table extract (nested Python lists)
with pdfplumber.open(str(PDF)) as pdf:
    page = pdf.pages[PAGE - 1]  # pdfplumber is 0-indexed
    tables = page.extract_tables()
    print("pdfplumber:", tables)

# 2) pymupdf4llm — markdown tables (chosen for Day 2 parse.py)
md = pymupdf4llm.to_markdown(str(PDF), pages=[PAGE - 1])
print("pymupdf4llm:", md)

# 3) docling — layout-model based (optional; left disabled)
# conv = DocumentConverter()
# result = conv.convert(PDF)
# print('docling:', result.document.export_to_markdown())
