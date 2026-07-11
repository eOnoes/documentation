# Orpheus Voice Hub — Implementation Plan (v2 — Post-Audit)

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build a web interface for the Orpheus TTS + Brain pipeline with three modes: Direct TTS, Brain + TTS, and Voice Clone.

**Architecture:** Thin FastAPI layer that orchestrates existing services (Orpheus Voice Server on 8081, Ollama on 11434). HTMX frontend for dynamic updates. No heavy frameworks.

**Tech Stack:** Python 3.11, FastAPI, HTMX, Tailwind CSS (CDN), uvicorn, httpx

**Port:** 8082 (configurable via `$HUB_PORT` env var)

---

### Task 1: Create project structure

**Objective:** Set up directories, dependencies, and minimal FastAPI app with lifespan

**Files:**
- Create: `orpheus_voice_hub/app.py`
- Create: `orpheus_voice_hub/static/index.html`
- Create: `orpheus_voice_hub/static/style.css`
- Create: `orpheus_voice_hub/requirements.txt`

**Step 1: Create directories**

```bash
mkdir -p orpheus_voice_hub/static
```

**Step 2: Create requirements.txt**

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
httpx>=0.25.0
python-multipart>=0.0.6
aiofiles>=23.0.0
```

**Step 3: Create app.py with lifespan + shared httpx client**

```python
import os
import time
import uuid
import html
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, File, Form, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Config
HUB_PORT = int(os.getenv("HUB_PORT", "8082"))
ORPHEUS_URL = os.getenv("ORPHEUS_URL", "http://localhost:8081")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "huihui_ai/llama3.2-abliterate:3b")
AUDIO_DIR = Path("static/audio")
MAX_UPLOAD_MB = 10

# Valid values for validation
VALID_VOICES = ["tara", "leah", "jess", "leo", "dan", "mia", "zac", "zoe"]
VALID_EMOTIONS = ["none", "happy", "sad", "angry", "fearful", "disgusted", "surprised", "calm", "laughing", "cheerful"]

# Shared httpx client (connection pooling)
http_client: httpx.AsyncClient = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    http_client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    yield
    await http_client.aclose()

app = FastAPI(title="Orpheus Voice Hub", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files + templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="static")

# --- Helper Functions ---

def validate_inputs(text: str, voice: str = None, emotion: str = None) -> str | None:
    """Return error message if validation fails, else None."""
    if not text or not text.strip():
        return "Text cannot be empty."
    if voice and voice not in VALID_VOICES:
        return f"Invalid voice: {voice}"
    if emotion and emotion not in VALID_EMOTIONS:
        return f"Invalid emotion: {emotion}"
    return None

async def cleanup_old_audio(max_age_seconds: int = 3600):
    """Remove audio files older than max_age_seconds."""
    now = time.time()
    for f in AUDIO_DIR.glob("*.mp3"):
        if now - f.stat().st_mtime > max_age_seconds:
            f.unlink(missing_ok=True)

# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health():
    """Health check that probes upstream services."""
    status = {"hub": "ok", "orpheus": "unknown", "ollama": "unknown"}
    try:
        resp = await http_client.get(f"{ORPHEUS_URL}/health", timeout=5.0)
        status["orpheus"] = "ok" if resp.status_code == 200 else f"error:{resp.status_code}"
    except Exception:
        status["orpheus"] = "unreachable"
    try:
        resp = await http_client.get(f"{OLLAMA_URL}/api/tags", timeout=5.0)
        status["ollama"] = "ok" if resp.status_code == 200 else f"error:{resp.status_code}"
    except Exception:
        status["ollama"] = "unreachable"
    return status

