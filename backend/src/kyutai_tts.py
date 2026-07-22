"""Kyutai Pocket TTS engine with streaming and voice cloning support."""

import asyncio
import os
from pathlib import Path
from typing import AsyncGenerator, Optional
import numpy as np
import torch
import safetensors
from pocket_tts.models.tts_model import TTSModel, init_states, prepare_text_prompt
from huggingface_hub import hf_hub_download, list_repo_files
import logging
import io
import wave

logger = logging.getLogger(__name__)

VOICE_REPO = "kyutai/pocket-tts-without-voice-cloning"
VOICE_DIR = "languages/english/embeddings"
LOCAL_VOICE_DIR = Path(__file__).resolve().parent.parent / "voices"

TARGET_PEAK = 10 ** (-4.8 / 20)  # -4.8 dBFS (matches predefined voice level)
CLONE_TARGET = 10 ** (-5 / 20)   # -5 dBFS for cloned voices
FADE_SAMPLES = 240       # 10ms at 24kHz
CROSSFADE_SAMPLES = 120  # 5ms at 24kHz


def _normalize(audio: np.ndarray) -> np.ndarray:
    peak = np.max(np.abs(audio))
    if peak < 1e-6:
        return audio
    return audio * (TARGET_PEAK / peak)


def _normalize_chunk(audio: np.ndarray, max_gain: float = 8.0) -> np.ndarray:
    peak = np.max(np.abs(audio))
    if peak < 1e-6:
        return audio
    gain = min(TARGET_PEAK / peak, max_gain)
    return audio * gain
    peak = np.max(np.abs(audio))
    if peak < 1e-6:
        return audio
    return audio * (TARGET_PEAK / peak)


def _fade_out(audio: np.ndarray, fade_samples: int = FADE_SAMPLES) -> np.ndarray:
    n = min(fade_samples, len(audio))
    if n <= 0:
        return audio
    fade = np.linspace(1.0, 0.0, n, dtype=np.float32)
    audio[-n:] *= fade
    return audio


def _fade_in(audio: np.ndarray, fade_samples: int = FADE_SAMPLES) -> np.ndarray:
    n = min(fade_samples, len(audio))
    if n <= 0:
        return audio
    fade = np.linspace(0.0, 1.0, n, dtype=np.float32)
    audio[:n] *= fade
    return audio


def _load_voice_state(voice_path: str, device: torch.device) -> dict:
    """Load a pre-computed voice state from a safetensors file."""
    result = {}
    with safetensors.safe_open(voice_path, framework="pt") as f:
        for key in f.keys():
            module_name, tensor_key = key.split("/")
            result.setdefault(module_name, {})
            if tensor_key == "current_end":
                tensor = f.get_tensor(key)
                result[module_name]["offset"] = torch.full(
                    (1,), fill_value=tensor.shape[0], dtype=torch.long, device=device
                )
            else:
                result[module_name][tensor_key] = f.get_tensor(key).to(device)
    return result


