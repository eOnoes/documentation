# The Dream — Implementation Plan Audit Report

> **Audited:** 2026-07-12  
> **Scope:** IMPLEMENTATION_PLAN.md (2234 lines)  
> **Reviewer:** Hermes Agent  
> **Areas:** RTX 4070/VPS feasibility, Security, Latency, Edge Cases, Mobile compatibility

---

## 1. Technical Feasibility (RTX 4070 + VPS)

### Summary: ✅ Feasible with critical fixes

#### RTX 4070 Path (Echo — local AI inference)

| Concern | Finding | Severity |
|---------|---------|----------|
| Whisper on CPU (line 1736) | `device="cpu"` explicitly set despite RTX 4070 availability. GPU inference is 4–10× faster. **Must change to `device="cuda"` with `compute_type="float16"`.** | 🔴 High |
| AI model inference | Echo running on same GPU (e.g., Ollama/vLLM + 7B Q4) is viable: 12GB VRAM handles 7B–13B quantized models at 30–50 tok/s. Fine for sub-2s response. | 🟢 OK |
| GPU memory contention | No coordination between Whisper + AI model sharing VRAM. If both use GPU simultaneously, OOM is possible. Recommend orchestrating staggered GPU usage or routing Whisper to CPU when AI is active. | 🟡 Medium |
| Tailscale overhead (line 155) | `ECHO_API_URL=http://echo.tailscale-ip:8000/v1/chat` adds 20–50ms VPN overhead on every AI call. Acceptable for MVP but note the constraint. | 🟡 Low |

#### VPS Path (Cyony)

| Concern | Finding | Severity |
|---------|---------|----------|
| VPS specs undisclosed | No CPU/RAM/GPU info in plan. Cyony API endpoint assumed but no SLO or scaling info. | 🟡 Medium |
| MiMo TTS dependency | Third-party API — latency, availability, and cost are outside project control. No retry-with-different-voice fallback if MiMo is down. | 🟡 Medium |
| Single-process design | FastAPI + uvicorn single-worker handles exactly one WS connection well, but no mention of `--workers N` or process manager (gunicorn) for multiple users. | 🟡 Low |

#### Overall Architecture

- The sequential pipeline (`buffer → STT → AI → TTS → stream`) is architecturally sound for a single-user MVP.
- Python + FastAPI + plain JS is a reasonable stack — no over-engineering.
- **Missing:** System resource monitoring, crash recovery, log rotation for production.

---

## 2. Security Concerns

### Summary: ⚠️ Several issues, most critical is missing WebSocket auth

#### API Key Handling

| Finding | Severity |
|---------|----------|
| API keys loaded from `.env` (lines 144–158) and passed as Bearer tokens (lines 1168, 1241). Correct pattern. | 🟢 OK |
| **No `.gitignore` content specified** — file listed in structure but never defined. Risk of committing `.env`. | 🟡 Medium |
| `AI_API_KEY` sent to BOTH Echo and Cyony endpoints without validation that the key matches the active provider. If Echo doesn't need a key but one is set, it's still sent in headers. | 🟡 Low |
| API keys appear in logs if debug logging is on. Line 1142 logs the full URL (harmless unless URL embeds credentials). | 🟢 OK |

#### WebSocket Authentication — 🔴 CRITICAL

| Finding | Severity |
|---------|----------|
| **No authentication on `/ws` endpoint** (lines 250–260, 417–441). Anyone with the server address can connect, send audio, and trigger AI calls. | 🔴 **Critical** |
| No token/API-key check at WebSocket connect. No `websocket.headers` verification. | 🔴 Critical |
| No origin validation — `websocket.headers.get("origin")` is never checked. An attacker's webpage can abuse the WebSocket if the user visits it. | 🔴 Critical |
| No rate limiting — an attacker could open 10,000 connections and exhaust server resources. | 🔴 Critical |
| No session cap — `SessionManager` will grow unbounded. | 🟡 Medium |

#### Transport Security

| Finding | Severity |
|---------|----------|
| Default connection uses `ws://` not `wss://` (line 1483: `ws://${location.hostname}:8765/ws`). All audio/text sent in cleartext. | 🔴 Critical |
| Nginx HTTPS/WSS setup documented (section 6.2) but not enforced — the plan says "use wss:// in production" (line 2158) but dev defaults are insecure. | 🟡 Medium |
| Certbot/Let's Encrypt referenced correctly (line 2148). | 🟢 OK |

#### Input Validation

| Finding | Severity |
|---------|----------|
| No JSON schema validation — raw `json.loads()` on every message. Malformed payload could crash handler (partially mitigated by `except Exception` on line 1359). | 🟡 Medium |
| Binary message framing (lines 308–314): no checksum, no message integrity. A corrupt byte could desync the entire stream. | 🟡 Low |
| File path traversal not applicable (no file serving endpoints), but `eval()`/`exec()` not used anywhere. | 🟢 OK |

#### Other

| Finding | Severity |
|---------|----------|
| No `helmet`-style HTTP headers on static file serving. | 🟢 Low |
| CORS middleware not configured on FastAPI (though WebSocket CORS works differently). | 🟡 Low |