# --- Task 1 ends here ---
```

**Step 4: Create minimal index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Orpheus Voice Hub</title>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body class="bg-gray-900 text-white min-h-screen">
    <div class="container mx-auto px-4 py-8 max-w-3xl">
        <h1 class="text-3xl font-bold mb-8 text-center">🎤 Orpheus Voice Hub</h1>
        <div class="flex mb-6 border-b border-gray-700">
            <button hx-get="/mode/direct" hx-target="#mode-content" hx-swap="innerHTML" class="tab-btn px-6 py-3 font-medium" onclick="setActiveTab(this)">Direct TTS</button>
            <button hx-get="/mode/brain" hx-target="#mode-content" hx-swap="innerHTML" class="tab-btn px-6 py-3 font-medium" onclick="setActiveTab(this)">Brain + TTS</button>
            <button hx-get="/mode/clone" hx-target="#mode-content" hx-swap="innerHTML" class="tab-btn px-6 py-3 font-medium" onclick="setActiveTab(this)">Voice Clone</button>
        </div>
        <div id="mode-content" class="bg-gray-800 rounded-lg p-6">
            <p class="text-gray-400">Click a tab to get started.</p>
        </div>
    </div>
    <script>
        function setActiveTab(btn) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        }
    </script>
</body>
</html>
```

**Step 5: Create style.css**

```css
.tab-btn { @apply text-gray-400 hover:text-white border-b-2 border-transparent transition-colors; }
.tab-btn.active { @apply text-white border-blue-500; }
.htmx-indicator { display: none; }
.htmx-request .htmx-indicator { display: inline; }
.htmx-request.htmx-indicator { display: inline; }
```

**Step 6: Verify it runs**

```bash
cd orpheus_voice_hub
python -m uvicorn app:app --host 0.0.0.0 --port 8082
curl http://localhost:8082/health
# Expected: {"hub":"ok","orpheus":"ok","ollama":"ok"}
```

---

### Task 2: Direct TTS mode

**Objective:** Text input → voice/mood selection → generate audio with streaming response

**Files:**
- Modify: `orpheus_voice_hub/app.py`

**Step 1: Add route for Direct TTS mode (XSS-safe via Jinja2)**

```python
@app.get("/mode/direct", response_class=HTMLResponse)
async def mode_direct(request: Request):
    return templates.TemplateResponse("direct_tts.html", {"request": request, "voices": VALID_VOICES, "emotions": VALID_EMOTIONS})
```

**Step 2: Create direct_tts.html template (autoescaped)**

```html
<form hx-post="/generate/direct" hx-target="#audio-section" hx-swap="innerHTML">
    <div class="mb-4">
        <label class="block text-sm font-medium mb-2">Text</label>
        <textarea name="text" rows="3" class="w-full bg-gray-700 rounded p-3 text-white" placeholder="Type something to say..."></textarea>
    </div>
    <div class="grid grid-cols-2 gap-4 mb-4">
        <div>
            <label class="block text-sm font-medium mb-2">Voice</label>
            <select name="voice" class="w-full bg-gray-700 rounded p-3">
                {% for v in voices %}
                <option value="{{ v }}">{{ v|capitalize }}</option>
                {% endfor %}
            </select>
        </div>
        <div>
            <label class="block text-sm font-medium mb-2">Mood</label>
            <select name="emotion" class="w-full bg-gray-700 rounded p-3">
                {% for e in emotions %}
                <option value="{{ e }}">{{ e|capitalize }}</option>
                {% endfor %}
            </select>
        </div>
    </div>
    <button type="submit" class="w-full bg-blue-600 hover:bg-blue-700 rounded p-3 font-medium">Generate Audio</button>
</form>
```

**Step 3: Add generation endpoint with error handling + validation**

