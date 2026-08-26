"""
app.py — Day 10: FastAPI entrypoint for FilingIQ.

ROLE
  HTTP API that loads indexes once at startup and serves:
    GET  /health  — liveness + which fiscal years are loaded
    POST /ask     — full RAG pipeline (classify → retrieve/compare → guardrails)

PIPELINE POSITION
  Client → /ask → classify_query
                 ├─ comparison (2+ years) → answer_comparison (Day 8)
                 └─ else → retrieve + guarded_generate (Days 5–7)

HOW TO RUN LOCALLY
  cd backend
  uvicorn app:app --reload

STARTUP
  lifespan() calls load_indexes() and stores:
    app.state.vectorstore, bm25_by_year, chunk_lookup
  Same objects evaluate.py uses — live and eval stay aligned.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from indexes import load_indexes
from query_understanding import classify_query
from retrieval import retrieve
from guardrails import guarded_generate
from multihop import answer_comparison


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Boot: rebuild BM25 from JSONL + connect Pinecone. Tear down: nothing special."""
    app.state.vectorstore, app.state.bm25_by_year, app.state.chunk_lookup = load_indexes()
    yield


app = FastAPI(lifespan=lifespan)

# Local Vite + production Vercel. Extra origins via FRONTEND_ORIGIN (comma-separated).
_cors_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "https://filing-iq-seven.vercel.app",
]
_cors_origins += [
    o.strip()
    for o in os.environ.get("FRONTEND_ORIGIN", "").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    """JSON body for POST /ask."""
    question: str


@app.get("/health")
async def health():
    """Cheap probe for Railway/Render — confirms boot + loaded years."""
    return {
        "status": "ok",
        "fiscal_years_loaded": sorted(app.state.bm25_by_year.keys()),
    }


@app.post("/ask")
async def ask(req: AskRequest):
    """
    Main Q&A endpoint.

    Routes comparisons through Day 8; everything else through single-pass
    retrieval + Day 6/7 guardrails (including unsupported → refusal).
    """
    try:
        intent = classify_query(req.question)

        # Cross-year: decompose + per-year retrieve (never one mixed retrieval)
        if intent.question_type == "comparison" and len(intent.fiscal_years) > 1:
            result = answer_comparison(
                req.question,
                intent,
                app.state.vectorstore,
                app.state.bm25_by_year,
                app.state.chunk_lookup,
            )
            return {"type": "comparison", **result}

        # lookup / explanation / unsupported (unsupported refused inside guardrails)
        chunks = retrieve(
            req.question,
            intent,
            app.state.vectorstore,
            app.state.bm25_by_year,
            app.state.chunk_lookup,
        )
        result = guarded_generate(req.question, chunks, intent)
        return {"type": "single", "intent": intent.model_dump(), **result}
    except Exception as e:
        # Return JSON 500 (with CORS) instead of crashing the worker → opaque 502
        from fastapi.responses import JSONResponse

        print(f"/ask failed: {type(e).__name__}: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": type(e).__name__, "detail": str(e)},
        )
