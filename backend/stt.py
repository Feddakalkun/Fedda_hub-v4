"""
Fedda Hub v4 — Faster-Whisper STT router
POST /stt  →  {"transcript": "..."}
Accepts multipart file upload (audio/webm or audio/wav)
"""

import os
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

router = APIRouter()

# Lazy-loaded Whisper model
_whisper_model = None

BASE_DIR = Path(__file__).parent


def _get_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    return _whisper_model


@router.post("/stt")
async def speech_to_text(file: UploadFile = File(...)):
    # Determine suffix from content-type or filename
    content_type = file.content_type or ""
    if "webm" in content_type or (file.filename or "").endswith(".webm"):
        suffix = ".webm"
    elif "wav" in content_type or (file.filename or "").endswith(".wav"):
        suffix = ".wav"
    elif "mp4" in content_type or (file.filename or "").endswith(".mp4"):
        suffix = ".mp4"
    else:
        suffix = ".webm"  # reasonable default for browser recordings

    # Save upload to a temp file in the backend dir (avoid /tmp on Windows)
    temp_dir = BASE_DIR / "stt_temp"
    temp_dir.mkdir(exist_ok=True)
    temp_path = temp_dir / f"{uuid.uuid4()}{suffix}"

    try:
        audio_bytes = await file.read()
        temp_path.write_bytes(audio_bytes)

        model = _get_model()
        segments, _info = model.transcribe(str(temp_path), beam_size=5)
        transcript = " ".join(seg.text.strip() for seg in segments).strip()
        return JSONResponse({"transcript": transcript})
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass
