# Tripp.Teacher — Completion Plan

**Audit Date:** June 26, 2026
**Total Source Files:** 76 (src/), 5 engines, 6 custom components, 4 pages, 45 UI components
**Stack:** React 19, TypeScript 5.9, Vite 7, Tailwind 3, Three.js, Mermaid, shadcn/ui

---

## 1. What Is Complete and Working

### Core Architecture ✅
- **Routing** — HashRouter with 3 routes: `/` (Chat), `/cockpit` (Dashboard), `*` (404)
- **Type System** — Comprehensive types for gates, intents, sessions, quizzes, profiles, offline packs, chat messages, review cards (201 lines, well-structured)
- **CSS/Theme** — Dark-first design with cyan-500 primary, glassmorphism, custom scrollbar, CSS variables for shadcn, `tailwind.config.js` fully configured

### Pages ✅

| Page | Status | Lines | Notes |
|------|--------|-------|-------|
| **TrippTeacherApp** | Complete | 835 | Full chat interface, sidebar, intake flow, research upload, keyboard shortcuts, smart scroll, focus mode |
| **TutorCockpit** | Complete | 998 | Gate navigation, content/media/quiz tabs, offline export, progress tracking, demo node generation |
| **NotFound** | Complete | 38 | Clean 404 with motion animation |
| **Home** | Dead code | 20 | Vite boilerplate counter — NOT routed anywhere, not used |

### Custom Components ✅

| Component | Status | Lines | Notes |
|-----------|--------|-------|-------|
| **CodeTunnel** | Complete | 367 | Three.js particle tunnel, mouse-reactive, focus mode blur, proper cleanup |
| **IntakePanel** | Complete | 453 | Full intake UI: detected/clarifying/building/ready/error states, progress bar, skip |
| **MediaRenderer** | Complete | 348 | Mermaid diagrams, video embeds, code blocks, images, error states, copy-to-clipboard |
| **QuizPanel** | Complete | 450 | Multiple question types, confidence rating, results with focus areas, mistake breakdown |
| **ResearchUpload** | Complete | 404 | ZIP drag-and-drop, JSZip parsing, preview with stats, lesson generation |
| **OfflineIndicator** | Complete | 246 | Network status pill, dropdown with sync controls, offline capability listing |

### Engines (Business Logic) ✅

| Engine | Status | Lines | Notes |
|--------|--------|-------|-------|
| **intent-detector** | Complete | 469 | 15+ regex patterns, stopwords list (100+), TECH indicators, scoring system, NLP-grade heuristic extraction |
| **intake-flow** | Complete | 355 | Full state machine (idle→detected→clarifying→building→ready→error), choice parsing, timeout handling |
| **media-engine** | Complete | 262 | Mermaid templates (7 types), YouTube/Vimeo embed conversion, media caching |
| **quiz-engine** | Complete | 409 | Quiz generation from content, 5 question types, heuristic grading, Jaccard similarity, mistake classification |
| **offline-manager** | Complete | 368 | IndexedDB with 4 stores, localStorage fallback, sync simulation, JSON export/import |
| **research-import** | Complete | 609 | ZIP parsing, markdown dimension parser, 5-gate lesson converter, concept map diagram generator |

### UI Components ✅
- 45 shadcn/ui components in `src/components/ui/` (accordion through toggle-group)
- Standard shadcn library — all appear complete and functional

### Infrastructure ✅
- `vite.config.ts` — alias `@` → `./src`, port 3000, kimi-plugin-inspect-react
- `tsconfig.json` — path aliases configured, separate app/node configs
- `tailwind.config.js` — Full shadcn theme, animations, sidebar tokens
- `index.css` — CSS variables, glassmorphism utilities, animation delays

---

## 2. What Is Missing or Broken

### 🔴 Critical Issues

#### 2.1 No Real AI Backend
**Impact:** The entire chat is simulated with `generateResponse()` — a 40-line function with canned responses.
- `generateResponse()` (line 808-835 of TrippTeacherApp.tsx) returns random generic strings
- Quiz generation is purely heuristic (no AI enhancement)
- No API keys, no backend URL, no `.env` file
- The `isLearningQuery` → `detectIntent` flow works locally, but there's no AI to actually build lessons

**What's needed:** OpenAI/Anthropic API integration or a backend service for:
- Real conversational AI responses
- AI-enhanced quiz generation
- Intelligent content generation per gate
- Personalized lesson adaptation

#### 2.2 No Authentication / User Management
- `LearnerProfile` type exists but is hardcoded as `getDefaultProfile()` (line 783-798)
- No login, no user accounts, no profile persistence
- No Supabase/Firebase/backend integration
- `profile` state is `const [profile] = useState<LearnerProfile>(getDefaultProfile())` — never updated

#### 2.3 No Data Persistence Layer
- All state lives in `useState` — lost on page refresh
- `localStorage` is used for topic transfer between Chat→Cockpit, but:
  - No actual data persistence for user progress
  - IndexedDB exists in offline-manager but only used for offline packs and quiz attempts
  - No database for user accounts, sessions, learning history

