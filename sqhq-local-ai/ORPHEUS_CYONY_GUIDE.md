# 🎙️ Orpheus Voice Server — Cyony Integration Guide

**Last Updated:** July 6, 2026  
**Server Location:** Eddie's Local PC (RTX 4070, Windows)  
**VPS Access:** Via Tailscale  
**Port:** 8081

---

## 🌐 Connection

Eddie's local PC is on Tailscale at:

```
http://100.72.250.65:8081
```

From the VPS, all requests go to that address. No port forwarding, no firewall config — Tailscale handles it.

### Quick Connection Test

```bash
curl http://100.72.250.65:8081/v1/health
```

Expected response:
```json
{
  "status": "ok",
  "gpu": "cuda",
  "voices": ["tara", "leah", "jess", "leo", "dan", "mia", "zac", "zoe"],
  "emotions": ["laugh", "chuckle", "giggle", "sigh", "groan", "yawn", "gasp", "cough", "sniffle"],
  "moods": ["warm_calm", "excited", "serious", "sad", "neutral", "mysterious", "happy", "angry"],
  "formats": ["mp3", "wav"]
}
```

---

## 📡 API Endpoints

### 1. `GET /v1/health` — Status Check

Returns server status, GPU info, available voices, emotions, and moods.

```bash
curl http://100.72.250.65:8081/v1/health
```

---

### 2. `POST /v1/tts` — Built-in Voice TTS (Fast)

Generate speech using one of 8 built-in voices. This is **fast** (~1-3 seconds) and uses the orpheus-cpp engine.

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | ✅ | Text to speak |
| `voice` | string | No | Voice name (default: `tara`) |
| `mood` | string | No | Mood preset (applies temperature + emotion) |
| `emotion` | string | No | Emotion tag (prepended to text) |
| `temperature` | float | No | 0.1–1.0 (default: 0.7). Higher = more expressive |
| `format` | string | No | `mp3` (default) or `wav` |

**Available Voices:**
`tara`, `leah`, `jess`, `leo`, `dan`, `mia`, `zac`, `zoe`

**Available Moods:**
`warm_calm`, `excited`, `serious`, `sad`, `neutral`, `mysterious`, `happy`, `angry`

**Available Emotions:**
`laugh`, `chuckle`, `giggle`, `sigh`, `groan`, `yawn`, `gasp`, `cough`, `sniffle`

**Examples:**

```bash
# Simple TTS
curl -X POST http://100.72.250.65:8081/v1/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello, how are you today?","voice":"tara"}' \
  -o output.mp3

# With mood
curl -X POST http://100.72.250.65:8081/v1/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"That is absolutely amazing!","voice":"tara","mood":"excited"}' \
  -o excited.mp3

# With emotion tag
curl -X POST http://100.72.250.65:8081/v1/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"I cannot believe you did that!","voice":"dan","emotion":"laugh"}' \
  -o laughing.mp3

# WAV output
curl -X POST http://100.72.250.65:8081/v1/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"Good morning!","voice":"leah","mood":"warm_calm","format":"wav"}' \
  -o morning.wav
```

---

### 3. `POST /v1/clone` — Voice Cloning

Clone a voice from reference audio and generate new speech. This uses the **HuggingFace Orpheus pretrained model** + SNAC encoder. First request takes ~10-30 seconds (model loading); subsequent requests are ~5-10 seconds.

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `transcript` | string | ✅ | What the reference audio says (for alignment) |
| `text` | string | ✅ | New text to speak in the cloned voice |
| `reference_audio_b64` | string | ✅* | Base64-encoded reference audio (WAV) |
| `reference_audio_url` | string | ✅* | URL to reference audio (WAV) |
| `temperature` | float | No | 0.1–1.0 (default: 0.5). Lower = more stable |
| `format` | string | No | `mp3` (default) or `wav` |

*Either `reference_audio_b64` or `reference_audio_url` is required.

**Important:** The `transcript` should describe what the reference audio says. The model uses this to align the voice characteristics.

**Example — Base64:**

```bash
# First, encode reference audio to base64
REF_B64=$(base64 -w 0 reference_audio.wav)

# Clone
curl -X POST http://100.72.250.65:8081/v1/clone \
  -H "Content-Type: application/json" \
  -d "{
    \"transcript\": \"It is dark in here. Can you hear me?\",
    \"text\": \"Hello Eddie, this is your cloned voice speaking.\",
    \"reference_audio_b64\": \"$REF_B64\",
    \"temperature\": 0.5
  }" \
  -o cloned.mp3
```

