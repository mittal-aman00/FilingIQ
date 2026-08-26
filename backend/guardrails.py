"""
guardrails.py — Day 6+7: refusal, numeric verification, citation verification.

ROLE
  Trust layer between generation and the user. Soft prompt rules are not enough
  in finance — wrong numbers look fluent. This module enforces:

    1. Refuse unsupported / weak-evidence questions BEFORE generating
    2. After generate: every number in the answer must appear in retrieved context
    3. Every citation (FY, page) must map to an actually-retrieved chunk
    4. On failure: regenerate once with feedback; if still bad → refuse

PIPELINE POSITION
  retrieve() → guarded_generate() → {answer, verified, citations}

TUNING
  REFUSAL_THRESHOLD is empirical — tune on Day 9 golden set (false refuse vs nonsense).

KNOWN LIMITATION
  Computed deltas (e.g. "+2.3 pp") are not in context. Day 8 handles arithmetic
  in Python and should whitelist those outputs rather than loosening verify_numbers.
"""

import re
from generate import generate_answer, extract_citations, REFUSAL_STRING

# Matches $, commas, parentheses, optional scale words / %
NUMBER_RE = re.compile(
    r"\(?\$?\s?-?[\d,]+\.?\d*\s?(?:billion|million|thousand|%)?\)?"
)

# Max FlashRank score below this → treat evidence as too weak to answer
# too low  → confident nonsense on weak hits
# too high → refuses answerable questions
REFUSAL_THRESHOLD = 0.3


def normalise(n: str) -> str:
    """Strip formatting so 1,234 and 1234 and $1,234 and 1,234 million all compare equal."""
    n = re.sub(r"[\$,\s\u202f\u00a0]", "", n)          # $, commas, all whitespace incl. narrow/no-break space
    n = re.sub(r"(billion|million|thousand|%)", "", n, flags=re.IGNORECASE)  # unit words
    return n.strip("()")


def verify_numbers(answer: str, context: str) -> tuple[bool, list[str]]:
    """
    True iff every substantive number in the answer appears in the context.

    Skips tiny tokens (len < 2) to ignore list markers / noise.
    Returns (ok, list_of_unverified_raw_strings).
    """
    ctx_numbers = {normalise(m) for m in NUMBER_RE.findall(context)}
    unverified = []
    for raw in NUMBER_RE.findall(answer):
        n = normalise(raw)
        if not n or len(n) < 2:
            continue
        if n not in ctx_numbers:
            unverified.append(raw)
    return (len(unverified) == 0, unverified)


def verify_citations(answer: str, chunks: list[dict]) -> bool:
    """
    True iff every cited (fiscal_year, page) was in the retrieved set.

    Invented page numbers fail this check even if the prose looks right.
    """
    retrieved_refs = {
        (c["metadata"]["fiscal_year"], c["metadata"]["page"]) for c in chunks
    }
    for cite in extract_citations(answer):
        if (cite["fiscal_year"], cite["page"]) not in retrieved_refs:
            return False
    return True


def should_refuse(rerank_scores: list[float], intent) -> bool:
    """Pre-generation refusal: unsupported intent or weak max retrieval score."""
    if intent.question_type == "unsupported":
        return True
    if not rerank_scores:
        return True
    if max(rerank_scores) < REFUSAL_THRESHOLD:
        return True
    return False


def guarded_generate(question: str, chunks: list[dict], intent) -> dict:
    """
    Full Day 6+7 path:
      refuse → generate → verify → optional one retry → refuse if still bad
    """
    scores = [c["score"] for c in chunks]
    if should_refuse(scores, intent):
        return {"answer": REFUSAL_STRING, "verified": True, "citations": []}

    result = generate_answer(question, chunks)
    numbers_ok, bad_numbers = verify_numbers(result["answer"], result["context"])
    citations_ok = verify_citations(result["answer"], chunks)

    if not numbers_ok or not citations_ok:
        # Feed the specific failure back so the model can self-correct once
        feedback = ""
        if not numbers_ok:
            feedback += f"\nThe figure(s) {bad_numbers} do not appear in the context. "
        if not citations_ok:
            feedback += "\nSome citations reference pages that were not retrieved. "
        feedback += (
            "Answer again using ONLY figures and citations present in the context."
        )

        retry_question = question + "\n\n[SYSTEM NOTE]" + feedback
        result = generate_answer(retry_question, chunks)
        numbers_ok, _ = verify_numbers(result["answer"], result["context"])
        citations_ok = verify_citations(result["answer"], chunks)

        # Prefer honest refusal over an unverified number
        if not numbers_ok or not citations_ok:
            return {"answer": REFUSAL_STRING, "verified": True, "citations": []}

    return {
        "answer": result["answer"],
        "verified": True,
        "citations": result["citations"],
    }
