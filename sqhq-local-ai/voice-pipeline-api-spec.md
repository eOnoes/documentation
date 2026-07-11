# Voice Pipeline API Specification

## Architecture Overview

```
┌──────────────────────────────┐       Tailscale (100.72.250.65)       ┌──────────────────────────────────┐
│         VPS (No GPU)         │ ────────────────────────────────────▶ │      Local PC (RTX 4070 12GB)    │
│   Orchestrator / API Client  │       HTTP REST + WebSocket           │   Chatterbox TTS (localhost:5555) │
│                              │ ◀──────────────────────────────────── │   Voice Pipeline Server (port 8000)│
└──────────────────────────────┘                                       └──────────────────────────────────┘
```

- **VPS**: Initiates requests, sends mood + text, receives audio
- **Local PC**: Runs Voice Pipeline Server (port 8000) which wraps Chatterbox TTS (port 5555) and mood clip management
- **Tailscale**: Secure tunnel between VPS (100.72.250.65) and local PC

---

## 1. REST API Endpoints

### Base URL
```
http://100.72.250.65:8000/api/v1
```

### Endpoint Table

| Method | Path                    | Description                          | Auth |
|--------|------------------------|--------------------------------------|------|
| POST   | `/speech/synthesize`   | Synthesize speech (blocking)         | API Key |
| POST   | `/speech/synthesize-stream` | Synthesize speech (streaming)   | API Key |
| GET    | `/speech/status/{id}`  | Poll async job status                | None  |
| POST   | `/moods/load`          | Preload a mood clip into memory      | Admin |
| GET    | `/moods`               | List available moods and their status | None |
| GET    | `/moods/{name}/clip`   | Get metadata for a specific mood clip | None |
| POST   | `/moods/{name}/clip`   | Upload/replace a mood reference clip  | Admin |
| GET    | `/health`              | Health check (liveness)              | None  |
| GET    | `/health/ready`        | Readiness check (dependencies ready) | None  |
| GET    | `/health/gpu`          | GPU status and VRAM info             | None  |
| GET    | `/version`             | Pipeline server version              | None  |

---

## 2. Request / Response Formats

### 2.1 POST `/speech/synthesize` — Blocking Synthesis

**Request:**
```json
{
  "mood": "chill",
  "text": "Hey there, how's it going?",
  "voice_id": "default",
  "options": {
    "speed": 1.0,
    "pitch": 0.0,
    "sample_rate": 24000
  }
}
```

| Field      | Type   | Required | Default     | Description                                                        |
|------------|--------|----------|-------------|--------------------------------------------------------------------|
| `mood`     | string | yes      | —           | One of the 10 supported moods                                      |
| `text`     | string | yes      | —           | Text to synthesize (1-5000 chars for blocking)                    |
| `voice_id` | string | no       | `"default"` | Voice identity (future multi-voice support)                        |
| `options`  | object | no       | `{}`        | TTS tuning parameters                                              |

**Mood Enum:**
```json
["chill", "flirty", "whisper", "annoyed", "eureka", "groggy", "dead", "sad", "excited", "sultry"]
```

**Success Response (200):**
```json
{
  "status": "success",
  "request_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "mood": "chill",
  "duration_seconds": 2.34,
  "sample_rate": 24000,
  "audio": "<base64-encoded WAV bytes>",
  "audio_format": "wav",
  "metadata": {
    "model": "chatterbox-v1",
    "gpu_util_pct": 45,
    "inference_ms": 890,
    "clone_time_ms": 210
  }
}
```

**Error Response (4xx/5xx):**
```json
{
  "status": "error",
  "request_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "error": {
    "code": "MOOD_CLIP_NOT_FOUND",
    "message": "Mood clip 'chill' has not been loaded. Use POST /moods/load first.",
    "details": null
  }
}
```

