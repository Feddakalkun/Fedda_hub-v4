"""
Fedda Hub v4 — ComfyUI integration router
Provides status check, txt2img generation, model listing, and image serving.
"""

import asyncio
import json
import uuid
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

COMFY_URL = "http://127.0.0.1:8188"
# Default ComfyUI output folder; adjust if your installation differs
COMFY_OUTPUT_DIR = Path.home() / "ComfyUI" / "output"

router = APIRouter()


# ── Request / response models ────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    prompt: str
    negative: str = ""
    steps: int = 20
    width: int = 512
    height: int = 512
    model: str = ""


# ── Helper: build a minimal txt2img workflow ─────────────────────────────────

def _build_workflow(prompt: str, negative: str, steps: int,
                    width: int, height: int, model: str) -> dict:
    """Return a ComfyUI API-format workflow dict for basic txt2img."""
    ckpt = model or "v1-5-pruned-emaonly.ckpt"
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": ckpt},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["1", 1], "text": prompt},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["1", 1], "text": negative},
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
                "seed": 0,
                "steps": steps,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
            },
        },
        "6": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["5", 0], "vae": ["1", 2]},
        },
        "7": {
            "class_type": "SaveImage",
            "inputs": {"images": ["6", 0], "filename_prefix": "fedda"},
        },
    }


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/status")
async def comfy_status():
    """Check whether ComfyUI is reachable."""
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{COMFY_URL}/system_stats")
            return {"online": r.status_code == 200}
    except Exception:
        return {"online": False}


@router.get("/models")
async def comfy_models():
    """Return list of available checkpoint models from ComfyUI."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{COMFY_URL}/object_info/CheckpointLoaderSimple")
            r.raise_for_status()
            data = r.json()
            models = (
                data.get("CheckpointLoaderSimple", {})
                    .get("input", {})
                    .get("required", {})
                    .get("ckpt_name", [None])[0]
                or []
            )
            return {"models": models}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ComfyUI unreachable: {e}")


@router.post("/generate")
async def comfy_generate(req: GenerateRequest):
    """Submit a txt2img job to ComfyUI and poll until an image is ready."""
    workflow = _build_workflow(
        req.prompt, req.negative, req.steps, req.width, req.height, req.model
    )
    client_id = str(uuid.uuid4())

    async with httpx.AsyncClient(timeout=120) as client:
        # Submit the prompt
        try:
            submit = await client.post(
                f"{COMFY_URL}/prompt",
                json={"prompt": workflow, "client_id": client_id},
            )
            submit.raise_for_status()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"ComfyUI submit error: {e}")

        prompt_id = submit.json().get("prompt_id")
        if not prompt_id:
            raise HTTPException(status_code=502, detail="No prompt_id returned by ComfyUI")

        # Poll /history until done (up to 120 s)
        for _ in range(120):
            await asyncio.sleep(1)
            try:
                hist = await client.get(f"{COMFY_URL}/history/{prompt_id}")
                hist.raise_for_status()
                data = hist.json()
            except Exception:
                continue

            if prompt_id not in data:
                continue

            outputs = data[prompt_id].get("outputs", {})
            for node_output in outputs.values():
                images = node_output.get("images", [])
                if images:
                    filename = images[0]["filename"]
                    return {"image_url": f"/comfy/output/{filename}"}

        raise HTTPException(status_code=504, detail="ComfyUI generation timed out")


@router.get("/output/{filename}")
async def comfy_output(filename: str):
    """Serve a generated image from ComfyUI's output directory."""
    # Sanitise filename to prevent path traversal
    safe_name = Path(filename).name
    image_path = COMFY_OUTPUT_DIR / safe_name
    if not image_path.exists():
        raise HTTPException(status_code=404, detail=f"Image not found: {safe_name}")
    return FileResponse(str(image_path))
