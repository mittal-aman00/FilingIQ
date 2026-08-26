# ingest_index.py — embedding removed, now ONLY parses/chunks/saves
import json
from convert import chunks_to_documents
import config


def save_chunks_for_bm25(documents: list) -> None:
    """The ONLY output of this file now — chunks.jsonl, which BOTH
    resume_embedding.py (for Pinecone) and indexes.py's BM25 rebuild
    read from."""
    with open(config.CHUNKS_PATH, "w", encoding="utf-8") as f:
        for doc in documents:
            f.write(json.dumps({
                "content": doc.page_content,
                "metadata": doc.metadata,
            }) + "\n")
    print(f"Saved {len(documents)} chunks to {config.CHUNKS_PATH}")


def run_ingestion(chunks: list[dict]) -> None:
    """Parsing + chunking + saving only. Embedding is now a SEPARATE
    step — run resume_embedding.py after this finishes."""
    documents = chunks_to_documents(chunks)
    save_chunks_for_bm25(documents)
    print("\nDone. Now run: python resume_embedding.py")


if __name__ == "__main__":
    from parse import parse_pdf
    from ingest_chunk import build_chunks

    filings = [
        ("data/raw/nvda_FY2024.pdf", 2024),
        ("data/raw/nvda_FY2025.pdf", 2025),
        ("data/raw/nvda_FY2026.pdf", 2026),
    ]

    all_chunks = []
    for path, fy in filings:
        parsed = parse_pdf(path)
        chunks = build_chunks(parsed, "NVDA", fy)
        all_chunks += chunks
        print(f"FY{fy}: {len(chunks)} chunks ({sum(c['metadata']['is_table'] for c in chunks)} tables)")

    print(f"\nTotal chunks: {len(all_chunks)}")
    run_ingestion(all_chunks)