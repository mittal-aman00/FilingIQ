"""
multihop.py — Day 8: cross-year comparison via per-year retrieval + Python math.

ROLE
  Handle question_type == "comparison" with multiple fiscal_years.
  Never retrieve all years in one pass. Decompose → answer each year →
  optionally compute delta with Decimal (not the LLM).

PIPELINE POSITION
  app.ask / evaluate → answer_comparison() when intent is multi-year comparison

STEPS
  1. decompose_comparison: one sub-question per year ("What was {metric} in FY{y}?")
  2. For each year: retrieve + generate_answer (single-year intent)
  3. extract_primary_number: heuristic $ figure from each sub-answer
  4. If requires_calculation and exactly 2 years with figures: compute_delta()

HONEST LIMITATIONS
  - extract_primary_number is regex, not structured extraction — verify on golden set.
  - Unit mismatch (million vs billion) is NOT reconciled; keep answers consistent.
  - Percent-point vs percent-change: compute_delta returns absolute delta + pct_change;
    refine if your golden set needs pp specifically.
"""

import re
from decimal import Decimal
from query_understanding import QueryIntent
from retrieval import retrieve
from guardrails import guarded_generate


def decompose_comparison(intent: QueryIntent) -> list[str]:
    """Turn one cross-year question into N single-year sub-questions —
    never retrieve across years in a single pass (Day 5's rule)."""
    metric = intent.metric or "the relevant figure"
    return [f"What was {metric} in fiscal year {year}?" for year in intent.fiscal_years]


def extract_primary_number(answer: str) -> str | None:
    """
    Best-effort: grabs the first dollar-figure in a short lookup answer.

    ⚠️ HONEST LIMITATION: this is a simple heuristic, not a solved problem.
    It works for clean single-figure answers ("Revenue was $130,497 million
    in FY2025 [FY2025, p.54, ...]") but will grab the WRONG number if the
    answer mentions multiple figures. Verify this against your golden set
    on Day 9 — if it's unreliable, replace it with a second small LLM call
    that extracts just the one requested figure as structured output
    (same pattern as query_understanding.py), rather than trusting regex
    on free text.
    """
    match = re.search(r"\$[\d,]+\.?\d*\s?(?:billion|million)?", answer)
    return match.group(0) if match else None


def compute_delta(later_value: str, earlier_value: str) -> dict:
    """Arithmetic goes through Decimal, NEVER through the LLM."""
    def clean(v: str) -> Decimal:
        v = v.replace("$", "").replace(",", "").strip()
        v = v.replace("billion", "").replace("million", "").strip()
        return Decimal(v)

    a, b = clean(later_value), clean(earlier_value)
    delta = a - b
    pct_change = (delta / b * 100) if b != 0 else None

    return {
        "later": str(a),
        "earlier": str(b),
        "delta": str(delta),
        "pct_change": round(float(pct_change), 2) if pct_change is not None else None,
    }


def answer_comparison(question: str, intent: QueryIntent, vectorstore,
                       bm25_by_year: dict, chunk_lookup: dict) -> dict:
    """
    Full Day 8 pipeline: decompose -> retrieve+answer PER year -> return
    sub-answers with extracted figures, ready for compute_delta() if the
    metric is numeric.
    """
    sub_questions = decompose_comparison(intent)
    sub_answers = []

    for year, sub_q in zip(intent.fiscal_years, sub_questions):
        year_intent = intent.model_copy(update={"fiscal_years": [year]})
        chunks = retrieve(sub_q, year_intent, vectorstore, bm25_by_year, chunk_lookup)
        result = guarded_generate(sub_q, chunks, year_intent)   # now verified, same as single-question path
        figure = extract_primary_number(result["answer"])
        sub_answers.append({
            "year": year,
            "question": sub_q,
            "answer": result["answer"],
            "citations": result["citations"],
            "extracted_figure": figure,
        })

    delta = None
    if intent.requires_calculation and len(sub_answers) == 2:
        figures = [s["extracted_figure"] for s in sub_answers]
        if all(figures):
            # sub_answers are in intent.fiscal_years order — later year first
            # only if fiscal_years was given descending; sort explicitly to be safe
            ordered = sorted(sub_answers, key=lambda s: s["year"], reverse=True)
            delta = compute_delta(ordered[0]["extracted_figure"], ordered[1]["extracted_figure"])

    return {"sub_answers": sub_answers, "delta": delta}