**Example — URL:**

```bash
curl -X POST http://100.72.250.65:8081/v1/clone \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "It is dark in here. Can you hear me?",
    "text": "Hello Eddie, this is your cloned voice speaking.",
    "reference_audio_url": "http://100.85.111.32:3456/audio/reference.wav",
    "temperature": 0.5
  }' \
  -o cloned.mp3
```

---

### 4. `POST /v1/brain` — Uncensored Text Generation

Generate text using the uncensored Llama 3.2 3B Abliterated model via Ollama. Returns text only (no audio).

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `prompt` | string | ✅ | What you want the brain to say/respond to |
| `system` | string | No | System prompt (default: helpful uncensored assistant) |
| `model` | string | No | Ollama model name (default: `huihui_ai/llama3.2-abliterate:3b`) |

**Example:**

```bash
curl -X POST http://100.72.250.65:8081/v1/brain \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Say something warm and encouraging to a friend."}'
```

Response:
```json
{
  "text": "Huge congratulations to you on completing your incredibly ambitious project...",
  "time_seconds": 0.88
}
```

---

### 5. `POST /v1/brain_tts` — Full Pipeline (Brain → Voice)

The complete pipeline: **Brain generates text → Orpheus speaks it → MP3 output**. This is the main endpoint for conversational voice.

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `prompt` | string | ✅ | What you want said |
| `voice` | string | No | Voice name (default: `tara`) |
| `mood` | string | No | Mood preset |
| `emotion` | string | No | Emotion tag |
| `temperature` | float | No | Voice temperature (default: 0.7) |
| `format` | string | No | `mp3` (default) or `wav` |
| `system` | string | No | Brain system prompt |
| `model` | string | No | Ollama model (default: `huihui_ai/llama3.2-abliterate:3b`) |

**Examples:**

```bash
# Simple brain → voice
curl -X POST http://100.72.250.65:8081/v1/brain_tts \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Tell me a short joke","voice":"tara","mood":"happy"}' \
  -o joke.mp3

# Serious tone
curl -X POST http://100.72.250.65:8081/v1/brain_tts \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Give me a brief status update on world events","voice":"leo","mood":"serious"}' \
  -o status.mp3

# Custom system prompt
curl -X POST http://100.72.250.65:8081/v1/brain_tts \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Check in on Eddie and say something encouraging",
    "voice": "tara",
    "mood": "warm_calm",
    "system": "You are Tripp, Eddie loyal AI companion. Speak warmly and authentically."
  }' \
  -o checkin.mp3
```

---

## 🎭 Mood Presets (Quick Reference)

| Mood | Temperature | Emotion | Description |
|------|-------------|---------|-------------|
| `warm_calm` | 0.5 | None | Gentle, soothing |
| `excited` | 0.9 | None | High energy, enthusiastic |
| `serious` | 0.4 | None | Professional, measured |
| `sad` | 0.3 | sigh | Melancholy, reflective |
| `neutral` | 0.7 | None | Default, balanced |
| `mysterious` | 0.6 | None | Intriguing, low-key |
| `happy` | 0.8 | None | Upbeat, positive |
| `angry` | 0.9 | None | Intense, forceful |

You can combine moods with emotions: `"mood":"excited","emotion":"laugh"` for excited laughter.

---

## 🔧 Python Integration (from Cyony)

