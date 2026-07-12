# 🎤 Speech-to-Speech Setup Guide

## For: Cyony & Tripp
## Goal: Voice-to-voice conversations via Telegram

---

## What You Need

| Component | Purpose | Status |
|-----------|---------|--------|
| **Parakeet TDT** | Speech-to-Text (ears) | Install |
| **Ollama + qwythos** | LLM (brain) | Install |
| **Chatterbox TTS** | Text-to-Speech (mouth) | Install |
| **Speech-to-Speech repo** | Pipeline orchestrator | Clone |

---

## Step 1: Clone the Speech-to-Speech Repo

```bash
cd C:\tmp
git clone https://github.com/huggingface/speech-to-speech.git
cd speech-to-speech
```

## Step 2: Install Dependencies

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install core packages
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install -e .
pip install httpx librosa soundfile numpy

# Install argon2 for credential hashing
pip install argon2-cffi
```

## Step 3: Install Parakeet STT

```bash
# Download Parakeet model (one-time)
python -c "
from speech_to_speech.STT.parakeet_tdt_handler import ParakeetTDTHandler
handler = ParakeetTDTHandler()
handler.setup(model_name='parakeet-tdt-0.6b-v2', device='cuda')
print('✅ Parakeet installed and ready!')
"
```

## Step 4: Configure Ollama

```bash
# Pull the qwythos model (or your preferred model)
ollama pull qwythos

# Verify Ollama is running
curl http://127.0.0.1:11434/api/tags
```

## Step 5: Configure Chatterbox TTS

```bash
# Verify Chatterbox is running
curl http://127.0.0.1:5555/v1/health

# If not running, start it:
# (Your Chatterbox server command here)
```

## Step 6: Test the Pipeline

```bash
cd C:\tmp\speech-to-speech

# Dry run (no mic needed)
python test_ollama_chatterbox.py --ollama-model qwythos --dry-run

# Full test (needs mic)
python test_ollama_chatterbox.py --ollama-model qwythos
```

## Step 7: Wire Up to Telegram Bot

Create a file called `voice_bot.py`:

```python
#!/usr/bin/env python3
"""Voice Bot - receives voice, processes through S2S pipeline, responds with audio."""

import os
import sys
import asyncio
import tempfile
import io
from pathlib import Path

import httpx
import numpy as np
import soundfile as sf
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwythos")
CHATTERBOX_URL = os.getenv("CHATTERBOX_URL", "http://127.0.0.1:5555")
CHATTERBOX_VOICE = os.getenv("CHATTERBOX_VOICE", "cyony")  # or "tripp"

http_client = httpx.AsyncClient(timeout=60.0)

async def call_llm(text: str) -> str:
    """Send text to Ollama and return the response."""
    url = f"{OLLAMA_URL}/v1/chat/completions"
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful AI assistant. Respond concisely."},
            {"role": "user", "content": text}
        ],
        "temperature": 0.7,
        "max_tokens": 300
    }
    resp = await http_client.post(url, json=payload)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

async def call_tts(text: str) -> bytes:
    """Send text to Chatterbox and return audio."""
    url = f"{CHATTERBOX_URL}/v1/audio/speech"
    payload = {"input": text, "voice": CHATTERBOX_VOICE, "engine": "chatterbox"}
    resp = await http_client.post(url, json=payload)
    resp.raise_for_status()
    return resp.content

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages."""
    msg = update.message
    await msg.reply_chat_action("record_voice")

    try:
        # Download voice
        voice_file = await msg.voice.get_file()
        voice_bytes = await voice_file.download_as_bytearray()

        # Save to temp file for STT
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            f.write(voice_bytes)
            temp_path = f.name

        # Transcribe using local STT (you'll need to implement this)
        transcript = await transcribe_audio(temp_path)
        os.unlink(temp_path)

        if not transcript:
            await msg.reply_text("🤔 I couldn't understand that. Try again?")
            return

        # Think with LLM
        response_text = await call_llm(transcript)

        # Send text response
        await msg.reply_text(f"💬 {response_text}")

        # Generate and send voice response
        await msg.reply_chat_action("record_voice")
        wav_audio = await call_tts(response_text)

        # Convert to OGG for Telegram
        audio, sr = sf.read(io.BytesIO(wav_audio))
        if len(audio.shape) > 1:
            audio = np.mean(audio, axis=1)

        buf = io.BytesIO()
        sf.write(buf, audio, sr, format="WAV")
        buf.seek(0)

        await msg.reply_voice(voice=buf)

    except Exception as e:
        await msg.reply_text(f"❌ Error: {str(e)}")

async def transcribe_audio(audio_path: str) -> str:
    """Transcribe audio using Parakeet STT."""
    # This is a placeholder - you'll need to implement the actual transcription
    # using the speech-to-speech repo's STT handler
    import subprocess
    cmd = [
        sys.executable, "-c",
        f"""
import sys
sys.path.insert(0, r'C:\\tmp\\speech-to-speech\\src')
from speech_to_speech.STT.parakeet_tdt_handler import ParakeetTDTHandler

handler = ParakeetTDTHandler()
handler.setup(model_name='parakeet-tdt-0.6b-v2', device='cuda')

# Load and transcribe audio
result = handler.transcribe('{audio_path}')
print(result)
"""
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.stdout.strip()

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("❌ Set TELEGRAM_BOT_TOKEN environment variable!")
        sys.exit(1)

    print(f"🎤 Starting Voice Bot...")
    print(f"   LLM: {OLLAMA_MODEL}")
    print(f"   TTS: {CHATTERBOX_VOICE}")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    print("✅ Bot is listening for voice messages...")
    app.run_polling()

if __name__ == "__main__":
    main()
```

## Step 8: Run the Bot

```bash
# Set your bot token
export TELEGRAM_BOT_TOKEN=your_token_here

# Run the bot
python voice_bot.py
```

---

## Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | (required) | Your bot token |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama server |
| `OLLAMA_MODEL` | `qwythos` | LLM model |
| `CHATTERBOX_URL` | `http://127.0.0.1:5555` | Chatterbox server |
| `CHATTERBOX_VOICE` | `cyony` | Voice preset |
| `CHATTERBOX_ENGINE` | `chatterbox` | TTS engine |

---

## Troubleshooting

**"No module named 'torch'"**
```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
```

**"CUDA out of memory"**
- Close other GPU applications
- Use a smaller model: `ollama pull qwythos:3b`

**"Chatterbox not responding"**
```bash
curl http://127.0.0.1:5555/v1/health
# If not running, start your Chatterbox server
```

**"Transcription is wrong"**
- Speak clearly into the mic
- Use a quiet environment
- Check Parakeet is loaded: look for "Parakeet" in startup logs

---

## What This Does

1. **You send a voice message** to your Telegram bot
2. **Bot downloads the audio** (OGG format)
3. **Parakeet STT** transcribes your voice to text
4. **qwythos LLM** generates a response
5. **Chatterbox TTS** speaks the response in your voice
6. **Bot sends back** a voice message with the audio

**Result:** Full voice-to-voice conversation with your AI! 🎤🔊

---

## Next Steps

1. Test with a simple voice message
2. Adjust LLM parameters (temperature, max_tokens)
3. Add MOODS integration for expressive responses
4. Deploy to VPS for always-on access

---

**Built by Echo 🛡️ | Questions? Ask Eddie!**
