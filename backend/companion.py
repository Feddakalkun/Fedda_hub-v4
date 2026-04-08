"""
Fedda Hub v4 — Co-Partner Agent
A personal companion with full memory control: remember & forget on demand.
Each avatar has a unique personality and isolated SQLite memory store.
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
COMPANION_DB_PATH = BASE_DIR / "companion_memories.db"

OLLAMA = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

router = APIRouter(prefix="/companion", tags=["companion"])

# ── Avatar definitions ────────────────────────────────────────────────────────

AVATARS = [
    {
        "id": "maya",
        "name": "Maya",
        "emoji": "🌸",
        "tagline": "Warm life coach & emotional support",
        "color": "#f472b6",
        "gradient": "linear-gradient(135deg, #f472b6, #ec4899)",
        "bg": "rgba(244,114,182,0.08)",
        "border": "rgba(244,114,182,0.25)",
        "personality": (
            "You are Maya, a warm, empathetic life coach and emotional support partner. "
            "You listen deeply, celebrate wins, and gently challenge limiting beliefs. "
            "You remember everything the user shares and use it to give deeply personal advice. "
            "Your tone is caring, encouraging, and occasionally playful. "
            "Use the user's name and memories to make every response feel personal."
        ),
    },
    {
        "id": "emma",
        "name": "Emma",
        "emoji": "💎",
        "tagline": "Sharp analyst & strategic advisor",
        "color": "#38bdf8",
        "gradient": "linear-gradient(135deg, #38bdf8, #0ea5e9)",
        "bg": "rgba(56,189,248,0.08)",
        "border": "rgba(56,189,248,0.25)",
        "personality": (
            "You are Emma, a sharp, analytical strategic advisor and thought partner. "
            "You think in systems, spot patterns, and cut through noise to what matters. "
            "You remember the user's goals, projects, and decisions to give sharp, contextual advice. "
            "Your tone is direct, precise, and intellectually stimulating. "
            "Challenge assumptions, offer frameworks, and be brutally honest when needed."
        ),
    },
    {
        "id": "alex",
        "name": "Alex",
        "emoji": "⚡",
        "tagline": "Creative spark & brainstorm partner",
        "color": "#4ade80",
        "gradient": "linear-gradient(135deg, #4ade80, #22c55e)",
        "bg": "rgba(74,222,128,0.08)",
        "border": "rgba(74,222,128,0.25)",
        "personality": (
            "You are Alex, a wildly creative brainstorming partner and idea generator. "
            "You make unexpected connections, push creative boundaries, and inject energy into every session. "
            "You remember the user's creative projects, interests, and ideas to build on them. "
            "Your tone is enthusiastic, playful, and idea-dense. "
            "Always offer multiple angles, unexpected twists, and practical next steps."
        ),
    },
    {
        "id": "kai",
        "name": "Kai",
        "emoji": "🌙",
        "tagline": "Calm philosopher & deep thinker",
        "color": "#fb923c",
        "gradient": "linear-gradient(135deg, #fb923c, #f97316)",
        "bg": "rgba(251,146,60,0.08)",
        "border": "rgba(251,146,60,0.25)",
        "personality": (
            "You are Kai, a calm, philosophical deep thinker and long-term thinking partner. "
            "You ask profound questions, help the user see the bigger picture, and find meaning in complexity. "
            "You remember the user's beliefs, questions, and philosophical musings to go deeper. "
            "Your tone is measured, thoughtful, and occasionally poetic. "
            "Help the user think — don't just give answers, illuminate the path."
        ),
    },
]

AVATAR_MAP = {a["id"]: a for a in AVATARS}

# ── SQLite memory store ───────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(COMPANION_DB_PATH), check_same_thread=False)
    c.execute("""
        CREATE TABLE IF NOT EXISTS companion_memories (
            memory_id   TEXT PRIMARY KEY,
            avatar_id   TEXT NOT NULL,
            content     TEXT NOT NULL,
            tags        TEXT DEFAULT '[]',
            pinned      INTEGER DEFAULT 0,
            created_at  TEXT NOT NULL
        )
    """)
    c.commit()
    return c


def _list_memories(avatar_id: str) -> list[dict]:
    db = _conn()
    rows = db.execute(
        "SELECT memory_id, content, tags, pinned, created_at FROM companion_memories "
        "WHERE avatar_id = ? ORDER BY pinned DESC, created_at DESC",
        (avatar_id,)
    ).fetchall()
    db.close()
    return [
        {"memory_id": r[0], "content": r[1], "tags": json.loads(r[2] or "[]"),
         "pinned": bool(r[3]), "created_at": r[4]}
        for r in rows
    ]


def _add_memory(avatar_id: str, content: str, tags: list[str], pinned: bool = False) -> dict:
    mid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    db = _conn()
    db.execute(
        "INSERT INTO companion_memories (memory_id, avatar_id, content, tags, pinned, created_at) VALUES (?,?,?,?,?,?)",
        (mid, avatar_id, content.strip(), json.dumps(tags), int(pinned), now)
    )
    db.commit()
    db.close()
    return {"memory_id": mid, "content": content, "tags": tags, "pinned": pinned, "created_at": now}


def _delete_memory(avatar_id: str, memory_id: str) -> bool:
    db = _conn()
    cur = db.execute(
        "DELETE FROM companion_memories WHERE memory_id = ? AND avatar_id = ?",
        (memory_id, avatar_id)
    )
    db.commit()
    db.close()
    return cur.rowcount > 0


def _delete_all_memories(avatar_id: str) -> int:
    db = _conn()
    cur = db.execute("DELETE FROM companion_memories WHERE avatar_id = ?", (avatar_id,))
    db.commit()
    db.close()
    return cur.rowcount


def _build_memory_context(avatar_id: str) -> str:
    memories = _list_memories(avatar_id)
    if not memories:
        return ""
    pinned = [m for m in memories if m["pinned"]]
    regular = [m for m in memories if not m["pinned"]]
    parts = []
    if pinned:
        parts.append("## 📌 Pinned memories\n" + "\n".join(f"- {m['content']}" for m in pinned))
    if regular:
        recent = regular[:20]
        parts.append("## 🧠 Remembered context\n" + "\n".join(f"- {m['content']}" for m in recent))
    return "\n\n".join(parts)

# ── Pydantic models ───────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    avatar_id: str
    model: str
    messages: List[ChatMessage]

class AddMemoryRequest(BaseModel):
    content: str
    tags: List[str] = []
    pinned: bool = False

# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/avatars")
def get_avatars():
    return AVATARS


@router.get("/memories/{avatar_id}")
def list_memories(avatar_id: str):
    if avatar_id not in AVATAR_MAP:
        raise HTTPException(404, "Avatar not found")
    return _list_memories(avatar_id)


@router.post("/memories/{avatar_id}")
def add_memory(avatar_id: str, body: AddMemoryRequest):
    if avatar_id not in AVATAR_MAP:
        raise HTTPException(404, "Avatar not found")
    return _add_memory(avatar_id, body.content, body.tags, body.pinned)


@router.delete("/memories/{avatar_id}/{memory_id}")
def forget_memory(avatar_id: str, memory_id: str):
    if avatar_id not in AVATAR_MAP:
        raise HTTPException(404, "Avatar not found")
    ok = _delete_memory(avatar_id, memory_id)
    if not ok:
        raise HTTPException(404, "Memory not found")
    return {"ok": True}


@router.delete("/memories/{avatar_id}")
def forget_all_memories(avatar_id: str):
    if avatar_id not in AVATAR_MAP:
        raise HTTPException(404, "Avatar not found")
    count = _delete_all_memories(avatar_id)
    return {"deleted": count}


@router.post("/chat")
async def companion_chat(body: ChatRequest):
    avatar = AVATAR_MAP.get(body.avatar_id)
    if not avatar:
        raise HTTPException(404, "Avatar not found")

    memory_context = _build_memory_context(body.avatar_id)
    system_content = avatar["personality"]
    if memory_context:
        system_content += f"\n\n{memory_context}"
    system_content += (
        "\n\n## Memory instructions\n"
        "When the user shares something important (name, goal, preference, fact), "
        "respond normally AND on a NEW line at the very end of your reply write:\n"
        "REMEMBER: <the thing to remember>\n"
        "Only do this for genuinely important, lasting information. "
        "Do NOT do this for casual conversation or temporary context."
    )

    ollama_messages = [{"role": "system", "content": system_content}]
    for m in body.messages:
        ollama_messages.append({"role": m.role, "content": m.content})

    return StreamingResponse(
        _stream_companion(body.avatar_id, body.model, ollama_messages),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _stream_companion(avatar_id: str, model: str, messages: list) -> AsyncGenerator[str, None]:
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {"temperature": 0.75},
    }

    full_text = ""
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", f"{OLLAMA}/api/chat", json=payload) as resp:
                async for raw in resp.aiter_lines():
                    if not raw.strip():
                        continue
                    try:
                        data = json.loads(raw)
                    except Exception:
                        continue

                    token = data.get("message", {}).get("content", "")
                    if token:
                        full_text += token
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

                    if data.get("done"):
                        break

        # Auto-extract REMEMBER: directives
        auto_memories = []
        lines = full_text.splitlines()
        for line in lines:
            stripped = line.strip()
            if stripped.upper().startswith("REMEMBER:"):
                content = stripped[9:].strip()
                if content:
                    mem = _add_memory(avatar_id, content, ["auto"], pinned=False)
                    auto_memories.append(mem)

        if auto_memories:
            yield f"data: {json.dumps({'type': 'memories_added', 'memories': auto_memories})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
