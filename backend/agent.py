"""
Fedda Hub v4 — Agent backend
Handles tool-calling loop: Ollama → tool execution → Ollama → stream to client

New in this version:
- Long-term memory (ChromaDB semantic + SQLite facts)
- Kokoro TTS  (/tts)
- Faster-Whisper STT  (/stt)
- Playwright browser tools (browser_goto, browser_screenshot, browser_search)
- Task planner tools (create_plan, mark_step_done)
- remember_fact / recall_facts
"""

import json
import os
import platform
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from typing import AsyncGenerator

import httpx
import psutil
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ── Sibling routers ──────────────────────────────────────────────────────────
from tts import router as tts_router
from stt import router as stt_router
from comfy import router as comfy_router
from companion import router as companion_router

# ── Memory helpers (imported lazily-safe at module level) ────────────────────
import memory as mem_module

OLLAMA = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
HOME = os.path.expanduser("~")

BASE_DIR = Path(__file__).parent
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
PLANS_DIR = BASE_DIR / "plans"
SCREENSHOTS_DIR.mkdir(exist_ok=True)
PLANS_DIR.mkdir(exist_ok=True)

# ── System prompt (rebuilt per-request to include live facts) ────────────────

_SYSTEM_PROMPT_BASE = (
    f"You are Fedda, a smart local AI assistant running on {platform.system()} {platform.release()}. "
    f"The user's home directory is: {HOME}. "
    f"Always use Windows-style paths with backslashes (e.g. C:\\\\Users\\\\...). "
    f"When listing Downloads, Documents, Desktop etc., expand them from the home dir: "
    f"{HOME}\\\\Downloads, {HOME}\\\\Documents, etc.\n\n"
    "## Available tools\n"
    "- **shell** — Run PowerShell commands on Windows.\n"
    "- **read_file** — Read any local file.\n"
    "- **write_file** — Write or overwrite a local file.\n"
    "- **list_dir** — List files and folders in a directory.\n"
    "- **web_search** — Search the web with DuckDuckGo.\n"
    "- **sysinfo** — Get CPU, RAM, disk and OS info.\n"
    "- **remember_fact(key, value)** — Persistently store a user fact (name, preference, etc.).\n"
    "- **recall_facts()** — Retrieve all stored facts about the user.\n"
    "- **browser_goto(url)** — Open a URL in a real browser, return page title + text.\n"
    "- **browser_screenshot(filename)** — Screenshot a browser page and save to disk.\n"
    "- **browser_search(query)** — Google a query in a real browser, return results.\n"
    "- **create_plan(goal, steps)** — Save a structured step-by-step plan to disk.\n"
    "- **mark_step_done(step_index)** — Mark a plan step as completed.\n"
    "- **comfyui_generate(prompt, negative, steps, width, height)** — Generate an image with Stable Diffusion via ComfyUI (must be running on port 8188).\n\n"
    "Be concise, helpful, and proactive — use tools whenever they would give a better answer. "
    "You have persistent memory: relevant past context will be prepended to your system prompt. "
    "Always check facts before making assumptions about the user."
)


def build_system_prompt(query: str) -> str:
    """Build system prompt with injected memory + facts for this request."""
    parts = [_SYSTEM_PROMPT_BASE]

    # Inject relevant memories
    try:
        memories = mem_module.query_memory(query, n=5)
        if memories:
            parts.append("\n## Relevant memories from past conversations\n" + "\n".join(f"- {m}" for m in memories))
    except Exception:
        pass

    # Inject facts
    try:
        facts = mem_module.get_facts()
        if facts != "(no facts stored)":
            parts.append(f"\n## Known facts about the user\n{facts}")
    except Exception:
        pass

    return "\n".join(parts)


