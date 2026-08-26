"""
convert.py — Day 3 helper: chunk dicts → LangChain Documents + stable chunk_id.

ROLE
  Bridge between Day 2's plain dicts and LangChain/Pinecone/BM25 APIs, which
  expect Document(page_content=..., metadata=...).

PIPELINE POSITION
  build_chunks() → chunks_to_documents() → Pinecone + chunks.jsonl

WHY chunk_id
  Retrieval fuses vector hits and BM25 hits by ID (RRF). We need a deterministic,
  human-readable ID on every Document, e.g. "NVDA-FY2025-p55-1".
  Counter per (ticker, year, page) makes IDs unique when a page has many chunks.
"""

from langchain_core.documents import Document


def chunks_to_documents(chunks: list[dict]) -> list[Document]:
    """Attach chunk_id metadata and wrap each chunk as a LangChain Document."""
    documents = []
    # How many chunks we have already emitted for each (ticker, year, page)
    page_counters = {}

    for c in chunks:
        meta = dict(c["metadata"])  # copy — never mutate the caller's dict
        key = (meta["ticker"], meta["fiscal_year"], meta["page"])
        page_counters[key] = page_counters.get(key, 0) + 1

        # Deterministic given the same chunking run; unique across the corpus
        chunk_id = (
            f"{meta['ticker']}-FY{meta['fiscal_year']}-p{meta['page']}-{page_counters[key]}"
        )
        meta["chunk_id"] = chunk_id

        documents.append(Document(page_content=c["content"], metadata=meta))

    return documents
