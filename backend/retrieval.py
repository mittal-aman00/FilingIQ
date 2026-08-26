"""
retrieval.py — Day 5: hybrid retrieval + RRF + optional FlashRank re-ranking.

ROLE
  Given a question + QueryIntent, return the top-k most relevant chunks
  (content, metadata, score) for generation / guardrails.

TECHNICAL NOTES
  - FlashRank loads a local cross-encoder (~100MB+ RAM). On Render free (512MB)
    that often OOMs and the proxy returns 502 → browser shows "Failed to fetch".
  - Set ENABLE_FLASHRANK=1 to turn it on (local / larger instances).
  - Default: RRF order only (still hybrid BM25 + vector).
"""

import os
from query_understanding import QueryIntent

_ranker = None
_flashrank_disabled_reason = None


def _flashrank_enabled() -> bool:
    return os.environ.get("ENABLE_FLASHRANK", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def get_ranker():
    """Lazy-load the cross-encoder once per process (optional)."""
    global _ranker, _flashrank_disabled_reason
    if not _flashrank_enabled():
        return None
    if _flashrank_disabled_reason:
        return None
    if _ranker is None:
        try:
            from flashrank import Ranker

            # TinyBERT is much lighter than MiniLM-L-12 — safer on small VMs
            _ranker = Ranker(model_name="ms-marco-TinyBERT-L-2-v2")
        except Exception as e:
            _flashrank_disabled_reason = str(e)
            print(f"FlashRank disabled after load failure: {e}")
            return None
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

    vector_hits = vectorstore.similarity_search(
        query, k=k, filter={"fiscal_year": {"$eq": year}}
    )
    vector_ids = [h.metadata["chunk_id"] for h in vector_hits]

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
    Hybrid retrieval → top_k chunks as {content, metadata, score}.

    Uses FlashRank when ENABLE_FLASHRANK=1; otherwise RRF ranking + heuristic scores.
    """
    years = intent.fiscal_years or list(bm25_by_year.keys())

    per_year_rankings = [
        retrieve_for_year(query, y, vectorstore, bm25_by_year) for y in years
    ]
    fused = reciprocal_rank_fusion(per_year_rankings)
    candidate_ids = list(fused.keys())[:20]

    candidates = [chunk_lookup[cid] for cid in candidate_ids if cid in chunk_lookup]
    if not candidates:
        return []

    if intent.needs_table:
        candidates.sort(key=lambda d: not d.metadata["is_table"])

    ranker = get_ranker()
    if ranker is not None:
        try:
            from flashrank import RerankRequest

            rerank_request = RerankRequest(
                query=query,
                passages=[
                    {"id": d.metadata["chunk_id"], "text": d.page_content}
                    for d in candidates
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
                        "score": float(r["score"]),
                    }
                )
            return results
        except Exception as e:
            print(f"FlashRank rerank failed, falling back to RRF: {e}")

    # Fallback: keep RRF / table-boosted order; give decaying scores for guardrails
    results = []
    for i, doc in enumerate(candidates[:top_k]):
        cid = doc.metadata["chunk_id"]
        rrf_score = fused.get(cid, 1.0 / (60 + i + 1))
        results.append(
            {
                "content": doc.page_content,
                "metadata": doc.metadata,
                # Scale into a range refusal threshold (0.3) can work with
                "score": float(min(1.0, rrf_score * 50)),
            }
        )
    return results