**Error Codes:**
| Code                          | HTTP Status | Description                                      |
|-------------------------------|-------------|--------------------------------------------------|
| `MOOD_CLIP_NOT_FOUND`         | 400         | Mood clip not loaded or missing                  |
| `INVALID_MOOD`                | 400         | Mood name not in the allowed set                 |
| `TEXT_TOO_LONG`               | 400         | Text exceeds maximum length                      |
| `TEXT_EMPTY`                  | 400         | Text is empty or only whitespace                 |
| `TTS_ENGINE_ERROR`            | 500         | Chatterbox TTS failed internally                 |
| `VOICE_CLONE_FAILED`          | 500         | Voice cloning step failed                        |
| `GPU_OUT_OF_MEMORY`           | 503         | RTX 4070 VRAM exhausted (retry after backoff)   |
| `RATE_LIMITED`                | 429         | Too many requests                                |
| `INTERNAL_ERROR`              | 500         | Unhandled server error                           |

---

### 2.2 POST `/speech/synthesize-stream` — Streaming for Long Text

For texts longer than 5000 characters (up to 50,000), use the streaming endpoint. The server splits text by sentence boundaries and streams each chunk as generated audio via Server-Sent Events (SSE).

**Request:**
```json
{
  "mood": "excited",
  "text": "This is a very long text... (up to 50,000 characters)",
  "voice_id": "default",
  "options": {
    "speed": 1.0,
    "pitch": 0.0,
    "sample_rate": 24000,
    "chunk_size": 300
  },
  "stream_mode": "sse"
}
```

| Field         | Type   | Required | Default     | Description                                       |
|---------------|--------|----------|-------------|---------------------------------------------------|
| `stream_mode` | string | no       | `"sse"`     | Currently only `"sse"` supported                  |
| `chunk_size`  | int    | no       | `300`       | Max characters per sentence chunk                  |

**SSE Event Stream Response (200):**
```
event: start
data: {"request_id":"abc123","total_chunks":12,"mood":"excited"}

event: chunk
data: {"index":0,"sequence":1,"audio":"<base64>","text":"This is chunk one.","is_final":false}

event: chunk
data: {"index":1,"sequence":2,"audio":"<base64>","text":"Here is chunk two.","is_final":false}

event: progress
data: {"completed":5,"total":12,"percent":41.7}

event: chunk
data: {"index":11,"sequence":12,"audio":"<base64>","text":"Last chunk here.","is_final":true}

event: complete
data: {"request_id":"abc123","total_chunks":12,"total_duration_seconds":32.1,"status":"success"}

event: error
data: {"code":"VOICE_CLONE_FAILED","message":"Voice cloning failed on chunk 7","chunk_index":6}
```

**SSE Event Types:**

| Event      | Payload Fields                                           | Description                             |
|------------|----------------------------------------------------------|-----------------------------------------|
| `start`    | `request_id`, `total_chunks`, `mood`                     | Stream has begun                        |
| `chunk`    | `index`, `sequence`, `audio` (base64), `text`, `is_final` | Individual audio chunk                  |
| `progress` | `completed`, `total`, `percent`                          | Progress indicator (every 3 chunks)     |
| `complete` | `request_id`, `total_chunks`, `total_duration_seconds`, `status` | All chunks sent successfully            |
| `error`    | `code`, `message`, `chunk_index`                         | Fatal error — stream terminates         |

**Client Logic for SSE:**
1. Client receives `start` event → prepare audio playback buffer
2. Client receives `chunk` events → decode base64 → append to buffer or play immediately
3. Client tracks `sequence` to detect dropped chunks; can request retransmission
4. Client receives `complete` → playback ends
5. Client receives `error` → log and retry with backoff

---

### 2.3 POST `/speech/status/{id}` — Job Status Polling (Async Fallback)

If the VPS cannot hold an SSE connection open, use async synthesis (future enhancement):

