import os
import subprocess
import tempfile
from functools import lru_cache

import numpy as np
from faster_whisper import WhisperModel

MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")
DEVICE = os.getenv("WHISPER_DEVICE", "auto")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
SAMPLE_RATE = 16000


@lru_cache(maxsize=1)
def _get_model() -> WhisperModel:
    return WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)


def _decode_to_pcm(audio_bytes: bytes) -> np.ndarray:
    with tempfile.NamedTemporaryFile(suffix=".webm") as tmp:
        tmp.write(audio_bytes)
        tmp.flush()
        proc = subprocess.Popen(
            [
                "ffmpeg",
                "-nostdin",
                "-loglevel", "error",
                "-seekable", "0",
                "-f", "webm",
                "-i", tmp.name,
                "-f", "s16le",
                "-ac", "1",
                "-ar", str(SAMPLE_RATE),
                "-",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, err = proc.communicate(timeout=30)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed: {err.decode(errors='replace')}"
        )
    return np.frombuffer(out, dtype=np.int16).astype(np.float32) / 32768.0


def debug_decode(audio_bytes: bytes) -> dict:
    """Run ffmpeg decode with full diagnostics. Never raises."""
    result = {
        "input_size": len(audio_bytes),
        "input_first_bytes": audio_bytes[:64].hex() if audio_bytes else "",
        "input_last_bytes": audio_bytes[-64:].hex() if audio_bytes else "",
    }
    try:
        proc = subprocess.Popen(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, _ = proc.communicate(timeout=10)
        result["ffmpeg_version"] = out.decode(errors="replace").split("\n")[0]
    except Exception as e:
        result["ffmpeg_version"] = str(e)

    with tempfile.NamedTemporaryFile(suffix=".webm") as tmp:
        tmp.write(audio_bytes)
        tmp.flush()
        result["tmp_path"] = tmp.name
        proc = subprocess.Popen(
            [
                "ffmpeg",
                "-nostdin",
                "-loglevel", "error",
                "-seekable", "0",
                "-f", "webm",
                "-i", tmp.name,
                "-f", "s16le",
                "-ac", "1",
                "-ar", str(SAMPLE_RATE),
                "-",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            out, err = proc.communicate(timeout=30)
            result["ffmpeg_returncode"] = proc.returncode
            result["ffmpeg_stdout_size"] = len(out)
            result["ffmpeg_stderr"] = err.decode(errors="replace")
            if proc.returncode == 0:
                audio = np.frombuffer(out, dtype=np.int16).astype(np.float32) / 32768.0
                result["decoded_shape"] = list(audio.shape)
                result["decoded_dtype"] = str(audio.dtype)
                result["decoded_min"] = float(audio.min())
                result["decoded_max"] = float(audio.max())
                result["decoded_mean"] = float(audio.mean())
        except subprocess.TimeoutExpired:
            proc.kill()
            result["ffmpeg_returncode"] = -1
            result["ffmpeg_stderr"] = "timeout"
        except Exception as e:
            result["ffmpeg_error"] = str(e)
    return result


def transcribe(audio_bytes: bytes) -> str:
    model = _get_model()
    audio = _decode_to_pcm(audio_bytes)
    segments, _ = model.transcribe(
        audio, beam_size=5, language="en", condition_on_previous_text=True
    )
    text = " ".join(segment.text.strip() for segment in segments)
    return text.strip()
