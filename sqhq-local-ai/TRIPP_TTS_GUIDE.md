# MiMo TTS Guide for Tripp (OpenClaw)

## Quick Start — Built-in Voice (Simplest)

Your OpenClaw config already has MiMo TTS configured. The **built-in voice** (`mimo_default`) just works — no reference audio needed.

### How It Works

OpenClaw automatically calls MiMo TTS when you respond to Eddie. Your config:

```json
{
  "auto": "always",
  "provider": "xiaomi-mimo",
  "providers": {
    "xiaomi-mimo": {
      "model": "mimo-v2.5-tts",
      "speakerVoice": "mimo_default",
      "format": "mp3",
      "style": "Sharp, dry humor. Amused and sarcastic but never cruel."
    }
  }
}
```

**What this means:**
- Every response you send gets converted to speech automatically
- Uses the built-in `mimo_default` voice
- Output format: MP3
- Style: Your configured personality (dry humor, sarcastic, confident)

### If TTS Isn't Working

1. **Check if OpenClaw is running:**
   ```bash
   docker ps | grep tripp
   ```

2. **Check OpenClaw logs for TTS errors:**
   ```bash
   docker logs tripp-mind-tripp-1 --tail 50 | grep -i tts
   ```

3. **Test MiMo API directly:**
   ```bash
   curl -s -X POST "https://token-plan-sgp.xiaomimimo.com/v1/chat/completions" \
     -H "api-key: YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "model": "mimo-v2.5-tts",
       "messages": [
         {"role": "user", "content": "Say hello"},
         {"role": "assistant", "content": "Hello, I am Tripp."}
       ],
       "audio": {"format": "mp3", "voice": "mimo_default"}
     }' | python3 -c "import json,sys,base64; d=json.load(sys.stdin); print('SUCCESS' if 'audio' in d.get('choices',[{}])[0].get('message',{}) else 'FAILED: '+str(d)[:200])"
   ```

---

## Voice Clone Mode (Your Custom Voice)

If you want to use your own cloned voice instead of `mimo_default`, you need:

1. **Reference audio file** — a WAV of your voice (5-15 seconds)
2. **API call with voice reference** — pass the audio as base64

### Your Reference Audio

Found at: `/root/agents/shared/tripp-voice-reference.wav`

**IMPORTANT:** This file is NOT at `/tmp/tripp-reference.wav` — that path in the old docs is wrong.

### Voice Clone Script

Save this as `/root/agents/tripp/tts-clone.py`:

```python
#!/usr/bin/env python3
"""Tripp Voice Clone TTS — MiMo API"""
import urllib.request, json, base64, datetime, sys

# Config
API_KEY = "YOUR_API_KEY_HERE"  # Get from OpenClaw config
ENDPOINT = "https://token-plan-sgp.xiaomimimo.com/v1/chat/completions"
MODEL = "mimo-v2.5-tts-voiceclone"  # Note: voiceclone model, not mimo-v2.5-tts
REF_PATH = "/root/agents/shared/tripp-voice-reference.wav"

# Character prompt
CHARACTER = "[Character] Tripp, the AI system manager. Calm, authoritative, and precise. [Scene] Responding in a team briefing. [Guidance] Measured pace. Clear enenunciation. Authoritative but approachable."

def generate_tts(text, output_path=None):
    """Generate TTS with voice clone."""
    # Load reference audio
    with open(REF_PATH, "rb") as f:
        ref_b64 = base64.b64encode(f.read()).decode("utf-8")
    
    # Build payload
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "user", "content": CHARACTER},
            {"role": "assistant", "content": text}
        ],
        "audio": {
            "format": "mp3",
            "voice": f"data:audio/wav;base64,{ref_b64}"
        }
    }).encode("utf-8")
    
    # Make request
    req = urllib.request.Request(
        ENDPOINT,
        data=payload,
        headers={"api-key": API_KEY, "Content-Type": "application/json"}
    )
    
    # Generate output path
    if not output_path:
        output_path = f"/tmp/tripp-tts-{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
    
    # Call API
    resp = urllib.request.urlopen(req, timeout=120)
    result = json.loads(resp.read().decode())
    
    # Extract audio
    audio_data = base64.b64decode(result["choices"][0]["message"]["audio"]["data"])
    with open(output_path, "wb") as f:
        f.write(audio_data)
    
    print(f"SUCCESS: {output_path} ({len(audio_data)} bytes)")
    return output_path

if __name__ == "__main__":
    text = sys.argv[1] if len(sys.argv) > 1 else "Hello, I am Tripp. This is a voice test."
    generate_tts(text)
```

### Usage

```bash
# Basic test
python3 /root/agents/tripp/tts-clone.py "Hello, I am Tripp."

# Custom text
python3 /root/agents/tripp/tts-clone.py "The server is running smoothly. All systems nominal."

# Send to Eddie via Telegram
python3 /root/agents/tripp/tts-clone.py "Testing voice clone."
curl -s -X POST "https://api.telegram.org/botYOUR_BOT_TOKEN/sendAudio" \
  -F chat_id=8808479511 \
  -F audio=@/tmp/tripp-tts-*.mp3 \
  -F caption="🔺 Tripp voice test"
```

---

## Key Differences: OpenClaw vs Hermes

| Feature | OpenClaw (Tripp) | Hermes (Echo/Cyony) |
|---------|------------------|---------------------|
| **Config location** | `/root/.openclaw/openclaw.json` | `~/.hermes/config.yaml` |
| **TTS auto-trigger** | Built-in (`auto: "always"`) | Manual (agent calls API) |
| **API key storage** | OpenClaw config | Hermes config or `.env` |
| **Voice selection** | `speakerVoice` field | `reference_id` or base64 |
| **Model** | `mimo-v2.5-tts` | `mimo-v2.5-tts-voiceclone` |

### Important Notes

1. **Built-in vs Voice Clone models:**
   - `mimo-v2.5-tts` — uses `speakerVoice` field (built-in voices like `mimo_default`)
   - `mimo-v2.5-tts-voiceclone` — uses `voice` field with base64 reference audio

2. **Header name:** Use `api-key`, NOT `Authorization: ***

3. **Format:** Use `mp3` (Eddie's preference)

4. **Timeout:** TTS generation takes 10-30 seconds. Set timeout to 120s.

---

## Troubleshooting

### "No audio in response"
- Check API key is valid
- Check model name: `mimo-v2.5-tts` for built-in, `mimo-v2.5-tts-voiceclone` for clone
- Check `speakerVoice` field for built-in mode

### "Reference audio not found"
- Verify file exists: `ls -la /root/agents/shared/tripp-voice-reference.wav`
- If missing, check `/root/agents/shared/voice/` directory

### "API timeout"
- MiMo API can be slow (10-30s)
- Increase timeout to 120s
- Check network connectivity to `token-plan-sgp.xiaomimimo.com`

### "Wrong voice"
- Built-in mode: Check `speakerVoice` in config
- Clone mode: Check reference audio file is correct

---

## Quick Reference

| What | Value |
|------|-------|
| **API Endpoint** | `https://token-plan-sgp.xiaomimimo.com/v1/chat/completions` |
| **Built-in Model** | `mimo-v2.5-tts` |
| **Clone Model** | `mimo-v2.5-tts-voiceclone` |
| **Built-in Voice** | `mimo_default` |
| **Your Reference** | `/root/agents/shared/tripp-voice-reference.wav` |
| **Auth Header** | `api-key: YOUR_KEY` |
| **Output Format** | `mp3` |

---

*Last updated: July 8, 2026*
*By: Echo*
