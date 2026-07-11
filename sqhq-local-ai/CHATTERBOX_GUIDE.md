# Chatterbox TTS — Complete Guide for Voice Cloning + Emotion Tags
**By Resemble AI** | **MIT License** | **Research compiled July 2026**

---

## Table of Contents
1. [Latest Version & Installation](#1-latest-version--installation)
2. [Model Variants: Turbo vs Multilingual V3](#2-model-variants-turbo-vs-multilingual-v3)
3. [Voice Cloning with Reference Audio](#3-voice-cloning-with-reference-audio)
4. [Emotion / Paralinguistic Tags](#4-emotion--paralinguistic-tags)
5. [Exaggeration & CFG Weight Controls](#5-exaggeration--cfg-weight-controls)
6. [Known Issues, Failures & Fixes](#6-known-issues-failures--fixes)
7. [Serving via API (FastAPI Wrappers)](#7-serving-via-api-fastapi-wrappers)
8. [Community Forks & Improvements](#8-community-forks--improvements)
9. [Eddie's Specific Situation: RTX 4070 12GB + Cyony's 20 WAV Clips](#9-eddies-specific-situation)
10. [Quick Reference Cheatsheet](#10-quick-reference-cheatsheet)

---

## 1. Latest Version & Installation

### Current Release
- **Latest PyPI version:** `chatterbox-tts==0.1.7` (released Mar 26, 2026)
- **GitHub latest release:** `v0.1.2` (Jun 13, 2025)
- **Latest model:** Chatterbox Multilingual V3 (improved over V2)

### ⚠️ IMPORTANT: pip install IS BROKEN (as of July 2026)
The `pip install chatterbox-tts` command **fails** due to a broken dependency: `pkuseg==0.0.25` requires NumPy at build time and cannot compile on most systems without manual workarounds. See [GitHub Issue #367](https://github.com/resemble-ai/chatterbox/issues/367).

### Workaround: Install from Source (RECOMMENDED for Windows)

```bash
# 1. Use Python 3.11 (mandatory — NOT 3.12 or 3.13)
# 2. Create clean venv
py -3.11 -m venv chatterbox-env
chatterbox-env\Scripts\activate

# 3. Upgrade pip
python -m pip install --upgrade pip

# 4. Install PyTorch with CUDA 12.1 (lock versions to avoid torchvision::nms error)
pip install torch==2.5.1+cu121 torchvision==0.20.1+cu121 torchaudio==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121

# 5. Clone and install Chatterbox from source
git clone https://github.com/resemble-ai/chatterbox.git
cd chatterbox
pip install -e .

# 6. Set HF_TOKEN (required to download model weights)
$env:HF_TOKEN="hf_your_read_token_here"
```

### Alternative: Use `uv` (Faster Dependency Resolution)
```bash
git clone https://github.com/resemble-ai/chatterbox.git
cd chatterbox
uv sync
```

### Install via Chatterbox-TTS-Server (EASIEST, all-in-one)
The [devnen/Chatterbox-TTS-Server](https://github.com/devnen/Chatterbox-TTS-Server) handles all dependencies and includes a Web UI + API. It has a **Windows Portable Mode** that bundles its own Python.

```bash
git clone https://github.com/devnen/Chatterbox-TTS-Server.git
cd Chatterbox-TTS-Server
# On Windows: double-click start.bat
# It auto-detects GPU, offers installation menu, handles deps
```

### Verify Installation
```python
from chatterbox.tts import ChatterboxTTS
print("Chatterbox ready")  # Should print without error
```

---

## 2. Model Variants: Turbo vs Multilingual V3

| Feature | **Chatterbox-Turbo** | **Chatterbox-Multilingual V3** | **Original Chatterbox** |
|---------|---------------------|-------------------------------|------------------------|
| **Parameters** | 350M | 500M | 500M |
| **Languages** | English only | 23+ languages | English only |
| **Decoder Steps** | 1 step (distilled) | 10 steps (Euler) | 10 steps (Euler) |
| **VRAM Usage** | ~3-4 GB | ~5-6.5 GB | ~5-6.5 GB |
| **Latency** | ~75ms (6x real-time) | ~200-500ms | ~200-500ms |
| **Paralinguistic Tags** | ✅ `[laugh]` `[chuckle]` `[cough]` | ❌ No | ❌ No |
| **Exaggeration/CFG** | ❌ (ignores exaggeration) | ✅ Full controls | ✅ Full controls |
| **Voice Conversion** | ❌ No VC class | ✅ Has VC class (vc.py) | ✅ Has VC class (vc.py) |
| **Best For** | Low-latency agents, streaming | Best quality, multilingual, creative control | High-quality English |
| **Minimum Reference** | 5 seconds | Any length (shorter OK) | Any length |

### Which One Should You Use?

**For Cyony's voice (English, expressive, emotion-rich):**
- **For best quality + emotion control → Use Original Chatterbox (0.5B English)**
  - Full exaggeration and CFG tuning
  - Works well with 5-15s reference clips
- **For fastest generation → Use Chatterbox-Turbo**
  - Paralinguistic tags work natively
  - Much lower VRAM, great for real-time
  - But: NO exaggeration/emotion knob — emotion is conveyed via `[laugh]` `[chuckle]` `[cough]` tags only
- **For multilingual (not needed here) → Multilingual V3**

### Why Eddie's Previous Attempt May Have Failed
- If you used `pip install chatterbox-tts` directly — it was broken
- If you used the wrong Python version (3.12+) — dependency conflicts
- If you didn't set `HF_TOKEN` — model downloads silently fail
- If you used Turbo but expected exaggeration controls — Turbo ignores exaggeration
- If you used very short reference clips (<5s for Turbo) — it crashes with "Audio prompt must be longer than 5 seconds"

---

## 3. Voice Cloning with Reference Audio

### How Zero-Shot Cloning Works
Chatterbox analyzes your reference clip to extract:
- **Speaker identity** (voice embeddings)
- **Speech patterns** (tokenized into speech tokens)
- **Prosody and style** (applied as conditioning to new text)

No training, no fine-tuning needed.

### Best Practices for Reference Audio

#### 🎯 Duration Guidelines
| Model | Minimum | Recommended | Max Used (code constant) |
|-------|---------|-------------|--------------------------|
| Turbo | **5 seconds** (hard requirement) | 6-15 seconds | First 10s at 22050Hz |
| Standard/Multilingual | Shorter OK | **6-15 seconds** | First 10s at 22050Hz |

#### 🎵 Audio Quality
- **Format:** WAV is ideal, but MP3/FLAC/OGG also work (anything librosa reads)
- **Sample rate:** 24kHz minimum (native model SR)
- **Bit depth:** 16-bit or 24-bit
- **Noise floor:** Clean, minimal background noise
- **Single speaker only** — no overlapping voices
- **Complete sentences** with natural pacing
- **No silence padding** at start/end (trim to ~200ms silence max)

#### 🎭 Content Matters
- **Match the target speaking style.** If you want energetic output, use an energetic reference clip.
- **Variety in your 20 clips is an asset.** You can:
  - Use the most natural-sounding single clip (10-15s)
  - Concatenate multiple short clips into one longer WAV (see below)

#### 🔧 Preparing Cyony's 20 WAV Clips
Since you have 20 clips (5-10s each, various emotions):

**Option A: Pick the best single clip (RECOMMENDED)**
1. Listen to all 20 clips
2. Pick the one that sounds clearest, most natural, and most representative
3. Make sure it's at least 6 seconds
4. Trim silence, normalize volume (to -3dB to -1dB peak)
5. Use that as your reference

**Option B: Concatenate the best clips**
Use FFmpeg to merge multiple clips into one longer reference:
```bash
# Create a file list
(for %i in (clip1.wav clip2.wav clip3.wav) do @echo file '%i') > filelist.txt
# Concatenate
ffmpeg -f concat -safe 0 -i filelist.txt -c copy combined_ref.wav
# Trim to ~15s
ffmpeg -i combined_ref.wav -t 15 trimmed_ref.wav
```

**Option C: Pre-process with noise removal**
```bash
# Remove background noise with FFmpeg's anlmdn filter
ffmpeg -i input.wav -af anlmdn=0.0001 clean_ref.wav
```

### Code: Voice Cloning

**Original (English) model — BEST for quality:**
```python
import torchaudio as ta
from chatterbox.tts import ChatterboxTTS

model = ChatterboxTTS.from_pretrained(device="cuda")

text = "This is Cyony's voice cloned with Chatterbox."
wav = model.generate(text, audio_prompt_path="cyony_best_clip.wav")
ta.save("output.wav", wav, model.sr)
```

**Turbo model — FASTEST:**
```python
from chatterbox.tts_turbo import ChatterboxTurboTTS

model = ChatterboxTurboTTS.from_pretrained(device="cuda")

text = "Hey there [chuckle], this is Cyony's voice using Turbo."
wav = model.generate(text, audio_prompt_path="cyony_best_clip.wav")
ta.save("output_turbo.wav", wav, model.sr)
```

### Pre-computing Voice Conditionals (Efficient for Batch)
```python
# Process reference once, generate many sentences
model.prepare_conditionals("cyony_best_clip.wav", exaggeration=0.5)

for line in lines:
    wav = model.generate(line)
    ta.save(f"output_{i}.wav", wav, model.sr)
```

---

## 4. Emotion / Paralinguistic Tags

### CRITICAL: Tags Only Work on Turbo Model
- **Chatterbox-Turbo:** ✅ `[laugh]` `[chuckle]` `[cough]` — processed natively
- **Original Chatterbox:** ❌ Tags are read aloud as literal text
- **Multilingual V3:** ❌ Same — tags become spoken words

### Available Tags (Turbo Only)

| Tag | Sound | Best For |
|-----|-------|----------|
| `[laugh]` | Full, natural laughter | Genuine amusement, jokes, punchlines |
| `[chuckle]` | Soft, subdued chuckle | Light humor, friendly conversation, professional warmth |
| `[cough]` | Natural cough | Realism, interruptions, character dialogue |

### Tag Formatting (MUST BE EXACT)
- ✅ **Correct:** `[laugh]`, `[chuckle]`, `[cough]` (lowercase, square brackets)
- ❌ **Incorrect:** `[Laugh]` (capitalized), `(chuckle)` (parentheses), `[CHUCKLE]` (all caps)
- Place tags **anywhere in text** where the sound makes conversational sense

### Examples

```python
# Mid-sentence chuckle
text = "Hi there, Sarah here calling you back [chuckle], have you got a minute?"

# End-of-sentence laugh
text = "And then the customer said they'd been waiting three years! [laugh]"

# Natural cough interruption
text = "Sorry about that [cough]. Let me get you those account details."

# Multiple tags in one sentence
text = "Oh that's hilarious! [chuckle] Um anyway [cough], where were we?"
```

### Best Practices
- **Use sparingly** — too many tags sound unnatural
- **Match emotional tone** — don't put `[laugh]` in a serious statement
- **Prefer `[chuckle]`** for professional/friendly tones
- **Test different placements** for naturalness
- **Don't place tags in the middle of words**

### Emotion via Exaggeration (Original/Multilingual Models Only)
Since Original Chatterbox doesn't support `[laugh]` tags, you control emotion through **exaggeration** and **cfg_weight**:

```python
# Calm, neutral
wav = model.generate(text, exaggeration=0.3, cfg_weight=0.6)

# Expressive, lively
wav = model.generate(text, exaggeration=0.7, cfg_weight=0.3)

# Dramatic, intense
wav = model.generate(text, exaggeration=1.0, cfg_weight=0.2)
```

---

## 5. Exaggeration & CFG Weight Controls

### Parameters (Original & Multilingual Models)

| Parameter | Range | Default | Effect |
|-----------|-------|---------|--------|
| `exaggeration` | 0.0 - 1.0+ | 0.5 | Emotion intensity. Higher = more expressive/dramatic. Lower = flat/monotone |
| `cfg_weight` | 0.0 - 1.0 | 0.5 | Speech pace & adherence. Lower = faster/more dynamic. Higher = slower/more literal |
| `temperature` | 0.05 - 5.0 | 0.8 | Voice randomness. Lower = more consistent. Higher = more varied |

### Tuning Guidelines
- **Default settings** (exaggeration=0.5, cfg_weight=0.5) work well for most prompts
- **Fast reference speaker:** Lower cfg_weight to ~0.3
- **Expressive/dramatic:** Lower cfg_weight (~0.3) + higher exaggeration (≥0.7)
- **Cranking exaggeration?** Drop cfg_weight to compensate (avoids rushed cadence)
- **Language transfer:** Set `cfg_weight=0` to avoid accent leakage

---

## 6. Known Issues, Failures & Fixes

### Issue 1: "pip install chatterbox-tts" FAILS
- **Error:** `pkuseg==0.0.25` build failure, `No module named 'numpy'`
- **Fix:** Install from source (`git clone + pip install -e .`) or use `devnen/Chatterbox-TTS-Server`
- **Status:** PR #376 submitted but Issue #367 still open (as of May 2026)

### Issue 2: Sequential Short Text Generation Crash
- **Error:** `srcIndex < srcSelectDimSize` failed (CUDA tensor indexing error)
- **Cause:** Very short text (<25 chars) causes internal state contamination between generations
- **Fix:** Pad short text to 30+ characters with **meaningful filler text**, not spaces/periods
  - ✅ Works: `"word is a word is a world"`
  - ❌ Still crashes: `"   ....   "` (padding alone doesn't work)
- **Workaround:** Use `",,{seg} hmm {seg},,"` pattern with commas and natural hesitations
- **Status:** Unfixed in official repo

### Issue 3: "torchvision::nms does not exist"
- **Cause:** Mismatched PyTorch/TorchVision versions
- **Fix:** Uninstall all three and reinstall matched versions:
  ```bash
  pip uninstall torch torchvision torchaudio -y
  pip install torch==2.5.1+cu121 torchvision==0.20.1+cu121 torchaudio==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121
  ```

### Issue 4: Randomly Very Slow Generation
- **Error:** Same sentence takes 15s normally, 200+ seconds randomly
- **Cause:** Unknown — may be CUDA memory fragmentation or cache buildup
- **Workarounds:**
  - Call `torch.cuda.empty_cache()` between generations
  - Restart Python process
  - Set `TTS_BF16=on` if using devnen's server (40% throughput improvement)
  - Use `rsxdalv/chatterbox` fork (`fast` branch) with torch.compile + bfloat16

### Issue 5: "Audio prompt must be longer than 5 seconds" (Turbo)
- **Fix:** Ensure reference clip is ≥5 seconds. Check with:
  ```python
  import librosa
  wav, sr = librosa.load("clip.wav", sr=None)
  print(f"Duration: {len(wav)/sr:.2f}s")
  ```

### Issue 6: Poor Voice Similarity
- **Fixes:**
  1. Use higher quality audio (reduce background noise)
  2. Try longer clip (10-15 seconds)
  3. Adjust `cfg_weight` lower (try 0.3)
  4. Match speaking style to target text
  5. Normalize volume to consistent level

### Issue 7: HF_TOKEN / Offline Issues
- **Error:** `MaxRetryError` when loading model
- **Fix:** Set `HF_TOKEN` env var OR pre-download models via `huggingface-cli login`
- **Offline use:** Set `HF_HUB_OFFLINE=1` after models are cached

### Issue 8: VRAM Management on RTX 4070 12GB
- Original/Multilingual: ~5-6.5 GB VRAM — should work fine
- Turbo: ~3-4 GB VRAM
- **If running out of VRAM:**
  - Use `torch.cuda.empty_cache()` between generations
  - Use Turbo model (lower VRAM)
  - Reduce batch sizes
  - Use bfloat16 if available

---

## 7. Serving via API (FastAPI Wrappers)

### Option 1: travisvn/chatterbox-tts-api ⭐ (623 stars)
**Best for:** OpenAI-compatible API, clean FastAPI implementation

```bash
git clone https://github.com/travisvn/chatterbox-tts-api.git
cd chatterbox-tts-api
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 4123
```

**Endpoints:**
- `POST /v1/audio/speech` — OpenAI-compatible TTS
- `POST /v1/audio/speech/stream` — Streaming audio
- `GET /voices` — List stored voices
- `POST /voices` — Upload voice to library
- `GET /docs` — Interactive Swagger docs

**API call example:**
```bash
curl -X POST http://localhost:4123/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{
    "input": "Hello from Chatterbox!",
    "voice": "cyony",
    "exaggeration": 0.5,
    "cfg_weight": 0.5
  }' \
  --output speech.wav
```

### Option 2: devnen/Chatterbox-TTS-Server ⭐ (1,300 stars)
**Best for:** Full Web UI, Windows Portable Mode, all-in-one

```bash
git clone https://github.com/devnen/Chatterbox-TTS-Server.git
cd Chatterbox-TTS-Server
# Windows: run start.bat
```

**Features:**
- Built-in Web UI at `http://localhost:8004`
- OpenAI-compatible API endpoints
- Hot-swap between Original, Multilingual, Turbo
- Predefined voices folder
- Large text processing (audiobook chunking)
- Streaming support
- Voice conditioning cache (avoids re-encoding)
- **Windows Portable Mode** — self-contained, no system Python needed

### Option 3: Self-Host with FastAPI (Minimal)
Here's a minimal FastAPI server if you want to build your own:

```python
# server.py
from fastapi import FastAPI
from pydantic import BaseModel
import torchaudio as ta
import io
from chatterbox.tts_turbo import ChatterboxTurboTTS
from fastapi.responses import Response

app = FastAPI()
model = ChatterboxTurboTTS.from_pretrained(device="cuda")

class TTSRequest(BaseModel):
    input: str
    voice: str = None  # path to reference WAV

@app.post("/v1/audio/speech")
async def tts(req: TTSRequest):
    wav = model.generate(
        req.input,
        audio_prompt_path=req.voice if req.voice else None
    )
    buffer = io.BytesIO()
    ta.save(buffer, wav, model.sr, format="wav")
    return Response(content=buffer.getvalue(), media_type="audio/wav")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## 8. Community Forks & Improvements

### 🏆 rsxdalv/chatterbox (164 stars) — SPEED OPTIMIZATION
**Branch:** `fast` | **GitHub:** https://github.com/rsxdalv/chatterbox

**What it does:**
- Torch.compile with cudagraphs backend
- bfloat16 support for T3 model (2-3x speedup on RTX 3090: ~39 it/s → ~108 it/s)
- Removes unnecessary CPU-GPU sync
- StaticCache for attention
- Aggressive caching of conditionals
- Custom modeling_llama copy without optimization blockers

**Install:**
```bash
pip install git+https://github.com/rsxdalv/chatterbox.git@fast
```

### 🏆 devnen/Chatterbox-TTS-Server (1,300 stars) — FULL SERVER
**GitHub:** https://github.com/devnen/Chatterbox-TTS-Server

**What it adds:**
- Windows Portable Mode (no system Python needed)
- Multi-engine hot-swapping
- Paralinguistic tag support in Web UI
- Large text processing (50-500 char chunks)
- Voice cloning via file upload
- Streaming endpoints
- AMD ROCm / Apple Silicon support
- SSL/HTTPS support

### 🏆 petermg/Chatterbox-TTS-Extended (570 stars) — POWER USER
**GitHub:** https://github.com/petermg/Chatterbox-TTS-Extended

**What it adds:**
- Text file input (multi-file drag & drop)
- Voice Conversion (VC) tab
- Whisper validation (transcribes output, checks accuracy)
- pyrnnoise denoising (removes artifacts)
- FFmpeg normalization (EBU R128 / Peak)
- Auto-Editor silence trimming
- Batch processing with parallel workers
- Candidates per chunk + retry on failure
- MP3/FLAC export

### 🏆 travisvn/chatterbox-tts-api (623 stars) — OPENAI API
**GitHub:** https://github.com/travisvn/chatterbox-tts-api

**What it adds:**
- OpenAI-compatible TTS endpoints
- Voice library with language metadata
- Streaming (raw audio + SSE)
- Progress tracking, statistics, request history
- Memory management (auto CUDA cache clearing)
- Docker-ready with multiple compose files

### 🏆 alexandrainst/coral_chatterbox — FINETUNING
**GitHub:** https://github.com/alexandrainst/coral_chatterbox (archived)

**What it adds:**
- Finetuning framework for T3 language model
- Preprocessing scripts for datasets
- Hyperparameter search (grid/random/optuna)
- Convert checkpoints for deployment

### Other Notable Forks
- **wobba/ComfyUI-ChatterBox-Turbo** — ComfyUI node integration
- **cstr/chatterbox-GGUF** — GGUF quantized version (less accurate, faster on CPU)
- **randombk/chatterbox-vllm** — vLLM port (WIP)

---

## 9. Eddie's Specific Situation

### Hardware: RTX 4070 12GB VRAM, Windows 10
- ✅ **Plenty of VRAM** for any Chatterbox model (Turbo: ~3-4GB, Original: ~5-6.5GB)
- ✅ **CUDA 12.1+ support** — install PyTorch 2.5.1+cu121
- ⚠️ Windows requires proper Python setup (3.11, not 3.12+)

### Assets: 20 WAV Clips of Cyony's Voice (5-10s, Various Emotions)
- ✅ **Ideal setup** — you have more than enough material
- ✅ **Multiple emotions** means you can pick the clip that best matches your target output

### Why Previous Attempt Failed (Most Likely Causes)

| Likely Issue | Why It Failed | Fix |
|-------------|---------------|-----|
| `pip install chatterbox-tts` broke | pkuseg dependency crash | Install from source or use devnen's server |
| Wrong Python version (3.12/3.13) | Dependency conflicts | Use Python **3.11 exclusively** |
| No HF_TOKEN set | Model download silently fails | Set `$env:HF_TOKEN` or `huggingface-cli login` |
| PyTorch/TorchVision mismatch | torchvision::nms error | Lock all three to matched CUDA 12.1 versions |
| Used Turbo but expected emotion knobs | Turbo ignores exaggeration | Use **Original Chatterbox** for full emotion control, OR use Turbo with `[chuckle]` tags |
| Reference clip too short (<5s for Turbo) | "Must be longer than 5 seconds" | Ensure reference ≥5s, or use Original model |
| Clip with background noise | Poor voice similarity | Use cleanest clip, pre-process with noise removal |
| Generated very short text | Sequential crash (Issue #201) | Pad texts to 30+ chars with meaningful filler |

### Recommended Setup for Cyony's Voice

**Step 1: Install devnen's server (easiest)**
```bash
git clone https://github.com/devnen/Chatterbox-TTS-Server.git
cd Chatterbox-TTS-Server
start.bat
# Choose NVIDIA option
```

**Step 2: Prepare reference clip**
```bash
# Pick the best 10-15s clip of Cyony
# Trim silence, normalize volume
ffmpeg -i cyony_best.wav -af "silenceremove=start_periods=1:start_silence=0.1:start_threshold=-50dB, loudnorm=I=-16:LRA=11:TP=-1.5" cyony_clean.wav
```

**Step 3: Test with Original model first**
```python
from chatterbox.tts import ChatterboxTTS
model = ChatterboxTTS.from_pretrained(device="cuda")
wav = model.generate(
    "This is Cyony's voice. I'm testing the voice cloning quality.",
    audio_prompt_path="cyony_clean.wav",
    exaggeration=0.5,
    cfg_weight=0.5
)
```

**Step 4: Then try Turbo for speed**
```python
from chatterbox.tts_turbo import ChatterboxTurboTTS
model = ChatterboxTurboTTS.from_pretrained(device="cuda")
wav = model.generate(
    "Hey there [chuckle], this is Cyony's voice using Turbo mode!",
    audio_prompt_path="cyony_clean.wav"
)
```

### Troubleshooting Checklist for Eddie
If it doesn't work, check these in order:
1. ✅ Is Python 3.11? (`python --version`)
2. ✅ Is HF_TOKEN set? (`echo $env:HF_TOKEN`)
3. ✅ Are PyTorch versions matched? (`pip list | grep torch`)
4. ✅ Is CUDA available? (`python -c "import torch; print(torch.cuda.is_available())"`)
5. ✅ Is reference audio ≥5s for Turbo? (librosa check)
6. ✅ Is reference audio clean, single speaker, no noise?
7. ✅ Is text ≥30 characters?

---

## 10. Quick Reference Cheatsheet

### Install
```bash
git clone https://github.com/resemble-ai/chatterbox.git && cd chatterbox
py -3.11 -m venv venv && venv\Scripts\activate
pip install torch==2.5.1+cu121 torchvision==0.20.1+cu121 torchaudio==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121
pip install -e .
$env:HF_TOKEN="hf_your_token_here"
```

### Generate (Original — best quality + emotion)
```python
from chatterbox.tts import ChatterboxTTS
import torchaudio as ta
model = ChatterboxTTS.from_pretrained(device="cuda")
wav = model.generate("Your text here.", audio_prompt_path="ref.wav", exaggeration=0.5, cfg_weight=0.5)
ta.save("out.wav", wav, model.sr)
```

### Generate (Turbo — fastest + paralinguistic tags)
```python
from chatterbox.tts_turbo import ChatterboxTurboTTS
model = ChatterboxTurboTTS.from_pretrained(device="cuda")
wav = model.generate("Text with [chuckle] tags.", audio_prompt_path="ref.wav")
```

### Reference Audio Requirements
- **Turbo:** ≥5 seconds, clean, single speaker
- **Original:** Any length, 6-15s recommended
- **Format:** WAV preferred, 24kHz+, no background noise

### Emotion Control
| Model | Method |
|-------|--------|
| **Original** | `exaggeration` (0.0-1.0+) + `cfg_weight` (0.0-1.0) |
| **Turbo** | `[laugh]` `[chuckle]` `[cough]` tags only |
| **Multilingual V3** | `exaggeration` + `cfg_weight` |

### Best API Server
```bash
# travisvn's API (OpenAI-compatible)
git clone https://github.com/travisvn/chatterbox-tts-api.git
cd chatterbox-tts-api && uv sync && uvicorn app.main:app --host 0.0.0.0 --port 4123

# devnen's Server (Web UI + Windows Portable)
git clone https://github.com/devnen/Chatterbox-TTS-Server.git
cd Chatterbox-TTS-Server && start.bat
```

### VRAM Usage on RTX 4070 12GB
- **Turbo:** ~3-4 GB ✅ Comfortable
- **Original:** ~5-6.5 GB ✅ Comfortable
- **Multilingual V3:** ~5-6.5 GB ✅ Comfortable

---

## Links & Resources

- **GitHub:** https://github.com/resemble-ai/chatterbox
- **PyPI:** https://pypi.org/project/chatterbox-tts/
- **HF Models:** https://huggingface.co/ResembleAI
- **Demo Page:** https://resemble-ai.github.io/chatterbox_demopage/
- **Discord:** https://discord.gg/rJq9cRJBJ6
- **Podonos Evaluation:** https://podonos.com/resembleai/chatterbox

**Key Community Forks:**
- https://github.com/devnen/Chatterbox-TTS-Server — Full server + Windows portable ⭐
- https://github.com/travisvn/chatterbox-tts-api — OpenAI-compatible API ⭐
- https://github.com/petermg/Chatterbox-TTS-Extended — Power user features ⭐
- https://github.com/rsxdalv/chatterbox — Speed optimizations (fast branch) ⭐
