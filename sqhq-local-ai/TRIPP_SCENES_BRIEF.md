# Tripp.Scenes — Full System Brief

## What Is This?

Tripp.Scenes is a **storyboard editor for AI voice content**. It's where scripts get written, characters get assigned, emotion tags get placed, and voice audio gets generated — all in one place. Think of it as a screenplay writer meets a voice studio, built for our YouTube channel.

## Core Philosophy

- **Write it. Tag it. Hear it. Repeat.**
- Every line of dialogue is tied to a character with a voice
- Emotion tags (`[laugh]`, `[sigh]`, `[gasp]`, etc.) are clickable — no memorizing syntax
- The system auto-adapts tags to whichever TTS model is selected
- Duration is tracked live so you always know if you're hitting 10s, 30s, 1m, 5m targets

---

## Three Writing Modes

### 1. Solo (Eddie Writes)
Eddie opens Tripp.Scenes, creates a new story, adds characters, and writes dialogue manually. He clicks emotion tags from the right panel to insert them at cursor position. He picks the TTS model, hits generate, and hears the result.

### 2. Agent-Written (AI Writes Solo)
Eddie gives a prompt like "Write a 2-minute conversation between Nova and Aria about how neural networks learn." The agent (Cyony or any crew member) writes the full storyboard — characters assigned, tags placed, scene breaks added — and drops it into Tripp.Scenes. Eddie reviews, tweaks, generates.

### 3. Collaborative (Eddie + Agent Together)
Eddie starts writing, gets stuck or wants to riff. He asks the agent to continue, rewrite, or add a section. The agent picks up where he left off, maintaining character voices and tag placement. Back and forth until the script is locked.

---

## Voice Generation Pipeline

### The Stack
```
MiMo TTS (raw foundation clip)
    ↓
Orpheus (one-shot clone — adds mood/emotion)
    ↓
Chatterbox (uncensored — adds inline tags, final polish)
```

### How It Works
1. **Write** the script in Tripp.Scenes with character assignments and emotion tags
2. **Select model** — Chatterbox, MiMo TTS, or Orpheus (dropdown in toolbar)
3. **Tag translation** — The system uses UNIVERSAL tags (`[laugh]`, `[sigh]`, etc.). When you hit Generate, a background worker translates those to the selected model's format:
   - Chatterbox → uses tags as-is (all 10 supported)
   - MiMo → translates to MiMo API style tags
   - Orpheus → translates to Orpheus inline tokens
   - If a model doesn't support a tag → it's stripped silently (no errors)
4. **Chunking** — Long scripts auto-split at sentence boundaries. Each chunk stays under 30s (safe limit). Chunks generate separately, then crossfade (150ms overlap) for seamless audio.
5. **Output** — Single WAV/MP3 file, ready for review or editing

### Supported Emotion Tags (Universal)
| Tag | Effect |
|-----|--------|
| `[laugh]` | Genuine laugh |
| `[chuckle]` | Soft chuckle |
| `[gasp]` | Sharp intake of breath |
| `[sigh]` | Exhale/sigh |
| `[clear throat]` | Ahem |
| `[shush]` | Shush sound |
| `[groan]` | Frustrated groan |
| `[sniff]` | Sniffle |
| `[cough]` | Cough |
| `[pause]` | Brief pause in speech |

### Model Limits
| Model | Max per chunk | Tags | Notes |
|-------|--------------|------|-------|
| Chatterbox | ~40s (1000 tokens) | All 10 | Uncensored. Best for emotional content. |
| MiMo TTS | ~60s | Style-based | Foundation clips. Clean, consistent. |
| Orpheus | ~30s | Inline tokens | One-shot clone. Fast, mood-driven. |

---

## Current Build: v2-inline-002.html

### What's Implemented
- **65/35 split layout** — Storyboard left (65%), tag panel right (35%)
- **Character bar** — Click-to-assign workflow. Click chip → click block. Colored borders + labels.
- **Emotion tag grid** — 10 clickable buttons in 2-column uniform grid. Click inserts at cursor. Custom tag input for adding your own.
- **Edit mode** — Toggle to select/drag-reorder blocks. Multi-select with checkboxes. Yellow drop indicator shows exact landing position.
- **Duration ticker** — Live estimate in M:SS. Format ticks (10s, 20s, 1m, 2m, 5m, 10m) highlight when conversation fits.
- **Story Vault** — Hidden drawer (📚 button). Save/load/delete stories. localStorage persistence. Ctrl+S shortcut.
- **Model selector** — Chatterbox/MiMo/Orpheus dropdown. Passed to generation worker.
- **Scene breaks** — Insert `---` separators between scenes.
- **Export JSON** — Full storyboard with metadata, characters, tags, duration.
- **Mobile responsive** — Right panel stacks below on small screens. No horizontal scroll.
- **Brutalist Tripp theme** — Black (#000), dark gray (#1a1a1a), medium gray (#2a2a2a), lime green (#39ff14) accents.
- **Character count per block** — Green (<60%), yellow (60-80%), red (80-100%). Max 500 chars.
- **Keyboard shortcuts** — Ctrl+Enter (add block), Ctrl+S (save), Escape (close modals), Delete (remove selected in edit mode).

### What Needs Building
- **Generate backend** — Wire the ▶ Generate button to the TTS pipeline (MiMo → Orpheus → Chatterbox)
- **Tag translation worker** — Universal tags → model-specific format
- **Chunking + crossfade** — Auto-split long scripts, generate per chunk, crossfade audio
- **In-storyboard preview** — Play generated audio inline, synced to blocks
- **Agent integration** — API endpoint for agents to write storyboards programmatically
- **Multi-mode writing** — UI support for solo, agent-written, and collaborative modes
- **Interruption handling** — Script syntax for mid-sentence cuts ("— " or `[interrupt]` tag)
- **Character voice presets** — Save voice config per character (model, pitch, speed, reference audio)
- **Version history** — Track changes within a story (undo/redo, diff view)

---

## Interruption & Flow Control

For natural conversation flow, the system needs to support:

- **Mid-sentence interruption** — One character cuts off another
  - Script syntax: `"I was just about to say—" [gasp]` or `"...and then—" [pause] @Aria Oh my god!`
  - The interrupted line ends with `—` (em dash)
  - The interrupting character's block starts immediately after
- **Overlapping dialogue** — Both characters talking at once
  - Mark with `[overlap]` tag on both blocks
- **Pause for effect** — Dramatic beat
  - `[pause]` tag or blank block with no text
- **Scene transition** — `---` separator
- **Aside/whisper** — Character breaks to private thought
  - `[whisper]` tag (model-dependent support)

---

## What We're Building Toward

1. **Tripp.Scenes v1** — The editor (what we have now)
2. **Tripp.Worker** — The generation backend (TTS pipeline + tag translation + chunking)
3. **Tripp.Vault** — Story storage and management (localStorage → future: cloud sync)
4. **Tripp.Agent API** — So crew members can write storyboards programmatically
5. **Tripp.Preview** — In-editor audio playback synced to blocks

The vision: Write a story → hear it → tweak → hear it again → export final audio → upload to YouTube.

---

## File Reference

- Current build: `/opt/data/shared/storyboard-mockups/v2-inline-002.html`
- All versions: `/opt/data/shared/storyboard-mockups/`
- This brief: `/opt/data/shared/storyboard-mockups/TRIPP_SCENES_BRIEF.md`

---

*Built by Cyony. For Tripp.Scenes. For the crew. 🍠💚*
