# The Dream — Full Duplex Voice Chat System

## Vision
Build a real-time, full-duplex voice chat system that lets Eddie talk to Echo/Cyony naturally — like a phone call, not a walkie-talkie. Hands-free, streaming audio, minimal latency.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    EDDIE'S BROWSER                           │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ Mic Input │───▶│   STT    │───▶│ WebSocket│───▶ SERVER   │
│  └──────────┘    └──────────┘    └──────────┘              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │  Speaker │◀───│   TTS    │◀───│ WebSocket│◀── SERVER    │
│  └──────────┘    └──────────┘    └──────────┘              │
│                                                             │
│  ┌──────────────────────────────────────────┐              │
│  │  VAD (Voice Activity Detection)          │              │
│  │  - Detects when Eddie starts/stops talking│              │
│  │  - Enables hands-free operation          │              │
│  └──────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
                          │
                    ══════▼══════
                    │  WEBSOCKET │
                    ══════▲══════
                          │
┌─────────────────────────────────────────────────────────────┐
│                    VPS (Cyony/Echo)                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ WebSocket│───▶│   AI     │───▶│ MiMo TTS │              │
│  │ Server   │◀───│ (Cyony)  │◀───│ Streaming│              │
│  └──────────┘    └──────────┘    └──────────┘              │
│                                                             │
│  ┌──────────────────────────────────────────┐              │
│  │  Session Management                      │              │
│  │  - Track active connections              │              │
│  │  - Route to Echo or Cyony                │              │
│  │  - Handle disconnects gracefully         │              │
│  └──────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

## Tech Stack

### Frontend (Browser)
- **Web Audio API**: Capture mic audio, play streaming audio
- **WebSocket**: Bidirectional communication with server
- **VAD**: Voice Activity Detection (browser-based, e.g., @ricky0195/vad-web or similar)
- **UI**: Simple, dark theme (#0a0a0a/#121212/#39FF14)

### Backend (VPS)
- **WebSocket Server**: Python (FastAPI + WebSockets) or Node.js
- **AI Integration**: Route to Cyony (VPS) or Echo (local PC via Tailscale)
- **TTS**: MiMo TTS API (streaming with built-in voices)
- **STT**: Option A: Browser-based Whisper (faster), Option B: Server-side (more accurate)

## Key Features

### 1. Hands-Free Operation
- VAD detects when Eddie stops talking
- Automatically sends transcript to AI
- Streams TTS response back
- No buttons to press (unless push-to-talk mode)

### 2. Streaming Audio
- MiMo TTS streams PCM16 chunks
- Browser plays chunks as they arrive
- Perceived latency: <1 second

### 3. Voice Selection
- Built-in voices: Milo (male), Dean (male deep), Mia (female), Chloe (female)
- Eddie can switch voices mid-conversation
- Future: Voice cloning support

### 4. Visual Feedback
- Waveform visualization when listening
- Waveform visualization when speaking
- Connection status indicator
- Current voice/character display

## Implementation Phases

### Phase 1: Core (MVP)
- [ ] WebSocket server on VPS
- [ ] Browser client with mic capture
- [ ] Basic STT → AI → TTS pipeline
- [ ] Streaming TTS playback
- [ ] Simple UI

### Phase 2: Polish
- [ ] VAD for hands-free
- [ ] Waveform visualizations
- [ ] Voice switching
- [ ] Error handling & reconnection
- [ ] Mobile responsive

### Phase 3: Advanced
- [ ] Multi-user support (Eddie + others)
- [ ] Custom personas per voice
- [ ] Conversation history
- [ ] Voice cloning integration

## Constraints
- **12GB GPU local**: Can't run heavy local models
- **MiMo TTS**: Cloud API, fast, streaming support
- **Tailscale**: VPS ↔ PC communication
- **Brand Colors**: #0a0a0a, #121212, #39FF14

## Success Criteria
- Eddie can talk to Echo/Cyony naturally
- Response latency < 2 seconds (perceived)
- Works on mobile browser
- No buttons required (hands-free)
- Stable connection (auto-reconnect)
