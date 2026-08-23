import io
import io
import itertools
import os
from functools import lru_cache

import av
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
    resampler = av.audio.resampler.AudioResampler(
        format="s16",
        layout="mono",
        rate=SAMPLE_RATE,
    )
    arrays: list[np.ndarray] = []
    with av.open(
        io.BytesIO(audio_bytes),
        mode="r",
        metadata_errors="ignore",
    ) as container:
        frames = container.decode(audio=0)
        for frame in itertools.chain(frames, [None]):
            if frame is not None:
                frame.pts = None
            for resampled in resampler.resample(frame):
                arrays.append(resampled.to_ndarray())
    if not arrays:
        return np.empty(0, dtype=np.float32)
    audio = np.concatenate(arrays, axis=1)[0]
    return audio.astype(np.float32) / 32768.0


def debug_decode(audio_bytes: bytes) -> dict:
    """Run the bundled PyAV decoder with full diagnostics. Never raises."""
    result = {
        "input_size": len(audio_bytes),
        "input_first_bytes": audio_bytes[:64].hex() if audio_bytes else "",
        "input_last_bytes": audio_bytes[-64:].hex() if audio_bytes else "",
        "decoder": "PyAV",
    }
    try:
        audio = _decode_to_pcm(audio_bytes)
        result["decoded_shape"] = list(audio.shape)
        result["decoded_dtype"] = str(audio.dtype)
        if audio.size:
            result["decoded_min"] = float(audio.min())
            result["decoded_max"] = float(audio.max())
            result["decoded_mean"] = float(audio.mean())
    except Exception as exc:
        result["decode_error"] = str(exc)
    return result


def transcribe(audio_bytes: bytes) -> str:
    model = _get_model()
    audio = _decode_to_pcm(audio_bytes)
    segments, _ = model.transcribe(
        audio, beam_size=5, language="en", condition_on_previous_text=True
    )
    text = " ".join(segment.text.strip() for segment in segments)
    return text.strip()