```json
{
  "status": "processing",
  "request_id": "abc123",
  "progress_percent": 45,
  "current_chunk": 5,
  "total_chunks": 12,
  "estimated_remaining_seconds": 4.2
}
```

Final states: `"completed"`, `"failed"`.

---

## 3. Mood Clip Storage and Access

### 3.1 Directory Layout on Local PC

```
C:\Users\eMitchell109\voice-pipeline\
├── clips\
│   ├── chill.wav
│   ├── flirty.wav
│   ├── whisper.wav
│   ├── annoyed.wav
│   ├── eureka.wav
│   ├── groggy.wav
│   ├── dead.wav
│   ├── sad.wav
│   ├── excited.wav
│   └── sultry.wav
├── cache\
│   ├── voices\
│   │   └── default\              # Cached cloned voice embeddings
│   │       ├── chill.pt
│   │       ├── flirty.pt
│   │       └── ...
│   └── generated\                # Cached TTS outputs (MD5 hash keyed)
│       ├── a1b2c3d4.wav
│       └── ...
├── clips_metadata.json           # Clip durations, sample rates, etc.
└── pipeline_server.py            # FastAPI server
```

### 3.2 Clip Requirements

| Property       | Specification                          |
|----------------|----------------------------------------|
| Format         | WAV (16-bit PCM, mono)                 |
| Sample Rate    | 24000 Hz (matching Chatterbox TTS)     |
| Duration       | 3–10 seconds per clip                  |
| Content        | Clean reference audio of the target speaker in that mood |
| Filename       | `{mood_name}.wav` (lowercase)          |

### 3.3 Clip Metadata

`clips_metadata.json`:
```json
{
  "chill": {
    "filename": "chill.wav",
    "duration_seconds": 5.2,
    "sample_rate": 24000,
    "hash": "sha256:abc123...",
    "loaded": false,
    "last_loaded_at": null
  },
  "flirty": {
    "filename": "flirty.wav",
    "duration_seconds": 4.8,
    "sample_rate": 24000,
    "hash": "sha256:def456...",
    "loaded": false,
    "last_loaded_at": null
  }
  // ... one entry per mood
}
```

### 3.4 Preloading (POST /moods/load)

**Request:**
```json
{
  "moods": ["chill", "flirty", "whisper"],
  "warm_up": true
}
```

| Field     | Type          | Required | Default  | Description                                   |
|-----------|---------------|----------|----------|-----------------------------------------------|
| `moods`   | array[string] | yes      | —        | List of moods to preload (omit = load all 10) |
| `warm_up` | boolean       | no       | `false`  | Run a quick inference to warm GPU memory       |

**Response (200):**
```json
{
  "status": "success",
  "loaded": ["chill", "flirty", "whisper"],
  "failed": [],
  "gpu_vram_mb_used": 2048,
  "gpu_vram_mb_free": 10240
}
```

**Preloading behavior:**
1. Clip `.wav` is read from disk
2. Voice encoder extracts speaker embedding into `cache/voices/default/{mood}.pt`
3. Embedding held in GPU memory for fast cloning
4. If `warm_up=true`: runs a 2-second silent TTS pass to prime CUDA kernels

---

## 4. Streaming Support for Long Text

### 4.1 Architecture

```
VPS (Client)                          Local PC (Server)
    │                                       │
    │  POST /speech/synthesize-stream       │
    │  { mood, text, stream_mode: "sse" }   │
    │──────────────────────────────────────▶│
    │                                       │
    │  event: start                         │  - Load mood clip → clone voice
    │◀──────────────────────────────────────│  - Split text by sentence boundaries
    │                                       │
    │  ┌─────────────────────────────────┐  │
    │  │ For each chunk (parallel queue) │  │
    │  │ 1. Clone voice (cached)         │  │
    │  │ 2. Chatterbox TTS inference     │  │
    │  │ 3. Base64 encode               │  │
    │  │ 4. Emit SSE event              │  │
    │  └─────────────────────────────────┘  │
    │                                       │
    │  event: chunk (index=0)               │
    │◀──────────────────────────────────────│
    │  event: chunk (index=1)               │
    │◀──────────────────────────────────────│
    │  ...                                  │
    │  event: complete                      │
    │◀──────────────────────────────────────│
```