---

## 3. Latency Bottlenecks

### Summary: 🔴 The sequential pipeline design will miss the <2s latency target

#### 🔴 High-Impact Bottlenecks

| # | Bottleneck | Location | Impact | Fix |
|---|------------|----------|--------|-----|
| 1 | **Whisper on CPU** | `stt_client.py` line 1736: `device="cpu"` | Adds 1–3s per utterance on CPU vs 100–400ms on GPU | Change to `device="cuda"`, `compute_type="float16"` |
| 2 | **Fully sequential AI → TTS pipeline** | `main.py` lines 1421–1442: waits for complete AI response before starting TTS | Adds AI_full + TTS_latency. For a 50-word response: AI(2s) + TTS(1.5s) = 3.5s total | Implement **chunked streaming**: start TTS on first AI token, stream TTS audio continuously |
| 3 | **No streaming ASR** | Session only flushes on VAD silence (line 1374) | User must finish speaking before processing begins. Adds full utterance length to perceived latency | Use streaming ASR (e.g., Whisper streaming, Deepgram) for partial results |
| 4 | **ScriptProcessorNode** | `audio.js` line 527 | Deprecated, high-latency processing on main thread. Adds ~10–30ms round-trip to audio path | Use `AudioWorklet` for production |

#### 🟡 Medium-Impact Bottlenecks

| # | Bottleneck | Impact | Fix |
|---|------------|--------|-----|
| 5 | HTTP client timeout of 30s (AI) and 60s (TTS) | No early timeout — if MiMo or AI hangs, session blocks for up to 60s | Add per-chunk timeouts (5s between chunks) |
| 6 | No jitter buffer in PCMStreamPlayer | `source.start(nextTime)` scheduling can create audible gaps under network jitter | Implement adaptive jitter buffer with 100–300ms target |
| 7 | Heartbeat every 30s (line 1853) | Unnecessary overhead for single-user MVP | Increase to 60s |
| 8 | Full buffer sent as single STT call | Long utterances (30s+) produce large PCM16 buffers → slow Whisper transcription | Chunk audio and use streaming ASR or split into segments |

#### 🟢 Low

| # | Bottleneck | Impact |
|---|------------|--------|
| 9 | Binary framing overhead (5 bytes per message) | ~0.1% overhead for 4KB audio frames — negligible |
| 10 | Python GIL in httpx streaming | `aiter_bytes()`/`aiter_lines()` release GIL — acceptable |

#### Latency Budget Estimate (Current Design — CPU Whisper)

```
VAD silence detect:  0.2s
Buffer flush + STT:  2.0s (CPU Whisper base, ~3s utterance)
AI inference:        2.0s (7B model, ~50 tokens)
TTS generation:      1.5s (MiMo, ~50 words)
Network RTT:         0.1s
Audio playback:      0.1s (first chunk buffered)
─────────────────────────────
Total:              ~5.9s  (exceeds <2s target by 3×)
```

#### Latency Budget With Fixes (GPU + Chunked Streaming)

```
VAD silence detect:  0.2s
Streaming ASR:       0.5s (first partial result)
AI first token:      0.5s (GPU inference)
TTS first chunk:     0.3s (MiMo streaming)
Network RTT:         0.1s
─────────────────────────────
Total:              ~1.6s  (within <2s target)
```

---

## 4. Missing Edge Cases

### Summary: ⚠️ 15 missing edge cases identified, 3 critical

#### 🔴 Critical Gaps

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 1 | **Barge-in / interrupt** | No mechanism to stop TTS when user starts speaking mid-response. AI will keep processing, audio will overlap. | User experience destroyed — both voices play simultaneously |
| 2 | **Message fragmentation** | Assumes `receive_bytes()` returns complete frames (line 423). WebSocket can fragment large messages; need reassembly buffer. | Can desync the binary protocol, causing data corruption or crashes |
| 3 | **Reconnection state loss** | On reconnect (line 1006), old session is removed and a new blank session created. Conversation history is lost. | User must restart conversation from scratch after any disconnect |

#### 🟡 Medium Gaps

| # | Issue | Impact |
|---|-------|--------|
| 4 | **No idle timeout** — session lives forever if client stays connected silently | Resource leak |
| 5 | **No sample rate validation** — if browser fails to get 16kHz (e.g., mobile Chrome gives 48kHz), audio will be pitch-shifted/garbled | Unusable audio |
| 6 | **Audio buffer no maximum size** — a user speaking for 5 minutes accumulates ~10MB of PCM16. No upper bound on `session.buffer` (line 353) | Memory exhaustion |
| 7 | **No conversation token cap** — `history[-20:]` limits by turn count, not tokens. A conversation with 20 long responses may exceed context window | AI confusion/truncation |
| 8 | **VAD never triggers** — if user is too quiet or background noise is high, `onSpeechEnd` never fires, buffer grows forever | "Hang" state — no response generated |
| 9 | **Empty AI response** — if AI returns empty string, code proceeds to TTS which streams nothing, then `send_tts_end` — client shows no response but status says "speaking" | Confusing UI state |
| 10 | **Model download on first use** — `faster-whisper` downloads model (~1.4GB for base) on first import, blocking the event loop (partially mitigated by `run_in_executor` on line 1759) | 30-60s delay on first transcription |
| 11 | **Graceful VAD fallback undefined** — Step 13 mentions push-to-talk fallback if VAD fails, but no button/UI for it exists | No speaking possible if VAD fails |
| 12 | **STT language hardcoded to 'en'** — `stt.py` line 1749 sets `language="en"`. Non-English speech will fail silently | Bad transcriptions for non-English users |

