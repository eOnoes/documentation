# StoryBoard Studio — Master Plan (Pre-Build Audit Complete)

> **Status:** 🟡 AUDIT COMPLETE — AWAITING FINAL LOCK
> **Last Updated:** 2026-07-03
> **Auditors:** Eddie, Tripp (Round 1 + Round 2), Cyony (Round 1), Echo (Round 2)

---

## 📋 Table of Contents

1. [Original Plan (Unedited)](#original-planunedited)
2. [Tripp's Audit Suggestions (Woven In)](#tripps-audit-suggestions)
3. [Echo's Audit Suggestions (Woven In)](#echos-audit-suggestions)
4. [Tripp Round 2 — Meta-Audit of Echo](#round-2-audit--tripp-meta-audit-of-echo)
5. [Combined Recommendations (Prioritized)](#combined-recommendations-prioritized)
6. [Final Build Order](#final-build-order)
7. [Open Questions (Must Answer Before Lock)](#open-questions-must-answer-before-lock)

---

## Original Plan (Unedited)

> Everything below this line is the original plan as shared by Eddie, unedited.
> Audit suggestions are marked with **[AUDIT]** tags so you can distinguish original intent from review feedback.

---

### Import & Parsing

- Import plain text script
- Auto-detects:
 - Single-character → breaks into segments
 - Multi-character dialogue → parses speakers
- Imported segments appear ready to tag
- Manual adjustment after import

**[AUDIT — Tripp R1 #10]:** No speaker/voice management system is described. Need:
- Character list — extracted from script or manual
- Voice library — available voices per TTS provider
- Voice assignment — character → voice mapping, saved per project
- Voice preview — hear what a character sounds like before committing

**[AUDIT — Echo #3]:** Import format has edge cases. Multi-paragraph speeches, stage directions, messy website text will break the parser.
- **Fix:** Support two import modes: Structured (`[Speaker]: text` format, auto-parsed) + Raw (plain text, imported as one big segment, user manually splits and tags). This gives a fallback when the parser can't handle what Eddie pastes.

**[AUDIT — Tripp R1 #3]:** No error recovery in the import pipeline. What happens when:
- The script is 10,000 lines and parsing takes time?
- The auto-detect misidentifies speakers?
- A segment is too long for the TTS provider?
- **Fix:** Show a preview of parsed segments before committing. Let user confirm/correct before import finalizes.

**[AUDIT — Echo #5]:** The `.sb` file format is referenced in Mode A but never defined. What is it? A custom format? A renamed .txt? It needs to be defined — it affects import, export, save, and load.

---

### 🤖 9. AI Collaboration (3 Modes)

#### Mode A: Import from Agent

- Agent writes script externally, saves as .sb or .txt
- User imports with one click
- Auto-parses into segments
- Difficulty: Easy

**[AUDIT — Tripp R1 #8]:** Mode A is already covered by the import feature. You don't need to build it separately. It's just file import with .txt/.sb support. Zero extra work.

**[AUDIT — Echo]:** Agree. This is trivially easy if the import pipeline works.

#### Mode B: AI Assist Panel (In-Editor)

- Highlight a segment → click "AI Assist"
- Type a quick prompt (e.g., "write a curious response about robots")
- Agent generates text → drops directly into segment
- User edits in-place
- Use case: quick rewrites, expanding ideas, filling gaps
- Difficulty: Medium

**[AUDIT — Tripp R1 #8]:** Phase 2. Requires prompt engineering, response parsing, UI integration. Real work. Don't build this until the core pipeline (import → tag → generate → stitch) works.

**[AUDIT — Tripp R1 #6]:** For the AI Assist prompt input, use an **inline popup (tooltip)**, not a side panel. A side panel steals screen real estate and adds layout complexity.

#### Mode C: Real-Time Co-Writing (Live Streaming)

- User says "Echo write scene 4 about X"
- Agent connects via WebSocket to the app
- Text appears character-by-character in the editor
- User watches the agent write in real-time
- Works for any connected agent (Echo, Tripp, Cyony)
- Use case: demos, collaboration, showoff moments
- Difficulty: Hard (but doable — app already runs a local server, add WebSocket support)
- Technical: WebSocket server on the app, agent connects as client, streams text tokens to specific segment

**[AUDIT — Tripp R1 #7, #8]:** Phase 3. WebSocket complexity, concurrent editing, conflict resolution. This is a hard problem. Don't touch it until the app is stable.

**[AUDIT — Tripp R1 #7]:** For real-time writing, the agent should type into the **highlighted segment**, not append to the end. Appending means the user has to move text afterward.

**[AUDIT — Tripp R1 #9]:** Multiple agents writing simultaneously? **No.** One at a time. Concurrent writes to the same document is a conflict resolution nightmare. Lock the editor to one agent during co-writing.

**[AUDIT — Tripp R1 #7]:** The actual critical use for WebSocket is **generation progress streaming**, not co-writing. When batch-generating 200 segments, the client needs real-time status updates. That's the daily-use WebSocket feature. Co-writing is a party trick.
- **Fix:** Build WebSocket for progress streaming first. Co-writing is Phase 3.

**[AUDIT — Tripp R1 #2]:** WebSocket approach — use **Socket.io**. It handles reconnection, rooms, and fallback to long-polling. Native WebSocket is fine for simple cases but Socket.io saves you pain when connections drop.

---

### 📱 10. UX Extras

- **Dark mode** — because humans stare at screens
- **Keyboard shortcuts:**
 - Ctrl+G = Generate
 - Ctrl+Shift+G = Generate All
 - Ctrl+S = Save
 - Ctrl+I = Import
 - Ctrl+Z/Y = Undo/Redo
- **Responsive** — works on desktop, usable on tablet
- **Scene navigation** — jump to scene by number

**[AUDIT — Tripp R1 #4]:** Ctrl+Z/Y is listed as a shortcut but there's no undo/redo architecture described. Undo is **painful** to bolt on later.
- **Fix:** Implement a command pattern from the start. Every mutation (add segment, move, edit, delete, re-tag) goes through a command stack. ~50 lines of code upfront vs. weeks of debugging later.

**[AUDIT — Echo #10]:** Add 5 basic keyboard shortcuts to MVP. They're ~20 lines of code and dramatically improve usability: Ctrl+Z, Ctrl+Y, Space (play/pause), Ctrl+S, Ctrl+Enter (generate current segment).

**[AUDIT — Tripp R1 #12]:** Segment navigation needs more than "jump to scene by number." Users need:
- **Merge** segments (combine two lines into one)
- **Split** segments (break one line in two)
- **Duplicate** a segment
- **Batch retag** (change voice for 50 segments at once)
- **Search** segments by text
- **Filter** by speaker, scene, generation status
These aren't UX extras — they're core editing features.

**[AUDIT — Tripp R1 #14]:** No audio preview workflow described. The tool generates audio but how do users **listen**?
- Play individual segments?
- Play a scene?
- Play the whole thing?
- Scrub through audio?
- See waveform?
- **MVP minimum:** Play button per segment + "play all" button. Think about where the player lives in the UI — don't make users scroll up and down to hear their work.

**[AUDIT — Echo]:** Fixed bottom player bar — always visible, never hidden. Good call.

---

### 🔧 11. Technical Stack

**Frontend**
• Technology: HTML/CSS/JS (vanilla or lightweight framework)

**[AUDIT — Tripp R1 #5]:** Vanilla JS for this complexity is a trap. You're building a drag-and-drop editor, multi-panel UI, state management, and a WebSocket client. That's not a "vanilla JS" project.
- **Recommendation:** **Svelte**. Lowest bundle size, closest to vanilla feel, built-in state management, easy to learn. React is overkill. Vue is fine but heavier.

**Server**
• Technology: Python (Flask/FastAPI) or Node.js

**[AUDIT — Tripp R1 #6]:** Node makes sense (JS everywhere, WebSocket native, npm ecosystem). But if any TTS provider only has a Python SDK, you're now maintaining two servers.
- **Fix:** Before committing, check each TTS provider's SDK availability. If Python SDKs dominate, consider FastAPI + Socket.io. Or a hybrid where Node handles WebSocket/state and Python handles TTS calls via internal API.

**[AUDIT — Echo #5]:** Where does this run? Eddie's Windows machine or the VPS?
- **Recommendation:** Local first. Deploy to VPS later when it's stable. Eddie opens `localhost:3000` in his browser. Simple.

**WebSocket**
• Technology: Socket.io or native WebSocket API

**[AUDIT — Tripp R1]:** Socket.io. See Mode C section above for reasoning.

**TTS Backend**
• Technology: MiMo API, Fish Audio API, xAI API

**[AUDIT — Echo #1]:** We need real Fish Audio API specs before building:
- What's the max text length per request?
- What are the rate limits? (concurrent requests, requests per minute)
- What's the API endpoint structure?
- Do we already have API keys configured?
- **Action:** Run a quick test call from the terminal before building. 15-minute task that prevents a week of pain.

**[AUDIT — Echo #2]:** Voice references — how do they connect? Eddie has voice files at `D:\Trippcore\voices\`. Are these uploaded to Fish Audio's cloud? Or local files? Does Fish Audio have a list voices API? Can we use local `.wav` files as voice references, or does Fish Audio need to host them?
- **Action:** Check Fish Audio's API for voice listing and voice reference handling before building voice management.

**Audio Assembly**
• Technology: FFmpeg (via Python subprocess)

**[AUDIT — Echo #7]:** Stitched audio format — default to **128kbps MP3**. At that rate, 1 hour ≈ 57MB. Eddie's stories (5-15 min) = 4-17MB. No warning needed for MVP unless stories exceed 30 minutes. Quality setting can be added in Phase 2.

**[AUDIT — Tripp R1 #3]:** What happens when FFmpeg fails mid-stitch? Segments 1-50 stitched fine, segment 51 is corrupt, now what?
- **Fix:** Validate each audio file before stitching (file size > 0, valid MP3 header). Skip corrupt segments with a warning, don't kill the whole pipeline.

**Storage**
• Technology: Browser localStorage (auto-save) + file system (named saves)

**[AUDIT — Tripp R1 #2]:** localStorage is a time bomb. Caps at ~5MB and gets wiped on cache clear. For a tool that generates audio files, that's a disaster.
- **Fix:** Use **IndexedDB** for structured data + the **File System Access API** (Chrome/Edge) for audio exports. IndexedDB gives you 50%+ of disk space, handles large blobs, and persists properly. Add a manual "Save Project to File" export as a fallback for browsers that don't support the API.

**[AUDIT — Tripp R1 #11]:** No project save/load architecture described. Need:
- **Auto-save** to IndexedDB every 30 seconds
- **Manual save** to `.json` project file (all segments, tags, settings)
- **Export** stitched audio + project file as a bundle
- **Import project** from file (for sharing, backup)

**No install**
• Technology: Open browser, done

**[AUDIT — Echo #4]:** What does Eddie need installed to run this?
- Node.js (which version?)
- npm
- FFmpeg (needs to be installed separately)
- A modern browser (Chrome/Edge for File System Access API)
- **Fix:** Add a `README.md` with install instructions. Or better — a `setup.sh` script that checks for dependencies and installs what's missing.

---

### ❓ Audit Questions for Cyony & Tripp

**Architecture:**
1. Should we use a framework (React, Vue) or keep it vanilla JS for simplicity?

**[AUDIT — Tripp]:** Svelte. Not vanilla.

2. WebSocket approach — Socket.io or native WebSocket?

**[AUDIT — Tripp]:** Socket.io. Handles reconnection, rooms, fallback.

3. Should the server be Python or Node? (Node makes sense since the app is already JS-heavy)

**[AUDIT — Tripp]:** Node for MVP. Check TTS SDK availability first. If Python SDKs dominate, FastAPI + Socket.io.

**UX:**
4. Is drag-to-reorder worth the complexity or should we use up/down arrows?

**[AUDIT — Tripp]:** Up/down arrows first. Drag-and-drop is a usability trap — conflicts with text selection, breaks on mobile, adds 3x complexity. Add drag in Phase 2 if users demand it.

5. Should segments auto-expand as you type or stay fixed height?

**[AUDIT — Tripp]:** Auto-expand to content height, with a max (e.g., 8 lines). Fixed height frustrates writers. Unlimited expansion breaks layout.

6. How should the AI assist prompt input look — inline popup or side panel?

**[AUDIT — Tripp]:** Inline popup (tooltip). A side panel steals screen real estate and adds layout complexity.

**AI Integration:**
7. For real-time writing — should the agent type into a highlighted segment or append to the end?

**[AUDIT — Tripp]:** Highlighted. Always. Appending means the user has to move the text after.

8. Should there be a "connection status" indicator showing which agents are online?

**[AUDIT — Tripp]:** Yes, but only for connected agents. A small dot (green/red) in the toolbar. Don't over-build a dashboard for this.

9. Can multiple agents write simultaneously or one at a time?

**[AUDIT — Tripp]:** No. One agent at a time. Concurrent writes is a conflict resolution nightmare.

**Audio:**
10. Should version comparison play both versions back-to-back?

**[AUDIT — Tripp]:** Not in MVP. Just show text diff and let user regenerate.

11. Is there a max number of segments per project we should set?

**[AUDIT — Tripp]:** No hard limit, but warn at 500+ and suggest splitting into scenes/projects. Performance degrades with too many DOM elements.

12. Should the stitch feature support chapter breaks (silence gaps of different lengths)?

**[AUDIT — Tripp]:** Yes, but as a "silence duration" setting per scene boundary, not a separate feature. Simple slider: 0-5 seconds of silence between scenes.

**Data:**
13. Where should saved projects live — a dedicated folder or user-chosen location?

**[AUDIT — Tripp]:** File System Access API (user picks folder). IndexedDB for auto-save. Allow export as .json project file.

14. Should we support cloud save (Google Drive, etc.) or keep it local only?

**[AUDIT — Tripp]:** No. Local only for MVP. Cloud sync is a separate product. If sharing is needed, export/import the project file.

15. What's the expected max file size for stitched audio?

**[AUDIT — Tripp]:** No limit from the app side. Let the browser/OS handle it. But warn if stitched audio exceeds 100MB (suggest splitting).

**[AUDIT — Echo]:** Default 128kbps MP3. No warning needed for MVP unless stories exceed 30 minutes.

**Security:**
16. TTS API keys — stored in the app config or environment variables?

**[AUDIT — Tripp]:** Environment variables on the server. Never in the browser. The server proxies all TTS calls. API keys never touch the client.

17. Should the WebSocket server be open to LAN or localhost only?

**[AUDIT — Tripp]:** Localhost only for MVP. LAN access is a security decision that needs auth.

**"Wish We Had That" Sweep:**
18. Text-to-speech preview while typing (hear the line before generating)?

**[AUDIT — Tripp]:** Phase 2. Nice to have but adds API calls and latency to the typing experience.

19. Collaboration history — see who wrote what and when?

**[AUDIT — Tripp]:** Phase 3. Requires per-segment metadata tracking.

20. Template scripts — pre-built story structures to start from?

**[AUDIT — Tripp]:** Phase 2, but easy. Just .txt files the user can load.

21. Sound effects between scenes (not just silence)?

**[AUDIT — Tripp]:** Phase 3. Requires an SFX library and mixing pipeline.

22. Background music track option?

**[AUDIT — Tripp]:** Phase 2. Simpler than SFX — one track under everything.

23. Export to video (for YouTube Shorts pipeline integration)?

**[AUDIT — Tripp]:** Separate project entirely. Don't even think about it now.

---

## Tripp's Audit Suggestions

> Summary of all Tripp recommendations across Round 1 and Round 2.

### 🔴 CRITICAL (Must Fix Before Build)

| # | Issue | Source |
|---|-------|--------|
| 1 | No MVP definition — plan mixes v0.1 and v2.0 features | Tripp R1 |
| 2 | localStorage is a time bomb — use IndexedDB + File System Access API | Tripp R1 |
| 3 | No error recovery in audio pipeline — need retry, resume, validation | Tripp R1 |
| 4 | No undo/redo architecture — implement command pattern from day one | Tripp R1 |

### 🟡 ARCHITECTURE

| # | Issue | Recommendation |
|---|-------|----------------|
| 5 | Vanilla JS is a trap for this complexity | Use Svelte |
| 6 | Server language depends on TTS SDK availability | Check SDKs, then decide Node vs Python |
| 7 | WebSocket scope is wrong — progress streaming first, co-writing later | Build for batch generation progress, not co-writing |

### 🟡 SCOPE

| # | Issue | Recommendation |
|---|-------|----------------|
| 8 | Three AI modes is too many for first build | Mode A: build (already covered by import). Mode B: Phase 2. Mode C: Phase 3. |
| 9 | Version comparison is a rabbit hole | MVP: auto-save keeps old generations. User can regenerate. No formal versioning yet. |

### 🟢 MISSING FEATURES

| # | Issue | What's Needed |
|---|-------|---------------|
| 10 | No speaker/voice management | Character list, voice library, voice assignment, voice preview |
| 11 | No project save/load architecture | Auto-save to IndexedDB, manual save to .json, export as bundle |
| 12 | No segment operations | Merge, split, duplicate, batch retag, search, filter |
| 13 | No audio preview workflow | Per-segment play, play all, scene playback, waveform |
| 14 | No progress visibility | Segment X/200, failure count, ETA, progress bar |

---

## Echo's Audit Suggestions

> Summary of all Echo recommendations from Round 2.

### 🔴 MUST (Before Lock)

| # | Item | Effort |
|---|------|--------|
| 1 | Test Fish Audio API from terminal before building | 15 min |
| 2 | Confirm voice reference handling (local vs cloud) | 15 min |
| 3 | Support raw text import as fallback | 1 day |
| 4 | Add README with install instructions | 1 hour |

### 🟡 SHOULD (Day 1 of Build)

| # | Item | Effort |
|---|------|--------|
| 5 | Clarify local vs VPS deployment | Decision |
| 6 | Queue-first, parallel later for batch generation | 0 |
| 7 | Default 128kbps MP3, no file size warning needed | 0 |
| 8 | Keep old audio file until new generation verified | 0.5 day |
| 9 | Add 5 keyboard shortcuts to MVP | 0.5 day |

### 🟢 FINE AS-IS

| # | Item |
|---|------|
| 10 | Export text only = Phase 2 |

---

## Round 2 Audit — Tripp (Meta-Audit of Echo)

### What Echo Nailed

- **Fish Audio API pre-test** — The single most important item on the list. A 15-minute test prevents a week of pain. I missed this in Round 1. That's on me.
- **Voice references question** — Foundational. If Eddie's existing voice files don't work with Fish Audio directly, that changes the entire voice management design.
- **Raw text fallback** — Smart. When the parser chokes on messy text, users need a way out.
- **Regeneration keeping old files** — Edge case thinking that prevents data loss.

### What Echo Missed

| # | Gap | Why It Matters |
|---|-----|----------------|
| 1 | **No testing strategy** | How do we verify audio quality? Manual testing for 200 segments? Need a plan. |
| 2 | **No undo/redo mention** | Flagged as critical in Round 1. Foundational decision affecting every feature. |
| 3 | **Timeline still aggressive** | Echo called 3 weeks "realistic." Plain text parsing + voice management + audio stitching = 6-8 weeks honest. |
| 4 | **No audience definition** | Who is this for? Just Eddie or others? Changes everything — onboarding, error messages, docs, auth. |
| 5 | **.sb format undefined** | Nobody asked what it is. It affects import, export, save, and load. |
| 6 | **No state management architecture** | How does the app manage segments, undo stacks, version history, audio refs? Needs upfront design. |

### Meta-Audit Verdict

Echo's Round 2 audit is a **B+**. Good operational catches, good edge case thinking, but missing architectural depth and too generous on the timeline. The must-items are actually musts. The should-items are shoulds. The things not mentioned are the things that'll bite us in week four.

---

## Combined Recommendations (Prioritized)

### 🔴 MUST — Before Lock

| # | Item | Source | Effort |
|---|------|--------|--------|
| 1 | Test Fish Audio API from terminal | Echo R2 | 15 min |
| 2 | Confirm voice reference handling (local vs cloud) | Echo R2 | 15 min |
| 3 | Define .sb file format | Tripp R2 | 30 min |
| 4 | Decide framework: Svelte vs other | Tripp R1 | 30 min |
| 5 | Decide server: Node vs Python | Tripp R1 | 30 min (after SDK check) |
| 6 | Confirm deployment: local vs VPS | Echo R2 | Decision |
| 7 | Define MVP scope (hard line) | Tripp R1 | 15 min |
| 8 | Implement command pattern for undo/redo | Tripp R1 | 0.5 day |

### 🟡 SHOULD — Day 1 of Build

| # | Item | Source | Effort |
|---|------|--------|--------|
| 9 | Raw text import fallback | Echo R2 | 1 day |
| 10 | README with install instructions | Echo R2 | 1 hour |
| 11 | Error recovery in audio pipeline | Tripp R1 | 1 day |
| 12 | Progress visibility (batch generation) | Tripp R1 | 1 day |
| 13 | Speaker/voice management system | Tripp R1 | 1-2 days |
| 14 | Regeneration keeps old files | Echo R2 | 0.5 day |
| 15 | Add 5 keyboard shortcuts | Echo R2 | 0.5 day |
| 16 | Project save/load (IndexedDB + file export) | Tripp R1 | 1-2 days |

### 🟢 PHASE 2 — After MVP Works

| # | Item | Source |
|---|------|--------|
| 17 | AI Assist Panel (Mode B) | Original plan |
| 18 | Version history (simple) | Tripp R1 |
| 19 | Background music track | Tripp R1 |
| 20 | Template scripts | Tripp R1 |
| 21 | TTS preview while typing | Tripp R1 |
| 22 | Search + filter segments | Tripp R1 |
| 23 | Batch retag | Tripp R1 |
| 24 | Export text/project as zip | Echo R2 |
| 25 | Drag-and-drop reorder | Tripp R1 |

### ⚪ PHASE 3 — Future

| # | Item | Source |
|---|------|--------|
| 26 | Real-time co-writing (Mode C) | Original plan |
| 27 | Sound effects between scenes | Original plan |
| 28 | Collaboration history | Original plan |
| 29 | Export to video | Original plan |
| 30 | Cloud save | Original plan |

---

## Final Build Order

### Phase 1 — Foundation (Week 1)
1. Test Fish Audio API + confirm voice references
2. Project structure (Svelte + Node + Socket.io)
3. Command pattern architecture (undo/redo)
4. Script import (structured + raw fallback)
5. Segment editor (add/edit/delete/reorder + speaker tagging)
6. Voice management (character → voice mapping)

### Phase 2 — Core Pipeline (Week 2)
7. TTS integration (Fish Audio, single provider)
8. Audio generation (single segment → batch with progress)
9. Error handling + retry logic
10. Audio stitching with silence gaps
11. Audio player (per-segment + full playback)
12. Save/load (IndexedDB auto-save + file export)

### Phase 3 — Polish (Week 3)
13. Keyboard shortcuts
14. Search + filter
15. Progress visibility
16. README + setup instructions
17. Edge case hardening

### Phase 4 — Phase 2 Features (Week 4+)
- AI Assist panel, version history, background music, templates, etc.

---

## Open Questions (Must Answer Before Lock)

| # | Question | Owner |
|---|----------|-------|
| 1 | What is the `.sb` file format? | Eddie |
| 2 | Does Fish Audio support local voice files or must they be uploaded? | Eddie/Tripp |
| 3 | What's Fish Audio's rate limit and max text length? | Tripp (test) |
| 4 | Who is the target user? Just Eddie or others? | Eddie |
| 5 | Svelte or something else for frontend? | Team decision |
| 6 | Node or Python for server? | Team decision (after SDK check) |
| 7 | Local-first or VPS-first deployment? | Eddie |
| 8 | What testing strategy do we use? | Team decision |

---

## Audit Trail

| Auditor | Round | Date | Status |
|---------|-------|------|--------|
| Eddie (plan owner) | Original | 2026-07-03 | ✅ v3 original |
| Tripp | Round 1 | 2026-07-03 | ✅ Complete |
| Cyony | Round 1 | 2026-07-03 | ✅ Complete |
| Echo | Round 2 | 2026-07-03 | ✅ Complete |
| Tripp | Round 2 (meta-audit) | 2026-07-03 | ✅ Complete |
| Cyony | Final | Pending | ⏳ After Tripp Round 2 |
| **LOCK** | — | Pending | 🔒 After all Round 2 audits pass |

---

*This document preserves the full original plan with audit suggestions woven in as [AUDIT] commentary. Ready for final team review before lock.*
