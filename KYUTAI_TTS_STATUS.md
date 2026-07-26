# Kyutai TTS 1.6B Integration Status

## Current State

✅ **Backend running** with Kokoro TTS (existing implementation)
✅ **Pocket TTS** and **Moshi** packages installed (but uninstalled due to dependency conflicts)
✅ **Voice cloning repository** identified: 901 pre-computed voice embeddings available at `kyutai/tts-voices`

## Dependency Conflicts

The Kyutai TTS 1.6B model requires the `moshi` package, which has incompatible dependencies with the existing Kokoro TTS setup:

```
moshi 0.2.13 requires:
  - huggingface-hub<1.0.0,>=0.24
  - safetensors<0.8.0,>=0.4.0

transformers (required by Kokoro) requires:
  - huggingface-hub<2.0,>=1.5.0
  - safetensors>=0.8.0
```

## Solutions

### Option 1: Separate Virtual Environment (Recommended)
Create a dedicated virtual environment for Kyutai TTS:

```bash
python3.12 -m venv kyutai-venv
source kyutai-venv/bin/activate
pip install git+https://github.com/kyutai-labs/delayed-streams-modeling.git
pip install torch torchaudio
```

Then run a separate TTS microservice on a different port (e.g., 8001).

### Option 2: Docker Container
Package Kyutai TTS 1.6B in a Docker container with all dependencies isolated.

### Option 3: Keep Kokoro (Current)
Continue using Kokoro TTS which is working reliably. The progress indicator feature can be implemented with Kokoro first, then migrate to Kyutai later.

## Voice Cloning Capability

✅ **Pre-computed voices**: 901 voice embeddings available
- Casual, announcer, merchant, etc.
- Multiple languages (EN, FR)
- Various emotional tones

❌ **True voice cloning from audio samples**: Not yet implemented
- Requires the voice encoder model
- Would need additional model downloads and implementation

## Implementation Plan

### Phase 1: Progress Indicator with Kokoro (2-3 hours)
- Implement TTS progress tracking with existing Kokoro TTS
- Add playback progress bar
- Add scrubbing/seek functionality
- **No backend changes required**

### Phase 2: Kyutai TTS Microservice (4-6 hours)
- Set up separate virtual environment or Docker container
- Create `/api/tts/kyutai` endpoint
- Implement streaming synthesis
- Integrate voice selection UI

### Phase 3: Voice Cloning (3-4 hours)
- Add voice encoder model
- Implement audio sample upload
- Create custom voice embeddings
- Add voice blend UI

## Files Created

- `backend/src/kyutai_tts.py` - Kyutai TTS engine wrapper (needs dependency fix)
- `backend/src/web_server.py` - Added `/api/tts/stream`, `/api/tts/voices`, `/api/tts/voices/clone` endpoints (commented out until dependencies resolved)

## Next Steps

1. **Decide**: Keep Kokoro for now or set up Kyutai in separate environment?
2. **If Kokoro**: Implement progress indicator UI immediately
3. **If Kyutai**: Create separate venv/Docker, test model loading, then integrate

## Model Details

**Kyutai TTS 1.6B-en_fr**
- Parameters: 1.8B (not 1.6B as named)
- Languages: English, French
- Sample rate: 24kHz
- Frame rate: 12.5 Hz
- Architecture: Hierarchical Transformer + Mimi audio tokenizer
- License: CC-BY 4.0
- HuggingFace: https://huggingface.co/kyutai/tts-1.6b-en_fr
- Voices: https://huggingface.co/kyutai/tts-voices (901 embeddings)
