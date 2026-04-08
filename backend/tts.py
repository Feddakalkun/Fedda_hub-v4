"""
Fedda Hub v4 — Kokoro TTS router
POST /tts  →  audio/mpeg (MP3 stream)
"""

import io
import re

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()

AVAILABLE_VOICES = {"af_heart", "af_sky", "af_bella", "am_adam", "bf_emma"}
DEFAULT_VOICE = "af_heart"

# Lazy-loaded Kokoro instance
_kokoro = None


def _get_kokoro():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        # Model files are auto-downloaded on first use to the default cache dir
        _kokoro = Kokoro("kokoro-v0_19.onnx", "voices.bin")
    return _kokoro


def _strip_markdown(text: str) -> str:
    """Remove common markdown tokens so they are not spoken aloud."""
    # Remove code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`[^`]*`", "", text)
    # Remove headers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove bold/italic
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
    # Remove links
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    # Remove images
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    # Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # Remove bullet/numbered list markers
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    # Collapse extra whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class TTSRequest(BaseModel):
    text: str
    voice: str = DEFAULT_VOICE


@router.post("/tts")
async def text_to_speech(req: TTSRequest):
    voice = req.voice if req.voice in AVAILABLE_VOICES else DEFAULT_VOICE
    clean_text = _strip_markdown(req.text)

    import numpy as np
    import soundfile as sf

    kokoro = _get_kokoro()
    samples, sample_rate = kokoro.create(clean_text, voice=voice, speed=1.0, lang="en-us")

    # Convert float32 samples → 16-bit PCM WAV in memory, then re-encode to MP3
    wav_buf = io.BytesIO()
    sf.write(wav_buf, samples, sample_rate, format="WAV", subtype="PCM_16")
    wav_buf.seek(0)

    # Re-encode to MP3 using pydub (falls back to WAV if pydub/ffmpeg unavailable)
    try:
        from pydub import AudioSegment
        seg = AudioSegment.from_wav(wav_buf)
        mp3_buf = io.BytesIO()
        seg.export(mp3_buf, format="mp3")
        mp3_buf.seek(0)
        return StreamingResponse(mp3_buf, media_type="audio/mpeg")
    except Exception:
        wav_buf.seek(0)
        return StreamingResponse(wav_buf, media_type="audio/wav")
