"""Kokoro text-to-speech service."""

import io
import os
import re
from functools import lru_cache

import numpy as np
import soundfile as sf
from kokoro import KPipeline

DEFAULT_VOICE = os.getenv("KOKORO_VOICE", "af_heart")
DEFAULT_LANG = os.getenv("KOKORO_LANG", "a")
DEFAULT_SAMPLE_RATE = 24000


@lru_cache(maxsize=1)
def _get_pipeline(lang_code: str = DEFAULT_LANG) -> KPipeline:
    return KPipeline(lang_code=lang_code)


def _strip_markdown(text: str) -> str:
    """Remove markdown code blocks and excessive formatting for TTS."""
    # Remove fenced code blocks
    text = re.sub(r"```[\w]*\n.*?\n```", "", text, flags=re.DOTALL)
    # Remove inline code backticks
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Remove links but keep label text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove images
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def synthesize(text: str, voice: str = None, lang_code: str = None) -> bytes:
    """Synthesize text into a WAV byte stream."""
    voice = voice or DEFAULT_VOICE
    lang_code = lang_code or DEFAULT_LANG
    pipeline = _get_pipeline(lang_code)

    clean_text = _strip_markdown(text)
    if not clean_text:
        clean_text = "I don't have anything to say."

    generator = pipeline(clean_text, voice=voice)
    segments = []
    for _, _, audio in generator:
        segments.append(audio)

    if not segments:
        raise RuntimeError("Kokoro produced no audio")

    audio = np.concatenate(segments)
    buffer = io.BytesIO()
    sf.write(buffer, audio, DEFAULT_SAMPLE_RATE, format="WAV", subtype="PCM_16")
    buffer.seek(0)
    return buffer.read()