#### 🟢 Low Gaps

| # | Issue |
|---|-------|
| 13 | Import `transcribe` inside async function (line 1391) works but is non-standard — better at module level |
| 14 | No `MAX_RESPONSE_SIZE` for AI output — very long responses could cause excessive TTS time |
| 15 | `.env` path is hardcoded relative (`{"env_file": ".env"}` on line 227) — fails if server run from a different working directory |

---

## 5. Mobile Compatibility

### Summary: ⚠️ Functional on Android Chrome / iOS Safari with significant caveats

#### 🔴 Critical Issues

| # | Issue | Severity |
|---|-------|----------|
| 1 | **No user gesture to start audio** (line 1525) — `VAD.start()` + `STT.start()` called in `init()`. iOS Safari requires user gesture (tap/click) to start `getUserMedia` and `SpeechRecognition`. On iOS the call will silently fail. | 🔴 Critical |
| 2 | **No audio output routing** — `audioContext.createBufferSource()` outputs to default audio device (earpiece on iOS, not speaker). User holds phone to ear. | 🔴 Critical |
| 3 | **Screen dimming** — no `WakeLock` API request. Screen may lock during VAD listening, killing audio context. | 🔴 Critical |

#### 🟡 Medium Issues

| # | Issue | Impact |
|---|-------|--------|
| 4 | **ScriptProcessorNode deprecated on mobile** — Chrome Android shows warnings, may be removed. Causes extra latency. | Performance/UX |
| 5 | **Sample rate constraint failure** — Mobile Safari may not support `{ sampleRate: 16000 }` in `getUserMedia`. Falls through silently — audio plays at wrong speed. | Broken audio |
| 6 | **VAD CDN bundle size (~2MB)** — noticeable on cellular connections, especially on repeated page loads. | Slow startup |
| 7 | **Battery drain** — continuous VAD + WebSocket + Canvas animation keeps CPU/radio active. No battery-aware mode (e.g., throttle VAD when battery < 20%). | Bad mobile experience |
| 8 | **No PWA / service worker** — no offline fallback, no install-to-homescreen metadata. | Missed mobile engagement |
| 9 | **Bluetooth headset** — no handling of `devicechange` event. If user plugs/unplugs Bluetooth during a call, audio breaks. | Reliability |

#### 🟢 Low Issues

| # | Issue |
|---|-------|
| 10 | Canvas waveform at 80px height (line 761) is small but workable |
| 11 | CSS `max-width: 600px` (line 694) works on mobile but transcript text at `0.9rem` may be small |
| 12 | No `touch-*` event handling — all interactions are click/change which work on mobile |

#### Mobile Browser Compatibility Matrix

| Feature | Chrome Android | Safari iOS | Firefox Android |
|---------|---------------|------------|-----------------|
| Web Audio API | ✅ Full | ✅ Full (needs gesture) | ✅ Full |
| getUserMedia | ✅ | ✅ (needs gesture) | ✅ |
| Web Speech API (STT) | ✅ | ✅ (needs gesture) | ❌ **Not supported** |
| Silero VAD Worklet | ✅ | ✅ | ⚠️ May require polyfill |
| WebSocket | ✅ | ✅ | ✅ |

**Key finding:** Firefox Android users cannot use browser-based STT and would be forced to the (currently undocumented) server-STT fallback path. If server STT also fails (e.g., no Whisper installed), Firefox users cannot use the app at all.

---

## Summary of Findings by Severity

| Severity | Count | Key Actions |
|----------|-------|-------------|
| 🔴 Critical | 9 | Add WebSocket auth, switch Whisper to CUDA, add barge-in handling, fix mobile gesture/earpiece/screen-lock, implement message reassembly, add reconnect state recovery, implement chunked AI→TTS streaming |
| 🟡 Medium | 14 | Add .gitignore, CORS, input validation, jitter buffer, idle timeout, rate limiting, session cap, audio format validation, token budget, VAD fallback UI, grammar for non-default languages, origin check, heartbeat to 60s |
| 🟢 Low | 8 | Module-level imports, max response size, env path, service worker, Bluetooth events, canvas sizing |

**Overall Verdict:** The plan is well-structured for an MVP but has significant issues that would prevent production deployment. The top 3 critical fixes are:

1. **Security:** Add WebSocket authentication and enforce WSS
2. **Latency:** Switch Whisper to GPU and implement chunked AI→TTS streaming  
3. **Mobile:** Add user gesture requirement, audio output routing to speaker, and WakeLock

Without these, the system is insecure (anyone can use your server), too slow (~6s vs <2s target), and broken on iOS.

---

*End of Audit Report*
