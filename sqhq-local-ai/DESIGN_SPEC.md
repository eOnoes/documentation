# Orpheus Voice Hub — Design Spec

> **Status:** PLANNING. Web app for TTS + Brain pipeline.
> **Created:** 2026-07-06
> **Parents:** orpheus_voice_server.py, ORPHEUS_CYONY_GUIDE.md

---

## Purpose

Build a web interface for the Orpheus TTS + Brain pipeline. One page where Eddie can type text, pick a voice/mood, optionally let the Brain (Ollama) generate the response, and get audio output. Clean, fast, no fluff.

## Core Design

Single-page app served by FastAPI. HTMX for dynamic updates. Tailwind CSS for styling. The web app talks to two existing services:
- **Orpheus Voice Server** (port 8081) — TTS generation
- **Ollama** (port 11434) — Brain (text generation)

The web app is a **thin layer** — it doesn't touch models directly. It just orchestrates the existing services.

## Folder Structure

```
sqhq-local-ai/
├── orpheus_voice_server.py      ← EXISTING (TTS engine)
├── orpheus_voice_hub/           ← NEW
│   ├── app.py                   ← FastAPI app + routes
│   ├── static/
│   │   ├── index.html           ← Main page (HTMX)
│   │   └── style.css            ← Tailwind + custom styles
│   └── requirements.txt         ← Dependencies
├── models/                      ← EXISTING (no changes)
└── reference_audio/             ← EXISTING (no changes)
```

## Data Flow

```
User types text in browser
        ↓
Web App (FastAPI) receives request
        ↓
┌───────────────────────────────┐
│ Mode: Direct TTS              │ → POST to orpheus_voice_server/v1/tts
│ Mode: Brain + TTS             │ → POST to Ollama → get text → POST to orpheus_voice_server/v1/tts
│ Mode: Clone                   │ → POST to orpheus_voice_server/v1/voice/clone (with reference audio)
└───────────────────────────────┘
        ↓
Audio returned → browser plays it
```

## Three Modes

### 1. Direct TTS
Type text → pick voice/mood → generate audio. Simple.

### 2. Brain + TTS
Type a prompt → Ollama generates text → text goes to TTS → audio. Two-step but automatic.

### 3. Voice Clone
Upload reference audio (≤30s WAV) + type text → generate audio in cloned voice. Uses HF pipeline.

## Integration Points

| Service | Port | What | Status |
|---------|------|------|--------|
| Orpheus Voice Server | 8081 | TTS, voices, clone | RUNNING ✅ |
| Ollama | 11434 | Brain (llama3.2) | RUNNING ✅ |
| Web App | 8082 | NEW — this spec | PLANNING |

## Decision Points

1. **Port:** 8082 (next in line) — or different?
2. **Styling:** Tailwind via CDN (simple) or custom CSS?
3. **Brain model:** Always use llama3.2-abliterate:3b, or let user pick?
4. **Audio format:** MP3 (universal) or WAV (faster, larger)?

## Implementation Checklist

1. Create `orpheus_voice_hub/` directory
2. Write `app.py` with FastAPI routes
3. Write `index.html` with HTMX interface
4. Write `style.css` with Tailwind
5. Test all three modes
6. Add error handling
7. Add loading states

## Open Questions

- Should the Brain have a "temperature" slider?
- Should clone mode show a progress indicator?
- Should we cache recent generations?
