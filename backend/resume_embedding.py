# resume_embedding.py
"""Resume Pinecone embedding in batches with progress saved to disk.

Progress file lives at FilingIQ/data/embed_progress.json (next to chunks.jsonl).
A relative path like "data/embed_progress.json" fails when you run from
backend/, because backend/data/ does not exist — that caused FileNotFoundError.
"""
import json
import time
from pathlib import Path

from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_pinecone import PineconeVectorStore
import config

# Absolute path under project data/ (same folder as chunks.jsonl)
PROGRESS_PATH = Path(config.ROOT) / "data" / "embed_progress.json"


def load_progress() -> int:
    """Returns how many chunks are already embedded. 0 if starting fresh."""
    if PROGRESS_PATH.exists():
        with open(PROGRESS_PATH, encoding="utf-8") as f:
            return json.load(f)["embedded_count"]
    return 0


def save_progress(count: int) -> None:
    """Write progress; create data/ if missing so open() never fails."""
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
        json.dump({"embedded_count": count}, f)


def load_chunks_as_documents() -> list:
    """Loads from the already-parsed chunks.jsonl — no re-parsing needed."""
    documents = []
    with open(config.CHUNKS_PATH, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            documents.append(
                Document(page_content=row["content"], metadata=row["metadata"])
            )
    return documents


def resume_embedding(batch_size: int = 90, pause_seconds: int = 65):
    documents = load_chunks_as_documents()
    total = len(documents)
    already_done = load_progress()

    if already_done >= total:
        print(f"All {total} chunks already embedded. Nothing left to do.")
        return

    print(f"Starting from chunk {already_done}/{total}")
    print(f"Progress file: {PROGRESS_PATH}")

    embeddings = GoogleGenerativeAIEmbeddings(
        model=config.EMBEDDING_MODEL, google_api_key=config.GEMINI_API_KEY
    )
    vectorstore = PineconeVectorStore.from_existing_index(
        index_name=config.INDEX_NAME, embedding=embeddings
    )

    for i in range(already_done, total, batch_size):
        batch = documents[i : i + batch_size]
        attempt = 0
        while attempt < 3:
            try:
                vectorstore.add_documents(batch)
                new_count = i + len(batch)
                save_progress(new_count)
                print(f"Embedded {new_count}/{total} chunks (progress saved)")
                break
            except Exception as e:
                if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                    attempt += 1
                    if attempt >= 3:
                        print(f"\nStopped at {i}/{total} — likely today's daily quota.")
                        print(
                            "Progress is saved — re-run this script tomorrow to continue."
                        )
                        return
                    wait = 20 * attempt
                    print(f"Rate limited — waiting {wait}s (attempt {attempt}/3)...")
                    time.sleep(wait)
                else:
                    raise
        if i + batch_size < total:
            time.sleep(pause_seconds)

    print(f"\nAll {total} chunks embedded successfully!")


if __name__ == "__main__":
    resume_embedding()
