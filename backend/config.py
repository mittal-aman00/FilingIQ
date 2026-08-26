"""
config.py — Shared settings for FilingIQ.

ROLE
  Single place for API keys, model names, and filesystem paths.
  Every other module imports from here so credentials/paths are not scattered.

PIPELINE POSITION
  Loaded first by almost every Day 3–10 module.

NOTES
  - .env lives next to this file (backend/.env), not at the project root.
  - CHUNKS_PATH points at FilingIQ/data/chunks.jsonl (next to the PDFs).
  - Keys are required at import time: missing GEMINI/PINECONE keys crash early.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Resolve paths from this file so scripts work from any working directory
BACKEND_DIR = Path(__file__).resolve().parent   # .../FilingIQ/backend
ROOT = BACKEND_DIR.parent                       # .../FilingIQ

# Load secrets from backend/.env into os.environ
load_dotenv(BACKEND_DIR / ".env")

# --- API credentials (required) ---
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
PINECONE_API_KEY = os.environ["PINECONE_API_KEY"]

# --- Vector index ---
# Pinecone index name must already exist (create once in Pinecone console / script)
INDEX_NAME = "filingiq-nvda"
# Gemini embedding model; dimension must match the Pinecone index (typically 768)
EMBEDDING_MODEL = "models/gemini-embedding-001"

# --- Keyword-index source of truth ---
# Written by inject_index.py; read by indexes.py at app/eval startup.
# Deliberately committed to git (not a pickle) so BM25 can be rebuilt anywhere.
CHUNKS_PATH = str(ROOT / "data" / "chunks.jsonl")

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
# Set LLM_PROVIDER=groq|gemini in env (Render / .env). Default: groq.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "groq").strip().lower()