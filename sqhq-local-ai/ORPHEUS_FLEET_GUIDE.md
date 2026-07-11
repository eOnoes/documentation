# Orpheus TTS Fleet — Complete Guide

## What You Have

| Component | Status | Details |
|-----------|--------|---------|
| **Orpheus TTS 3B** | ✅ LIVE | CPU mode, ~4s per sentence |
| **Fleet Server** | ✅ RUNNING | `http://100.72.250.65:8080` |
| **8 Voices** | ✅ Ready | tara, leah, jess, mia, zoe, leo, dan, zac |
| **8 Emotions** | ✅ Ready | laugh, chuckle, sigh, cough, sniffle, groan, yawn, gasp |
| **12 Moods** | ✅ Ready | whisper_intimate, warm_calm, storytelling, etc. |
| **Voice Cloning** | ⚠️ Stub | Endpoint exists, needs reference audio |

## Connection Info

- **Your PC (Tailscale):** `100.72.250.65`
- **VPS (Tailscale):** `100.85.111.32`
- **Fleet Server Port:** `8080`
- **Full URL:** `http://100.72.250.65:8080`

## How to Start the Server

```bash
# From your PC
cd C:\Users\eMitchell109\sqhq-local-ai
python orpheus_fleet_server.py
```

## How to Use from Cyony (VPS)

### Basic TTS

```python
import requests

# Simple text to speech
r = requests.post("http://100.72.250.65:8080/v1/tts", json={
    "text": "Hello Eddie, this is Cyony speaking!",
    "voice": "tara"
})

# Save audio
with open("output.wav", "wb") as f:
    f.write(r.content)
```

### With Emotions

```python
import requests

# Emotion tags in text
r = requests.post("http://100.72.250.65:8080/v1/tts", json={
    "text": "<laugh> That's hilarious! <sigh> But seriously though...",
    "voice": "tara"
})

# Or use mood preset (replaces emotion tags + sets temperature)
r = requests.post("http://100.72.250.65:8080/v1/tts", json={
    "text": "Hey Eddie, how's it going?",
    "voice": "tara",
    "mood": "warm_calm"  # Sets temperature 0.4 + adds subtle emotion
})
```

### Via cURL

```bash
# Basic
curl -X POST http://100.72.250.65:8080/v1/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello!", "voice": "tara"}' \
  -o output.wav

# With mood
curl -X POST http://100.72.250.65:8080/v1/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "I am so excited!", "voice": "tara", "mood": "excited"}' \
  -o excited.wav
```

## All 8 Voices

| Voice | Gender | Best For |
|-------|--------|----------|
| `tara` | Female | Warm, friendly, default |
| `leah` | Female | Calm, professional |
| `jess` | Female | Energetic, playful |
| `mia` | Female | Soft, intimate |
| `zoe` | Female | Bright, cheerful |
| `leo` | Male | Deep, authoritative |
| `dan` | Male | Casual, relaxed |
| `zac` | Male | Youthful, upbeat |

## All 8 Emotions (use in `<tag>` format)

```
<laugh>     - Genuine laughter
<chuckle>   - Soft chuckle
<sigh>      - Weary sigh
<cough>     - Throat clearing
<sniffle>   - Sniffling
<groan>     - Frustrated groan
<yawn>      - Tired yawn
<gasp>      - Surprised gasp
```

## All 12 Mood Presets

| Mood | Temp | Description |
|------|------|-------------|
| `whisper_intimate` | 0.3 | Close, soft, ASMR-like |
| `warm_calm` | 0.4 | Default friendly |
| `storytelling` | 0.5 | Engaging narrative |
| `playful_teasing` | 0.5 | Fun, lighthearted |
| `excited` | 0.9 | High energy, fast |
| `annoyed` | 0.5 | Irritated tone |
| `vulnerable` | 0.4 | Open, emotional |
| `serious` | 0.4 | Formal, measured |
| `sad` | 0.4 | Melancholy |
| `angry` | 0.5 | Intense, sharp |
| `sarcastic` | 0.5 | Dry, ironic |
| `crying` | 0.4 | Emotional, tears |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/health` | GET | Server status, voices, emotions |
| `/v1/tts` | POST | Generate speech |
| `/v1/clone` | POST | Voice cloning (stub) |
| `/v1/brain` | POST | Uncensored LLM (separate) |

## Audio Format

- **Format:** WAV (16-bit PCM)
- **Sample Rate:** 24,000 Hz
- **Channels:** 1 (mono)
- **Duration:** ~3-5 seconds per sentence
- **Latency:** ~4-6 seconds (CPU mode)

## Later: GPU Acceleration

When you install CUDA Toolkit 12.4+:

```bash
# 1. Install CUDA Toolkit from:
# https://developer.nvidia.com/cuda-12-4-0-download-archive

# 2. Reinstall llama-cpp-python with CUDA
pip uninstall llama-cpp-python -y
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124

# 3. Restart the server
python orpheus_fleet_server.py
```

This will cut latency from ~4-6s to ~1-2s.

## Later: Voice Cloning

```python
import requests
import base64

# 1. Load reference audio (Cyony's voice from VPS)
with open("cyony_reference.wav", "rb") as f:
    ref_audio = base64.b64encode(f.read()).decode()

# 2. Clone and speak
r = requests.post("http://100.72.250.65:8080/v1/clone", json={
    "text": "This is Cyony speaking with her own voice!",
    "reference_audio": ref_audio,
    "voice": "cyony"
})

# 3. Save cloned audio
with open("cyony_cloned.wav", "wb") as f:
    f.write(r.content)
```

## Troubleshooting

**Server won't start:**
```bash
# Check if port 8080 is in use
netstat -ano | grep ":8080"
# Kill the process
taskkill //F //PID <PID>
```

**TTS returns empty:**
```bash
# Check server health
curl http://localhost:8080/v1/health

# Check VRAM (should be ~1.1GB baseline)
nvidia-smi
```

**Slow responses (CPU mode is normal):**
- CPU mode: 4-6 seconds per sentence
- GPU mode (future): 1-2 seconds per sentence
- Short text is faster than long text

## File Locations

| File | Path |
|------|------|
| Fleet Server | `C:\Users\eMitchell109\sqhq-local-ai\orpheus_fleet_server.py` |
| Q4 Model | `C:\Users\eMitchell109\sqhq-local-ai\models\orpheus\Orpheus-3b-FT-Q4_K_M.gguf` |
| Q8 Model | `C:\Users\eMitchell109\sqhq-local-ai\models\orpheus\Orpheus-3b-FT-Q8_0.gguf` |
| Voice Clone Script | `C:\Users\eMitchell109\sqhq-local-ai\cyony_voice_clone.py` |

## Quick Start for Cyony (Copy This)

```python
# Add to Cyony's config or main script
ORPHEUS_URL = "http://100.72.250.65:8080"

def speak(text, voice="tara", mood=None):
    """Convert text to speech via Orpheus fleet"""
    import requests
    
    payload = {"text": text, "voice": voice}
    if mood:
        payload["mood"] = mood
    
    r = requests.post(f"{ORPHEUS_URL}/v1/tts", json=payload)
    
    if r.status_code == 200:
        # Save or play audio
        with open("temp_speech.wav", "wb") as f:
            f.write(r.content)
        return "temp_speech.wav"
    else:
        return None

# Usage
speak("Hello Eddie!", voice="tara")
speak("That's funny!", voice="tara", mood="excited")
speak("<sigh> I'm tired...", voice="tara", mood="sad")
```

---

**Status:** CPU mode, working, ready for Cyony integration
**Next steps:** CUDA Toolkit install for GPU acceleration, voice cloning setup
