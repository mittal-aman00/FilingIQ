"""
generate.py — Day 6: grounded answer generation + citation parsing.

ROLE
  Given retrieved chunks, prompt the LLM to answer ONLY from that context,
  with mandatory inline citations in a parseable format.

PIPELINE POSITION
  chunks → generate_answer() → {answer, citations, context}
  Usually called via guardrails.guarded_generate() (which verifies afterwards).

CITATION FORMAT
  [FY2025, p.31, Section Name]
  Parsed by CITATION_RE so the UI / verify_citations can validate them.

GUARDRAILS IN THE PROMPT (soft)
  Rules 1–7 reduce hallucinations; Day 7 still VERIFY numbers and citations
  in code because models can invent plausible page numbers.
"""

import re
from llm import call_llm

# Exact refusal string — also checked by evaluate.py for refusal accuracy
REFUSAL_STRING = "This information is not disclosed in the filings provided."

SYSTEM = """You are a financial analyst assistant. Answer ONLY using the provided
context from NVIDIA's SEC 10-K filings. Follow these rules exactly:

1. Use ONLY figures and facts present in the context below. Never use outside
   knowledge or your training data.
2. If the context does not contain the answer, say exactly:
   'This information is not disclosed in the filings provided.'
   Do not speculate, estimate, or approximate.
3. State the fiscal year explicitly with every figure — never say 'revenue was X'
   without saying which year.
4. Preserve the sign convention of the source. A figure in parentheses is negative.
5. You do not give investment advice, price targets, or predictions.
6. Cite every figure inline in this exact format: [FY2025, p.31, Section Name]
   Use standard ASCII square brackets [ ] only — never full-width or
   CJK-style brackets 【 】.
7. Answer concisely and factually. Analysts value precision over prose.
"""

# Captures groups: year, page, section title
CITATION_RE = re.compile(r"[\[【]FY(\d{4}),\s*p\.(\d+),\s*([^\]】]+)[\]】]")


def build_context(chunks: list[dict]) -> str:
    """
    Label each chunk with the same citation header the model must reuse.

    Example block:
      [FY2025, p.55, Item 8]
      Section: ...
      | Revenue | ...
    """
    parts = []
    for c in chunks:
        m = c["metadata"]
        parts.append(
            f"[FY{m['fiscal_year']}, p.{m['page']}, {m['section']}]\n{c['content']}"
        )
    return "\n\n---\n\n".join(parts)


def extract_citations(answer: str) -> list[dict]:
    """Parse all inline citations from the answer into structured dicts."""
    return [
        {"fiscal_year": int(y), "page": int(p), "section": s.strip()}
        for y, p, s in CITATION_RE.findall(answer)
    ]


def generate_answer(question: str, chunks: list[dict]) -> dict:
    """
    Produce a grounded answer.

    If retrieval returned nothing, refuse immediately (no LLM call).
    Returns answer text, parsed citations, and the context string (for numeric verify).
    """
    if not chunks:
        return {"answer": REFUSAL_STRING, "citations": [], "context": ""}

    context = build_context(chunks)
    user_prompt = f"Context:\n{context}\n\nQuestion: {question}"

    answer = call_llm(system=SYSTEM, user=user_prompt, temperature=0.0)
    citations = extract_citations(answer)

    return {"answer": answer, "citations": citations, "context": context}
