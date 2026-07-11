# Tripp.Teacher 🧠

Adaptive AI tutoring system with a 5-gate learning journey.

## Features

- **AI-Powered Chat** — MiMo (mimo-v2.5) backend with offline fallback
- **Adaptive Intake** — Detects topics, asks clarifying questions, builds personalized plans
- **5-Gate Learning** — Understand → Apply → Synthesize → Teach → Advance
- **Research Import** — Upload ZIP files with structured research packs
- **Quiz Engine** — AI-generated quizzes with heuristic fallback
- **Spaced Repetition** — SM-2 algorithm for long-term retention
- **Offline Support** — Full IndexedDB persistence, works without internet
- **Tutor Cockpit** — Analytics, student management, lesson builder

## Quick Start

```bash
# Install dependencies
npm install

# Set up environment
cp .env.example .env
# Edit .env and add your MiMo API key

# Start dev server
npm run dev

# Build for production
npm run build
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `VITE_MIMO_API_KEY` | Yes* | MiMo API key from xiaomimimo.com |

*Without an API key, the app falls back to offline heuristic mode.

## Architecture

```
src/
  pages/
    TrippTeacherApp.tsx    — Main chat interface with inline intake
    TutorCockpit.tsx       — Teaching dashboard
  components/custom/
    IntakePanel.tsx        — Side panel (desktop) for intake flow
    QuizPanel.tsx          — Quiz display and grading
    LessonRenderer.tsx     — Gate content display
    MediaRenderer.tsx      — Mermaid, code, video embeds
    ResearchUpload.tsx     — ZIP research pack import
  lib/
    engines/
      intent-detector.ts   — Topic extraction from natural language
      intake-flow.ts       — Conversational intake state machine
      teaching-engine.ts   — 5-gate course generation
      quiz-engine.ts       — AI + heuristic quiz generation
      research-import.ts   — Research pack parser
      media-engine.ts      — Mermaid, code blocks, video
      offline-manager.ts   — IndexedDB persistence
    mimo.ts                — MiMo chat API integration
    offlineWorker.ts       — Teaching content storage
    progressTracker.ts     — XP, streaks, learning stats
    interest-store.ts      — User interest persistence
    spaced-repetition.ts   — SM-2 review scheduling
```

## Learning Flow

1. **Chat** — User types what they want to learn
2. **Intent Detection** — System extracts topic + confidence
3. **Inline Intake** — Confirmation button + 4 clarifying questions in chat
4. **Plan Generation** — Builds personalized 5-gate journey
5. **Learning** — Gates unlock sequentially with quizzes
6. **Review** — Spaced repetition schedules concept reviews

## Tech Stack

- React 18 + TypeScript
- Vite
- Tailwind CSS
- Framer Motion
- Recharts (analytics)
- Mermaid (diagrams)
- MiMo AI (mimo-v2.5)
- IndexedDB (offline)
