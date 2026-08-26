"""
evaluate.py — Day 9: golden-set evaluation harness.

ROLE
  Run questions through the SAME pipeline as /ask and score:
    - Answer accuracy (substring match on expected_contains for answerable Qs)
    - Refusal accuracy (expects REFUSAL_STRING phrase for unanswerable Qs)

PIPELINE POSITION
  load_indexes → for each golden row → run_pipeline → metrics + data/eval_results.json

IMPORTANT
  GOLDEN_SET below is a TEMPLATE with a few examples only.
  You must expand to ~50 questions and VERIFY every expected figure against the PDFs.
  Include 8–10 deliberately unanswerable items (refusal is a first-class metric).

HOW TO RUN
  cd backend
  python evaluate.py
  (writes results relative to CWD — run from backend or adjust the output path)

NOTE
  Numeric accuracy via substring is stricter/more objective than RAGAS alone;
  lead with it in README, then add RAGAS if desired.
"""

import json
from indexes import load_indexes
from query_understanding import classify_query
from retrieval import retrieve
from multihop import answer_comparison
from guardrails import guarded_generate

# --- Expand this to ~50 rows before treating Day 9 as complete ---
GOLDEN_SET = [
    {
        "question": "What was NVIDIA's total revenue in fiscal year 2025?",
        "category": "lookup",
        "expected_contains": "130,497",  # VERIFY against the FY2025 10-K before trusting
        "answerable": True,
    },
    {
        "question": "What will NVIDIA's stock price be in 2027?",
        "category": "unsupported",
        "expected_contains": None,
        "answerable": False,
    },
    {
        "question": "What did the CEO have for breakfast on the FY2025 earnings call?",
        "category": "unsupported",
        "expected_contains": None,
        "answerable": False,
    },
    # Add ~47 more: lookup_table, lookup_prose, comparison, multi-hop, unanswerable, ...
]


def run_pipeline(question: str, vectorstore, bm25_by_year, chunk_lookup) -> str:
    """
    Mirror app.py /ask routing so eval and production test the same code path.
    Returns the answer string used for scoring.
    """
    intent = classify_query(question)

    if intent.question_type == "comparison" and len(intent.fiscal_years) > 1:
        result = answer_comparison(
            question, intent, vectorstore, bm25_by_year, chunk_lookup
        )
        # Flatten sub-answers for simple substring scoring
        return " | ".join(s["answer"] for s in result["sub_answers"])

    chunks = retrieve(question, intent, vectorstore, bm25_by_year, chunk_lookup)
    result = guarded_generate(question, chunks, intent)
    return result["answer"]


def evaluate():
    """Score GOLDEN_SET; print summary; dump per-row results to JSON."""
    vectorstore, bm25_by_year, chunk_lookup = load_indexes()

    results = []
    correct = 0
    refusal_correct = 0
    refusal_total = 0
    answerable_total = 0

    for row in GOLDEN_SET:
        answer = run_pipeline(
            row["question"], vectorstore, bm25_by_year, chunk_lookup
        )

        if not row["answerable"]:
            # Refusal success = system used the calibrated refusal phrase
            refusal_total += 1
            fired = "not disclosed" in answer.lower()
            if fired:
                refusal_correct += 1
            results.append({**row, "got": answer, "refusal_fired": fired})
        else:
            answerable_total += 1
            # Strict: expected figure string must appear verbatim in the answer
            hit = bool(row["expected_contains"]) and row["expected_contains"] in answer
            if hit:
                correct += 1
            results.append({**row, "got": answer, "correct": hit})

    print(f"\nAnswer accuracy:  {correct}/{answerable_total}")
    print(f"Refusal accuracy: {refusal_correct}/{refusal_total}")

    with open("data/eval_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    return results


if __name__ == "__main__":
    evaluate()