app = FastAPI(title="Fedda Agent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(tts_router)
app.include_router(stt_router)
app.include_router(comfy_router, prefix="/comfy")
app.include_router(companion_router, prefix="/api")

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
    {
        "type": "function",
        "function": {
            "name": "remember_fact",
            "description": (
                "Persistently store a fact about the user (name, preference, location, etc.). "
                "Use this whenever the user shares personal information you should remember."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Fact label, e.g. 'name' or 'favourite_language'"},
                    "value": {"type": "string", "description": "The value to store"},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_facts",
            "description": "Return all facts previously stored about the user.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_goto",
            "description": "Navigate a real browser to a URL and return the page title and first 2000 characters of visible text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL including scheme (https://)"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_screenshot",
            "description": "Take a screenshot of the current browser page and save it to disk. Returns the saved file path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Filename for the screenshot (without path), e.g. 'page.png'"},
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_search",
            "description": "Search Google using a real browser and return the top search result snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_plan",
            "description": "Save a structured step-by-step plan for a goal to disk. Use this to break down complex tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "description": "The overall goal of the plan"},
                    "steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ordered list of steps to achieve the goal",
                    },
                },
                "required": ["goal", "steps"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mark_step_done",
            "description": "Mark a step in the current plan as done by its zero-based index. Returns the updated plan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "step_index": {"type": "integer", "description": "Zero-based index of the step to mark done"},
                },
                "required": ["step_index"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "comfyui_generate",
            "description": "Generate an image using ComfyUI (Stable Diffusion). Provide a text prompt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Positive prompt describing the image"},
                    "negative": {"type": "string", "description": "Negative prompt (what to avoid)", "default": ""},
                    "steps": {"type": "integer", "description": "Number of steps (default 20)", "default": 20},
                    "width": {"type": "integer", "default": 512},
                    "height": {"type": "integer", "default": 512},
                },
                "required": ["prompt"],
            },
        },
    },
]

# ── Tool executor ────────────────────────────────────────────────────────────

PLAN_FILE = PLANS_DIR / "current_plan.json"


