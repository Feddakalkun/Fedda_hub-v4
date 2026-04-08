"""
Fedda Hub v4 — Long-term memory module
- ChromaDB for semantic memory (turn summaries)
- SQLite for explicit key/value facts
"""

import os
import sqlite3
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
MEMORY_DB_DIR = BASE_DIR / "memory_db"
FACTS_DB_PATH = BASE_DIR / "facts.db"

MEMORY_DB_DIR.mkdir(parents=True, exist_ok=True)

# ── ChromaDB setup ───────────────────────────────────────────────────────────

_chroma_client = None
_collection = None


def _get_collection():
    global _chroma_client, _collection
    if _collection is None:
        import chromadb
        from chromadb.utils import embedding_functions

        _chroma_client = chromadb.PersistentClient(path=str(MEMORY_DB_DIR))
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        _collection = _chroma_client.get_or_create_collection(
            name="fedda_memory", embedding_function=ef
        )
    return _collection


# ── Semantic memory ──────────────────────────────────────────────────────────

def save_memory(text: str, metadata: dict | None = None) -> None:
    """Embed and store a turn summary in ChromaDB."""
    import uuid
    col = _get_collection()
    doc_id = str(uuid.uuid4())
    col.add(
        documents=[text],
        metadatas=[metadata or {}],
        ids=[doc_id],
    )


def query_memory(text: str, n: int = 5) -> list[str]:
    """Return top-n relevant memories for the given query text."""
    col = _get_collection()
    count = col.count()
    if count == 0:
        return []
    results = col.query(query_texts=[text], n_results=min(n, count))
    docs = results.get("documents", [[]])[0]
    return docs


# ── Facts (SQLite) ───────────────────────────────────────────────────────────

def _get_facts_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(FACTS_DB_PATH))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS facts (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    conn.commit()
    return conn


def save_fact(key: str, value: str) -> None:
    """Store an explicit key/value fact (upsert)."""
    conn = _get_facts_conn()
    conn.execute(
        "INSERT INTO facts (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key.strip(), value.strip()),
    )
    conn.commit()
    conn.close()


def get_facts() -> str:
    """Return all stored facts as a formatted string."""
    conn = _get_facts_conn()
    rows = conn.execute("SELECT key, value FROM facts ORDER BY key").fetchall()
    conn.close()
    if not rows:
        return "(no facts stored)"
    return "\n".join(f"• {k}: {v}" for k, v in rows)
