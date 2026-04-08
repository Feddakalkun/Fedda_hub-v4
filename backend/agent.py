"""
Fedda Hub v4 — Agent backend
Handles tool-calling loop: Ollama → tool execution → Ollama → stream to client
"""

import json
import os
import platform
import subprocess
import urllib.parse
import urllib.request
from typing import AsyncGenerator

import httpx
import psutil
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

OLLAMA = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

app = FastAPI(title="Fedda Agent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Tool definitions sent to Ollama ─────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "shell",
            "description": (
                "Run a shell command and return stdout + stderr. "
                "Use PowerShell syntax on Windows. Prefer short, safe commands."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to execute"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a local file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative file path"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write (or overwrite) a local file with given content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and folders at a path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path (default: current dir)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web with DuckDuckGo and return top results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sysinfo",
            "description": "Get CPU, RAM, disk usage and OS information.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

# ── Tool executor ────────────────────────────────────────────────────────────

def execute_tool(name: str, args: dict) -> str:
    try:
        if name == "shell":
            cmd = args["command"]
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", cmd],
                    capture_output=True, text=True, timeout=30,
                )
            else:
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=30,
                )
            out = (result.stdout or "") + (result.stderr or "")
            return out[:5000].strip() or "(no output)"

        elif name == "read_file":
            with open(args["path"], "r", encoding="utf-8", errors="replace") as f:
                return f.read()[:8000]

        elif name == "write_file":
            path = args["path"]
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(args["content"])
            return f"✓ Written {len(args['content'])} chars to {path}"

        elif name == "list_dir":
            path = args.get("path", ".")
            entries = sorted(os.listdir(path))
            lines = [
                ("📁 " if os.path.isdir(os.path.join(path, e)) else "📄 ") + e
                for e in entries
            ]
            return "\n".join(lines) or "(empty)"

        elif name == "web_search":
            q = urllib.parse.quote(args["query"])
            url = (
                f"https://api.duckduckgo.com/?q={q}"
                "&format=json&no_redirect=1&no_html=1&skip_disambig=1"
            )
            with urllib.request.urlopen(url, timeout=10) as r:
                data = json.loads(r.read())
            parts: list[str] = []
            if data.get("AbstractText"):
                parts.append(data["AbstractText"])
            for item in data.get("RelatedTopics", [])[:6]:
                if isinstance(item, dict) and item.get("Text"):
                    parts.append(item["Text"])
            return "\n\n".join(parts) or "No results found."

        elif name == "sysinfo":
            cpu = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            return (
                f"OS: {platform.system()} {platform.release()}\n"
                f"CPU: {cpu}%  ({psutil.cpu_count()} cores)\n"
                f"RAM: {mem.used // 1024**2} MB / {mem.total // 1024**2} MB  ({mem.percent}%)\n"
                f"Disk: {disk.used // 1024**3} GB / {disk.total // 1024**3} GB  ({disk.percent}%)"
            )

        return f"Unknown tool: {name}"
    except Exception as e:
        return f"Tool error ({name}): {e}"


# ── SSE event helper ─────────────────────────────────────────────────────────

def sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


# ── Agent loop ───────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    model: str
    messages: list[dict]


async def agent_stream(model: str, messages: list[dict]) -> AsyncGenerator[str, None]:
    """
    1. Call Ollama (no-stream) to let the model decide on tools.
    2. Execute any tool calls, append results, repeat (max 8 rounds).
    3. Call Ollama again with stream=True for the final human-readable answer.
    """
    history = list(messages)
    max_rounds = 8

    async with httpx.AsyncClient(timeout=120) as client:
        for _ in range(max_rounds):
            # Non-streaming call to get tool decisions
            resp = await client.post(
                f"{OLLAMA}/api/chat",
                json={"model": model, "messages": history, "tools": TOOLS, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()
            msg = data.get("message", {})
            tool_calls = msg.get("tool_calls") or []

            if not tool_calls:
                break  # No tools needed — proceed to streaming answer

            # Append assistant tool-call message to history
            history.append({"role": "assistant", "content": msg.get("content", ""), "tool_calls": tool_calls})

            # Execute each tool and stream progress events
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}

                yield sse({"type": "tool_start", "name": name, "args": args})
                result = execute_tool(name, args)
                yield sse({"type": "tool_end", "name": name, "result": result})

                history.append({"role": "tool", "content": result})

        # Streaming final answer
        async with client.stream(
            "POST",
            f"{OLLAMA}/api/chat",
            json={"model": model, "messages": history, "stream": True},
        ) as stream:
            async for line in stream.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield sse({"type": "token", "content": token})
                    if chunk.get("done"):
                        break
                except Exception:
                    pass

    yield sse({"type": "done"})


@app.post("/agent/chat")
async def chat(req: ChatRequest):
    return StreamingResponse(
        agent_stream(req.model, req.messages),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
