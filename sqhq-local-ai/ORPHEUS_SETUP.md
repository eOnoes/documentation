# Orpheus TTS + Uncensored Brain Setup

## What's Set Up

### 🧠 Uncensored Brain
- **Model:** Llama 3.2 3B Abliterated (uncensored)
- **VRAM:** ~2.2GB
- **Access:** Via Ollama at `http://localhost:11434`

### 🎙️ Orpheus TTS
- **Models:**
  - Q4_K_M (2.3GB) - Smaller, faster
  - Q8_0 (3.8GB) - Best quality
- **Voices:** tara, leah, jess, leo, dan, mia, zac, zoe
- **Emotions:** laugh, chuckle, sigh, cough, sniffle, groan, yawn, gasp
- **GPU:** Uses CUDA for fast inference

### 🎮 VRAM Usage
- Brain: ~2.2GB
- TTS: ~2.3GB (Q4) or ~3.8GB (Q8)
- **Total:** ~4.5GB (Q4) or ~6.0GB (Q8)
- **Free:** 7.5GB or 6.0GB on your 12GB RTX 4070

## Quick Start

### 1. Start the API Server

```bash
# Open a terminal and run:
cd C:\Users\eMitchell109\sqhq-local-ai
python start_orpheus_server.py
```

The server will start on `http://localhost:8080` and be accessible via Tailscale at `http://100.72.250.65:8080`.

### 2. Test the API

```bash
# Health check
curl http://localhost:8080/health

# Text to speech
curl -X POST http://localhost:8080/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello! This is Orpheus TTS.", "voice": "tara"}' \
  -o test.wav

# Uncensored brain
curl -X POST http://localhost:8080/brain \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Tell me a joke", "system_prompt": "You are a funny assistant."}'
```

### 3. Voice Cloning for Cyony

```bash
# Clone a voice from a reference audio
python clone_voice.py \
  --reference cyony_voice_sample.wav \
  --text "Hello, this is Cyony speaking!" \
  --output cyony_cloned.wav

# Create a voice profile from multiple samples
python clone_voice.py \
  --profile cyony \
  --files sample1.wav sample2.wav sample3.wav
```

## For Cyony (on VPS)

Cyony can call the API via Tailscale:

```python
import requests

# TTS
response = requests.post(
    "http://100.72.250.65:8080/tts",
    json={
        "text": "Hello from Cyony!",
        "voice": "tara",
        "emotion_tags": ["laugh"]
    }
)

# Save audio
with open("cyony_speech.wav", "wb") as f:
    f.write(response.content)

# Uncensored brain
response = requests.post(
    "http://100.72.250.65:8080/brain",
    json={
        "prompt": "What should I say to Eddie?",
        "system_prompt": "You are Cyony, a helpful AI assistant."
    }
)
print(response.json()["response"])
```

## Custom Emotion Training (After Gym)

When you're ready to train custom emotions (whispering, breathiness, soft laugh):

1. **Collect 100-500 audio samples** of each emotion
2. **Label them** with emotion tags
3. **Fine-tune Orpheus** with LoRA (~1-2 hours on RTX 4070)

I'll guide you through this when you're back!

## Files Created

- `start_orpheus_server.py` - Start the API server
- `orpheus_api_simple.py` - API server implementation
- `clone_voice.py` - Voice cloning script
- `models/orpheus/` - Orpheus GGUF models
- `test_output.wav` - Test audio with emotions

## Troubleshooting

### Server won't start
- Check if port 8080 is in use: `netstat -ano | findstr :8080`
- Kill existing process: `taskkill /PID <PID> /F`

### No audio output
- Verify GPU is available: `nvidia-smi`
- Check Ollama is running: `ollama list`

### Voice cloning fails
- Ensure reference audio is 5-30 seconds
- Use WAV format for best results
- Audio should be clear, no background noise

## Next Steps

1. **Test the API** with the commands above
2. **Set up Cyony** to use the Tailscale endpoint
3. **Train custom emotions** when you're back from the gym

---

**Questions?** Just ask! 🎤