#### 2.4 Dead Code: Home.tsx
- `src/pages/Home.tsx` is a Vite boilerplate counter component
- Never imported or routed — pure dead code
- Also imports `App.css` which is the Vite default CSS (should be removed)

### 🟡 Medium Issues

#### 2.5 App.css is Vite Default
- `src/App.css` contains Vite boilerplate styles (`logo-spin`, `.card`, `.read-the-docs`)
- `Home.tsx` imports it, but nothing else does
- Should be deleted entirely

#### 2.6 `@types/three` vs `three` Version Mismatch
- `package.json`: `"three": "^0.184.0"` and `"@types/three": "^0.184.1"` — should be fine
- BUT `CodeTunnel` uses raw Three.js directly without a React wrapper — potential memory leak if component unmounts during animation

#### 2.7 `kimi-plugin-inspect-react` in Production
- `vite.config.ts` line 4: `import { inspectAttr } from 'kimi-plugin-inspect-react'`
- This is a dev/inspection plugin that should not be in production builds
- Should be conditional or removed from production

#### 2.8 No Error Boundaries
- No React Error Boundary anywhere in the app
- CodeTunnel Three.js errors could crash the entire app
- MediaRenderer has per-component error handling, but app-level errors are unprotected

#### 2.9 Quiz Engine: Multiple Choice Generation is Weak
- `generateMultipleChoice()` (quiz-engine.ts line 360-377) generates static options:
  ```
  options: [
    `A framework for ${topic}`,
    `A programming language`,
    `A database system`,
    `A design pattern`,
  ]
  ```
- These are always the same 4 options regardless of topic — not useful for learning

#### 2.10 `sql.js` Dependency Not Used
- Listed in `package.json` but never imported anywhere
- Dead dependency

#### 2.11 `uuid` Dependency — Potential Dead Code
- Listed in `package.json` but not imported in any source file
- IDs are generated with `Date.now()` + `Math.random()` instead

### 🟢 Minor Issues

#### 2.12 `framer-motion` Version
- Using `framer-motion ^12.40.0` — very recent, should be fine

#### 2.13 Package Name
- `package.json`: `"name": "my-app"` — should be `"tripp-teacher"`

#### 2.14 No Linting/Formatting Config
- ESLint is configured (`eslint`, `typescript-eslint`) but no `.eslintrc` or `eslint.config.js` visible
- No Prettier config
- No `.editorconfig`

#### 2.15 No `robots.txt`, `favicon`, or `manifest.json`
- No PWA manifest despite offline capabilities being a core feature
- No favicon customization

#### 2.16 Sidebar Navigation — Goals/Progress/Library Dead Links
- Sidebar in TrippTeacherApp has buttons for "Goals", "Progress", "Library" but they're just `NavButton` components with no routes or functionality

---

## 3. What Needs to Be Built

### Phase 1: Production Foundation (Must Have)

| # | Task | Priority | Effort | Description |
|---|------|----------|--------|-------------|
| 1.1 | **AI Backend Integration** | P0 | Large | Connect to OpenAI/Anthropic for real chat, lesson generation, and quiz AI. Replace `generateResponse()`. |
| 1.2 | **Authentication System** | P0 | Medium | Supabase Auth or Firebase Auth. Login/signup flows. Protect routes. |
| 1.3 | **Data Persistence** | P0 | Large | Supabase/Firebase for user profiles, session history, progress, quiz attempts. Replace localStorage-only approach. |
| 1.4 | **Error Boundaries** | P0 | Small | Wrap main routes and CodeTunnel in ErrorBoundary components |
| 1.5 | **Delete Dead Code** | P0 | Tiny | Remove `Home.tsx`, `App.css`, unused `sql.js` and `uuid` deps |
| 1.6 | **Package Identity** | P0 | Tiny | Rename `package.json` name to `tripp-teacher` |

### Phase 2: Learning Experience (High Priority)

| # | Task | Priority | Effort | Description |
|---|------|----------|--------|-------------|
| 2.1 | **Real Lesson Content Generation** | P1 | Large | AI generates actual lesson content for each gate based on topic + research pack. Replace template-based `generateNodeContent()`. |
| 2.2 | **AI-Enhanced Quiz Generation** | P1 | Medium | Use AI to generate meaningful multiple-choice questions instead of hardcoded ones |
| 2.3 | **Spaced Repetition System** | P1 | Medium | Implement `ReviewCard` type (already defined in types) for SM-2 algorithm-based review scheduling |
| 2.4 | **Goals/Progress/Library Pages** | P1 | Medium | Build the three dead sidebar nav items into real pages |
| 2.5 | **Profile Management** | P1 | Small | Allow users to edit their name, preferences, pace. Persist to backend. |

### Phase 3: Polish & Robustness (Medium Priority)

