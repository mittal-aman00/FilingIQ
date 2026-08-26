<div align="center">

# FilingIQ

### Financial Filing Intelligence for Equity Research

**Table-aware RAG over NVIDIA SEC 10-K filings — with numerical verification, citation enforcement, cross-year comparison, and calibrated refusal.**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-8-646CFF?logo=vite&logoColor=white)](https://vitejs.dev/)
[![Pinecone](https://img.shields.io/badge/Pinecone-Vector_DB-000000)](https://www.pinecone.io/)
[![Gemini](https://img.shields.io/badge/Gemini-Embeddings-4285F4?logo=google&logoColor=white)](https://ai.google.dev/)
[![Groq](https://img.shields.io/badge/Groq-LLM-F55036)](https://groq.com/)
[![Hybrid RAG](https://img.shields.io/badge/Retrieval-BM25_+_Vector_+_RRF_+_FlashRank-f5a623)](#6--technology-stack)

**Repo:** [github.com/mittal-aman00/FilingIQ](https://github.com/mittal-aman00/FilingIQ)

</div>

---

## Table of Contents

1. [One-sentence pitch](#1--one-sentence-pitch)
2. [The problem this solves](#2--the-problem-this-solves)
3. [What FilingIQ does (functional)](#3--what-filingiq-does-functional)
4. [What FilingIQ deliberately does NOT do](#4--what-filingiq-deliberately-does-not-do)
5. [End-to-end system flow](#5--end-to-end-system-flow)
6. [Technology stack](#6--technology-stack)
7. [File-by-file technical map](#7--file-by-file-technical-map)
8. [Runtime request path (`/ask`)](#8--runtime-request-path-ask)
9. [Ingestion path (one-time / when PDFs change)](#9--ingestion-path-one-time--when-pdfs-change)
10. [Project structure](#10--project-structure)
11. [What `.gitignore` excludes (and why)](#11--what-gitignore-excludes-and-why)
12. [Quick start](#12--quick-start)
13. [Evaluation harness](#13--evaluation-harness)
14. [Security & production notes](#14--security--production-notes)
15. [Interview / portfolio talking points](#15--interview--portfolio-talking-points)

---

## 1. One-sentence pitch

An equity research analyst asks *"How did operating margin change from FY24 to FY25, and what did management attribute it to?"* — FilingIQ retrieves the exact figures from income-statement tables across years, computes the delta in Python (not the LLM), quotes management language from the MD&A, cites page and section for every number, and **refuses** if the figure is not actually disclosed.

---

## 2. The problem this solves

Most “chat with a PDF” demos fail on financial filings for five reasons:

| # | Hard problem | Why generic RAG fails |
|---|--------------|------------------------|
| 1 | **Tables carry the meaning** | Character-split chunking destroys rows/columns |
| 2 | **A wrong number is catastrophic** | Fluent hallucinations look trustworthy |
| 3 | **Period ambiguity** | “What was revenue?” silently answers the wrong year |
| 4 | **Cross-year questions** | One mixed retrieval lets the strongest year dominate top‑k |
| 5 | **Knowing when to refuse** | Guessing is worse than saying “not disclosed” |

FilingIQ is built to solve those five — not to opine on whether to buy NVIDIA stock.

---

## 3. What FilingIQ does (functional)

**Corpus:** three consecutive NVIDIA Form 10‑K PDFs (FY2024, FY2025, FY2026).

**User experience (frontend):**

1. **Mock login** — any email/password unlocks the Bloomberg-style terminal UI.
2. **Left panel** — chat thread history (persisted in browser `localStorage`), new/delete/export.
3. **Center panel** — ask questions about the ingested filings; see answers with type/verified chips.
4. **Right panel (Evidence)** — full transparency: verified badge, fiscal-year chips, interpreted intent, citations, comparison delta / sub-answers, raw API payload.

**Question types the system handles:**

| Type | Example | Behavior |
|------|---------|----------|
| **Lookup** | “What was total revenue in FY2025?” | Single-year hybrid retrieval → grounded answer + citations |
| **Explanation** | “What risks around export controls?” | Prefer prose / Risk Factors sections |
| **Comparison** | “How did operating income change FY24→FY25?” | Decompose → retrieve **per year** → Python `Decimal` math |
| **Unsupported** | “Should I buy NVDA?” / “Price next year?” | Refused at intent layer / guardrails — no investment advice |

**Trust signals returned to the UI:**

- Structured citations: `[FY2025, p.55, Section Name]`
- Numeric verification (every figure must appear in retrieved context)
- Citation verification (cited pages must have been retrieved)
- Optional regenerate-once on failure, then refuse
- Comparison `delta` / `%` computed outside the LLM

---

## 4. What FilingIQ deliberately does NOT do

- ❌ Stock picks, price targets, or forward-looking forecasts
- ❌ Answers from model “world knowledge” about NVIDIA outside the provided filings
- ❌ Mixing fiscal years in a single BM25/vector pass (by design)
- ❌ Letting the LLM do money arithmetic (Python `Decimal` does)

This scope boundary is a **product feature**, not a missing feature.

---

## 5. End-to-end system flow

### 5.1 Big picture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     REACT + VITE FRONTEND (Bloomberg UI)                  │
│   Login (mock) · History · Chat · Evidence (intent / cites / verified)    │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │  POST /ask   GET /health
┌─────────────────────────────────▼────────────────────────────────────────┐
│                         FASTAPI BACKEND (app.py)                          │
│              CORS · lifespan loads indexes once at startup                │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │
        ┌─────────────────────────┴─────────────────────────┐
        ▼                                                   ▼
┌─────────────────────┐                         ┌───────────────────────────┐
│ query_understanding │                         │     comparison path       │
│ classify → QueryIntent│                        │      (multihop.py)        │
└──────────┬──────────┘                         └─────────────┬─────────────┘
           │                                                  │
           ▼                                                  ▼
┌─────────────────────┐                         per-year retrieve + generate
│    retrieval.py     │                         + Decimal compute_delta()
│ BM25/year + Pinecone│
│ RRF → FlashRank     │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ generate + guardrails│
│ citations · numbers ·│
│ refusal calibration  │
└─────────────────────┘
```

### 5.2 Two indexes, one source of truth

| Index | Where it lives | Rebuilt when? |
|-------|----------------|---------------|
| **Vector (semantic)** | Pinecone cloud (`filingiq-nvda`) | Once via `inject_index.py` / `resume_embedding.py` |
| **BM25 (keyword)** | In memory at app start, **one retriever per fiscal year** | Every FastAPI boot from `data/chunks.jsonl` |
| **chunks.jsonl** | Git-committed plain text | When you re-run ingestion after PDF/chunking changes |

**Why BM25 is not a `.pkl` on GitHub:** pickle binaries are opaque and awkward to version. JSONL is readable, diffable, and lets `indexes.py` rebuild BM25 anywhere.

**Why one BM25 per year:** LangChain’s plain `BM25Retriever` does not hard-filter metadata well. Partitioning by `fiscal_year` makes “never mix years” automatic for Day 5/8 comparison logic.

---

## 6. Technology stack

### Parsing & chunking
| Tool | Role |
|------|------|
| **PyMuPDF4LLM** | Primary PDF → markdown (chosen after Day 1 parser benchmark) |
| **pdfplumber** | Benchmark / coordinate table extraction comparison |
| **Docling** | Evaluated then removed (RAM + Windows console Unicode issues) |
| **RecursiveCharacterTextSplitter** | Prose only (1000 / 200 overlap); **tables stay atomic** |

### Retrieval (hybrid)
| Tool | Role |
|------|------|
| **Gemini Embedding (`gemini-embedding-001`)** | Dense vectors for semantic search |
| **Pinecone** | Serverless vector store + metadata filters (`fiscal_year`) |
| **BM25 (`rank_bm25` / LangChain BM25Retriever)** | Exact tokens: “Note 14”, line items, SKUs |
| **Reciprocal Rank Fusion (RRF, k=60)** | Merge ranked ID lists from vector + BM25 (and across years) |
| **FlashRank (ms-marco MiniLM)** | Cross-encoder re-rank → final top‑k |

### Generation & safety
| Tool | Role |
|------|------|
| **Groq / Gemini 2.5 Flash** (`llm.py`, switch via `LLM_PROVIDER`) | Grounded generation + structured intent JSON |
| **Pydantic `QueryIntent`** | Forced schema for classification |
| **Guardrails** | Unsupported refuse, retrieval-score refuse, numeric verify, citation verify, one retry |
| **Python `Decimal`** | Verified arithmetic for YoY deltas (harness pattern) |

### API & UI
| Tool | Role |
|------|------|
| **FastAPI + Uvicorn** | `/ask`, `/health`, CORS for Vite |
| **React 19 + Vite 8 + React Router** | Login + 3-panel terminal |
| **localStorage** | Mock session + chat history persistence |

### Evaluation harness
| Tool | Role |
|------|------|
| **`evaluate.py` golden set** | Same pipeline as `/ask`; answer accuracy + refusal accuracy |
| **Numeric substring checks** | Objective metric for finance (stricter than fuzzy LLM judges alone) |

---

## 7. File-by-file technical map

Use this section when you return months later and need to explain *exactly* what each file owns.

### Backend — ingestion & indexes

| File | Responsibility |
|------|----------------|
| `backend/benchmark_parsers.py` | **Day 1.** Side-by-side pdfplumber vs pymupdf4llm on the income-statement page. |
| `backend/parse.py` | PDF → `ParsedDoc` of `Element`s (`heading` / `table` / `text`) with page numbers; filters PDF chrome noise. |
| `backend/injest_chunk.py` | Table-aware chunking: whole table = one chunk + section/year prefix; prose split; rich metadata. |
| `backend/convert.py` | Chunk dicts → LangChain `Document` + stable `chunk_id` (`NVDA-FY2025-p55-1`). |
| `backend/inject_index.py` | One-shot: parse all 3 filings → write `data/chunks.jsonl` → embed to Pinecone (JSONL first if embed fails). |
| `backend/resume_embedding.py` | Batch embed with progress at `data/embed_progress.json` (survives free-tier rate limits). |
| `backend/indexes.py` | Startup loader: JSONL → BM25-by-year + Pinecone connect + `chunk_lookup`. |
| `backend/config.py` | Keys, index name, embedding model, `CHUNKS_PATH`, `LLM_PROVIDER`. |

### Backend — ask pipeline

| File | Responsibility |
|------|----------------|
| `backend/llm.py` | Shared LLM client (Groq/Gemini); structured JSON mode for intent. |
| `backend/query_understanding.py` | Question → `QueryIntent` (type, years, metric, needs_table, requires_calculation). |
| `backend/retrieval.py` | Per-year hybrid search → RRF → optional table boost → FlashRank. |
| `backend/generate.py` | Prompt with labeled context; parse `[FY…, p.…, …]` citations; refusal string. |
| `backend/guardrails.py` | Pre-refuse + post-verify numbers/citations + one regenerate + final refuse. |
| `backend/multihop.py` | Comparison: decompose → per-year answers → extract figures → `compute_delta`. |
| `backend/app.py` | FastAPI lifespan + route: comparison → multihop else retrieve+guardrails. |
| `backend/evaluate.py` | Golden-set harness mirroring `/ask` (expand to ~50 Qs for full Day 9). |

### Backend — tests / smoke

| File | Responsibility |
|------|----------------|
| `backend/test_parse.py` | Spot-check parsed elements on income-statement page. |
| `backend/test_indexes.py` | BM25 exact-term vs vector semantic sanity check. |

### Frontend

| File | Responsibility |
|------|----------------|
| `frontend/src/pages/Login.jsx` | Mock auth gate. |
| `frontend/src/pages/Workspace.jsx` | 3-panel shell; calls `/ask`; persists chats. |
| `frontend/src/components/HistorySidebar.jsx` | Thread list / export JSON. |
| `frontend/src/components/ChatPanel.jsx` | Messages + suggestions + composer. |
| `frontend/src/components/EvidencePanel.jsx` | Intent, FY chips, verified, cites, delta, raw payload. |
| `frontend/src/lib/api.js` | `VITE_API_URL` → `localhost:8000`. |
| `frontend/src/lib/storage.js` | localStorage session + chats. |

### Data

| Path | Responsibility |
|------|----------------|
| `data/raw/*.pdf` | Source 10‑Ks (gitignored by default — download locally). |
| `data/chunks.jsonl` | Committed chunk source of truth for BM25 (+ metadata/`chunk_id`). |

---

## 8. Runtime request path (`/ask`)

```
User types question in ChatPanel
        │
        ▼
POST /ask { "question": "..." }     ← api.js → FastAPI app.py
        │
        ▼
classify_query()                     ← query_understanding.py (LLM, temperature=0)
        │
        ├─ question_type == comparison AND len(fiscal_years) > 1
        │         │
        │         ▼
        │   answer_comparison()       ← multihop.py
        │         for each year:
        │           retrieve(year-scoped) → generate_answer()
        │         optional compute_delta(Decimal)
        │         return { sub_answers, delta }
        │
        └─ else (lookup / explanation / unsupported)
                  │
                  ▼
            retrieve()                ← retrieval.py
              per year: Pinecone filter + BM25[year] → RRF
              fuse years → top 20 → FlashRank → top 5
                  │
                  ▼
            guarded_generate()        ← guardrails.py → generate.py
              unsupported / weak score → REFUSAL
              else generate → verify numbers + citations
              fail → retry once → still fail → REFUSAL
                  │
                  ▼
            JSON to EvidencePanel + chat bubble
```

**Key technical invariants:**

1. Intent drives **hard filters**, not only semantic similarity.
2. Comparison never does one retrieval with `fiscal_year ∈ {2024,2025,2026}` hoping for balance.
3. Numbers in answers must appear in retrieved context (computed deltas are handled on the comparison path).
4. Citations must map to retrieved `(fiscal_year, page)` pairs.

---

## 9. Ingestion path (one-time / when PDFs change)

```
data/raw/nvda_FY2024.pdf
data/raw/nvda_FY2025.pdf
data/raw/nvda_FY2026.pdf
        │
        ▼
parse_pdf()                 ← parse.py (PyMuPDF4LLM page chunks → Elements)
        │
        ▼
build_chunks()              ← injest_chunk.py (tables atomic + metadata)
        │
        ▼
chunks_to_documents()       ← convert.py (+ chunk_id)
        │
        ├──────────────────► data/chunks.jsonl          (commit this)
        │
        └──────────────────► Pinecone upsert            (cloud)
                              └─ if rate-limited:
                                   resume_embedding.py  (batched + progress file)
        │
        ▼
At API start: load_indexes()  ← indexes.py
   BM25 rebuilt in memory from JSONL (per year)
   Pinecone connected (no re-embed)
```

---

## 10. Project structure

```
FilingIQ/
├── README.md                          ← you are here
├── .gitignore
├── data/
│   ├── raw/                           ← PDFs (ignored; download locally)
│   │   ├── nvda_FY2024.pdf
│   │   ├── nvda_FY2025.pdf
│   │   └── nvda_FY2026.pdf
│   ├── chunks.jsonl                   ← committed BM25/source-of-truth
│   └── embed_progress.json            ← local resume state (ignored)
├── backend/
│   ├── .env                           ← secrets (ignored)
│   ├── app.py                         ← FastAPI entry
│   ├── config.py
│   ├── parse.py / injest_chunk.py / convert.py / inject_index.py
│   ├── resume_embedding.py
│   ├── indexes.py / retrieval.py / query_understanding.py
│   ├── generate.py / guardrails.py / multihop.py / llm.py
│   ├── evaluate.py
│   └── test_*.py / benchmark_parsers.py
└── frontend/
    ├── package.json
    ├── .env.example                   ← VITE_API_URL=http://localhost:8000
    └── src/                           ← Login + Workspace + Evidence UI
```

---

## 11. What `.gitignore` excludes (and why)

Read this before cloning or interviewing — missing these files is **intentional**.

| Ignored path | Why |
|--------------|-----|
| **`.env` / `**/.env`** | Contains `GEMINI_API_KEY`, `PINECONE_API_KEY`, `GROQ_API_KEY`. Never commit secrets. |
| **`data/raw/*.pdf`** | Large third-party SEC documents. Keep repo light; download from [SEC EDGAR](https://www.sec.gov/edgar/search/) into `data/raw/` with the expected filenames. `chunks.jsonl` is enough for BM25; Pinecone still needs your cloud index. |
| **`data/embed_progress.json`** | Local checkpoint for batched embedding resumes — machine-specific, not source. |
| **`frontend/node_modules/`** | Reinstall with `npm install`. |
| **`frontend/dist/`** | Build artifact; regenerate with `npm run build`. |
| **`__pycache__/`, `*.pyc`, `.venv/`** | Python bytecode / local virtualenvs. |
| **`backend/data/`** | Accidental local scratch relative to backend CWD. |
| **`.idea/`, `.vscode/`, `.DS_Store`** | Editor / OS noise. |

**Intentionally committed:**

| Path | Why |
|------|-----|
| **`data/chunks.jsonl`** | Source of truth so BM25 rebuilds without pickles or re-parsing PDFs. |
| **`frontend/.env.example`** | Documents `VITE_API_URL` without secrets. |
| **Application source** | Backend + frontend code. |

---

## 12. Quick start

### Prerequisites

- Python 3.12+
- Node.js 18+
- Pinecone index `filingiq-nvda` (cosine, dimension matching Gemini embeddings — typically **768** if you set `output_dimensionality=768`, otherwise match your index)
- API keys: Gemini (embeddings), Pinecone, Groq (or Gemini for generation)

### 1) Secrets

Create `backend/.env`:

```env
GEMINI_API_KEY=...
PINECONE_API_KEY=...
GROQ_API_KEY=...
```

`config.py` also reads `LLM_PROVIDER` (`groq` or `gemini`).

### 2) Data

Place filings (if not present):

```
data/raw/nvda_FY2024.pdf
data/raw/nvda_FY2025.pdf
data/raw/nvda_FY2026.pdf
```

If `data/chunks.jsonl` is already in the repo, you can skip re-chunking. You still need a populated Pinecone index (`inject_index.py` or `resume_embedding.py`).

### 3) Backend

```bash
cd backend
pip install langchain-core langchain-community langchain-google-genai langchain-pinecone pinecone rank-bm25 python-dotenv fastapi uvicorn flashrank langchain-text-splitters pymupdf4llm pdfplumber pydantic google-genai
# plus your Groq client deps as used in llm.py

uvicorn app:app --reload --port 8000
```

Health check: `http://127.0.0.1:8000/health`

### 4) Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** — sign in with any email/password.

---

## 13. Evaluation harness

`backend/evaluate.py` runs the **same code path as `/ask`** over a golden set and reports:

- **Answer accuracy** — expected figure substring present (finance-grade, binary)
- **Refusal accuracy** — unanswerable questions correctly decline (“not disclosed…”)

The checked-in golden set is a **template**. For a portfolio-complete Day 9, expand to ~50 questions across lookup / prose / comparison / ambiguous / unanswerable, with every `expected_contains` verified by hand against the PDFs.

```bash
cd backend
python evaluate.py
```

---

## 14. Security & production notes

**Already in place:**

- Secrets via `.env` (gitignored)
- Intent-layer refusal for investment advice / predictions
- Numeric + citation verifiers before showing answers
- CORS limited to local Vite origins in `app.py`
- Mock login only (demo UX — not enterprise auth)

**Before real production:**

- Replace mock login with real auth (JWT / OAuth)
- Lock CORS to your deployed frontend domain
- Rate-limit `/ask` (LLM + embedding cost control)
- Pin `requirements.txt` versions
- Do not commit live API keys; rotate any key that ever leaked
- Optionally add PDF download script instead of shipping filings

---

<div align="center">

### FilingIQ

**Retrieve what the filing says. Verify every number. Refuse when you can’t.**

Built with **PyMuPDF4LLM · Pinecone · BM25 · RRF · FlashRank · FastAPI · Groq/Gemini · React/Vite**

</div>
