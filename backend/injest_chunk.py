"""
injest_chunk.py — Day 2: table-aware chunking.

ROLE
  Turn a ParsedDoc (from parse.py) into retrieval units: {content, metadata} dicts.
  These dicts are later converted to LangChain Documents and indexed (Day 3).

PIPELINE POSITION
  ParsedDoc → build_chunks() → list[dict] → convert.chunks_to_documents() → inject_index

DESIGN RULES (why this is not naive 1000-char splitting)
  1. A TABLE is one atomic chunk — never split across chunks (headers + numbers must stay together).
  2. PROSE may be split with RecursiveCharacterTextSplitter (size + overlap).
  3. Section headings are NOT chunks; they stamp current_section onto following content.
  4. Prepend "Section / Table / Fiscal Year" onto table text so embeddings have words, not just digits.
  5. Metadata (fiscal_year, is_table, page, ...) drives filters and citations later.

OUTPUT SHAPE
  {
    "content": str,          # what gets embedded / BM25-tokenized
    "metadata": {
      "ticker", "fiscal_year", "section", "page", "is_table", "chunk_type"
    }
  }
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter

# chunk_size=1000: typical RAG window for prose
# chunk_overlap=200: keeps sentences near boundaries in both neighbor chunks
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)


def build_chunks(parsed_doc, ticker: str, fiscal_year: int):
    """Walk parsed elements → list of {content, metadata} chunks for one filing."""
    chunks = []
    # Running section label (Item 7 MD&A, Note 4, ...). Starts Unknown until first heading.
    current_section = "Unknown"

    for element in parsed_doc.elements:
        if element.type == "heading":
            # Update label only — headings are not stored as their own chunks
            current_section = element.text

        elif element.type == "table":
            # Keep the WHOLE table as one chunk (atomic unit of meaning)
            table_md = element.to_markdown()
            # Context prefix: makes the chunk semantically retrievable by natural questions
            content = (
                f"Section: {current_section}\n"
                f"Table: {element.caption or '(untitled)'}\n"
                f"Fiscal Year: FY{fiscal_year}\n\n"
                f"{table_md}"
            )
            chunks.append(
                {
                    "content": content,
                    "metadata": {
                        "ticker": ticker,                 # multi-company filter later
                        "fiscal_year": fiscal_year,       # hard period filter (Day 4/5)
                        "section": current_section,       # citations + optional section filter
                        "page": element.page,             # [FY2025, p.55, ...] citations
                        "is_table": True,                 # boost for numeric questions
                        "chunk_type": "table",
                    },
                }
            )

        elif element.type == "text":
            # Split long prose; stamp the same section prefix on every piece
            for piece in splitter.split_text(element.text):
                chunks.append(
                    {
                        "content": f"Section: {current_section}\n\n{piece}",
                        "metadata": {
                            "ticker": ticker,
                            "fiscal_year": fiscal_year,
                            "section": current_section,
                            "page": element.page,
                            "is_table": False,
                            "chunk_type": "prose",
                        },
                    }
                )

    return chunks
