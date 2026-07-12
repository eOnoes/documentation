# MiMo TTS Guide — For Eddie & Cyony

## What is MiMo TTS?

MiMo TTS is Xiaomi's text-to-speech service with **3 models**:
1. **mimo-v2.5-tts** — Built-in voices (Milo, Dean, Mia, Chloe) with streaming
2. **mimo-v2.5-tts-voicedesign** — Create new voices from text descriptions
3. **mimo-v2.5-tts-voiceclone** — Clone voices from audio samples

---

## Quick Start (5 minutes)

### Step 1: Your API Key

**Eddie's key is already configured!**
- Location: `C:\Users\eMitchell109\AppData\Local\hermes\.env`
- Variable: `XIAOMI_API_KEY`
- Value: `tp-sry...ptih` (starts with `tp-`)

**Cyony (VPS):** Add this to your `.env` file:
```
XIAOMI_API_KEY=your-key-here
```

### Step 2: Test It Works

**PowerShell test:**
```powershell
$env:XIAOMI_API_KEY="your-key-here"
python -c "
import requests, os, base64

key = os.environ['XIAOMI_API_KEY']
url = 'https://token-plan-sgp.xiaomimimo.com/v1/chat/completions'

resp = requests.post(url, headers={'api-key': key}, json={
    'model': 'mimo-v2.5-tts',
    'messages': [{'role': 'user', 'content': 'Hello! This is a test.'}],
    'stream': False
})

data = resp.json()
audio_b64 = data['choices'][0]['message']['audio']['data']
with open('test.wav', 'wb') as f:
    f.write(base64.b64decode(audio_b64))
print('Saved test.wav')
"
```

---

## Usage Examples

### Basic TTS (Built-in Voices)

```python
import requests, os, base64

key = os.environ['XIAOMI_API_KEY']
url = 'https://token-plan-sgp.xiaomimimo.com/v1/chat/completions'

# Available voices: Milo (male), Dean (male), Mia (female), Chloe (female)
voice = "Milo"

resp = requests.post(url, headers={'api-key': key}, json={
    'model': 'mimo-v2.5-tts',
    'messages': [{
        'role': 'user',
        'content': 'Hello! I am your AI assistant.',
        'voice': voice
    }],
    'stream': False
})

audio_b64 = resp.json()['choices'][0]['message']['audio']['data']
with open('output.wav', 'wb') as f:
    f.write(base64.b64decode(audio_b64))
```

### With Emotion Tags

```python
# Add emotion tags in the content
content = '(excited) This is amazing news! (calm) Let me explain what happened.'

resp = requests.post(url, headers={'api-key': key}, json={
    'model': 'mimo-v2.5-tts',
    'messages': [{'role': 'user', 'content': content}],
    'stream': False
})
```

**Available tags:**
- `(excited)` — High energy, enthusiastic
- `(sad)` — Melancholy, down
- `(angry)` — Frustrated, mad
- `(gentle)` — Soft, caring
- `(lazy)` — Relaxed, unhurried
- `(magnetic)` — Confident, compelling

### Director Mode (Advanced)

```python
# Use script format for multi-character scenes
content = """[Character] Cold, authoritative mentor
[Scene] Standing in a dimly lit office, arms crossed
[Guidance] Measured words with controlled intensity

[beat] I gave you one rule. One.

[beat] Never reveal the source. (pause)

[beat] And yet here we are."""

resp = requests.post(url, headers={'api-key': key}, json={
    'model': 'mimo-v2.5-tts',
    'messages': [{'role': 'user', 'content': content}],
    'stream': False
})
```

### Voice Design (Create New Voices)

```python
# Design a voice from text description
content = "[design] A warm, friendly male voice in his 30s with a slight Southern accent"

resp = requests.post(url, headers={'api-key': key}, json={
    'model': 'mimo-v2.5-tts-voicedesign',
    'messages': [{'role': 'user', 'content': content}],
    'stream': False
})

# Save the designed voice as a reference file
audio_b64 = resp.json()['choices'][0]['message']['audio']['data']
with open('designed_voice.wav', 'wb') as f:
    f.write(base64.b64decode(audio_b64))
```

### Voice Cloning

```python
# Clone from an audio file
import base64

# Read reference audio
with open('reference.wav', 'rb') as f:
    audio_b64 = base64.b64encode(f.read()).decode()

# Clone and speak
content = "Hello! I am your cloned voice."

resp = requests.post(url, headers={'api-key': key}, json={
    'model': 'mimo-v2.5-tts-voiceclone',
    'messages': [{'role': 'user', 'content': content}],
    'audio': {'voice': f'data:audio/wav;base64,{audio_b64}'},
    'stream': False
})
```

---

## Streaming (For Real-Time)

```python
# Streaming gives you audio chunks as they're generated
resp = requests.post(url, headers={'api-key': key}, json={
    'model': 'mimo-v2.5-tts',
    'messages': [{'role': 'user', 'content': 'This text will stream as audio.'}],
    'stream': True
}, stream=True)

for line in resp.iter_lines():
    if line:
        data = json.loads(line.decode('utf-8').removeprefix('data: '))
        if 'audio' in data.get('choices', [{}])[0].get('delta', {}):
            audio_b64 = data['choices'][0]['delta']['audio']['data']
            audio_bytes = base64.b64decode(audio_b64)
            # Play each chunk immediately!
```

**Note:** Only `mimo-v2.5-tts` (built-in voices) supports true streaming. Voice clone/design return all audio at once.

---

## Voice Clone with Streaming (Workaround)

Since voice clone doesn't stream, use this pattern:

```python
# 1. Design a voice once
designed_voice = design_voice("A warm, friendly female voice")

# 2. Use it as a preset
for chunk in stream_speech("Hello!", voice=designed_voice):
    play_immediately(chunk)
```

---

## API Reference

| Model | Endpoint | Streaming | Use Case |
|-------|----------|-----------|----------|
| `mimo-v2.5-tts` | `/v1/chat/completions` | ✅ Yes | Built-in voices |
| `mimo-v2.5-tts-voicedesign` | `/v1/chat/completions` | ❌ No | Create new voices |
| `mimo-v2.5-tts-voiceclone` | `/v1/chat/completions` | ❌ No | Clone from audio |

**Base URLs:**
- Token Plan: `https://token-plan-sgp.xiaomimimo.com/v1/chat/completions`
- Direct: `https://api.xiaomimimo.com/v1/chat/completions`

**Auth:** `api-key: YOUR_KEY` or `Authorization: Bearer YOUR_KEY`

---

## Tips

1. **Use emotion tags** for natural-sounding speech
2. **Director mode** is great for multi-character dialogues
3. **Voice design** lets you create consistent brand voices
4. **Streaming** reduces perceived latency by 50%+
5. **Clone quality** depends on reference audio quality (clean, no background noise)

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| 401 Unauthorized | Check your API key is set correctly |
| 404 Not Found | Use correct base URL (Token Plan vs Direct) |
| Empty audio | Check content format (tags must be in parentheses) |
| Slow response | Use streaming mode |

---

## For Cyony (VPS Setup)

1. **Get the API key from Eddie** (same key works for both)
2. **Add to your .env file:**
   ```
   XIAOMI_API_KEY=your-key-here
   ```
3. **Test with the Python script above**

**Note:** Cyony can use MiMo TTS via the Hermes `text_to_speech` tool or directly via API calls.

---

*Last updated: July 2026*