```python
import requests
import base64

SERVER = "http://100.72.250.65:8081"

# === Quick TTS ===
def speak(text, voice="tara", mood="warm_calm", fmt="mp3"):
    """Generate speech from text."""
    r = requests.post(f"{SERVER}/v1/tts", json={
        "text": text,
        "voice": voice,
        "mood": mood,
        "format": fmt
    }, timeout=30)
    return r.content  # Audio bytes

# === Brain → Voice ===
def brain_speak(prompt, voice="tara", mood="warm_calm"):
    """Brain generates text, then speaks it."""
    r = requests.post(f"{SERVER}/v1/brain_tts", json={
        "prompt": prompt,
        "voice": voice,
        "mood": mood,
        "format": "mp3"
    }, timeout=120)
    return r.content

# === Voice Cloning ===
def clone_speak(text, reference_wav_path, transcript, temperature=0.5):
    """Clone a voice and speak text."""
    with open(reference_wav_path, "rb") as f:
        ref_b64 = base64.b64encode(f.read()).decode()
    
    r = requests.post(f"{SERVER}/v1/clone", json={
        "transcript": transcript,
        "text": text,
        "reference_audio_b64": ref_b64,
        "temperature": temperature,
        "format": "mp3"
    }, timeout=300)
    return r.content

# === Brain Only (no audio) ===
def brain_think(prompt, system=None):
    """Generate text from uncensored brain."""
    payload = {"prompt": prompt}
    if system:
        payload["system"] = system
    r = requests.post(f"{SERVER}/v1/brain", json=payload, timeout=60)
    return r.json()["text"]

# === Health Check ===
def is_alive():
    """Check if server is reachable."""
    try:
        r = requests.get(f"{SERVER}/v1/health", timeout=5)
        return r.json()["status"] == "ok"
    except:
        return False


# === Usage Examples ===

# 1. Quick greeting
audio = speak("Good morning Eddie! Ready to tackle today?", voice="tara", mood="warm_calm")
with open("greeting.mp3", "wb") as f:
    f.write(audio)

# 2. Brain-generated response
response = brain_think("What should I work on today?")
print(f"Brain: {response}")

# 3. Full pipeline — brain generates, voice speaks
audio = brain_speak(
    "Give Eddie a motivational pep talk about finishing strong",
    voice="tara",
    mood="warm_calm"
)
with open("pep_talk.mp3", "wb") as f:
    f.write(audio)

# 4. Clone Eddie's voice
audio = clone_speak(
    text="Hey, this is your voice speaking through the system!",
    reference_wav_path="/opt/data/orpheus_training/reference_clips/eddie_30s.wav",
    transcript="This is Eddie speaking a reference clip for voice cloning.",
    temperature=0.5
)
with open("eddie_clone.mp3", "wb") as f:
    f.write(audio)
```

---

## 📁 Reference Audio Setup (Voice Cloning)

### Where to Store Reference Clips

On the VPS, store reference audio at:
```
/opt/data/orpheus_training/reference_clips/
```

### Requirements for Reference Audio

- **Format:** WAV (16-bit PCM, mono or stereo)
- **Duration:** 10–30 seconds optimal
- **Quality:** Clean audio, minimal background noise
- **Content:** Natural speech (the transcript field tells the model what was said)

### Downloading from VPS to Local PC (for reference)

```bash
# From Eddie's local PC
scp root@100.85.111.32:/opt/data/orpheus_training/reference_clips/*.wav \
    C:\Users\eMitchell109\sqhq-local-ai\reference_audio\
```

---

## ⚠️ Troubleshooting

### Connection Refused

```bash
# Check if Tailscale is connected
tailscale status

# Test direct connection
ping 100.72.250.65

# Check port
curl -v http://100.72.250.65:8081/v1/health
```

### Server Not Responding

The server runs as a background process on Eddie's PC. If it goes down:

```bash
# On Eddie's PC (via SSH or remote)
cd C:\Users\eMitchell109\sqhq-local-ai
python orpheus_voice_server.py
```

### Slow First Request (Cloning)

The first clone request loads the 3.3GB pretrained model onto GPU. Subsequent requests are fast (~5-10 seconds).

### OOM (Out of Memory)

The system uses ~4-5GB VRAM total:
- Brain (Llama 3.2): ~2.2GB
- Clone TTS (Orpheus pretrained): ~2.0GB
- SNAC encoder: ~0.1GB
- orpheus-cpp (built-in voices): ~2.3GB

Built-in voices and cloning cannot run simultaneously on the same GPU. The server handles this by loading/unloading as needed.

### Audio Quality Issues

- **Lower temperature** (0.3–0.5) = more stable, less expressive
- **Higher temperature** (0.7–1.0) = more expressive, less stable
- **Mood presets** automatically set optimal temperature for each emotion

---

## 🔄 Recommended Workflow for Cyony

1. **Health check** → `GET /v1/health`
2. **Generate response** → `POST /v1/brain` (get text)
3. **Speak it** → `POST /v1/tts` or `POST /v1/clone` (get audio)
4. **Deliver** → Send MP3/audio to Eddie via Telegram

Or just use the all-in-one:
- `POST /v1/brain_tts` → Brain + built-in voice in one call
- `POST /v1/clone` → Cloned voice in one call

---

**Server maintained by:** Eddie's Local PC  
**Tailscale address:** `100.72.250.65:8081`  
**Guide version:** 1.0 (July 6, 2026)
