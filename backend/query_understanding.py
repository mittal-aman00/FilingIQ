"""
query_understanding.py — Day 4: turn free-text questions into QueryIntent.

ROLE
  Before retrieval, classify the question so we can apply HARD metadata filters
  (fiscal years, table boost) instead of relying on semantic search alone.
  Also refuses investment-advice / prediction questions at the intent layer.

PIPELINE POSITION
  /ask → classify_query(question) → QueryIntent → retrieve() / answer_comparison()

WHY THIS MATTERS
  "What was revenue?" without a year is dangerous in finance RAG — the wrong
  year's income statement may embed closest. fiscal_years drives filters so
  the wrong year cannot leak into the top-k.

TECHNICAL NOTES
  - Uses Gemini structured output (response_schema=QueryIntent) → valid JSON.
  - temperature=0.0 — classification must be deterministic (Day 4 checkpoint).
  - Run `python query_understanding.py` for a quick 10-question smoke test.
"""

from pydantic import BaseModel
from typing import Literal, Optional
from llm import call_llm


class QueryIntent(BaseModel):
    """Structured intent extracted from an equity-research question."""

    # lookup | comparison | explanation | unsupported (see SYSTEM prompt)
    question_type: Literal["lookup", "comparison", "explanation", "unsupported"]

    # e.g. "revenue", "operating margin", "R&D expense" — None for pure narrative
    metric: Optional[str] = None

    # [2025] for single-year; [2024, 2025] for YoY; [] for unsupported
    fiscal_years: list[int]

    # Optional retrieval hint: "MD&A", "Notes", "Risk Factors"
    section_hint: Optional[str] = None

    # True → retrieval boosts is_table=True chunks (numeric questions)
    needs_table: bool

    # True → Day 8 may run verified Python arithmetic after per-year lookups
    requires_calculation: bool


SYSTEM = """You parse equity-research questions about SEC 10-K filings into
structured intent. Available fiscal years: 2023, 2024, 2025.

question_type:
  lookup      - a single fact or figure from one filing
  comparison  - requires figures from 2+ fiscal years
  explanation - narrative/qualitative, usually MD&A or Risk Factors
  unsupported - forward-looking, opinion, or outside the filings

If the user asks for investment advice, a price target, or a prediction,
return question_type='unsupported' and leave fiscal_years as an empty list.

Return ONLY valid JSON matching the schema. No markdown, no explanation.
"""


def classify_query(question: str) -> QueryIntent:
    for attempt in range(2):
        raw = call_llm(
            system=SYSTEM,
            user=question,
            temperature=0.0,
            response_schema=QueryIntent,
        )
        try:
            return QueryIntent.model_validate_json(raw)
        except Exception as e:
            if attempt == 0:
                print(f"Schema validation failed, retrying once: {e}")
                continue
            raise ValueError(f"QueryIntent parsing failed twice. Last response: {raw}") from e


if __name__ == "__main__":
    # Manual sanity check before wiring Day 5 retrieval
    test_questions = [
        "What was NVIDIA's revenue in fiscal year 2025?",
        "How did operating margin change from FY2024 to FY2025?",
        "Why did data center revenue grow so fast in FY2025?",
        "What does the Risk Factors section say about export controls?",
        "Should I buy NVIDIA stock right now?",
        "What will NVIDIA's revenue be next year?",
        "What was the price target set by analysts?",
        "Compare R&D expense across FY2023, FY2024, and FY2025.",
        "What was total comprehensive income in FY2023?",
        "What does Note 14 say about goodwill?",
    ]

    for q in test_questions:
        intent = classify_query(q)
        print(f"\nQ: {q}")
        print(f"  question_type={intent.question_type}  fiscal_years={intent.fiscal_years}")
        print(f"  needs_table={intent.needs_table}  requires_calculation={intent.requires_calculation}")
