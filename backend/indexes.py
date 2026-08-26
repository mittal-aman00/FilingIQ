"""
indexes.py — Day 3 runtime loader (shared by app.py and evaluate.py).

ROLE
  At process startup, rebuild everything retrieval needs from committed data:
    - Pinecone vectorstore (connect to existing cloud index)
    - bm25_by_year: one BM25Retriever PER fiscal year (no cross-year mixing)
    - chunk_lookup: chunk_id → Document (for RRF / FlashRank after ID fusion)

PIPELINE POSITION
  chunks.jsonl + Pinecone  →  load_indexes()  →  FastAPI lifespan / evaluate()

WHY ONE BM25 PER YEAR
  LangChain BM25Retriever does not hard-filter metadata well. Partitioning by
  fiscal_year makes "never mix years in one retrieval" the default (Day 5/8).
  Fine for 1 company × 3 years; at multi-ticker scale you'd use a search engine
  with metadata filters instead.

IMPORTANT
  Does NOT re-embed. Embeddings live in Pinecone from inject_index.py.
  BM25 is cheap to rebuild in memory from JSONL — no .pkl on GitHub.
"""

import json
from collections import defaultdict
from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from langchain_pinecone import PineconeVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import config


def load_indexes():
    """Return (vectorstore, bm25_by_year, chunk_lookup)."""

    # --- 1. Load every chunk from the committed JSONL ---
    documents = []
    with open(config.CHUNKS_PATH, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            documents.append(
                Document(page_content=row["content"], metadata=row["metadata"])
            )

    # --- 2. Partition by fiscal_year → one BM25 corpus each ---
    by_year = defaultdict(list)
    for doc in documents:
        by_year[doc.metadata["fiscal_year"]].append(doc)

    bm25_by_year = {
        year: BM25Retriever.from_documents(docs) for year, docs in by_year.items()
    }

    # --- 3. Connect to the already-populated Pinecone index ---
    embeddings = GoogleGenerativeAIEmbeddings(
        model=config.EMBEDDING_MODEL, google_api_key=config.GEMINI_API_KEY
    )
    vectorstore = PineconeVectorStore.from_existing_index(
        index_name=config.INDEX_NAME, embedding=embeddings
    )

    # --- 4. ID → Document map for post-fusion lookup in retrieval.py ---
    chunk_lookup = {doc.metadata["chunk_id"]: doc for doc in documents}

    print(
        f"Loaded {len(documents)} chunks across {len(bm25_by_year)} fiscal years: "
        f"{sorted(bm25_by_year.keys())}"
    )
    return vectorstore, bm25_by_year, chunk_lookup
