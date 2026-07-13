---
type: Brand Identity
title: Tripp Brand Identity
description: >-
  Dark-first, high-contrast design system with lemon green accent applied across
  all Tripp interfaces.
tags:
  - design
  - ui
  - branding
timestamp: '2026-07-13T16:44:00.542Z'
---
Tripp is a dark-first, high-contrast design system applied across all agent interfaces and notifications.

## Colors

| Name | Hex | Usage |
|------|-----|-------|
| **Primary Black** | `#0a0a0a` | Backgrounds, deep surfaces |
| **Dark Gray** | `#121212` | Cards, panels, elevated surfaces |
| **Lemon Green Accent** | `#39FF14` | Primary accent, CTAs, highlights, active states |
| **Text (Primary)** | `#ffffff` | Main text on dark backgrounds |
| **Text (Secondary)** | `#a1a1aa` | Secondary/muted text |

## Design Philosophy

- **Dark-first, high contrast** — optimized for readability and reduced eye strain
- **Minimal, clean typography** — no decorative flourishes
- **Green accent for energy and tech feel** — creates distinctive visual identity
- **Mobile-first responsive design** — interfaces optimized for phone use
- **Voice interaction preferred over text** — primary input method is voice

## Applied To

- [Deep Dashboard](/system/deep-architecture.md) — port 3800
- [The Dream](#the-dream-chat-interface) — port 8765
- All agent interfaces and notifications

# The Dream (Chat Interface)

Browser-based voice-first AI chat interface.

- **Port:** 8765 (HTTPS, CA-signed cert)
- **Features:** Push-to-talk, STT pipeline, text input fallback (Android primary)
- **Tech:** Python server, WebSocket, browser STT
- **Status:** PWA installed on Eddie's phone

# Fish Speech TTS

Text-to-speech service used for agent voice output.

- **Model:** S2-Pro NF4 (`groxaxo/s2-pro-BnB-4Bits`)
- **Port:** 8880
- **Voice:** `default`
- **VRAM:** ~9.8GB
- **Status:** Running on PC