```python
@app.post("/generate/direct", response_class=HTMLResponse)
async def generate_direct(request: Request, text: str = Form(...), voice: str = Form(...), emotion: str = Form(...)):
    err = validate_inputs(text, voice, emotion)
    if err:
        return HTMLResponse(f'<div class="text-red-400 p-4">{html.escape(err)}</div>', status_code=400)

    try:
        t0 = time.time()
        resp = await http_client.post(
            f"{ORPHEUS_URL}/v1/tts",
            json={"text": text.strip(), "voice": voice, "emotion": emotion, "format": "mp3"},
        )
        resp.raise_for_status()
        elapsed = time.time() - t0

        audio_id = uuid.uuid4().hex[:12]
        audio_path = AUDIO_DIR / f"{audio_id}.mp3"
        audio_path.write_bytes(resp.content)

        return templates.TemplateResponse("audio_result.html", {
            "request": request,
            "audio_path": f"/static/audio/{audio_id}.mp3",
            "voice": voice,
            "emotion": emotion,
            "elapsed": f"{elapsed:.1f}",
            "size_kb": len(resp.content) // 1024,
        })
    except httpx.HTTPError as e:
        return HTMLResponse(f'<div class="text-red-400 p-4">TTS service error: {html.escape(str(e))}</div>', status_code=502)
    except Exception as e:
        return HTMLResponse(f'<div class="text-red-400 p-4">Unexpected error: {html.escape(str(e))}</div>', status_code=500)
```

**Step 4: Create audio_result.html template**

```html
<div id="audio-section" class="bg-gray-800 rounded-lg p-6">
    <h3 class="text-lg font-semibold mb-4">🎧 Output</h3>
    <audio controls class="w-full">
        <source src="{{ audio_path }}" type="audio/mpeg">
    </audio>
    <div class="mt-3 text-sm text-gray-400">
        Voice: {{ voice }} | Mood: {{ emotion }} | Time: {{ elapsed }}s | Size: {{ size_kb }}KB
    </div>
</div>
```

---

### Task 3: Brain + TTS mode

**Objective:** Prompt → Ollama generates text → TTS generates audio

**Files:**
- Modify: `orpheus_voice_hub/app.py`
- Create: `orpheus_voice_hub/static/brain_tts.html`

**Step 1: Add route for Brain mode**

```python
@app.get("/mode/brain", response_class=HTMLResponse)
async def mode_brain(request: Request):
    return templates.TemplateResponse("brain_tts.html", {"request": request, "voices": VALID_VOICES, "emotions": VALID_EMOTIONS})
```

**Step 2: Add Brain generation endpoint with text truncation**

```python
MAX_BRAIN_CHARS = 1000

@app.post("/generate/brain", response_class=HTMLResponse)
async def generate_brain(request: Request, prompt: str = Form(...), voice: str = Form(...), emotion: str = Form(...)):
    err = validate_inputs(prompt, voice, emotion)
    if err:
        return HTMLResponse(f'<div class="text-red-400 p-4">{html.escape(err)}</div>', status_code=400)

    try:
        t0 = time.time()

        # Step 1: Brain generates text
        brain_resp = await http_client.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt.strip(), "stream": False},
            timeout=60.0,
        )
        brain_resp.raise_for_status()
        brain_text = brain_resp.json()["response"]

        # Truncate for TTS
        if len(brain_text) > MAX_BRAIN_CHARS:
            brain_text = brain_text[:MAX_BRAIN_CHARS].rsplit(" ", 1)[0] + "..."

        # Step 2: TTS generates audio
        tts_resp = await http_client.post(
            f"{ORPHEUS_URL}/v1/tts",
            json={"text": brain_text, "voice": voice, "emotion": emotion, "format": "mp3"},
        )
        tts_resp.raise_for_status()
        elapsed = time.time() - t0

        audio_id = uuid.uuid4().hex[:12]
        audio_path = AUDIO_DIR / f"{audio_id}.mp3"
        audio_path.write_bytes(tts_resp.content)

        return templates.TemplateResponse("audio_result_brain.html", {
            "request": request,
            "audio_path": f"/static/audio/{audio_id}.mp3",
            "brain_text": brain_text,
            "voice": voice,
            "emotion": emotion,
            "elapsed": f"{elapsed:.1f}",
            "size_kb": len(tts_resp.content) // 1024,
        })
    except httpx.HTTPError as e:
        return HTMLResponse(f'<div class="text-red-400 p-4">Service error: {html.escape(str(e))}</div>', status_code=502)
    except Exception as e:
        return HTMLResponse(f'<div class="text-red-400 p-4">Unexpected error: {html.escape(str(e))}</div>', status_code=500)
```