class PocketTTSEngine:
    """Kyutai Pocket TTS with streaming synthesis and voice cloning."""

    def __init__(self, model_name: str = "english"):
        self.model_name = model_name
        self._model: Optional[TTSModel] = None
        self._voice_cache: dict[str, dict] = {}
        self._voice_mtimes: dict[str, float] = {}
        self._available_voices: list[str] = []
        self._device = torch.device("cpu")
        self._local_voices = self._scan_local_voices()

    @staticmethod
    def _scan_local_voices() -> set[str]:
        local = set()
        if LOCAL_VOICE_DIR.is_dir():
            for f in os.listdir(str(LOCAL_VOICE_DIR)):
                if f.endswith(".safetensors"):
                    local.add(f.replace(".safetensors", ""))
        return local

    def _load_model(self):
        if self._model is None:
            logger.info(f"Loading Pocket TTS model: {self.model_name}...")
            self._model = TTSModel.load_model(self.model_name)
            self._device = next(self._model.parameters()).device
            logger.info("Pocket TTS model loaded")

    async def list_voices(self) -> list[str]:
        if not self._available_voices:
            voices = set()
            try:
                files = await asyncio.to_thread(list_repo_files, VOICE_REPO)
                for f in files:
                    if f.startswith(VOICE_DIR) and f.endswith(".safetensors"):
                        name = f.split("/")[-1].replace(".safetensors", "")
                        voices.add(name)
            except Exception as e:
                logger.warning(f"Failed to list HF voices: {e}")
            self._available_voices = sorted(voices)

        local_voices = set()
        local_dir = LOCAL_VOICE_DIR
        if local_dir.is_dir():
            for f in os.listdir(str(local_dir)):
                if f.endswith(".safetensors"):
                    name = f.replace(".safetensors", "")
                    local_voices.add(name)
                    self._local_voices.add(name)

        return sorted(set(self._available_voices) | local_voices)

    async def load_voice(self, voice_name: str) -> dict:
        local_path = LOCAL_VOICE_DIR / f"{voice_name}.safetensors"
        if local_path.is_file():
            mtime = local_path.stat().st_mtime
            cached = self._voice_mtimes.get(voice_name)
            if voice_name in self._voice_cache and cached == mtime:
                return self._voice_cache[voice_name]
            logger.info(f"Loading local voice: {voice_name}")
            state = await asyncio.to_thread(_load_voice_state, str(local_path), self._device)
            self._voice_mtimes[voice_name] = mtime
        else:
            if voice_name in self._voice_cache:
                return self._voice_cache[voice_name]
            voice_path = await asyncio.to_thread(
                hf_hub_download,
                VOICE_REPO,
                f"{VOICE_DIR}/{voice_name}.safetensors",
            )
            logger.info(f"Loading voice state: {voice_name}")
            state = await asyncio.to_thread(_load_voice_state, voice_path, self._device)

        self._voice_cache[voice_name] = state
        logger.info(f"Voice loaded: {voice_name}")
        return state

    async def _get_states(self, text: str, voice: str) -> dict:
        """Get model states, using voice conditioning if available."""
        if voice:
            try:
                return await self.load_voice(voice)
            except Exception as e:
                logger.warning(f"Voice '{voice}' not available, using default: {e}")
        return init_states(
            self._model.flow_lm,
            batch_size=1,
            sequence_length=len(text) + 50,
        )

    async def synthesize_full(
        self,
        text: str,
        voice: str = "",
    ) -> tuple[np.ndarray, float]:
        self._load_model()
        logger.info(f"Synthesizing: '{text[:50]}...' voice={voice or 'default'}")

        try:
            states = await self._get_states(text, voice)
            text_str, _ = prepare_text_prompt(
                text,
                pad_with_spaces_for_short_inputs=False,
                remove_semicolons=False,
            )

            with torch.no_grad():
                result = self._model.generate_audio(states, text_str)

            if hasattr(result, "audio"):
                audio = result.audio.cpu().numpy()
            elif isinstance(result, torch.Tensor):
                audio = result.cpu().numpy()
            else:
                audio = np.array([])

            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            audio = _fade_out(audio)

            duration = len(audio) / 24000 if len(audio) > 0 else 0.0
            logger.info(f"Generated {duration:.2f}s")
            return audio, duration

        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return np.zeros(24000, dtype=np.float32), 1.0

    async def synthesize_streaming(
        self,
        text: str,
        voice: str = "",
        chunk_size: int = 20,
    ) -> AsyncGenerator[tuple[np.ndarray, dict], None]:
        """Synthesize audio and yield chunks as they're decoded."""
        self._load_model()
        logger.info(f"Streaming: '{text[:50]}...' voice={voice or 'default'}")

        states = await self._get_states(text, voice)
        text_str, _ = prepare_text_prompt(
            text,
            pad_with_spaces_for_short_inputs=False,
            remove_semicolons=False,
        )

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        sentinel = object()
        _queue_put = lambda item: asyncio.run_coroutine_threadsafe(queue.put(item), loop).result()
        is_clone = voice in self._local_voices

        def producer():
            try:
                last_chunk = None
                is_first = True
                locked_gain = None
                with torch.no_grad():
                    for chunk_idx, chunk in enumerate(
                        self._model.generate_audio_stream(states, text_str)
                    ):
                        audio = chunk.cpu().numpy()
                        if audio.dtype != np.float32:
                            audio = audio.astype(np.float32)
                        if is_clone:
                            peak = np.max(np.abs(audio))
                            if peak > 1e-6:
                                if locked_gain is None:
                                    locked_gain = min(CLONE_TARGET / peak, 4.0)
                                elif peak * locked_gain > 1.0:
                                    locked_gain = 0.99 / peak
                                audio = audio * locked_gain
                        if is_first:
                            _fade_in(audio, FADE_SAMPLES)
                            is_first = False
                        if last_chunk is not None:
                            _queue_put((last_chunk, {"chunk": chunk_idx - 1}))
                        last_chunk = audio
                if last_chunk is not None:
                    _fade_out(last_chunk, FADE_SAMPLES)
                    _queue_put((last_chunk, {"chunk": chunk_idx, "last": True}))
                logger.info(f"Streaming done, {chunk_idx + 1} chunks")
            except Exception as e:
                logger.error(f"Streaming TTS failed: {e}")
                import traceback
                logger.error(traceback.format_exc())
                _queue_put((np.zeros(0, dtype=np.float32), {"error": str(e)}))
            finally:
                _queue_put(sentinel)

        executor = loop.run_in_executor(None, producer)

        while True:
            item = await queue.get()
            if item is sentinel:
                break
            yield item

        await executor


_tts_engine: Optional[PocketTTSEngine] = None


def get_tts_engine() -> PocketTTSEngine:
    global _tts_engine
    if _tts_engine is None:
        _tts_engine = PocketTTSEngine("english")
    return _tts_engine
