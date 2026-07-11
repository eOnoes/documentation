# Orpheus TTS Fleet Setup — Replaces Pocket TTS

## What Changed

| Before (Pocket TTS) | After (Orpheus TTS) |
|---------------------|---------------------|
| CPU-only | GPU-accelerated (RTX 4070) |
| No emotion support | 8 emotion tags built-in |
| Low quality | High-quality neural voice |
| Single voice | 8 voices available |
| VPS-based | Eddie's PC (lower latency) |

## Quick Start

### 1. Start the Server

```bash
cd C:\Users\eMitchell109\sqhq-local-ai
python orpheus_fleet_server.py
```

The server runs on:
- **Local:** http://localhost:8080
- **Tailscale:** http://100.72.250.65:8080

### 2. Test It

```bash
# Health check
curl http://localhost:8080/v1/health

# Text to speech
curl -X POST http://localhost:8080/v1/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello from Orpheus!", "voice": "tara"}' \
  -o test.wav

# With mood preset (replaces Pocket TTS temperature)
curl -X POST http://localhost:8080/v1/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "This is so exciting!", "mood": "excited"}' \
  -o excited.wav
```

### 3. Cyony on VPS

Cyony can call the API via Tailscale:

```python
import requests

# Basic TTS
r = requests.post("http://100.72.250.65:8080/v1/tts", 
    json={"text": "Hello!", "voice": "tara"})
with open("speech.wav", "wb") as f:
    f.write(r.content)

# With mood (like Pocket TTS temperature control)
r = requests.post("http://100.72.250.65:8080/v1/tts",
    json={"text": "I love you!", "mood": "warm_calm"})
```

## Mood Presets

These replace Pocket TTS temperature control:

| Mood | Temperature | Emotion Tags |
|------|-------------|--------------|
| `whisper_intimate` | 0.3 | sigh |
| `warm_calm` | 0.4 | — |
| `storytelling` | 0.7 | chuckle |
| `playful_teasing` | 0.6 | laugh |
| `excited` | 0.9 | gasp |
| `annoyed` | 0.7 | sigh |
| `vulnerable` | 0.35 | sigh |
| `serious` | 0.5 | — |
| `sad` | 0.4 | sigh |
| `angry` | 0.8 | groan |
| `sarcastic` | 0.6 | chuckle |
| `crying` | 0.3 | sigh, groan |

## Available Voices

- **tara** — Female, warm, friendly (default)
- **leah** — Female, professional, clear
- **jess** — Female, young, energetic
- **mia** — Female, soft, gentle
- **zoe** — Female, confident, bold
- **leo** — Male, deep, authoritative
- **dan** — Male, casual, relaxed
- **zac** — Male, youthful, upbeat

## Voice Cloning

### Download Reference Audio from VPS

```bash
scp root@100.85.111.32:/opt/data/shared-memory/voice/reference-*.mp3 .
scp root@100.85.111.32:/opt/data/shared-memory/voice/jarvis_reference_combined.wav .
```

### Clone a Voice

```bash
# Using the voice clone script
python cyony_voice_clone.py --text "Hello Eddie!" --output cyony.wav
```

## API Reference

### POST /v1/tts

```json
{
  "text": "Hello!",
  "voice": "tara",           // optional, default "tara"
  "mood": "excited",         // optional, uses preset
  "emotion_tags": ["laugh"], // optional, manual tags
  "temp": 0.7,              // optional, overrides mood
  "return_format": "wav"     // optional, "wav" or "mp3"
}
```

Returns: Audio file (WAV or MP3)

### POST /v1/clone

```json
{
  "text": "Hello!",
  "reference_audio": "base64_encoded_audio",
  "voice": "cyony"          // optional name
}
```

### POST /v1/brain

```json
{
  "prompt": "Tell me a joke",
  "system_prompt": "You are helpful",
  "max_tokens": 512
}
```

Returns: `{"ok": true, "response": "..."}`

## Files

- `orpheus_fleet_server.py` — Main API server
- `cyony_voice_clone.py` — Voice cloning script
- `models/orpheus/` — Orpheus GGUF models
- `start_orpheus_server.py` — Quick start script

## Troubleshooting

### Server won't start
```bash
# Check if port 8080 is in use
netstat -ano | findstr :8080
# Kill existing process
taskkill /PID <PID> /F
```

### No audio output
```bash
# Verify GPU is available
nvidia-smi
# Check Ollama is running
ollama list
```

### Cyony can't connect
```bash
# Test from VPS
ssh root@100.85.111.32
curl http://100.72.250.65:8080/v1/health
```

## VRAM Usage

- **Brain (Llama 3.2 3B):** ~2.2GB
- **TTS (Orpheus 3B Q4):** ~2.3GB
- **Total:** ~4.5GB
- **Free:** 7.5GB on RTX 4070

## Next Steps

1. **Test the server** with the commands above
2. **Update Cyony's config** to use Orpheus endpoint
3. **Train custom emotions** when you're back from the gym

---

**Questions?** Just ask! 🎤