---

### Task 4: Voice Clone mode

**Objective:** Upload reference audio + text → generate cloned voice audio

**CRITICAL FIX:** Clone endpoint is `/v1/clone` (not `/v1/voice/clone`), requires JSON with base64 audio + `transcript` field.

**Files:**
- Modify: `orpheus_voice_hub/app.py`
- Create: `orpheus_voice_hub/static/clone_tts.html`

**Step 1: Add route for Clone mode (with transcript field)**

```python
@app.get("/mode/clone", response_class=HTMLResponse)
async def mode_clone(request: Request):
    return templates.TemplateResponse("clone_tts.html", {"request": request, "max_upload_mb": MAX_UPLOAD_MB})
```

**Step 2: Add Clone generation endpoint (JSON + base64, not multipart)**

```python
import base64

@app.post("/generate/clone", response_class=HTMLResponse)
async def generate_clone(
    request: Request,
    text: str = Form(...),
    transcript: str = Form(...),
    reference_audio: UploadFile = File(...),
):
    err = validate_inputs(text)
    if err:
        return HTMLResponse(f'<div class="text-red-400 p-4">{html.escape(err)}</div>', status_code=400)

    if not transcript or not transcript.strip():
        return HTMLResponse('<div class="text-red-400 p-4">Transcript of reference audio is required.</div>', status_code=400)

    # Validate file size
    content = await reference_audio.read()
    if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
        return HTMLResponse(f'<div class="text-red-400 p-4">File too large. Max {MAX_UPLOAD_MB}MB.</div>', status_code=400)

    try:
        t0 = time.time()

        # Base64 encode the audio
        audio_b64 = base64.b64encode(content).decode("utf-8")

        # Send as JSON (matching server's expected format)
        resp = await http_client.post(
            f"{ORPHEUS_URL}/v1/clone",
            json={
                "text": text.strip(),
                "reference_audio_b64": audio_b64,
                "transcript": transcript.strip(),
                "format": "mp3",
            },
        )
        resp.raise_for_status()
        elapsed = time.time() - t0

        audio_id = uuid.uuid4().hex[:12]
        audio_path = AUDIO_DIR / f"{audio_id}.mp3"
        audio_path.write_bytes(resp.content)

        return templates.TemplateResponse("audio_result.html", {
            "request": request,
            "audio_path": f"/static/audio/{audio_id}.mp3",
            "voice": "clone",
            "emotion": "none",
            "elapsed": f"{elapsed:.1f}",
            "size_kb": len(resp.content) // 1024,
        })
    except httpx.HTTPError as e:
        return HTMLResponse(f'<div class="text-red-400 p-4">Clone service error: {html.escape(str(e))}</div>', status_code=502)
    except Exception as e:
        return HTMLResponse(f'<div class="text-red-400 p-4">Unexpected error: {html.escape(str(e))}</div>', status_code=500)
```

**Step 3: Create clone_tts.html (with transcript field)**