| # | Task | Priority | Effort | Description |
|---|------|----------|--------|-------------|
| 3.1 | **PWA Manifest** | P2 | Small | Add `manifest.json`, service worker for true offline support |
| 3.2 | **Code Highlighting** | P2 | Small | Use `prism-react-renderer` or `highlight.js` in CodeRenderer instead of plain `<code>` |
| 3.3 | **Markdown Rendering** | P2 | Small | Replace custom `FormattedText`/`FormattedLesson` with `react-markdown` for full MD support |
| 3.4 | **API Rate Limiting / Retry** | P2 | Small | Add retry logic and rate limiting for AI API calls |
| 3.5 | **Loading States** | P2 | Small | Add skeleton loaders for content, media, quiz panels |
| 3.6 | **Keyboard Navigation** | P2 | Small | Full keyboard support for quiz (already partial), intake, cockpit |
| 3.7 | **Linting + Formatting** | P2 | Small | Add ESLint config, Prettier, pre-commit hooks |
| 3.8 | **Favicon + Branding** | P2 | Tiny | Custom favicon, meta tags, OG tags |

### Phase 4: Advanced Features (Lower Priority)

| # | Task | Priority | Effort | Description |
|---|------|----------|--------|-------------|
| 4.1 | **Multiplayer/Social** | P3 | Large | Share learning paths, study groups, leaderboards |
| 4.2 | **Voice Input** | P3 | Medium | Web Speech API for hands-free learning queries |
| 4.3 | **Video Recording** | P3 | Medium | Record "teach back" sessions for Gate 4 (Teach) |
| 4.4 | **Analytics Dashboard** | P3 | Medium | Detailed learning analytics, time tracking, weakness analysis |
| 4.5 | **Custom Themes** | P3 | Small | Light/dark mode toggle (next-themes already in deps) |
| 4.6 | **i18n** | P3 | Medium | Internationalization for multi-language support |

---

## 4. Priority Order for Completion

### Sprint 1: Remove Blockers (1-2 days)
1. Delete `Home.tsx`, `App.css` — dead code cleanup
2. Remove `sql.js`, `uuid` from `package.json`
3. Rename package to `tripp-teacher`
4. Wrap app in ErrorBoundary
5. Fix `kimi-plugin-inspect-react` to be dev-only
6. Add `.env.example` with placeholder API keys

### Sprint 2: AI Backend (1-2 weeks)
1. Set up backend (Supabase or custom Node.js)
2. Add OpenAI/Anthropic API integration
3. Replace `generateResponse()` with real AI chat
4. Build AI-enhanced lesson generation for each gate
5. Build AI-enhanced quiz generation

### Sprint 3: Auth & Persistence (1 week)
1. Implement Supabase Auth (login/signup/logout)
2. Create database schema for users, sessions, progress
3. Replace `localStorage` data transfer with database reads
4. Persist learner profiles, quiz attempts, progress

### Sprint 4: Learning Features (1 week)
1. Build Goals page (learning objectives tracker)
2. Build Progress page (statistics, charts using Recharts — already a dep)
3. Build Library page (saved courses, research packs)
4. Implement spaced repetition with ReviewCard type
5. Profile editing UI

### Sprint 5: Polish (3-5 days)
1. PWA manifest + service worker
2. Code syntax highlighting
3. Markdown rendering upgrade
4. Loading skeletons
5. ESLint + Prettier config
6. Favicon + meta tags

---

## 5. Architecture Recommendations

### State Management
The current app uses 10+ `useState` hooks in `TrippTeacherApp` and `TutorCockpit`. Consider:
- **Zustand** (lightweight) for global state (current topic, user profile, sync status)
- Or keep local state but lift shared state to context

### AI Integration Pattern
```
Chat Input → Intent Detection (existing) → AI Response Generator
                                              ↓
                                    ┌─────────────────────┐
                                    │ OpenAI / Anthropic   │
                                    │ System prompt with   │
                                    │ gate context +       │
                                    │ learner profile      │
                                    └─────────────────────┘
                                              ↓
                                    Streamed response → Chat UI
```

### Data Flow
```
User types message
  → Intent detector checks if learning query
    → If yes: AI-enhanced intake flow → Build personalized plan
    → If no: AI chat response

Cockpit loads topic from localStorage/DB
  → Generates/loads gate nodes
  → Content tab: renders lesson content
  → Media tab: renders diagrams, code, videos
  → Quiz tab: AI-generated questions → offline grading → save to DB
```

---

## 6. Summary

| Category | Count |
|----------|-------|
| Files audited | 76 source files |
| Complete components | 6/6 custom components |
| Complete pages | 3/4 (Home is dead) |
| Complete engines | 6/6 engines |
| Critical gaps | 3 (no AI backend, no auth, no persistence) |
| Dead code files | 2 (`Home.tsx`, `App.css`) |
| Dead dependencies | 2 (`sql.js`, `uuid`) |
| UI components | 45 shadcn/ui components |
| Estimated effort to production | **4-6 weeks** |

**Bottom Line:** The frontend is well-built and nearly complete. The 5-gate learning system, intake flow, quiz engine, offline support, and research import are all functional. The core blocker is the **absence of a backend** — the chat is simulated, there's no authentication, and data doesn't persist. Once AI integration and a data layer are added, this is a production-ready tutoring platform.
