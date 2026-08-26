"""
retrieval.py — Day 5: hybrid retrieval + RRF + FlashRank re-ranking.

ROLE
  Given a question + QueryIntent, return the top-k most relevant chunks
  (content, metadata, score) for generation / guardrails.

PIPELINE POSITION
  QueryIntent → retrieve() → chunks → generate / guarded_generate / multihop

RETRIEVAL STRATEGY
  1. For EACH fiscal year in intent.fiscal_years (never one mixed-year search):
       - Vector search in Pinecone with metadata filter fiscal_year == year
       - BM25 search on that year's retriever only
       - Reciprocal Rank Fusion (RRF) merges the two ranked ID lists
  2. Fuse the per-year rankings again with RRF → top 20 candidate IDs
  3. Optional: if needs_table, sort tables ahead of prose before rerank
  4. FlashRank cross-encoder re-scores query↔passage → final top_k

WHY NOT ONE MULTI-YEAR FILTER
  Strongest-matching year dominates top-k; other years disappear.
  Per-year retrieval (then merge) is required for fair YoY evidence.

TECHNICAL NOTES
  - RRF score: 1 / (k + rank + 1) with k=60 (standard constant).
  - FlashRank model loaded once (singleton) — cold start is slow, reuse is cheap.
  - chunk_lookup maps chunk_id → Document after ID-only fusion.
"""

from flashrank import Ranker, RerankRequest
from query_understanding import QueryIntent

_ranker = None


def get_ranker():
    """Lazy-load the cross-encoder once per process."""
    global _ranker
    if _ranker is None:
        # ms-marco MiniLM: small, local, good enough for passage re-ranking
        _ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2")
    return _ranker


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = 60) -> dict:
    """
    Merge several ranked lists of chunk_ids into one score dict (higher = better).

    Each list contributes 1/(k+rank+1). Items that appear in multiple lists accumulate.
    Returns {chunk_id: score} sorted descending by score.
    """
    scores = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking):
            scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (k + rank + 1)
    return dict(sorted(scores.items(), key=lambda x: -x[1]))


def retrieve_for_year(
    query: str, year: int, vectorstore, bm25_by_year: dict, k: int = 20
) -> list[str]:
    """Hybrid search scoped to ONE year → ranked list of chunk_ids (best first)."""

    # Semantic hits (filtered so other years cannot appear)
    vector_hits = vectorstore.similarity_search(
        query, k=k, filter={"fiscal_year": {"$eq": year}}
    )
    vector_ids = [h.metadata["chunk_id"] for h in vector_hits]

    # Keyword hits (exact tokens: "Note 14", line-item names, etc.)
    bm25_ids = []
    if year in bm25_by_year:
        retriever = bm25_by_year[year]
        retriever.k = k
        bm25_hits = retriever.invoke(query)
        bm25_ids = [h.metadata["chunk_id"] for h in bm25_hits]

    fused = reciprocal_rank_fusion([vector_ids, bm25_ids])
    return list(fused.keys())


def retrieve(
    query: str,
    intent: QueryIntent,
    vectorstore,
    bm25_by_year: dict,
    chunk_lookup: dict,
    top_k: int = 5,
) -> list[dict]:
    """
    Full Day 5 pipeline → list of {content, metadata, score}.

    If intent.fiscal_years is empty, searches all loaded years (fallback).
    """
    years = intent.fiscal_years or list(bm25_by_year.keys())

    # Independent hybrid search per year, then fuse the year rankings
    per_year_rankings = [
        retrieve_for_year(query, y, vectorstore, bm25_by_year) for y in years
    ]
    fused = reciprocal_rank_fusion(per_year_rankings)
    candidate_ids = list(fused.keys())[:20]

    candidates = [chunk_lookup[cid] for cid in candidate_ids if cid in chunk_lookup]
    if not candidates:
        return []

    # Soft prior: put tables first for numeric questions (FlashRank still decides)
    if intent.needs_table:
        candidates.sort(key=lambda d: not d.metadata["is_table"])

    ranker = get_ranker()
    rerank_request = RerankRequest(
        query=query,
        passages=[
            {"id": d.metadata["chunk_id"], "text": d.page_content} for d in candidates
        ],
    )
    reranked = ranker.rerank(rerank_request)

    id_to_doc = {d.metadata["chunk_id"]: d for d in candidates}
    results = []
    for r in reranked[:top_k]:
        doc = id_to_doc[r["id"]]
        results.append(
            {
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": r["score"],  # used by should_refuse() in guardrails
            }
        )
    return results