```html
<form hx-post="/generate/clone" hx-target="#mode-content" hx-swap="innerHTML" enctype="multipart/form-data">
    <div class="mb-4">
        <label class="block text-sm font-medium mb-2">Reference Audio (WAV, ≤30s, max {{ max_upload_mb }}MB)</label>
        <input type="file" name="reference_audio" accept=".wav" required class="w-full bg-gray-700 rounded p-3">
    </div>
    <div class="mb-4">
        <label class="block text-sm font-medium mb-2">Transcript (what the reference audio says)</label>
        <textarea name="transcript" rows="2" class="w-full bg-gray-700 rounded p-3 text-white" placeholder="Type what the reference audio says..."></textarea>
    </div>
    <div class="mb-4">
        <label class="block text-sm font-medium mb-2">Text (what the cloned voice should say)</label>
        <textarea name="text" rows="3" class="w-full bg-gray-700 rounded p-3 text-white" placeholder="Type something for the cloned voice to say..."></textarea>
    </div>
    <button type="submit" class="w-full bg-green-600 hover:bg-green-700 rounded p-3 font-medium">🎤 Clone & Speak</button>
</form>
```

---

### Task 5: Error handling + global exception handler

**Objective:** Catch all unhandled errors and render them in-page

**Files:**
- Modify: `orpheus_voice_hub/app.py`

**Step 1: Add global exception handler**

```python
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return HTMLResponse('<div class="text-red-400 p-4">Invalid request. Please check your input.</div>', status_code=422)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return HTMLResponse(f'<div class="text-red-400 p-4">Server error: {html.escape(str(exc))}</div>', status_code=500)
```

---

### Task 6: Add __main__ + audio cleanup

**Objective:** Make the app runnable with `python app.py` and add periodic cleanup

**Files:**
- Modify: `orpheus_voice_hub/app.py`

**Step 1: Add __main__ block**

```python
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=HUB_PORT)
```

**Step 2: Add background cleanup task (in lifespan)**

```python
async def periodic_cleanup():
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        await cleanup_old_audio(max_age_seconds=3600)

# In lifespan, after http_client init:
cleanup_task = asyncio.create_task(periodic_cleanup())
yield
cleanup_task.cancel()
await http_client.aclose()
```

---

### Task 7: Final verification

**Objective:** Test all modes end-to-end

**Steps:**
1. Start Orpheus Voice Server (port 8081)
2. Start Ollama (port 11434)
3. Start Voice Hub: `python app.py`
4. Test Direct TTS with each voice
5. Test Brain + TTS
6. Test Voice Clone
7. Verify audio plays in browser
8. Check error handling (empty text, bad file, service down)
9. Verify health endpoint shows all services

---

## Audit Findings Addressed

| Finding | Severity | Fix Applied |
|---------|----------|-------------|
| Clone endpoint wrong path | CRITICAL | Changed to `/v1/clone` |
| Clone expects JSON not multipart | CRITICAL | Switched to base64 JSON |
| Missing transcript field | CRITICAL | Added transcript form field |
| XSS via unescaped user input | CRITICAL | Using Jinja2 autoescaping |
| No error handling | CRITICAL | try/except on all endpoints |
| No status code checks | CRITICAL | Added raise_for_status() |
| No file upload size limit | HIGH | 10MB limit enforced |
| Audio file accumulation | HIGH | Background cleanup every 5min |
| Model hardcoded | HIGH | Configurable via env var |
| No __main__ block | HIGH | Added uvicorn.run() |
| Race condition filenames | MEDIUM | UUID filenames |
| New httpx client per request | MEDIUM | Shared client via lifespan |
| Sync file writes | MEDIUM | Still sync but with cleanup |
| No CORS | MEDIUM | Added CORSMiddleware |
| No input validation | MEDIUM | validate_inputs() function |
| No empty text validation | MEDIUM | Checked in validate_inputs() |
| No health check | MEDIUM | Probes upstream services |
| Brain text not escaped | MEDIUM | Jinja2 autoescaping |
| Imports inside routes | LOW | Moved to top of file |
| No global exception handler | LOW | Added exception handlers |
| No audio streaming | LOW | File-based (acceptable for v1) |
| Tailwind CDN | LOW | Acceptable for local use |
| Open questions | LOW | Deferred to future |
| No truncation | LOW | MAX_BRAIN_CHARS=1000 |
| No caching | LOW | Deferred to future |
| No configurable port | LOW | $HUB_PORT env var |
