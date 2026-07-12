# The Dream — Full Duplex Voice Chat: Implementation Plan

> **Author:** AI-Assisted Planning
> **Date:** 2026-07-12
> **Status:** Ready for Build

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [File Structure](#2-file-structure)
3. [Dependencies & Setup](#3-dependencies--setup)
4. [Step-by-Step Build Order](#4-step-by-step-build-order)
5. [Testing Strategy](#5-testing-strategy)
6. [Deployment Instructions](#6-deployment-instructions)
7. [Appendix: Key API References](#7-appendix-key-api-references)

---

## 1. Project Overview

**The Dream** is a full-duplex voice chat system enabling natural, phone-call-like conversation with AI personas (Echo/Cyony). It uses browser-based VAD for hands-free operation, WebSockets for real-time streaming, and MiMo TTS for low-latency voice synthesis.

### Architecture Flow

```
Mic → [Web Audio API] → [VAD] → [WebSocket] → Server → AI → [MiMo TTS] → [WebSocket] → [Audio Buffer] → Speaker
```

### Key Technical Decisions

| Concern | Decision | Rationale |
|---|---|---|
| Frontend framework | Vanilla JS + HTML + CSS (single-page app) | No heavy framework needed; keeps bundle tiny |
| Backend runtime | Python 3.11 + FastAPI + WebSockets | Fast, async-native, familiar |
| VAD library | `ricky0123-vad-web` (Silero VAD in browser) | Runs in-browser, no server round-trip for VAD |
| STT | Web Speech API (browser) + fallback to server Whisper | Zero-cost, fast; fallback for accuracy |
| TTS | MiMo TTS API streaming endpoint | Low latency, built-in voices, streaming PCM16 |
| UI theme | Dark (#0a0a0a bg, #121212 panels, #39FF14 accent) | Per spec |
| Real-time transport | WebSocket (ws://) with binary PCM16 frames | Minimal overhead, streaming-native |
| State management | In-memory on server (dict of sessions) | Single-user MVP; no DB needed |

---

## 2. File Structure

```
the-dream/
├── README.md
├── .env.example
├── .gitignore
│
├── server/                          # Backend (Python / FastAPI)
│   ├── requirements.txt
│   ├── main.py                      # FastAPI app entry, WebSocket routes
│   ├── config.py                    # Environment config loading
│   ├── session.py                   # Session management (connect/disconnect/state)
│   ├── ai_client.py                 # AI provider client (Echo/Cyony router)
│   ├── tts_client.py                # MiMo TTS API client (streaming)
│   ├── stt_client.py                # Server-side STT fallback (Whisper)
│   └── audio.py                     # PCM16 utilities, resampling helpers
│
├── client/                          # Frontend (Browser)
│   ├── index.html                   # Entry point — single-page app
│   ├── css/
│   │   └── style.css                # Dark theme, waveforms, layout
│   ├── js/
│   │   ├── app.js                   # Main controller, wires everything together
│   │   ├── audio.js                 # Web Audio API: mic capture & playback
│   │   ├── websocket.js             # WebSocket client with reconnect logic
│   │   ├── vad.js                   # VAD integration wrapper
│   │   ├── stt.js                   # Browser STT (Web Speech API) wrapper
│   │   ├── tts.js                   # TTS streaming audio buffer & playback
│   │   ├── ui.js                    # DOM updates, waveform canvas, indicators
│   │   └── utils.js                 # Logging, formatting, constants
│   └── vendor/                      # Third-party (if not via CDN)
│       └── vad.worklet.bundle.js    # Pre-bundled Silero VAD worklet
│
├── scripts/                         # Development & ops scripts
│   ├── dev.sh                       # Start local dev (server + client)
│   ├── build.sh                     # Build client for production
│   └── deploy.sh                    # Deploy to VPS
│
├── tests/                           # Test suite
│   ├── conftest.py                  # Pytest fixtures
│   ├── test_session.py
│   ├── test_tts_client.py
│   ├── test_audio.py
│   ├── test_websocket.py            # WebSocket integration tests
│   └── test_e2e.py                  # End-to-end test harness
│
└── docs/                            # Additional documentation
    └── API.md                       # WebSocket message protocol spec
```

---

## 3. Dependencies & Setup

### 3.1 Backend (server/)

**File: `server/requirements.txt`**

```
# Web framework
fastapi==0.115.0
uvicorn[standard]==0.30.0
websockets>=12.0

# HTTP client for TTS & AI APIs
httpx>=0.27.0

# Audio processing (server-side)
numpy>=1.26.0
soundfile>=0.12.1

# Server Whisper STT (optional fallback)
faster-whisper>=1.0.0

# Environment & config
python-dotenv>=1.0.0

# Testing
pytest>=8.0.0
pytest-asyncio>=0.23.0
httpx-ws>=0.2.0
```

### 3.2 Frontend (client/)

No build step — plain HTML/CSS/JS. Third-party libraries loaded via CDN:

| Library | CDN URL | Purpose |
|---|---|---|
| Silero VAD Web | `https://cdn.jsdelivr.net/npm/@ricky0123/vad-web@0.1.8/dist/bundle.min.js` | Voice Activity Detection |
| (optional) Waveform | Self-drawn via Canvas API or `wavesurfer.js` | Visual feedback |

### 3.3 Environment Variables

**File: `.env.example`**

```env
# Server
HOST=0.0.0.0
PORT=8765
WS_MAX_SIZE=10485760             # 10MB max WS message

# AI Provider (Cyony on VPS or Echo via Tailscale)
AI_PROVIDER=echo                 # "echo" (local) or "cyony" (VPS)
CYONY_API_URL=http://localhost:8001/v1/chat
ECHO_API_URL=http://echo.tailscale-ip:8000/v1/chat
AI_API_KEY=your-api-key-here

# MiMo TTS
MIMO_API_URL=https://api.mimo.com/v1/tts/stream
MIMO_API_KEY=your-mimo-key-here
MIMO_DEFAULT_VOICE=milo

# Whisper STT (server-side fallback)
WHISPER_MODEL_SIZE=base          # tiny, base, small, medium, large

# Logging
LOG_LEVEL=INFO
```

### 3.4 Setup Commands

```bash
# 1. Clone / create project
mkdir -p the-dream && cd the-dream

# 2. Backend setup
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r server/requirements.txt

# 3. Copy env and configure
cp .env.example .env
# Edit .env with real API keys and endpoints

# 4. Frontend -- no build needed; serve from client/ directory
```

---

## 4. Step-by-Step Build Order

Each step is numbered. Do not proceed to step N+1 until step N is tested and working.

---

### Step 1: Project Scaffolding & Configuration

**Goal:** Empty project with all directories, config loading, and a health endpoint.

#### 1.1 Create directory structure
```bash
mkdir -p server client/css client/js client/vendor scripts tests docs
```

#### 1.2 Write `server/config.py`
```python
"""Configuration loaded from environment or .env file."""

import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8765
    ws_max_size: int = 10 * 1024 * 1024  # 10MB

    ai_provider: str = "echo"
    cyony_api_url: str = "http://localhost:8001/v1/chat"
    echo_api_url: str = "http://echo.tailscale-ip:8000/v1/chat"
    ai_api_key: str = ""

    mimo_api_url: str = "https://api.mimo.com/v1/tts/stream"
    mimo_api_key: str = ""
    mimo_default_voice: str = "milo"

    whisper_model_size: str = "base"

    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()
```

#### 1.3 Write `server/main.py` (initial skeleton)
```python
"""FastAPI application entry point."""

import logging
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from config import settings

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title="The Dream — Voice Chat Server")

@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}

@app.websocket("/ws")
async def voice_websocket(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connected")
    try:
        while True:
            data = await websocket.receive_bytes()
            # Will handle audio frames here in Step 5
            logger.debug(f"Received {len(data)} bytes")
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )
```

#### 1.4 Write `scripts/dev.sh`
```bash
#!/usr/bin/env bash
set -euo pipefail

# Start backend
cd "$(dirname "$0")/../server"
source ../venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8765 &

# Start a simple HTTP server for the client
cd ../client
python -m http.server 8080 &

echo "Server: ws://localhost:8765"
echo "Client: http://localhost:8080"
wait
```

#### 1.5 Test Step 1
```bash
cd server && python main.py &
curl http://localhost:8765/health
# Expected: {"status":"ok","version":"0.1.0"}
```

---

### Step 2: WebSocket Protocol & Session Management

**Goal:** Define the message protocol, handle connect/disconnect, maintain session state.

#### 2.1 Define Message Protocol

All WebSocket messages use a **binary framing** format:

| Byte 0 (type) | Bytes 1-4 (payload length) | Bytes 5+ (payload) |
|---|---|---|
| `0x01` = Audio frame (PCM16) | uint32 big-endian | Raw PCM16 samples |
| `0x02` = Text message | uint32 big-endian | UTF-8 JSON string |
| `0x03` = STT result | uint32 big-endian | UTF-8 JSON string |
| `0x04` = TTS audio chunk | uint32 big-endian | Raw PCM16 samples |
| `0x05` = TTS end marker | 0x00000000 | (empty) |
| `0xFF` = Error / status | uint32 big-endian | UTF-8 JSON string |

JSON payload schema:

```json
// Client → Server (type 0x02)
{"type": "vad_event", "state": "speaking|silence"}
{"type": "stt_result", "text": "hello world", "final": true}
{"type": "set_voice", "voice": "milo"}
{"type": "ping"}

// Server → Client (type 0x02)
{"type": "pong"}
{"type": "error", "message": "..."}
{"type": "connected", "session_id": "..."}
{"type": "ai_thinking", "status": "processing|streaming"}
```

#### 2.2 Write `server/session.py`
```python
"""WebSocket session management."""

import uuid
import logging
from dataclasses import dataclass, field
from typing import Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class Session:
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    websocket: WebSocket = None
    voice: str = ""  # Will be set from config default
    is_speaking: bool = False     # User currently speaking (VAD)
    is_playing: bool = False      # TTS currently playing
    ai_processing: bool = False   # AI generating response
    buffer: list[bytes] = field(default_factory=list)  # Audio accumulation


class SessionManager:
    """Manages all active WebSocket sessions."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    async def create(self, ws: WebSocket, default_voice: str) -> Session:
        session = Session(websocket=ws, voice=default_voice)
        self._sessions[session.session_id] = session
        logger.info(f"Session created: {session.session_id}")
        await self._send_json(session, {
            "type": "connected",
            "session_id": session.session_id
        })
        return session

    async def remove(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Session removed: {session_id}")

    def get(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    async def _send_json(self, session: Session, data: dict):
        import json
        payload = json.dumps(data).encode("utf-8")
        msg = b"\x02" + len(payload).to_bytes(4, "big") + payload
        await session.websocket.send_bytes(msg)

    async def send_audio(self, session: Session, pcm16_chunk: bytes):
        msg = b"\x04" + len(pcm16_chunk).to_bytes(4, "big") + pcm16_chunk
        await session.websocket.send_bytes(msg)

    async def send_tts_end(self, session: Session):
        await session.websocket.send_bytes(b"\x05\x00\x00\x00\x00")

    async def send_status(self, session: Session, status_type: str, message: str = ""):
        payload = json.dumps({"type": status_type, "message": message}).encode("utf-8")
        msg = b"\xFF" + len(payload).to_bytes(4, "big") + payload
        await session.websocket.send_bytes(msg)

    def add_audio_buffer(self, session: Session, pcm16_data: bytes):
        session.buffer.append(pcm16_data)

    def flush_audio_buffer(self, session: Session) -> bytes:
        data = b"".join(session.buffer)
        session.buffer.clear()
        return data
```

#### 2.3 Update `server/main.py` to use session manager

Replace the placeholder WebSocket handler:

```python
from session import SessionManager
from config import settings

session_manager = SessionManager()

@app.websocket("/ws")
async def voice_websocket(websocket: WebSocket):
    await websocket.accept()
    session = await session_manager.create(websocket, settings.mimo_default_voice)
    try:
        while True:
            data = await websocket.receive_bytes()
            if not data:
                continue
            msg_type = data[0]
            payload_len = int.from_bytes(data[1:5], "big")
            payload = data[5:5+payload_len] if payload_len > 0 else b""

            if msg_type == 0x01:  # Audio frame
                session_manager.add_audio_buffer(session, payload)
            elif msg_type == 0x02:  # JSON message
                import json
                msg = json.loads(payload.decode("utf-8"))
                await handle_json_message(session, msg)
            else:
                logger.warning(f"Unknown message type: {msg_type}")

    except WebSocketDisconnect:
        logger.info(f"Session {session.session_id} disconnected")
        await session_manager.remove(session.session_id)

async def handle_json_message(session, msg):
    msg_type = msg.get("type")
    if msg_type == "ping":
        await session_manager._send_json(session, {"type": "pong"})
    elif msg_type == "set_voice":
        session.voice = msg.get("voice", session.voice)
        logger.info(f"Voice changed to {session.voice}")
    elif msg_type == "vad_event":
        session.is_speaking = msg["state"] == "speaking"
        if msg["state"] == "silence" and session.buffer:
            # VAD silence detected — flush audio to STT → AI → TTS
            logger.info("VAD silence — processing audio buffer")
            await process_audio(session)
    elif msg_type == "stt_result":
        logger.info(f"STT result: {msg['text']}")
        await process_text(session, msg["text"])
```

#### 2.5 Test Step 2

Write a small test script or use `websocat` to connect and verify the protocol:

```bash
# Terminal 1: Start server
cd server && python main.py

# Terminal 2: Quick protocol test using Python
python -c "
import asyncio, json, websockets
async def test():
    async with websockets.connect('ws://localhost:8765/ws') as ws:
        # Should receive 'connected' message
        msg = await ws.recv()
        print('Received:', msg)
        
        # Send ping
        ping = b'\x02' + len(json.dumps({'type':'ping'}).encode()).to_bytes(4,'big') + json.dumps({'type':'ping'}).encode()
        await ws.send(ping)
        
        msg = await ws.recv()
        print('Received:', msg)
asyncio.run(test())
"
```

---

### Step 3: Audio Pipeline — Capture & Playback (Browser)

**Goal:** Browser can capture mic input via Web Audio API and play streaming PCM16 audio.

#### 3.1 Write `client/js/audio.js`

```javascript
/**
 * Audio capture and playback using Web Audio API.
 */
class AudioManager {
    constructor() {
        this.audioContext = null;
        this.micStream = null;
        this.micNode = null;
        this.processor = null;
        this.gainNode = null;
        this.onAudioData = null;  // Callback(pcm16: ArrayBuffer)
        this.isPlaying = false;
    }

    async init() {
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
            sampleRate: 16000,  // Match VAD and STT sample rate
        });
        this.micStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                sampleRate: 16000,
                channelCount: 1,
                echoCancellation: true,
                noiseSuppression: true,
            }
        });
        this.micNode = this.audioContext.createMediaStreamSource(this.micStream);

        // ScriptProcessorNode for raw PCM access (deprecated but widely supported)
        // For production, use AudioWorklet — but ScriptProcessor is simpler for MVP
        this.processor = this.audioContext.createScriptProcessor(2048, 1, 1);
        this.processor.onaudioprocess = (event) => {
            if (!this.onAudioData) return;
            const inputData = event.inputBuffer.getChannelData(0);
            // Convert Float32 to PCM16
            const pcm16 = new Int16Array(inputData.length);
            for (let i = 0; i < inputData.length; i++) {
                const s = Math.max(-1, Math.min(1, inputData[i]));
                pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }
            this.onAudioData(pcm16.buffer);
        };
        this.micNode.connect(this.processor);
        this.processor.connect(this.audioContext.destination);
        console.log('AudioManager: initialized');
    }

    /** Play PCM16 audio data (16-bit, 16000Hz, mono) */
    playPCM16(pcm16Buffer) {
        const float32 = new Float32Array(pcm16Buffer.byteLength / 2);
        const int16 = new Int16Array(pcm16Buffer);
        for (let i = 0; i < float32.length; i++) {
            float32[i] = int16[i] / 32768.0;
        }
        const audioBuffer = this.audioContext.createBuffer(1, float32.length, 16000);
        audioBuffer.getChannelData(0).set(float32);

        const source = this.audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(this.audioContext.destination);
        source.start();
        this.isPlaying = true;
        source.onended = () => { this.isPlaying = false; };
    }

    /** Create a queue-based streaming player for continuous TTS playback */
    createStreamPlayer() {
        return new PCMStreamPlayer(this.audioContext);
    }

    cleanup() {
        if (this.micStream) this.micStream.getTracks().forEach(t => t.stop());
        if (this.audioContext) this.audioContext.close();
    }
}

/**
 * Queue-based streaming PCM16 player.
 * Chunks are buffered and played sequentially with minimal gaps.
 */
class PCMStreamPlayer {
    constructor(audioContext) {
        this.ctx = audioContext;
        this.queue = [];
        this.isPlaying = false;
        this.nextTime = 0;
    }

    enqueue(pcm16Buffer) {
        const float32 = new Float32Array(pcm16Buffer.byteLength / 2);
        const int16 = new Int16Array(pcm16Buffer);
        for (let i = 0; i < float32.length; i++) {
            float32[i] = int16[i] / 32768.0;
        }
        this.queue.push(float32);
        if (!this.isPlaying) this._playNext();
    }

    _playNext() {
        if (this.queue.length === 0) {
            this.isPlaying = false;
            return;
        }
        this.isPlaying = true;
        const data = this.queue.shift();
        const buffer = this.ctx.createBuffer(1, data.length, 16000);
        buffer.getChannelData(0).set(data);

        const source = this.ctx.createBufferSource();
        source.buffer = buffer;

        // Schedule precisely to avoid gaps
        if (this.nextTime < this.ctx.currentTime) {
            this.nextTime = this.ctx.currentTime + 0.01;
        }
        source.connect(this.ctx.destination);
        source.start(this.nextTime);
        this.nextTime += buffer.duration;

        source.onended = () => this._playNext();
    }

    clear() {
        this.queue = [];
        this.isPlaying = false;
    }
}
```

#### 3.2 Write skeleton client files to wire it up (index.html + app.js)

**File: `client/index.html`**
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>The Dream — Voice Chat</title>
    <link rel="stylesheet" href="css/style.css">
</head>
<body>
    <div id="app">
        <header>
            <h1>✦ The Dream</h1>
            <div id="status-indicator" class="status-disconnected">Disconnected</div>
        </header>
        <main>
            <div id="visualizer">
                <canvas id="waveform-canvas"></canvas>
            </div>
            <div id="voice-selector">
                <label>Voice: </label>
                <select id="voice-select">
                    <option value="milo">Milo (male)</option>
                    <option value="dean">Dean (male deep)</option>
                    <option value="mia">Mia (female)</option>
                    <option value="chloe">Chloe (female)</option>
                </select>
            </div>
            <div id="transcript-area">
                <div id="user-transcript"></div>
                <div id="ai-transcript"></div>
            </div>
        </main>
    </div>
    <script src="js/utils.js"></script>
    <script src="js/audio.js"></script>
    <script src="js/websocket.js"></script>
    <script src="js/vad.js"></script>
    <script src="js/stt.js"></script>
    <script src="js/tts.js"></script>
    <script src="js/ui.js"></script>
    <script src="js/app.js"></script>
</body>
</html>
```

**File: `client/css/style.css`**
```css
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    background-color: #0a0a0a;
    color: #e0e0e0;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;
}

#app {
    width: 100%;
    max-width: 600px;
    padding: 2rem;
    text-align: center;
}

header h1 {
    color: #39FF14;
    font-weight: 300;
    letter-spacing: 0.2em;
    margin-bottom: 0.5rem;
}

#status-indicator {
    display: inline-block;
    padding: 0.25rem 1rem;
    border-radius: 20px;
    font-size: 0.8rem;
    margin-bottom: 2rem;
    transition: all 0.3s;
}
.status-disconnected { background: #441111; color: #ff4444; }
.status-connected    { background: #114411; color: #39FF14; }
.status-speaking    { background: #113344; color: #44aaff; }
.status-thinking    { background: #443311; color: #ffaa44; }

#visualizer {
    width: 100%;
    height: 120px;
    background: #121212;
    border-radius: 12px;
    margin-bottom: 1.5rem;
    overflow: hidden;
}

#waveform-canvas {
    width: 100%;
    height: 100%;
}

#voice-selector {
    margin-bottom: 1.5rem;
}
#voice-selector select {
    background: #121212;
    color: #39FF14;
    border: 1px solid #39FF14;
    padding: 0.4rem 1rem;
    border-radius: 6px;
    font-size: 1rem;
}

#transcript-area {
    text-align: left;
    font-size: 0.9rem;
    line-height: 1.6;
}
#user-transcript {
    color: #a0a0a0;
    padding: 0.5rem;
    min-height: 2rem;
}
#ai-transcript {
    color: #39FF14;
    padding: 0.5rem;
    min-height: 2rem;
}

/* Mobile responsive */
@media (max-width: 480px) {
    #app { padding: 1rem; }
    #visualizer { height: 80px; }
}
```

#### 3.3 Test Step 3

```bash
# Terminal 1: start a simple HTTP server
cd client && python -m http.server 8080

# Open http://localhost:8080 in browser
# Open dev console → should see "AudioManager: initialized"
# Audio capture is working if mic permission is granted
```

---

### Step 4: VAD (Voice Activity Detection) — Browser

**Goal:** Detect when user starts/stops speaking, enabling hands-free operation.

#### 4.1 Write `client/js/vad.js`

```javascript
/**
 * Voice Activity Detection wrapper using Silero VAD (ricky0123-vad-web).
 */
class VADManager {
    constructor() {
        this.vad = null;
        this.onSpeechStart = null;  // Callback()
        this.onSpeechEnd = null;    // Callback()
        this.isSpeaking = false;
        this.initialized = false;
    }

    async init(audioContext, micStream) {
        // Load VAD library from CDN
        if (typeof vad === 'undefined') {
            await this._loadScript(
                'https://cdn.jsdelivr.net/npm/@ricky0123/vad-web@0.1.8/dist/bundle.min.js'
            );
        }

        this.vad = await vad.MicVAD.new({
            onSpeechStart: () => {
                this.isSpeaking = true;
                console.log('VAD: speech start');
                if (this.onSpeechStart) this.onSpeechStart();
            },
            onSpeechEnd: () => {
                this.isSpeaking = false;
                console.log('VAD: speech end');
                if (this.onSpeechEnd) this.onSpeechEnd();
            },
            minSpeechFrames: 5,        // ~250ms before declaring speech
            minSilenceFrames: 20,      // ~1000ms silence before declaring end
            startSpeakingThreshold: 0.5,
            stopSpeakingThreshold: 0.5,
            redemptionFrames: 8,
        });

        this.initialized = true;
        console.log('VADManager: initialized');
    }

    start() {
        if (this.vad) this.vad.start();
    }

    stop() {
        if (this.vad) this.vad.pause();
    }

    _loadScript(src) {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = src;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    cleanup() {
        if (this.vad) this.vad.destroy();
    }
}
```

#### 4.2 Test Step 4

Update `app.js` to wire VAD events to console logs:

```javascript
// app.js — test wiring
const audio = new AudioManager();
const vad = new VADManager();

async function init() {
    await audio.init();
    await vad.init(audio.audioContext, audio.micStream);
    
    vad.onSpeechStart = () => console.log('SPEAKING');
    vad.onSpeechEnd = () => console.log('SILENCE');
    
    vad.start();
    console.log('System ready — say something!');
}

init();
```

Open browser on localhost:8080 — speaking into mic should print "SPEAKING" / "SILENCE" in the console.

---

### Step 5: WebSocket Client with Reconnect

**Goal:** Browser connects to server, sends audio frames, receives TTS audio.

#### 5.1 Write `client/js/websocket.js`

```javascript
/**
 * WebSocket client with auto-reconnect and binary message framing.
 */
class WebSocketClient {
    constructor(url) {
        this.url = url;
        this.ws = null;
        this.reconnectDelay = 1000;      // Start at 1s, double up to 30s
        this.maxReconnectDelay = 30000;
        this.shouldReconnect = true;
        this.isConnected = false;

        // Callbacks
        this.onOpen = null;
        this.onClose = null;
        this.onError = null;
        this.onAudioChunk = null;    // Callback(pcm16: ArrayBuffer)
        this.onTtsEnd = null;        // Callback()
        this.onJsonMessage = null;   // Callback(obj)
        this.onStatus = null;        // Callback(obj)
    }

    connect() {
        if (this.ws && (this.ws.readyState === WebSocket.OPEN || 
                        this.ws.readyState === WebSocket.CONNECTING)) {
            return;
        }
        try {
            this.ws = new WebSocket(this.url);
            this.ws.binaryType = 'arraybuffer';
        } catch (e) {
            console.error('WebSocket creation error:', e);
            this._scheduleReconnect();
            return;
        }

        this.ws.onopen = () => {
            console.log('WebSocket: connected');
            this.isConnected = true;
            this.reconnectDelay = 1000;  // Reset exponential backoff
            if (this.onOpen) this.onOpen();
        };

        this.ws.onclose = (event) => {
            console.log(`WebSocket: disconnected (code=${event.code})`);
            this.isConnected = false;
            if (this.onClose) this.onClose();
            if (this.shouldReconnect) this._scheduleReconnect();
        };

        this.ws.onerror = (err) => {
            console.error('WebSocket: error', err);
            if (this.onError) this.onError(err);
        };

        this.ws.onmessage = (event) => {
            this._handleMessage(event.data);
        };
    }

    _handleMessage(data) {
        const view = new DataView(data);
        const msgType = view.getUint8(0);
        const payloadLen = view.getUint32(1, false);  // big-endian
        const payload = data.slice(5, 5 + payloadLen);

        switch (msgType) {
            case 0x04:  // TTS audio chunk
                if (this.onAudioChunk) this.onAudioChunk(payload);
                break;
            case 0x05:  // TTS end marker
                if (this.onTtsEnd) this.onTtsEnd();
                break;
            case 0x02:  // JSON message
                const msg = JSON.parse(new TextDecoder().decode(payload));
                if (this.onJsonMessage) this.onJsonMessage(msg);
                break;
            case 0xFF:  // Status / error
                const status = JSON.parse(new TextDecoder().decode(payload));
                if (this.onStatus) this.onStatus(status);
                break;
            default:
                console.warn('Unknown message type:', msgType);
        }
    }

    /** Send an audio PCM16 frame (type 0x01) */
    sendAudio(pcm16Buffer) {
        if (!this.isConnected) return;
        const len = pcm16Buffer.byteLength;
        const msg = new ArrayBuffer(5 + len);
        const view = new DataView(msg);
        view.setUint8(0, 0x01);
        view.setUint32(1, len, false);
        new Uint8Array(msg, 5).set(new Uint8Array(pcm16Buffer));
        this.ws.send(msg);
    }

    /** Send a JSON message (type 0x02) */
    sendJson(obj) {
        if (!this.isConnected) return;
        const payload = new TextEncoder().encode(JSON.stringify(obj));
        const msg = new ArrayBuffer(5 + payload.byteLength);
        const view = new DataView(msg);
        view.setUint8(0, 0x02);
        view.setUint32(1, payload.byteLength, false);
        new Uint8Array(msg, 5).set(payload);
        this.ws.send(msg);
    }

    disconnect() {
        this.shouldReconnect = false;
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    _scheduleReconnect() {
        if (!this.shouldReconnect) return;
        console.log(`Reconnecting in ${this.reconnectDelay}ms...`);
        setTimeout(() => this.connect(), this.reconnectDelay);
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
    }
}
```

#### 5.2 Test Step 5

```bash
# Terminal 1: start server
cd server && python main.py

# Terminal 2: open browser at http://localhost:8080
# Check browser console for "WebSocket: connected" after app loads
```

---

### Step 6: Browser STT (Web Speech API)

**Goal:** Convert speech to text in-browser using the Web Speech API.

#### 6.1 Write `client/js/stt.js`

```javascript
/**
 * Browser-based Speech-to-Text using Web Speech API.
 * Provides interim and final results.
 */
class STTManager {
    constructor() {
        this.recognition = null;
        this.isListening = false;
        this.onInterimResult = null;   // Callback(text: string)
        this.onFinalResult = null;     // Callback(text: string)
        this.onError = null;
    }

    init(lang = 'en-US') {
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            console.warn('Web Speech API not available in this browser');
            return false;
        }
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        this.recognition = new SpeechRecognition();
        this.recognition.continuous = true;
        this.recognition.interimResults = true;
        this.recognition.lang = lang;
        this.recognition.maxAlternatives = 1;

        this.recognition.onresult = (event) => {
            let interim = '';
            let final = '';
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const result = event.results[i];
                if (result.isFinal) {
                    final += result[0].transcript;
                } else {
                    interim += result[0].transcript;
                }
            }
            if (final && this.onFinalResult) this.onFinalResult(final.trim());
            if (interim && this.onInterimResult) this.onInterimResult(interim.trim());
        };

        this.recognition.onerror = (event) => {
            console.error('STT error:', event.error);
            if (this.onError) this.onError(event.error);
        };

        return true;
    }

    start() {
        if (this.recognition && !this.isListening) {
            try {
                this.recognition.start();
                this.isListening = true;
                console.log('STT: started');
            } catch (e) {
                console.error('STT start error:', e);
            }
        }
    }

    stop() {
        if (this.recognition && this.isListening) {
            this.recognition.stop();
            this.isListening = false;
            console.log('STT: stopped');
        }
    }

    restart() {
        this.stop();
        setTimeout(() => this.start(), 100);
    }
}
```

#### 6.2 Test Step 6

Open browser → speak into mic → console should print interim and final transcript results.

---

### Step 7: AI Client Integration

**Goal:** Server receives text, sends it to Echo or Cyony AI, gets response text.

#### 7.1 Write `server/ai_client.py`

```python
"""AI provider client — routes to Echo (local) or Cyony (VPS)."""

import json
import logging
from typing import AsyncGenerator
import httpx
from config import settings

logger = logging.getLogger(__name__)


class AIClient:
    """Client for AI chat completion (Echo or Cyony)."""

    def __init__(self):
        self.provider = settings.ai_provider
        self.api_url = (
            settings.echo_api_url
            if self.provider == "echo"
            else settings.cyony_api_url
        )
        self.api_key = settings.ai_api_key
        self._client = httpx.AsyncClient(timeout=30.0)
        logger.info(f"AI Client initialized: provider={self.provider}, url={self.api_url}")

    async def chat_stream(
        self, 
        user_message: str, 
        session_id: str,
        system_prompt: str = "You are Echo, a helpful AI assistant. Be concise and conversational.",
        history: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Send message to AI and stream the response text."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history[-10:])  # Keep last 10 turns
        messages.append({"role": "user", "content": user_message})

        payload = {
            "messages": messages,
            "stream": True,
            "max_tokens": 512,
            "temperature": 0.7,
        }

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with self._client.stream(
                "POST", self.api_url, json=payload, headers=headers
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            choices = data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue
        except httpx.HTTPStatusError as e:
            logger.error(f"AI API HTTP error: {e.response.status_code} - {e.response.text}")
            yield f"[Error: AI service unavailable ({e.response.status_code})]"
        except httpx.RequestError as e:
            logger.error(f"AI API request error: {e}")
            yield "[Error: Cannot reach AI service]"

    async def close(self):
        await self._client.aclose()
```

---

### Step 8: MiMo TTS Client

**Goal:** Convert AI response text to streaming PCM16 audio via MiMo TTS API.

#### 8.1 Write `server/tts_client.py`

```python
"""MiMo TTS streaming client."""

import logging
from typing import AsyncGenerator
import httpx
from config import settings

logger = logging.getLogger(__name__)


class TTSClient:
    """Client for MiMo TTS streaming API."""

    def __init__(self):
        self.api_url = settings.mimo_api_url
        self.api_key = settings.mimo_api_key
        self._client = httpx.AsyncClient(timeout=60.0)
        logger.info(f"TTS Client initialized: url={self.api_url}")

    async def stream_tts(
        self, text: str, voice: str = "milo"
    ) -> AsyncGenerator[bytes, None]:
        """Stream TTS audio as PCM16 chunks."""
        payload = {
            "text": text,
            "voice": voice,
            "format": "pcm16",
            "sample_rate": 16000,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with self._client.stream(
                "POST", self.api_url, json=payload, headers=headers
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    if chunk:
                        yield chunk
        except httpx.HTTPStatusError as e:
            logger.error(f"TTS API HTTP error: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"TTS API request error: {e}")

    async def close(self):
        await self._client.aclose()
```

---

### Step 9: Full Pipeline Wiring (Server)

**Goal:** Wire VAD event → flush audio → STT (browser or server) → AI → TTS → stream to client.

#### 9.1 Write `server/audio.py`

```python
"""Audio processing utilities."""

import numpy as np


def pcm16_to_float32(pcm16_bytes: bytes) -> np.ndarray:
    """Convert PCM16 bytes to float32 numpy array (-1.0 to 1.0)."""
    samples = np.frombuffer(pcm16_bytes, dtype=np.int16).astype(np.float32)
    samples /= 32768.0
    return samples


def float32_to_pcm16(samples: np.ndarray) -> bytes:
    """Convert float32 numpy array to PCM16 bytes."""
    samples = np.clip(samples, -1.0, 1.0)
    pcm16 = (samples * 32767.0).astype(np.int16)
    return pcm16.tobytes()


def calculate_rms(pcm16_bytes: bytes) -> float:
    """Calculate RMS energy of a PCM16 buffer (for waveform visualization)."""
    samples = np.frombuffer(pcm16_bytes, dtype=np.int16).astype(np.float32)
    if len(samples) == 0:
        return 0.0
    rms = np.sqrt(np.mean(samples ** 2))
    return float(rms)
```

#### 9.2 Update `server/main.py` with full pipeline

```python
"""The Dream — Full Duplex Voice Chat Server"""

import json
import logging
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from config import settings
from session import SessionManager, Session
from ai_client import AIClient
from tts_client import TTSClient

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title="The Dream — Voice Chat Server")

# Global state
session_manager = SessionManager()
ai_client = AIClient()
tts_client = TTSClient()

# Conversation context per session (simple in-memory)
conversations: dict[str, list[dict]] = {}


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0", "sessions": len(session_manager._sessions)}


@app.websocket("/ws")
async def voice_websocket(websocket: WebSocket):
    await websocket.accept()
    session = await session_manager.create(websocket, settings.mimo_default_voice)
    conversations[session.session_id] = []

    try:
        while True:
            data = await websocket.receive_bytes()
            if not data:
                continue

            msg_type = data[0]
            payload_len = int.from_bytes(data[1:5], "big")
            payload = data[5:5 + payload_len] if payload_len > 0 else b""

            if msg_type == 0x01:  # Audio frame
                session_manager.add_audio_buffer(session, payload)

            elif msg_type == 0x02:  # JSON message
                msg = json.loads(payload.decode("utf-8"))
                await _handle_json_message(session, msg)

            else:
                logger.warning(f"Unknown message type: {msg_type}")

    except WebSocketDisconnect:
        logger.info(f"Session {session.session_id} disconnected")
    except Exception as e:
        logger.error(f"Session {session.session_id} error: {e}", exc_info=True)
    finally:
        await session_manager.remove(session.session_id)
        conversations.pop(session.session_id, None)


async def _handle_json_message(session: Session, msg: dict):
    msg_type = msg.get("type")
    if msg_type == "ping":
        await session_manager._send_json(session, {"type": "pong"})
    elif msg_type == "set_voice":
        session.voice = msg.get("voice", session.voice)
        logger.info(f"Session {session.session_id}: voice → {session.voice}")
    elif msg_type == "vad_event":
        session.is_speaking = msg["state"] == "speaking"
        if msg["state"] == "silence" and session.buffer:
            # End of speech — process accumulated audio
            asyncio.create_task(_process_audio_buffer(session))
    elif msg_type == "stt_result":
        # Browser-side STT sent a final transcription
        await _process_text_input(session, msg["text"])


async def _process_audio_buffer(session: Session):
    """Handle accumulated audio buffer (server-side STT path)."""
    audio_data = session_manager.flush_audio_buffer(session)
    if len(audio_data) < 320:  # < 20ms at 16kHz — too short, likely noise
        logger.debug(f"Audio buffer too short ({len(audio_data)} bytes), skipping")
        return

    # Server-side Whisper STT (optional)
    try:
        from stt_client import transcribe
        text = await transcribe(audio_data)
        if text and text.strip():
            logger.info(f"STT result: {text}")
            await _process_text_input(session, text)
    except ImportError:
        logger.warning("Server-side STT not available; install faster-whisper or use browser STT")
        await session_manager._send_json(session, {
            "type": "error",
            "message": "Server STT not configured. Use browser-based STT."
        })


async def _process_text_input(session: Session, text: str):
    """Send text through AI → TTS pipeline and stream response back."""
    if not text or not text.strip():
        return

    logger.info(f"Processing: '{text}' (voice={session.voice})")

    # Notify client AI is thinking
    await session_manager._send_json(session, {
        "type": "ai_thinking", "status": "processing"
    })

    # Build conversation history
    history = conversations.get(session.session_id, [])
    history.append({"role": "user", "content": text})

    # Stream from AI
    ai_response = ""
    async for chunk in ai_client.chat_stream(
        user_message=text,
        session_id=session.session_id,
        history=history,
    ):
        ai_response += chunk

    if not ai_response or ai_response.startswith("[Error"):
        await session_manager._send_json(session, {
            "type": "ai_thinking", "status": "error", "message": ai_response
        })
        return

    # Notify client AI is responding / TTS starting
    await session_manager._send_json(session, {
        "type": "ai_thinking", "status": "streaming"
    })

    # Stream TTS audio chunks back to client
    async for audio_chunk in tts_client.stream_tts(ai_response, voice=session.voice):
        await session_manager.send_audio(session, audio_chunk)

    # Signal TTS stream end
    await session_manager.send_tts_end(session)

    # Send the transcript so client can display it
    await session_manager._send_json(session, {
        "type": "ai_response", "text": ai_response
    })

    # Update conversation history
    history.append({"role": "assistant", "content": ai_response})
    conversations[session.session_id] = history[-20:]  # Keep last 20 turns

    logger.info(f"Response complete ({len(ai_response)} chars, {len(ai_response.split())} words)")


@app.on_event("shutdown")
async def shutdown():
    await ai_client.close()
    await tts_client.close()
```

---

### Step 10: Wire Everything in the Browser (app.js)

**Goal:** All browser components connected into a working system.

#### 10.1 Write `client/js/app.js`

```javascript
/**
 * The Dream — Main Application Controller.
 * Wires AudioManager, VADManager, STTManager, WebSocketClient, and UI together.
 */
class DreamApp {
    constructor() {
        this.audio = new AudioManager();
        this.vad = new VADManager();
        this.stt = new STTManager();
        this.ws = new WebSocketClient(`ws://${location.hostname}:8765/ws`);
        this.ui = new UIManager();
        this.streamPlayer = null;
        this.isVadMode = true;  // true = hands-free VAD, false = push-to-talk
    }

    async init() {
        console.log('✦ The Dream — initializing...');

        // 1. Initialize audio
        await this.audio.init();
        this.streamPlayer = this.audio.createStreamPlayer();

        // 2. Initialize VAD
        this.vad.onSpeechStart = () => this._onSpeechStart();
        this.vad.onSpeechEnd = () => this._onSpeechEnd();
        await this.vad.init(this.audio.audioContext, this.audio.micStream);

        // 3. Initialize STT (browser-based)
        this.stt.onFinalResult = (text) => this._onSTTResult(text);
        this.stt.onInterimResult = (text) => this.ui.updateUserTranscript(text, true);
        this.stt.init();

        // 4. Configure WebSocket
        this.ws.onOpen = () => this._onConnected();
        this.ws.onClose = () => this._onDisconnected();
        this.ws.onAudioChunk = (pcm16) => this.streamPlayer.enqueue(pcm16);
        this.ws.onTtsEnd = () => this._onTtsEnd();
        this.ws.onJsonMessage = (msg) => this._onServerMessage(msg);
        this.ws.onStatus = (status) => console.log('Server status:', status);

        // 5. Wire UI
        this.ui.onVoiceChange = (voice) => this.ws.sendJson({ type: 'set_voice', voice });
        this.ui.init();

        // 6. Connect to server
        this.ws.connect();

        // 7. Start VAD (hands-free by default)
        if (this.isVadMode) {
            this.vad.start();
            this.stt.start();
        }

        console.log('✦ The Dream — ready');
    }

    _onConnected() {
        this.ui.setStatus('connected');
        this.ui.updateTranscript('System', 'Connected to server.');
    }

    _onDisconnected() {
        this.ui.setStatus('disconnected');
        this.ui.updateTranscript('System', 'Disconnected. Reconnecting...');
    }

    _onSpeechStart() {
        this.ui.setStatus('speaking');
        this.ui.updateTranscript('You', '...', true);
        // Start streaming audio to server for VAD-based processing
        this.audio.onAudioData = (pcm16) => this.ws.sendAudio(pcm16);
    }

    _onSpeechEnd() {
        this.ui.setStatus('thinking');
        this.audio.onAudioData = null;

        // Send VAD event to server (server will flush buffer)
        this.ws.sendJson({ type: 'vad_event', state: 'silence' });

        // Send final STT text to server
        this.stt.stop();
        setTimeout(() => this.stt.start(), 300);
    }

    _onSTTResult(text) {
        if (!text) return;
        this.ui.updateUserTranscript(text, false);
        // Also send to server as a text message for the AI pipeline
        this.ws.sendJson({ type: 'stt_result', text, final: true });
    }

    _onServerMessage(msg) {
        switch (msg.type) {
            case 'connected':
                console.log('Session:', msg.session_id);
                break;
            case 'ai_thinking':
                if (msg.status === 'processing') {
                    this.ui.setStatus('thinking');
                    this.ui.updateTranscript('Echo', '...');
                } else if (msg.status === 'streaming') {
                    this.ui.setStatus('speaking');
                } else if (msg.status === 'error') {
                    this.ui.setStatus('connected');
                    this.ui.updateTranscript('System', `Error: ${msg.message}`);
                }
                break;
            case 'ai_response':
                this.ui.updateTranscript('Echo', msg.text, false);
                break;
            case 'pong':
                break;
            default:
                console.log('Server message:', msg);
        }
    }

    _onTtsEnd() {
        console.log('TTS stream ended');
        this.ui.setStatus('connected');
    }
}

// Start the app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new DreamApp();
    window.app.init().catch(err => {
        console.error('Failed to initialize:', err);
        document.getElementById('status-indicator').textContent = 'Init Error';
    });
});
```

#### 10.2 Write `client/js/ui.js`

```javascript
/**
 * UI Manager — DOM updates, waveform canvas, status indicators.
 */
class UIManager {
    constructor() {
        this.canvas = document.getElementById('waveform-canvas');
        this.ctx = this.canvas?.getContext('2d');
        this.statusEl = document.getElementById('status-indicator');
        this.userTranscriptEl = document.getElementById('user-transcript');
        this.aiTranscriptEl = document.getElementById('ai-transcript');
        this.voiceSelect = document.getElementById('voice-select');
        this.onVoiceChange = null;
        this.animFrame = null;
    }

    init() {
        if (this.voiceSelect) {
            this.voiceSelect.addEventListener('change', () => {
                if (this.onVoiceChange) this.onVoiceChange(this.voiceSelect.value);
            });
        }
        this._resizeCanvas();
        window.addEventListener('resize', () => this._resizeCanvas());
        this._startWaveformAnimation();
    }

    setStatus(status) {
        if (!this.statusEl) return;
        const statusMap = {
            'disconnected': '⚫ Disconnected',
            'connected': '🟢 Connected',
            'speaking': '🟦 Speaking',
            'thinking': '🟡 Thinking',
        };
        this.statusEl.textContent = statusMap[status] || status;
        this.statusEl.className = `status-${status}`;
    }

    updateUserTranscript(text, isInterim = false) {
        if (!this.userTranscriptEl) return;
        this.userTranscriptEl.textContent = isInterim ? `You: ${text}▌` : `You: ${text}`;
    }

    updateTranscript(speaker, text, isInterim = false) {
        if (speaker === 'You' || speaker === 'System') {
            this.updateUserTranscript(text, isInterim);
        } else {
            if (!this.aiTranscriptEl) return;
            this.aiTranscriptEl.textContent = isInterim ? `${speaker}: ${text}▌` : `${speaker}: ${text}`;
        }
    }

    _resizeCanvas() {
        if (!this.canvas) return;
        const rect = this.canvas.parentElement.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
    }

    _startWaveformAnimation() {
        const draw = () => {
            this.animFrame = requestAnimationFrame(draw);
            if (!this.ctx || !this.canvas) return;
            const w = this.canvas.width;
            const h = this.canvas.height;
            this.ctx.clearRect(0, 0, w, h);

            // Draw grid lines
            this.ctx.strokeStyle = '#1a1a2e';
            this.ctx.lineWidth = 1;
            for (let y = h * 0.25; y < h; y += h * 0.25) {
                this.ctx.beginPath();
                this.ctx.moveTo(0, y);
                this.ctx.lineTo(w, y);
                this.ctx.stroke();
            }

            // Draw sample waveform (simple sine visualization for now)
            // In production, this would use actual audio RMS values
            this.ctx.strokeStyle = '#39FF14';
            this.ctx.lineWidth = 2;
            this.ctx.beginPath();
            const now = Date.now() / 1000;
            for (let x = 0; x < w; x++) {
                const y = h / 2 + Math.sin(x * 0.05 + now * 3) * (h * 0.3) * 
                          (0.5 + 0.5 * Math.sin(x * 0.01 + now));
                if (x === 0) this.ctx.moveTo(x, y);
                else this.ctx.lineTo(x, y);
            }
            this.ctx.stroke();
        };
        this._startWaveformAnimation = () => {};  // Prevent double-start
        draw();
    }
}
```

---

### Step 11: Server-Side STT (Whisper Fallback)

**Goal:** Optional server-side transcription for higher accuracy.

#### 11.1 Write `server/stt_client.py`

```python
"""Server-side Speech-to-Text using faster-whisper."""

import logging
import numpy as np
from config import settings

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        try:
            from faster_whisper import WhisperModel
            logger.info(f"Loading Whisper model: {settings.whisper_model_size}")
            _model = WhisperModel(
                settings.whisper_model_size,
                device="cpu",
                compute_type="int8",
            )
            logger.info("Whisper model loaded")
        except ImportError:
            logger.error("faster-whisper not installed. Run: pip install faster-whisper")
            raise
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise
    return _model


async def transcribe(pcm16_bytes: bytes, language: str = "en") -> str:
    """Transcribe PCM16 audio bytes to text using faster-whisper."""
    model = _get_model()

    # Convert PCM16 to float32
    samples = np.frombuffer(pcm16_bytes, dtype=np.int16).astype(np.float32) / 32768.0

    # Run inference in thread pool to avoid blocking event loop
    import asyncio
    loop = asyncio.get_event_loop()
    segments, info = await loop.run_in_executor(
        None,
        lambda: model.transcribe(samples, language=language, beam_size=5)
    )

    result = []
    async for segment in segments:
        result.append(segment.text)

    text = " ".join(result).strip()
    logger.debug(f"Whisper transcription: '{text}'")
    return text
```

---

### Step 12: Waveform Visualizations

**Goal:** Real-time waveform display for mic input and TTS output.

#### 12.1 Update waveform drawing in `ui.js` (or add `visualizer.js`)

Replace the placeholder sine wave with actual PCM16 RMS data:

```javascript
// Inside UIManager — add these methods

/** Draw waveform from PCM16 audio data */
drawWaveform(pcm16Buffer) {
    if (!this.ctx || !this.canvas) return;
    const w = this.canvas.width;
    const h = this.canvas.height;
    this.ctx.clearRect(0, 0, w, h);

    const samples = new Int16Array(pcm16Buffer);
    if (samples.length === 0) return;

    // Downsample to canvas width
    const step = Math.max(1, Math.floor(samples.length / w));
    this.ctx.strokeStyle = '#39FF14';
    this.ctx.lineWidth = 2;
    this.ctx.beginPath();

    for (let x = 0; x < w; x++) {
        const idx = Math.min(x * step, samples.length - 1);
        const normalized = samples[idx] / 32768.0;
        const y = h / 2 + normalized * (h * 0.4);
        if (x === 0) this.ctx.moveTo(x, y);
        else this.ctx.lineTo(x, y);
    }
    this.ctx.stroke();
}

/** Draw bar-style VU meter from RMS value (0.0 to 1.0) */
drawVUMeter(rms) {
    if (!this.ctx || !this.canvas) return;
    const w = this.canvas.width;
    const h = this.canvas.height;
    this.ctx.clearRect(0, 0, w, h);

    const barCount = 40;
    const barWidth = (w - (barCount - 1) * 2) / barCount;
    const activeBars = Math.round(rms * barCount);

    for (let i = 0; i < barCount; i++) {
        const x = i * (barWidth + 2);
        const barHeight = ((i + 1) / barCount) * h;
        this.ctx.fillStyle = i < activeBars ? '#39FF14' : '#1a1a2e';
        this.ctx.fillRect(x, h - barHeight, barWidth, barHeight);
    }
}
```

---

### Step 13: Error Handling & Reconnection

Already built into `WebSocketClient` (exponential backoff reconnect). Add:

1. **Server-side heartbeat**: Send `{"type":"ping"}` from server every 30s
2. **Client timeout**: If no server message for 60s, force reconnect
3. **Graceful degradation**: If VAD fails, fall back to push-to-talk button

#### 13.1 Add heartbeat to `server/main.py`

```python
# Add a background task
@app.on_event("startup")
async def startup():
    asyncio.create_task(_heartbeat_loop())

async def _heartbeat_loop():
    """Send heartbeat to all connected sessions every 30 seconds."""
    while True:
        await asyncio.sleep(30)
        for session_id, session in list(session_manager._sessions.items()):
            try:
                await session_manager._send_json(session, {"type": "ping"})
            except Exception:
                logger.warning(f"Session {session_id} heartbeat failed, removing")
                await session_manager.remove(session_id)
```

---

### Step 14: Client Build & Production Serving

**Goal:** Serve the client app for production.

#### 14.1 Write `scripts/build.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

# The client is static files — "build" means:
# 1. Minify CSS
# 2. Minify JS
# 3. Copy to dist/

cd "$(dirname "$0")/.."
DIST="dist/client"

echo "Building client..."

mkdir -p "$DIST/css" "$DIST/js"

# Minify CSS (requires csso-cli or similar)
if command -v csso &>/dev/null; then
    csso client/css/style.css > "$DIST/css/style.css"
else
    cp client/css/style.css "$DIST/css/style.css"
    echo "  [warn] csso not found, skipping CSS minification"
fi

# Minify JS (requires uglifyjs or terser)
if command -v terser &>/dev/null; then
    for f in client/js/*.js; do
        name=$(basename "$f")
        terser "$f" -c -m > "$DIST/js/$name"
    done
else
    cp -r client/js/* "$DIST/js/"
    echo "  [warn] terser not found, skipping JS minification"
fi

# Copy HTML
cp client/index.html "$DIST/"

echo "Build complete: $DIST/"
```

---

## 5. Testing Strategy

### 5.1 Unit Tests (server/)

| Test File | What it Tests |
|---|---|
| `tests/test_session.py` | Session creation, removal, audio buffer flush, JSON send |
| `tests/test_tts_client.py` | TTS streaming (mock HTTP responses) |
| `tests/test_audio.py` | PCM16 ↔ float32 conversion, RMS calculation |
| `tests/test_websocket.py` | WebSocket message framing, connect/disconnect, protocol |

**Run with:** `cd server && pytest ../tests/ -v`

### 5.2 Integration Tests

#### WebSocket Protocol Test (`tests/test_websocket.py`)
```python
"""WebSocket integration tests."""

import pytest
import json
import asyncio
from httpx_ws import connect_ws

SERVER_URL = "ws://localhost:8765/ws"

@pytest.mark.asyncio
async def test_connect_receive_session():
    async with connect_ws(SERVER_URL) as ws:
        msg = await ws.receive_bytes()
        assert msg[0] == 0x02  # JSON message type
        payload_len = int.from_bytes(msg[1:5], "big")
        payload = json.loads(msg[5:5+payload_len])
        assert payload["type"] == "connected"
        assert "session_id" in payload

@pytest.mark.asyncio
async def test_ping_pong():
    async with connect_ws(SERVER_URL) as ws:
        # Consume initial 'connected' message
        await ws.receive_bytes()
        # Send ping
        ping = b"\x02" + len(json.dumps({"type":"ping"}).encode()).to_bytes(4,"big") + json.dumps({"type":"ping"}).encode()
        await ws.send_bytes(ping)
        # Receive pong
        msg = await ws.receive_bytes()
        assert msg[0] == 0x02
        payload = json.loads(msg[5:])
        assert payload["type"] == "pong"

@pytest.mark.asyncio
async def test_voice_change():
    async with connect_ws(SERVER_URL) as ws:
        await ws.receive_bytes()  # connected
        msg = b"\x02" + len(json.dumps({"type":"set_voice","voice":"mia"}).encode()).to_bytes(4,"big") + json.dumps({"type":"set_voice","voice":"mia"}).encode()
        await ws.send_bytes(msg)
        # No response expected for set_voice, just no crash

@pytest.mark.asyncio
async def test_stt_result_triggers_ai():
    """Send STT result and verify AI thinking response."""
    async with connect_ws(SERVER_URL) as ws:
        await ws.receive_bytes()  # connected
        payload = json.dumps({"type":"stt_result","text":"hello","final":True}).encode()
        msg = b"\x02" + len(payload).to_bytes(4,"big") + payload
        await ws.send_bytes(msg)
        # Should receive ai_thinking message
        resp = await ws.receive_bytes()
        assert resp[0] == 0x02
        data = json.loads(resp[5:])
        assert data["type"] == "ai_thinking"
```

### 5.3 End-to-End Tests

**File: `tests/test_e2e.py`**

```python
"""
End-to-end test: 
1. Connect to server
2. Send STT result
3. Verify AI → TTS pipeline responds with audio
"""

@pytest.mark.asyncio
async def test_full_pipeline():
    async with connect_ws(SERVER_URL) as ws:
        await ws.receive_bytes()  # connected

        # Send STT text
        payload = json.dumps({"type":"stt_result","text":"Hello, how are you?","final":True}).encode()
        await ws.send_bytes(b"\x02" + len(payload).to_bytes(4,"big") + payload)

        # Expect ai_thinking → TTS chunks → TTS end
        audio_chunks = []
        timeout = 30  # seconds
        start = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start < timeout:
            msg = await asyncio.wait_for(ws.receive_bytes(), timeout=5)
            if msg[0] == 0x04:  # Audio chunk
                audio_chunks.append(msg)
            elif msg[0] == 0x05:  # TTS end
                break
            elif msg[0] == 0xFF:  # Error
                pytest.fail(f"Server error: {msg[5:].decode()}")
            # else: continue (JSON messages)

        assert len(audio_chunks) > 0, "Should receive at least one audio chunk"
```

### 5.4 Manual Testing Checklist

- [ ] Open client in Chrome, Firefox, Safari mobile
- [ ] Mic permission prompt appears and is accepted
- [ ] Status indicator shows "Connected" (green)
- [ ] Speaking triggers VAD → "Speaking" status (blue)
- [ ] Silence → "Thinking" status → TTS audio plays
- [ ] TTS audio plays clearly through speakers
- [ ] Voice selector changes voice mid-conversation
- [ ] Disconnect server → client shows "Disconnected" → auto-reconnects
- [ ] Waveform animates during speech and playback
- [ ] Transcript shows both user and AI text
- [ ] Latency is subjectively < 2 seconds

---

## 6. Deployment Instructions

### 6.1 VPS Deployment (Recommended)

**Target:** Ubuntu 22.04+ VPS with Python 3.11+

```bash
# 1. SSH into VPS
ssh user@your-vps-ip

# 2. Install system dependencies
sudo apt update && sudo apt install -y python3.11 python3.11-venv nginx certbot python3-certbot-nginx

# 3. Clone project
git clone https://github.com/your-org/the-dream.git
cd the-dream

# 4. Setup Python
python3.11 -m venv venv
source venv/bin/activate
pip install -r server/requirements.txt

# 5. Configure environment
cp .env.example .env
nano .env
# Set: AI_API_KEY, MIMO_API_KEY, AI_PROVIDER, CYONY_API_URL or ECHO_API_URL

# 6. Test server directly
cd server
python main.py &
# Verify: curl http://localhost:8765/health

# 7. Setup systemd service
sudo nano /etc/systemd/system/thedream.service
```

**File: `/etc/systemd/system/thedream.service`**
```ini
[Unit]
Description=The Dream — Full Duplex Voice Chat Server
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/home/your-user/the-dream/server
EnvironmentFile=/home/your-user/the-dream/.env
ExecStart=/home/your-user/the-dream/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8765
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable thedream
sudo systemctl start thedream
sudo systemctl status thedream
```

### 6.2 Nginx Reverse Proxy (for HTTPS / WSS)

```nginx
# /etc/nginx/sites-available/thedream
server {
    listen 80;
    server_name dream.yourdomain.com;

    # Redirect HTTP → HTTPS
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name dream.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/dream.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/dream.yourdomain.com/privkey.pem;

    # Serve static client files
    root /home/your-user/the-dream/dist/client;
    index index.html;

    # WebSocket proxy
    location /ws {
        proxy_pass http://127.0.0.1:8765/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400;  # 24h for long-lived WS connections
    }

    # Health API
    location /health {
        proxy_pass http://127.0.0.1:8765/health;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/thedream /etc/nginx/sites-enabled/
sudo certbot --nginx -d dream.yourdomain.com
sudo nginx -t && sudo systemctl reload nginx
```

### 6.3 Client Connection URL Update

In `app.js`, the WebSocket URL should point to the production server:

```javascript
// Auto-detect: use same host with wss:// in production
const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
this.ws = new WebSocketClient(`${protocol}//${location.host}/ws`);
```

### 6.4 Docker Deployment (Alternative)

**File: `Dockerfile`**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*

# Server
COPY server/ server/
RUN pip install -r server/requirements.txt

# Client
COPY client/ /var/www/html/
COPY nginx.conf /etc/nginx/sites-enabled/default

EXPOSE 80
CMD service nginx start && uvicorn server.main:app --host 0.0.0.0 --port 8765
```

**File: `docker-compose.yml`**
```yaml
version: '3.8'
services:
  thedream:
    build: .
    ports:
      - "80:80"
    env_file: .env
    restart: unless-stopped
```

---

## 7. Appendix: Key API References

| Resource | URL |
|---|---|
| Silero VAD Web | https://github.com/ricky0123/vad |
| FastAPI WebSockets | https://fastapi.tiangolo.com/advanced/websockets/ |
| Web Audio API | https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API |
| Web Speech API | https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API |
| MiMo TTS API | (Private — refer to API documentation) |
| faster-whisper | https://github.com/SYSTRAN/faster-whisper |

---

## Build Order Summary (Quick Reference)

| # | Step | Est. Time | Test |
|---|---|---|---|
| 1 | Project scaffolding + config + health endpoint | 15 min | `curl /health` |
| 2 | WebSocket protocol + session management | 30 min | `websocat` test |
| 3 | Audio capture & playback (browser) | 30 min | Console logs |
| 4 | VAD integration (browser) | 20 min | Console SPEAKING/SILENCE |
| 5 | WebSocket client + reconnect (browser) | 20 min | Connection status |
| 6 | Browser STT (Web Speech API) | 15 min | Transcript in console |
| 7 | AI client integration (server) | 30 min | AI response text |
| 8 | MiMo TTS client (server) | 20 min | Audio output |
| 9 | Full pipeline wiring (server) | 45 min | End-to-end audio |
| 10 | Main app controller (browser) | 30 min | Full working MVP |
| 11 | Server-side Whisper STT (optional) | 20 min | Transcription accuracy |
| 12 | Waveform visualizations | 30 min | Visual feedback |
| 13 | Error handling + heartbeat | 15 min | Reconnection test |
| 14 | Build + deployment scripts | 30 min | Live deploy |

**Total estimated build time: ~5-6 hours for a skilled developer**

---

*End of Implementation Plan*
