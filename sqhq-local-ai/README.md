# Cyony Mood-Clone Voice Pipeline

**Complete documentation for the VPS-to-local Chatterbox TTS mood-clone pipeline.**

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [How It Works](#how-it-works)
3. [The 10 Moods](#the-10-moods)
4. [API Reference](#api-reference)
5. [Starting the Server](#starting-the-server)
6. [Usage Examples](#usage-examples)
7. [cfg_weight & Exaggeration Tuning](#cfg_weight--exaggeration-tuning)
8. [Emotion Tags](#emotion-tags)
9. [Bug Fixes Applied](#bug-fixes-applied)
10. [Troubleshooting](#troubleshooting)
11. [File Locations](#file-locations)
12. [Related Documentation](#related-documentation)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        VPS (Orchestrator)                        │
│                     100.85.111.32 (Tailscale)                    │
│                                                                  │
│   Cyony Bot receives Telegram message                            │
│   → Determines mood from context                                │
│   → POST http://100.72.250.65:5555/v1/audio/mood                │
│     {"mood": "whisper", "input": "Hey..."}                       │
└────────────────────────────┬────────────────────────────────────┘
                             │ Tailscale (WireGuard)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Local PC (Chatterbox TTS)                     │
│                  100.72.250.65 (Tailscale)                       │
│                    RTX 4070 12GB, 64GB RAM                       │
│                                                                  │
│   cyony_server.py (FastAPI, port 5555)                          │
│   ├── Standard Chatterbox (cfg_weight + exaggeration)           │
│   ├── Turbo Chatterbox (fast speech + [laugh]/[sigh] tags)      │
│   └── MiMo TTS (emotion-tagged speech)                          │
│                                                                  │
│   Mood Pipeline:                                                 │
│   1. Acquire GPU semaphore (thread-safe)                        │
│   2. Pad short text >25 chars (fix #201)                        │
│   3. Clear hooks (fix #504)                                     │
│   4. Load mood reference clip from local storage                │
│   5. Clone voice FROM mood clip (zero-shot)                     │
│   6. Generate speech with cfg_weight for emotion transfer       │
│   7. Layer tags ([laugh], [sigh]) on top                        │
│   8. VRAM cleanup after generation                              │
│   9. Release semaphore                                           │
│  10. Return WAV audio to VPS                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## How It Works

### The Core Concept

**Clone FROM mood-specific reference clips to transfer emotional quality.**

Instead of generating neutral speech and trying to add emotion, we:
1. Have pre-recorded clips of Cyony speaking IN each mood (whisper, sultry, annoyed, etc.)
2. Use Chatterbox's zero-shot voice cloning to clone FROM that mood clip
3. The cloned voice inherits the emotional prosody, pacing, and tone
4. All new text is generated in that cloned mood voice

### Why Standard Chatterbox (Not Just Turbo)

| Feature | Turbo (350M) | Standard (500M) |
|---------|--------------|-----------------|
| Speed | ~3s per chunk | ~4s per chunk |
| VRAM | ~3GB | ~3GB |
| `cfg_weight` | ❌ Ignored | ✅ Supported |
| `exaggeration` | ❌ Ignored | ✅ Supported |
| `[laugh]`/`[sigh]` tags | ✅ Supported | ❌ Read as literal text |
| **Best for** | Fast speech, inline tags | **Mood cloning, emotion transfer** |

**We use Standard for mood cloning** because `cfg_weight` and `exaggeration` control how strongly the mood transfer happens.

### The Flow

1. **VPS sends request**: `POST /v1/audio/mood` with mood name + text
2. **Local PC loads mood clip**: Fetches the pre-recorded mood reference WAV
3. **Clone voice FROM mood clip**: Standard Chatterbox extracts speaker embedding + prosody from the mood clip
4. **Generate speech**: Text is synthesized in the cloned mood voice
5. **Return audio**: WAV file sent back to VPS via Tailscale

---

## The 10 Moods

| Mood | Description | cfg_weight | Best For |
|------|-------------|------------|----------|
| **chill** | Relaxed, easygoing, laid-back | 0.5 | Casual conversation, updates |
| **flirty** | Playful, teasing, warm | 0.4 | Banter, humor, light moments |
| **whisper** | Quiet, intimate, breathy | 0.5 | Secrets, asides, emphasis |
| **annoyed** | Irritated, clipped, tense | 0.5 | Frustration, complaints |
| **eureka** | Excited discovery, breakthrough | 0.5 | Ideas, realizations, "aha!" |
| **groggy** | Tired, slow, low-energy | 0.5 | Morning, late night, exhaustion |
| **dead** | Monotone, flat, emotionless | 0.5 | Deadpan delivery, sarcasm |
| **sad** | Melancholic, slow, heavy | 0.5 | Sympathy, disappointment |
| **excited** | High energy, fast, enthusiastic | 0.4 | Celebration, good news |
| **sultry** | Deep, smooth, suggestive | 0.4 | Charm, allure, emphasis |

### Mood Clips Location

```
C:\Users\eMitchell109\sqhq-local-ai\reference_audio\cyony\moods\
├── chill_raw.wav
├── flirty_raw.wav
├── whisper_raw.wav
├── annoyed_raw.wav
├── eureka_raw.wav
├── groggy_raw.wav
├── dead_raw.wav
├── sad_raw.wav
├── excited_raw.wav
└── sultry_raw.wav
```

---

## API Reference

### POST `/v1/audio/mood`

Generate speech in a specific mood.

**Request:**
```json
{
  "mood": "whisper",
  "input": "Hey... come here...",
  "tags": "[sigh]",
  "exaggeration": 0.5,
  "silence_between": null,
  "crossfade_ms": null
}
```

**Parameters:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mood` | string | required | One of the 10 mood names |
| `input` | string | required | Text to speak |
| `tags` | string | null | Emotion tags: `[laugh]`, `[sigh]`, `[chuckle]`, `[cough]` |
| `exaggeration` | float | 0.5 | Mood intensity (0.0-1.0) |
| `silence_between` | float | 0.3 | Silence between chunks (seconds) |
| `crossfade_ms` | int | 50 | Crossfade duration between chunks |

**Response:** WAV audio (24kHz, mono)

**Headers:**
- `X-Generation-Time`: Time taken (seconds)
- `X-Audio-Duration`: Audio length (seconds)
- `X-Mood`: Mood used
- `X-Cfg-Weight`: cfg_weight applied

**Error Responses:**
- `400`: Unknown mood or empty text
- `500`: Generation failed
- `503`: Server busy (another request in progress)

---

### GET `/v1/moods`

List all available moods with descriptions.

**Response:**
```json
{
  "moods": {
    "chill": {
      "description": "Relaxed, easygoing, laid-back",
      "cfg_weight": 0.5,
      "clip_exists": true
    },
    ...
  }
}
```

---

### POST `/v1/audio/speech`

Standard speech generation (Turbo, fast).

**Request:**
```json
{
  "input": "Hello world!",
  "engine": "chatterbox",
  "voice": "cyony",
  "temperature": null,
  "repetition_penalty": null
}
```

**Parameters:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `input` | string | required | Text to speak |
| `engine` | string | "chatterbox" | "chatterbox" or "mimo" |
| `voice` | string | "cyony" | Voice name or path to reference WAV |
| `mimo_voice` | string | "nova" | MiMo voice name (if engine=mimo) |
| `mimo_style` | string | null | MiMo style tag |
| `temperature` | float | null | Sampling temperature |
| `repetition_penalty` | float | null | Repetition penalty |

---

### GET `/v1/health`

Server health check.

**Response:**
```json
{
  "status": "ok",
  "engines": {
    "chatterbox_turbo": {
      "status": "loaded",
      "device": "cuda:0",
      "vram_used_gb": 6.0,
      "note": "Fast speech + [laugh]/[sigh] tags"
    },
    "chatterbox_standard": {
      "status": "loaded",
      "device": "cuda:0",
      "note": "Mood cloning with cfg_weight support"
    },
    "mimo": {
      "status": "loaded",
      "note": "Local MiMo TTS engine"
    }
  }
}
```

---

## Starting the Server

### Prerequisites
- Python 3.11 in `chatterbox-env`
- CUDA-capable GPU (RTX 4070 12GB)
- ~6GB VRAM available (both models loaded)

### Start Command
```bash
cd C:\Users\eMitchell109\sqhq-local-ai
chatterbox-env\Scripts\python.exe cyony_server.py
```

### Verify
```bash
curl http://localhost:5555/v1/health
```

### From VPS
```bash
ssh root@100.85.111.32
curl http://100.72.250.65:5555/v1/health
```

---

## Usage Examples

### Example 1: Whisper Mood
```bash
curl -X POST http://localhost:5555/v1/audio/mood \
  -H "Content-Type: application/json" \
  -d '{"mood": "whisper", "input": "Hey... come here... I need to tell you something."}' \
  --output whisper.wav
```

### Example 2: Excited with Tags
```bash
curl -X POST http://localhost:5555/v1/audio/mood \
  -H "Content-Type: application/json" \
  -d '{"mood": "excited", "input": "This is amazing! We did it!", "tags": "[laugh]"}' \
  --output excited.wav
```

### Example 3: Sultry with High Exaggeration
```bash
curl -X POST http://localhost:5555/v1/audio/mood \
  -H "Content-Type: application/json" \
  -d '{"mood": "sultry", "input": "You like that, don't you?", "exaggeration": 0.7}' \
  --output sultry.wav
```

### Example 4: Python Client
```python
import requests

# Generate whisper speech
r = requests.post('http://localhost:5555/v1/audio/mood', json={
    'mood': 'whisper',
    'input': 'This is a secret...',
    'tags': '[sigh]'
})

if r.status_code == 200:
    with open('output.wav', 'wb') as f:
        f.write(r.content)
    print(f"Generated {r.headers['X-Audio-Duration']}s audio")
else:
    print(f"Error: {r.status_code} - {r.text}")
```

### Example 5: List All Moods
```bash
curl http://localhost:5555/v1/moods | python -m json.tool
```

---

## cfg_weight & Exaggeration Tuning

### cfg_weight (0.0–1.0, default 0.5)

Controls how strongly the generated speech adheres to the reference voice's characteristics.

| Value | Effect |
|-------|--------|
| 0.0–0.3 | Low adherence — text-driven prosody, more deliberate pacing |
| 0.4–0.5 | Balanced — reference voice with some text influence |
| 0.6–0.7 | High adherence — strong mood transfer from reference clip |
| 0.8–1.0 | Maximum — very strong reference influence (may sound unnatural) |

**For mood cloning:** Start at 0.5, increase to 0.6–0.7 if mood transfer is too weak.

### exaggeration (0.0–1.0, default 0.5)

Controls emotional expressiveness intensity.

| Value | Effect |
|-------|--------|
| 0.0–0.3 | Flat, neutral, minimal emotion |
| 0.4–0.6 | Natural, conversational emotion |
| 0.7–0.8 | Dramatic, heightened emotion |
| 0.9–1.0 | Extreme (may produce gibberish) |

**Important:** Higher exaggeration speeds up speech. Compensate with lower cfg_weight if needed.

### Interaction

- **cfg_weight + exaggeration are interacting parameters** — tune them as a pair
- Higher cfg_weight + higher exaggeration = strongest mood transfer
- If output sounds unnatural, try: cfg_weight=0.5, exaggeration=0.4
- If mood is too subtle, try: cfg_weight=0.6, exaggeration=0.6

---

## Emotion Tags

Tags add non-speech sounds IN the cloned voice.

### Available Tags

| Tag | Sound | Best Used With |
|-----|-------|----------------|
| `[laugh]` | Natural laughter | Excited, flirty, eureka |
| `[chuckle]` | Soft laugh | Chill, flirty |
| `[sigh]` | Exhale/breath | Whisper, sad, groggy |
| `[cough]` | Cough sound | Dead, annoyed |

### Important Notes

- **Turbo only:** Tags only work on Turbo model, not Standard
- **Layered on top:** Tags don't change voice identity, just add emotional coloring
- **Usage:** Include in `input` text or `tags` field
- **Placement:** Works best at natural pauses in speech

### Example
```json
{
  "mood": "excited",
  "input": "[laugh] This is so cool! [laugh] I can't believe it!",
  "tags": "[laugh]"
}
```

---

## Bug Fixes Applied

### Fix #201: Short-text CUDA Crash

**Problem:** Chatterbox crashes with `Assertion 'srcIndex < srcSelectDimSize' failed` when generating short text (<25 chars).

**Solution:** Pad short text with meaningful filler.
```python
if len(text.strip()) < 25:
    text = f"...ummmm {text}"
```

**Why meaningful filler:** Spaces/punctuation don't help. The model needs actual tokens to maintain tensor alignment.

---

### Fix #504: Hook Leak

**Problem:** `AlignmentStreamAnalyzer` leaks forward hooks on transformer attention layers with every `generate()` call. After ~33 hooks, quality degrades and output collapses.

**Solution:** Clear hooks before each generation.
```python
for layer in self.model.cond_stage_model.model.transformer.layers:
    if hasattr(layer.self_attn, '_forward_hooks'):
        layer.self_attn._forward_hooks.clear()
```

---

### VRAM Cleanup

**Problem:** Repeated generations fragment VRAM, causing OOM even if total usage should fit.

**Solution:** Clear CUDA cache after each generation.
```python
import torch
if torch.cuda.is_available():
    torch.cuda.empty_cache()
```

---

### Thread Safety

**Problem:** Chatterbox is NOT thread-safe. Concurrent `generate()` calls corrupt internal state.

**Solution:** Semaphore limits to one request at a time.
```python
_gpu_semaphore = threading.Semaphore(1)

# In endpoint:
if not _gpu_semaphore.acquire(blocking=False):
    raise HTTPException(503, "Server busy")
try:
    # ... generate ...
finally:
    _gpu_semaphore.release()
```

---

## Troubleshooting

### "Server busy — another generation in progress"

Another request is using the GPU. Wait a few seconds and retry.

### "Mood clip not found"

The mood reference WAV is missing. Check:
```bash
ls C:\Users\eMitchell109\sqhq-local-ai\reference_audio\cyony\moods\
```

### "Unknown mood: xxx"

Typo in mood name. Available moods:
`chill`, `flirty`, `whisper`, `annoyed`, `eureka`, `groggy`, `dead`, `sad`, `excited`, `sultry`

### VRAM Out of Memory

Both models use ~6GB total. If OOM:
1. Restart server to free VRAM
2. Check for other GPU processes: `nvidia-smi`
3. Reduce text length (shorter chunks)

### Audio Sounds Bad/Flat

- Increase `cfg_weight` (0.6–0.7)
- Increase `exaggeration` (0.6–0.7)
- Use a cleaner reference clip
- Check reference clip isn't corrupted

### Tags Don't Work

Tags only work on Turbo model. The `/v1/audio/mood` endpoint uses Standard (for cfg_weight). Use `/v1/audio/speech` with Turbo if you need tags.

---

## File Locations

### Local PC (100.72.250.65)

| Path | Description |
|------|-------------|
| `C:\Users\eMitchell109\sqhq-local-ai\cyony_server.py` | Main server |
| `C:\Users\eMitchell109\sqhq-local-ai\reference_audio\cyony\clips\` | 23 voice reference clips |
| `C:\Users\eMitchell109\sqhq-local-ai\reference_audio\cyony\moods\` | 10 mood reference clips |
| `C:\Users\eMitchell109\sqhq-local-ai\chatterbox-repo\` | Chatterbox source |
| `C:\Users\eMitchell109\sqhq-local-ai\chatterbox-env\` | Python virtualenv |

### VPS (100.85.111.32)

| Path | Description |
|------|-------------|
| `/root/agents/shared/cyony-voice-pipeline/pipeline_config.json` | Pipeline configuration |
| `/root/agents/shared/cyony-voice-pipeline/clone-ready/` | Mood clips (source of truth) |

---

## Related Documentation

| Document | Description |
|----------|-------------|
| `CHATTERBOX_EMOTION_AUDIT.md` | Deep dive into emotion/mood cloning |
| `voice-pipeline-api-spec.md` | Full API specification |
| `CYONY_VOICE_GUIDE.md` | Voice setup guide |
| `EMOTION_TAG_GUIDE.md` | Emotion tags reference |

---

## Quick Reference Card

```bash
# Start server
cd C:\Users\eMitchell109\sqhq-local-ai
chatterbox-env\Scripts\python.exe cyony_server.py

# Health check
curl http://localhost:5555/v1/health

# List moods
curl http://localhost:5555/v1/moods

# Generate mood speech
curl -X POST http://localhost:5555/v1/audio/mood \
  -H "Content-Type: application/json" \
  -d '{"mood": "whisper", "input": "Hello!"}' \
  --output output.wav

# Generate standard speech
curl -X POST http://localhost:5555/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"input": "Hello!", "voice": "cyony"}' \
  --output output.wav

# From VPS
curl http://100.72.250.65:5555/v1/health
```

---

**Last Updated:** 2026-07-11  
**Version:** 3.0 (Mood Pipeline)  
**Maintained by:** Echo 🛡️