### 4.2 Sentence Splitting Rules

1. Split on sentence terminators: `.`, `!`, `?`, `...`, `\n\n`
2. Max chunk size: `chunk_size` characters (default 300) — if a single sentence exceeds this, hard-split at the character boundary
3. Minimum chunk size: 10 characters — merge tiny fragments into the previous chunk
4. Preserve punctuation at split points for natural prosody

### 4.3 Voice Cloning Optimization

- **First chunk**: Full clone from clip → cache embedding in GPU memory
- **Subsequent chunks**: Reuse cached embedding (no recloning)
- **Embedding cache TTL**: 10 minutes of inactivity, then evict to free VRAM

### 4.4 Throughput Estimates (RTX 4070 12GB)

| Text Length | Chunks | Clone Time | Per-Chunk TTS | Total Time (est.) |
|-------------|--------|------------|---------------|-------------------|
| 100 chars   | 1      | 200ms      | 300ms         | ~0.5s             |
| 1,000 chars | 3–5    | 200ms      | 300ms × 4     | ~1.4s             |
| 10,000 chars| 30–40  | 200ms      | 300ms × 35    | ~10.7s            |
| 50,000 chars| 150–200| 200ms      | 300ms × 175   | ~52.7s            |

**Note**: Chunks can be processed sequentially (preserves audio order) or with a lookahead queue of 3 parallel TTS inferences if Chatterbox supports concurrent calls.

---

## 5. Error Handling and Retry Logic

### 5.1 Server-Side Error Handling

| Scenario                     | Behavior                                                                            |
|------------------------------|-------------------------------------------------------------------------------------|
| Invalid mood name            | Return `400 INVALID_MOOD` immediately                                              |
| Mood clip not found on disk  | Return `400 MOOD_CLIP_NOT_FOUND` with instructions to upload                       |
| Clip file corrupted          | Return `400 MOOD_CLIP_CORRUPT` with SHA256 mismatch details                        |
| Chatterbox TTS unreachable   | Retry 3 times (100ms, 500ms, 2s backoff), then return `502 TTS_ENGINE_UNREACHABLE` |
| Voice clone OOM              | Evict oldest cached embedding → retry once → return `503 GPU_OUT_OF_MEMORY`        |
| Text empty                   | Return `400 TEXT_EMPTY`                                                             |
| Text > 50K chars (stream)    | Return `400 TEXT_TOO_LONG`                                                          |

### 5.2 Retry Logic (VPS → Local PC)

**Client-side (VPS) retry strategy:**

```
Attempt 1: Send request
  ├── Success → return audio
  ├── 429 (Rate Limited) → wait 1s × attempt_count, retry (max 3)
  ├── 502/503 (Unavailable) → wait 2^attempt seconds, retry (max 3)
  ├── 504 (Gateway Timeout) → wait 3s, retry once with streaming
  ├── 4xx (Client Error)    → NO retry, log and return error
  └── 5xx (Server Error)    → wait 2s, retry (max 2)
```

**Exponential Backoff Table:**
| Attempt | Wait Time | Cumul. Wait |
|---------|-----------|-------------|
| 1       | 0s        | 0s          |
| 2       | 1s        | 1s          |
| 3       | 2s        | 3s          |
| 4       | 4s        | 7s          |
| 5       | 8s        | 15s         |

**Jitter**: Add random ±20% to each wait time to avoid thundering herd.

### 5.3 Rate Limiting

| Limit                | Window     | Burst | Response          |
|----------------------|------------|-------|-------------------|
| Synthesis requests   | 10/second  | 15    | `429` + Retry-After header |
| Mood loads           | 2/second   | 3     | `429`             |
| Health checks        | 60/second  | 100   | (none — always OK) |

