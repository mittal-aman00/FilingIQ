"""
parse.py — Day 1/2 bridge: PDF → structured elements.

ROLE
  Convert a SEC 10-K PDF into a list of Element objects that build_chunks()
  can consume. This is the adapter between raw PDF parsers and Day 2 chunking.

PIPELINE POSITION
  PDFs (data/raw/) → parse_pdf() → ParsedDoc → injest_chunk.build_chunks()

WHY THIS EXISTS
  pdfplumber / pymupdf4llm return tables and text in library-specific shapes.
  build_chunks() needs a stable contract: heading | table | text + page number.
  parse.py normalizes PyMuPDF4LLM markdown into that contract.

TECHNICAL NOTES
  - page_chunks=True → one markdown blob per page (preserves page numbers).
  - use_ocr=False → faster; NVIDIA 10-Ks are text PDFs, not scanned images.
  - Tables are detected as markdown pipe-rows (| ... |), kept intact as one Element.
  - Headers/footers (timestamps, SEC URLs, page "53/87") are filtered as noise.
"""

import pymupdf4llm
from dataclasses import dataclass
import re


@dataclass
class Element:
    """One atomic piece of a page: heading, table, or prose block.

    This is the shape build_chunks() expects (element.type / .text / .page / .caption).
    """
    type: str                    # "heading" | "table" | "text"
    text: str                    # raw heading text, markdown table, or paragraph
    page: int                    # PDF page number for citations [FY..., p.N, ...]
    caption: str | None = None   # optional table title; often None for SEC PDFs

    def to_markdown(self):
        """Tables are already stored as markdown; return that string unchanged."""
        return self.text


@dataclass
class ParsedDoc:
    """A full filing after parsing — Elements in reading order.

    Matches the parsed_doc.elements loop in injest_chunk.build_chunks().
    """
    elements: list


def parse_pdf(pdf_path: str) -> ParsedDoc:
    """PDF path → ParsedDoc.

    1. PyMuPDF4LLM emits per-page markdown dicts.
    2. Each page's text is split into heading / table / text Elements.
    """
    # List[{"text": str, "metadata": {"page_number": int, ...}}, ...]
    pages = pymupdf4llm.to_markdown(pdf_path, page_chunks=True, use_ocr=False)

    elements = []
    for page in pages:
        page_num = page["metadata"].get("page_number")
        elements.extend(_split_page(page["text"], page_num))

    return ParsedDoc(elements=elements)


# Regexes for common PDF chrome that should not become retrieval chunks
_NOISE_PATTERNS = [
    re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4},?\s*\d{1,2}:\d{2}\s*(AM|PM)?$", re.IGNORECASE),  # print timestamp
    re.compile(r"^nvda-\d+$", re.IGNORECASE),   # filing id like nvda-20250126
    re.compile(r"^https?://\S+$"),              # SEC EDGAR URL in footer
    re.compile(r"^\d{1,4}(/\d{1,4})?$"),        # page number or "53/87"
]


def _is_noise(text: str) -> bool:
    """True if the whole text block is PDF chrome (not financial content)."""
    return any(p.match(text.strip()) for p in _NOISE_PATTERNS)


def _split_page(md_text: str, page_num: int) -> list[Element]:
    """Line-scan one page of markdown into typed Elements.

    State machine:
      '#' line  → flush buffer, emit heading Element immediately
      '|' line  → accumulate into a table buffer (do not split mid-table)
      blank     → flush current buffer
      other     → accumulate into a text buffer

    flush() commits the buffer as one Element (skips noisy prose).
    """
    elements = []
    buffer, buffer_type = [], None  # lines collected so far + current type

    def flush():
        """Commit buffer → Element, then reset buffer."""
        nonlocal buffer, buffer_type
        content = "\n".join(buffer).strip()
        if content and not (buffer_type == "text" and _is_noise(content)):
            elements.append(Element(type=buffer_type, text=content, page=page_num))
        buffer, buffer_type = [], None

    for line in md_text.split("\n"):
        stripped = line.strip()

        if stripped.startswith("#"):
            flush()
            elements.append(
                Element(
                    type="heading",
                    text=stripped.lstrip("#").strip(),  # drop markdown # markers
                    page=page_num,
                )
            )

        elif stripped.startswith("|"):
            # Start a new table buffer when switching types
            if buffer_type != "table":
                flush()
                buffer_type = "table"
            buffer.append(line)  # keep raw line so | alignment stays valid markdown

        elif stripped == "":
            flush()

        else:
            if buffer_type != "text":
                flush()
                buffer_type = "text"
            buffer.append(line)

    flush()  # trailing content at end of page
    return elements
