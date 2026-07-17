"""Local speech-to-text using faster-whisper."""

import io
import os
from functools import lru_cache

from faster_whisper import WhisperModel

MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")
DEVICE = os.getenv("WHISPER_DEVICE", "auto")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")


@lru_cache(maxsize=1)
def _get_model() -> WhisperModel:
    return WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)


def transcribe(audio_bytes: bytes) -> str:
    """Transcribe audio bytes (WAV, MP3, OGG, WEBM) to text."""
    model = _get_model()
    buffer = io.BytesIO(audio_bytes)
    segments, _ = model.transcribe(buffer, beam_size=5, language="en", condition_on_previous_text=True)
    text = " ".join(segment.text.strip() for segment in segments)
    return text.strip()
