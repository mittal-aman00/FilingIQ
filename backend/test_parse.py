# """
# test_parse.py — Manual Day 1/2 check: does parse_pdf preserve the income statement?

# ROLE
#   Spot-check Element typing + table markdown on a known page before full ingestion.

# HOW TO RUN
#   cd backend
#   python test_parse.py

# TIP
#   Adjust income_stmt_page if your PDF's page numbering differs by year
#   (FY2025 income statement was around p.55 in earlier runs).
# """

# from parse import parse_pdf
# from pathlib import Path

# ROOT = Path(__file__).resolve().parent.parent
# PDF = ROOT / "data" / "raw" / "nvda_FY2025.pdf"

# # Prefer absolute path via ROOT so cwd does not matter
# parsed = parse_pdf(str(PDF))

# # Filter to the income-statement page and print typed elements
# income_stmt_page = 54
# table_elements = [el for el in parsed.elements if el.page == income_stmt_page]

# print(f"Total elements in filing: {len(parsed.elements)}")
# print(f"Elements on page {income_stmt_page}: {len(table_elements)}")
# for el in table_elements:
#     print(f"[{el.type}] {el.text[:1000]}")

# # Optional diagnostics (uncomment when debugging pymupdf page metadata):
# # import pymupdf4llm
# # pages = pymupdf4llm.to_markdown(str(PDF), page_chunks=True, use_ocr=False)
# # print("Keys per page:", pages[5].keys())
# # print("Metadata keys:", pages[5]["metadata"].keys())
# # print("Page number:", pages[5]["metadata"].get("page_number"))





# # quick check — REPL or a scratch script
# from indexes import load_indexes

# vectorstore, bm25_by_year, chunk_lookup = load_indexes()
# print(f"Chunk lookup size: {len(chunk_lookup)}")   # should be 2762
# print(f"Years available: {sorted(bm25_by_year.keys())}")   # [2024, 2025, 2026]




from indexes import load_indexes
from query_understanding import classify_query
from retrieval import retrieve
from multihop import answer_comparison


vectorstore, bm25_by_year, chunk_lookup = load_indexes()

# question = "Should I buy NVIDIA stock right now?"
# intent = classify_query(question)
# print(intent)

# results = retrieve(question, intent, vectorstore, bm25_by_year, chunk_lookup)
# for r in results:
#     print(f"score={r['score']:.3f} page={r['metadata']['page']} table={r['metadata']['is_table']}")
#     print(r['content'][:150], "\n")


question = "How did revenue change from FY2024 to FY2025?"
intent = classify_query(question)
result = answer_comparison(question, intent, vectorstore, bm25_by_year, chunk_lookup)

for s in result["sub_answers"]:
    print(s["year"], "→", s["extracted_figure"], "|", s["answer"][:100])
print("Delta:", result["delta"])

from guardrails import guarded_generate


# print("\n--- ANSWER ---")
# print(result["answer"])
# print("\n--- CITATIONS ---")
# print(result["citations"])



# import config
# print(config.__file__)
# print(dir(config))



from generate import generate_answer
from guardrails import verify_numbers, verify_citations

raw = generate_answer(question, results)
print("RAW ANSWER:", raw["answer"])
print("CITATIONS FOUND:", raw["citations"])

numbers_ok, bad_numbers = verify_numbers(raw["answer"], raw["context"])
print("Numbers OK:", numbers_ok, "| Flagged as unverified:", bad_numbers)

citations_ok = verify_citations(raw["answer"], results)
print("Citations OK:", citations_ok)