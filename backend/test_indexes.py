"""
test_indexes.py — Day 3 sanity check: BM25 exact-term vs vector semantic hits.

ROLE
  Prove both indexes load and behave differently before wiring Day 5 hybrid retrieval.

HOW TO RUN
  cd backend
  python test_indexes.py

EXPECT
  - BM25(FY2025) on "Note 14 goodwill" → keyword/page hits in 2025
  - Vector on "why did data center revenue grow" → conceptually related chunks

REQUIRES
  data/chunks.jsonl present AND Pinecone index populated (inject_index.py).
  chunks must include metadata.chunk_id (from convert.chunks_to_documents).
"""

from indexes import load_indexes

# load_indexes returns three objects (vectorstore, bm25_by_year, chunk_lookup)
vectorstore, bm25_by_year, chunk_lookup = load_indexes()

# --- BM25: exact tokens / note references (should beat pure vectors here) ---
print("BM25 (FY2025) — query: 'Note 14 goodwill'")
results = results = bm25.invoke("Note 14 goodwill")
for r in results[:3]:
    print(" ", r.metadata["fiscal_year"], r.metadata["page"], r.page_content[:80])

# --- Vector: semantic / conceptual questions ---
print("\nVector — query: 'why did data center revenue grow'")
results = vectorstore.similarity_search("why did data center revenue grow", k=3)
for r in results:
    print(" ", r.metadata["fiscal_year"], r.metadata["page"], r.page_content[:80])

print(f"\nchunk_lookup size: {len(chunk_lookup)}")
