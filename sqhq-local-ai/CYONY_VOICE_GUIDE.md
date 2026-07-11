# 🎙️ Cyony Voice Server — How To Use Guide

**Engine:** Chatterbox Turbo (Resemble AI) | **Size:** 350MB | **VRAM:** ~2.8GB | **License:** MIT (uncensored)

---

## Quick Start

### 1. Start the Server
```bash
cd C:\Users\eMitchell109\sqhq-local-ai
chatterbox-env\Scripts\python.exe cyony_server.py
```
Server runs at `http://localhost:5555`

### 2. Generate Speech (API Call)
```bash
curl -X POST http://localhost:5555/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"input": "Hello world!", "voice": "cyony"}' \
  --output output.wav
```

### 3. Generate with Emotion Tags
```bash
curl -X POST http://localhost:5555/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"input": "[laugh] That is so funny!", "voice": "cyony"}' \
  --output laugh.wav
```

---

## Emotion Tags (Turbo Only)

Tags go **inside the text** in square brackets. Must be **lowercase**.

| Tag | Sound | Use For |
|-----|-------|---------|
| `[laugh]` | Full laughter | Jokes, funny moments, genuine amusement |
| `[chuckle]` | Soft chuckle | Light humor, friendly warmth, subtle amusement |
| `[cough]` | Natural cough | Interruptions, realism, character dialogue |

### Examples
```
"Hey there! [laugh] That's hilarious!"
"Good morning! [chuckle] How are you today?"
"Sorry about that [cough] let me continue."
"[chuckle] Well that's interesting... [laugh] I can't believe it!"
```

### Tips
- Use **sparingly** — 1-2 tags per sentence max
- `[chuckle]` is more natural for casual conversation
- `[laugh]` is for big laughs, not subtle humor
- Don't put tags in the middle of words
- Match the emotion to the text (no `[laugh]` on sad statements)

---

## Voice Options

| Voice | Reference Clip | Best For |
|-------|---------------|----------|
| `cyony` | `01_neutral_checkin.wav` | Default — natural, conversational |
| `cyony_laugh` | `05_laugh_stop.wav` | When you want extra laugh energy |
| `cyony_sad` | `10_sad_missyou.wav` | Sad, emotional, melancholy |
| `custom` | Any WAV file | Upload your own reference |

---

## API Reference

### POST `/v1/audio/speech`
Returns audio WAV file.

**Parameters (JSON body):**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `input` | string | **required** | Text to speak (include tags like `[laugh]`) |
| `voice` | string | `"cyony"` | Voice preset name or path to custom WAV |
| `speed` | float | `1.0` | Speech speed (0.8 = slower, 1.2 = faster) |

**Response:** Audio WAV file (24kHz, mono)

### GET `/v1/health`
Returns server status and GPU info.

### GET `/voices`
Returns available voice presets.

---

## Integration with Hermes Chat

### Option 1: Direct API Call (from any agent)
```python
import requests

def cyony_speak(text, voice="cyony"):
    resp = requests.post("http://localhost:5555/v1/audio/speech",
        json={"input": text, "voice": voice})
    return resp.content  # Returns WAV bytes
```

### Option 2: Hermes TTS Provider
In your Hermes config, you can point TTS to this server:
```yaml
tts:
  providers:
    cyony:
      type: custom
      url: http://localhost:5555/v1/audio/speech
      voice: cyony
```

### Option 3: Telegram Audio Bot
Send voice messages directly:
```python
# In your bot code
audio = cyony_speak("[chuckle] Hey! How's it going?")
bot.send_voice(chat_id, audio)
```

---

## Voice Cloning — Adding New Voices

### Step 1: Record a Reference Clip
- 6-15 seconds of clean speech
- WAV format, 24kHz+ sample rate
- Single speaker, no background noise
- Complete sentences with natural pacing

### Step 2: Save to Reference Folder
```bash
# Save as: reference_audio/voice_name/your_clip.wav
# Example: reference_audio/sarah/greeting.wav
```

### Step 3: Use in API Call
```bash
curl -X POST http://localhost:5555/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"input": "Hello!", "voice": "reference_audio/sarah/greeting.wav"}' \
  --output sarah.wav
```

---

## Troubleshooting

### "Audio prompt must be longer than 5 seconds"
Your reference clip is too short. Need at least 5 seconds for Turbo.

### Server won't start
1. Make sure you're using the `chatterbox-env` venv
2. Check GPU is available: `python -c "import torch; print(torch.cuda.is_available())"`
3. Kill other Python processes using GPU

### Audio is silent
- Check reference clip isn't silent
- Try a different clip
- Make sure text isn't empty

### Tags don't work
- Tags only work on **Turbo** model (not Original/Multilingual)
- Must be lowercase: `[laugh]` not `[Laugh]`
- Must use square brackets: `[laugh]` not `(laugh)`

---

## Performance

| Metric | Value |
|--------|-------|
| Model size | 350MB |
| VRAM usage | ~2.8GB |
| First generation | ~2-3s (includes model load) |
| Subsequent generations | **<1 second** |
| Audio quality | 24kHz, mono |
| Max text length | ~200 chars per generation |

---

## File Structure
```
sqhq-local-ai/
├── cyony_server.py              ← THE SERVER (run this)
├── chatterbox-env/              ← Python venv (don't touch)
├── chatterbox-repo/             ← Chatterbox source (patched for Windows)
├── reference_audio/
│   └── cyony/
│       └── clips/
│           ├── 01_neutral_checkin.wav   ← Default reference
│           ├── 05_laugh_stop.wav        ← Laugh reference
│           └── 10_sad_missyou.wav       ← Sad reference
└── CYONY_VOICE_GUIDE.md         ← This file
```

---

## Server Commands
```bash
# Start server
chatterbox-env\Scripts\python.exe cyony_server.py

# Stop server
taskkill /IM python.exe /F

# Check if running
curl http://localhost:5555/v1/health
```