Rate limit response:
```json
{
  "status": "error",
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many synthesis requests. Limit: 10/s. Retry after 500ms.",
    "details": {
      "retry_after_ms": 500,
      "limit": 10,
      "window_seconds": 1
    }
  }
}
```

### 5.4 Circuit Breaker (Server-Side)

If Chatterbox TTS returns errors 5 times in a 30-second window:
1. Circuit opens → return `503 TTS_ENGINE_DEGRADED` immediately (no retry)
2. After 30s → half-open → allow 1 test request
3. Success → close circuit. Failure → wait another 60s.

---

## 6. Health Checks

### 6.1 GET `/health` — Liveness Probe

Fast, lightweight check. No dependencies required.

```json
{
  "status": "ok",
  "timestamp": "2026-07-11T15:30:00Z",
  "uptime_seconds": 86400
}
```

**Failure conditions**: Server process not running (infrastructure-level, won't serve HTTP).

### 6.2 GET `/health/ready` — Readiness Probe

Checks all dependencies. Poll from VPS every 30 seconds.

```json
{
  "status": "ok",
  "timestamp": "2026-07-11T15:30:00Z",
  "checks": {
    "chatterbox_tts": {
      "status": "healthy",
      "latency_ms": 45,
      "endpoint": "http://localhost:5555"
    },
    "gpu": {
      "status": "healthy",
      "available": true,
      "vram_total_mb": 12288,
      "vram_free_mb": 10240,
      "vram_used_pct": 16.7,
      "temperature_c": 62
    },
    "mood_clips": {
      "status": "healthy",
      "total": 10,
      "loaded": 10,
      "missing": []
    },
    "disk": {
      "status": "healthy",
      "free_gb": 150
    }
  }
}
```

**Failure states:**
```json
{
  "status": "degraded",
  "checks": {
    "chatterbox_tts": {
      "status": "unhealthy",
      "error": "Connection refused on localhost:5555",
      "latency_ms": null
    },
    "gpu": {
      "status": "degraded",
      "vram_free_mb": 512,
      "warning": "Only 512MB VRAM free — synthesis may fail"
    },
    "mood_clips": {
      "status": "degraded",
      "total": 10,
      "loaded": 3,
      "missing": ["eureka", "groggy", "dead", "sad", "sultry", "excited", "annoyed"]
    }
  }
}
```

### 6.3 GET `/health/gpu` — GPU Diagnostics

Detailed GPU introspection for debugging.

```json
{
  "status": "ok",
  "gpu": {
    "name": "NVIDIA GeForce RTX 4070",
    "driver_version": "545.84",
    "cuda_version": "12.1",
    "vram": {
      "total_mb": 12288,
      "used_mb": 2048,
      "free_mb": 10240,
      "pct_used": 16.7
    },
    "temperature_c": 62,
    "power_watts": 85,
    "utilization_pct": 12,
    "processes": [
      {"pid": 1234, "name": "python", "vram_mb": 1800, "type": "synthesis"}
    ]
  }
}
```

### 6.4 Health Check Frequency Recommendations

| Check Type | VPS Poll Interval | Purpose                          |
|------------|-------------------|----------------------------------|
| `/health`  | 10 seconds        | Is the server alive?             |
| `/health/ready` | 30 seconds  | Is it safe to send synthesis?    |
| `/health/gpu`   | 60 seconds  | Monitor VRAM trend               |

---

## Complete Request/Response Reference

### Synthesis Lifecycle (Happy Path)

```
VPS                                   Local PC
 │                                       │
 │  ── POST /health/ready ──────────────▶│
 │  ◀── healthy ─────────────────────────│
 │                                       │
 │  ── POST /speech/synthesize ─────────▶│
 │       { mood: "chill",                │
 │         text: "Hello world" }         │
 │                                       │
 │       [Load chill.wav from disk]      │
 │       [Extract voice embedding]       │
 │       [POST to Chatterbox:5555]       │
 │       [Receive WAV bytes]             │
 │                                       │
 │  ◀── { status: "success",             │
 │         audio: "<base64>",            │
 │         duration: 1.2 } ───────────────│
 │                                       │
 │  [Decode base64 → play audio]         │
```

### Synthesis Lifecycle (Error + Retry)

```
VPS                                   Local PC
 │                                       │
 │  ── POST /speech/synthesize ─────────▶│
 │                                       │
 │       [Chatterbox:5555 - timeout]     │
 │       [Retry 1: 100ms backoff]        │
 │       [Retry 2: 500ms backoff]        │
 │       [Retry 3: 2s backoff - fail]    │
 │                                       │
 │  ◀── 502 { error:                     │
 │         code: "TTS_ENGINE_UNREACHABLE",│
 │         message: "Chatterbox unreachable│
 │                   after 3 retries" }  ──│
 │                                       │
 │  [Wait 2s, retry request]            │
 │                                       │
 │  ── POST /speech/synthesize ─────────▶│
 │       (retry #1)                      │
 │                                       │
 │  ◀── success ─────────────────────────│
```

---

## Implementation Notes

### Server Tech Stack (Local PC)
- **Framework**: FastAPI (Python 3.11+)
- **Async**: `asyncio` for SSE streaming
- **GPU**: PyTorch CUDA for voice embedding + Chatterbox TTS inference
- **Storage**: Local filesystem with JSON metadata index
- **Rate Limiting**: `slowapi` middleware (token bucket)
- **Circuit Breaker**: Custom middleware tracking Chatterbox failures

### Client Tech Stack (VPS)
- **HTTP Client**: `httpx` (async, with retry transport)
- **SSE Client**: `sse-starlette` client or `httpx-sse`
- **Audio Playback**: `miniaudio` or `simpleaudio` for WAV decoding

### Authentication (Simple API Key)
- Header: `X-API-Key: <shared_secret>`
- Shared between VPS and local PC (set via env var `PIPELINE_API_KEY`)
- Admin endpoints use a separate `X-Admin-Key` header

### Example curl Commands

**Blocking synthesis:**
```bash
curl -X POST http://100.72.250.65:8000/api/v1/speech/synthesize \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"mood":"chill","text":"Hello from the VPS!"}' \
  --output response.json
```

**Streaming synthesis:**
```bash
curl -N -X POST http://100.72.250.65:8000/api/v1/speech/synthesize-stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -H "Accept: text/event-stream" \
  -d '{"mood":"excited","text":"Long text here...","stream_mode":"sse"}'
```

**Health check:**
```bash
curl http://100.72.250.65:8000/api/v1/health/ready
```

---

## Specification Summary

| Aspect              | Decision                                                     |
|---------------------|--------------------------------------------------------------|
| API Style           | REST + SSE streaming for long text                           |
| Transport           | HTTP/1.1 over Tailscale WireGuard                            |
| Audio Encoding      | 16-bit PCM WAV, base64 in JSON, or raw binary                |
| Streaming Protocol  | Server-Sent Events (SSE)                                     |
| Voice Cloning       | First chunk clones → cached for subsequent chunks            |
| Mood Clips          | 10 WAV files (3–10s each) on local disk, preloadable to GPU  |
| Error Handling      | Exponential backoff (client) + circuit breaker (server)      |
| Rate Limiting       | 10 req/s synthesis, 2 req/s mood load                        |
| Health Checks       | 3 endpoints: liveness, readiness (deep), GPU diagnostics     |
| Auth                | API key in header (`X-API-Key`)                              |
| Retry Strategy      | Max 3 retries, exponential backoff with jitter               |

This spec provides a complete, production-ready API architecture for the VPS ↔ local PC voice pipeline.