def execute_tool(name: str, args: dict) -> str:
    try:
        # ── Original tools ───────────────────────────────────────────────────
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
            path = os.path.expanduser(args.get("path", "."))
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
            disk_path = "C:\\" if platform.system() == "Windows" else "/"
            disk = psutil.disk_usage(disk_path)
            return (
                f"OS: {platform.system()} {platform.release()}\n"
                f"CPU: {cpu}%  ({psutil.cpu_count()} cores)\n"
                f"RAM: {mem.used // 1024**2} MB / {mem.total // 1024**2} MB  ({mem.percent}%)\n"
                f"Disk: {disk.used // 1024**3} GB / {disk.total // 1024**3} GB  ({disk.percent}%)"
            )

        # ── Memory tools ─────────────────────────────────────────────────────
        elif name == "remember_fact":
            mem_module.save_fact(args["key"], args["value"])
            return f"✓ Remembered: {args['key']} = {args['value']}"

        elif name == "recall_facts":
            return mem_module.get_facts()

        # ── Browser tools ────────────────────────────────────────────────────
        elif name == "browser_goto":
            from playwright.sync_api import sync_playwright
            url = args["url"]
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=30000)
                title = page.title()
                text = page.inner_text("body")[:2000]
                browser.close()
            return f"Title: {title}\n\n{text}"

        elif name == "browser_screenshot":
            from playwright.sync_api import sync_playwright
            filename = Path(args["filename"]).name  # strip any path component
            out_path = SCREENSHOTS_DIR / filename
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.screenshot(path=str(out_path))
                browser.close()
            return f"✓ Screenshot saved to {out_path}"

        elif name == "browser_search":
            from playwright.sync_api import sync_playwright
            query = args["query"]
            search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(search_url, timeout=30000)
                # Extract result snippets from common Google result selectors
                results: list[str] = []
                for el in page.query_selector_all("div.BNeawe, div.VwiC3b, span.aCOpRe"):
                    txt = el.inner_text().strip()
                    if txt and txt not in results:
                        results.append(txt)
                    if len(results) >= 10:
                        break
                browser.close()
            return "\n\n".join(results) if results else "No results found."

        # ── Task planner tools ───────────────────────────────────────────────
        elif name == "create_plan":
            plan = {
                "goal": args["goal"],
                "steps": [{"index": i, "text": s, "done": False} for i, s in enumerate(args["steps"])],
            }
            PLAN_FILE.write_text(json.dumps(plan, indent=2), encoding="utf-8")
            step_list = "\n".join(f"  [{i}] {s}" for i, s in enumerate(args["steps"]))
            return f"✓ Plan created for goal: {args['goal']}\nSteps:\n{step_list}"

        elif name == "mark_step_done":
            if not PLAN_FILE.exists():
                return "No active plan found. Use create_plan first."
            plan = json.loads(PLAN_FILE.read_text(encoding="utf-8"))
            idx = int(args["step_index"])
            steps = plan.get("steps", [])
            if idx < 0 or idx >= len(steps):
                return f"Invalid step index {idx}. Plan has {len(steps)} steps (0-{len(steps)-1})."
            steps[idx]["done"] = True
            PLAN_FILE.write_text(json.dumps(plan, indent=2), encoding="utf-8")
            lines = [f"  [{'✓' if s['done'] else ' '}] {s['index']}. {s['text']}" for s in steps]
            return f"Goal: {plan['goal']}\n" + "\n".join(lines)

        # ── ComfyUI image generation ──────────────────────────────────────────
        elif name == "comfyui_generate":
            import httpx as _httpx
            import json as _json
            prompt = args.get("prompt", "")
            negative = args.get("negative", "")
            steps = args.get("steps", 20)
            width = args.get("width", 512)
            height = args.get("height", 512)
            try:
                resp = _httpx.post("http://127.0.0.1:8000/comfy/generate", json={
                    "prompt": prompt, "negative": negative, "steps": steps,
                    "width": width, "height": height, "model": ""
                }, timeout=120)
                if resp.status_code == 200:
                    data = resp.json()
                    return f"Image generated: {data.get('image_url', 'unknown')}"
                return f"ComfyUI error: {resp.status_code} {resp.text[:200]}"
            except Exception as e:
                return f"ComfyUI not available: {e}"

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
    1. Build system prompt with injected memory + facts.
    2. Call Ollama (no-stream) to let the model decide on tools.
    3. Execute any tool calls, append results, repeat (max 8 rounds).
    4. Call Ollama again with stream=True for the final human-readable answer.
    5. Save a summary of the turn to long-term memory.
    """
    history = list(messages)

    # Extract latest user query for memory retrieval
    user_query = ""
    for m in reversed(history):
        if m.get("role") == "user":
            user_query = m.get("content", "")
            break

    system_prompt = build_system_prompt(user_query)

    if not history or history[0].get("role") != "system":
        history.insert(0, {"role": "system", "content": system_prompt})
    else:
        history[0]["content"] = system_prompt

    max_rounds = 8
    final_answer_tokens: list[str] = []

    async with httpx.AsyncClient(timeout=120) as client:
        for _ in range(max_rounds):
            resp = await client.post(
                f"{OLLAMA}/api/chat",
                json={"model": model, "messages": history, "tools": TOOLS, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()
            msg = data.get("message", {})
            tool_calls = msg.get("tool_calls") or []

            if not tool_calls:
                break

            history.append({"role": "assistant", "content": msg.get("content", ""), "tool_calls": tool_calls})

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
                        final_answer_tokens.append(token)
                        yield sse({"type": "token", "content": token})
                    if chunk.get("done"):
                        break
                except Exception:
                    pass

    yield sse({"type": "done"})

    # Persist turn summary to long-term memory (fire-and-forget, best-effort)
    if user_query and final_answer_tokens:
        final_answer = "".join(final_answer_tokens)[:500]
        summary = f"User: {user_query[:200]}\nFedda: {final_answer}"
        try:
            mem_module.save_memory(summary, metadata={"model": model})
        except Exception:
            pass


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
