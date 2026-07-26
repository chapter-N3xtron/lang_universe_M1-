# TTS Implementation Status

## Current State

✅ **Kokoro TTS** - Decommissioned (uninstalled)
❌ **Kyutai TTS 1.6B** - Requires CUDA GPU (not available on macOS)
❌ **Kyutai Pocket TTS** - Requires HuggingFace authentication & license acceptance

## Pocket TTS Setup Required

Pocket TTS is restricted and requires:

1. **HuggingFace Login**
   ```bash
   huggingface-cli login
   ```

2. **Accept License** at https://huggingface.co/kyutai/pocket-tts

3. **Use Authenticated Loading**
   ```python
   from huggingface_hub import login
   login(token="your_hf_token")
   
   from pocket_tts import TTSModel
   model = TTSModel.from_pretrained("kyutai/pocket-tts")
   ```

## Voice Cloning Support

✅ **901 pre-computed voices** available at `kyutai/tts-voices`
- No authentication required for voices repository
- Can be used with Pocket TTS once model is loaded

## Recommended Next Steps

### Option 1: Complete Pocket TTS Setup (Recommended)
1. Create HuggingFace account at https://huggingface.co
2. Accept Pocket TTS license at https://huggingface.co/kyutai/pocket-tts
3. Generate access token at https://huggingface.co/settings/tokens
4. Run: `huggingface-cli login` and paste token
5. Restart backend server

**Time:** 5 minutes
**Benefit:** CPU-optimized, fast, supports voice cloning

### Option 2: Keep Kokoro
Re-install Kokoro TTS which works without authentication:
```bash
pip install kokoro
```

**Time:** 2 minutes  
**Benefit:** Works immediately, no authentication

### Option 3: Use External TTS API
Use cloud TTS services (Google, AWS, Azure) via API

**Time:** 30+ minutes setup
**Benefit:** High quality, no local GPU needed

## Files Created

- `backend/src/kyutai_tts.py` - Pocket TTS wrapper (needs HF auth)
- `backend/src/web_server.py` - Updated with Pocket TTS endpoints

## Technical Details

**Pocket TTS Specifications:**
- Parameters: 100M
- Languages: Multilingual (EN, FR, DE, ES, IT, JA)
- Sample Rate: 24kHz
- CPU Performance: ~0.1x RTF (10x faster than real-time on M2)
- Voice Cloning: Supported via pre-computed embeddings
- Streaming: Supported

**Voice Repository:**
- URL: https://huggingface.co/kyutai/tts-voices
- Voices: 901 pre-computed embeddings
- Format: `.safetensors` files
- No authentication required for voices

## Decision Needed

**Please choose:**
1. Set up HuggingFace auth for Pocket TTS (recommended)
2. Re-install Kokoro
3. Use external TTS API

Once you decide, I'll complete the implementation.
