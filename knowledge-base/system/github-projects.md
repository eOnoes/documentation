---
type: System Architecture
title: eOnoes GitHub Projects
description: >-
  Deep dive into Eddie's eOnoes organization repositories and their current
  status.
resource: 'https://github.com/eOnoes'
tags:
  - github
  - repositories
  - development
timestamp: '2026-07-13T19:40:01.491Z'
---
The **eOnoes** GitHub organization contains Eddie's personal and work projects. This document provides detailed status and technical information for each repository.

## Active Personal Projects

### SideQuestHQ (sqhq-android)
**Personal command center** — Eddie's "life dashboard" for tracking reminders, receipts, ledger, assets, and vehicles.

- **Frontend:** TypeScript (SideQuestHQ web), Kotlin/Jetpack Compose (sqhq-android)
- **Recent work (July 2026):** Terminal/command-line aesthetic redesign across all 6 data screens. GitHub Actions CI pipeline added (debug + release APKs). Home button navigation fix, reminder swipe persistence, font size bump.
- **Status:** Active development. Android app is the primary interface (Eddie's Pixel 10).

### Fort-Yams
Rust project. Tagline: "For the fam. If you don't allow this... I'm cooked fam 😳🧛‍♀️"

- **Language:** Rust
- **Status:** Low activity, last updated July 6, 2026

### tripp-scenes
**Agent collaboration scenes** — webhooks for cross-machine agent coordination.

- **Language:** JavaScript (Node.js)
- **Recent work:** Tailscale IP allowlisting for cross-machine webhook delivery. PR #1 merged (v2 collaboration).
- **Status:** Supports the agent fleet (Echo ↔ Tripp ↔ Cyony).
- **See:** [Deep Knowledge System](/system/deep-architecture.md) for the agent architecture this supports.

### RMOL (Robotics/Mechanics On Linux)
**Feed aggregator and content management system.**

- **Language:** JavaScript
- **Branch protection:** Enabled on main — requires PRs for all changes.
- **PR History:**
  - #4: Open (Echo's "Add industrial feed and Blackline shift exports")
  - #1: Open (hardening)
  - #2: Merged (hardening)
  - #3: Merged (seed data)
- **Status:** Needs merge for PRs #1 and #4. 2 open issues.

## Superseded / Archived Projects

### Tripp.Mind
**Superseded by Deep.** Was the original shared knowledge management system using SiYuan + Gateway + Event Bridge.

- **License:** AGPL-3.0
- **Status:** Archived conceptually. Replaced by [Deep Knowledge System](/system/deep-architecture.md).

### audit-orchestrator
**Multi-agent workflow tool** — predecessor to current Codex/Kimi orchestration.

- **Features:** Sequential agent dispatch, 2-round auditing (audit → fix → re-audit), completion detection, Telegram notifications
- **Status:** Conceptually absorbed into current orchestrator patterns.

## Work Repositories (Heat Treating Company)

Internal tools for Eddie's heat treating workplace. All private repositories.

| Repo | Language | Description | Status |
|------|----------|-------------|--------|
| HTOL | JavaScript | Heat Treat Operations Log | Active |
| MOL.Base | JavaScript | Base app for MOL build projects | Active |
| QOL | JavaScript | Quality Operations Log | Least active (last updated May 2, 2026) |

## Infrastructure

### documentation
**Shared documentation hub** — Python-based auto-sync.

- **Status:** Very active (auto-commits every ~30 min via cron)
- **Hosting:** GitHub Pages or similar

---

**Owner:** [Eddie](/personas/eddie.md)

# Infrastructure

### documentation
**Shared documentation hub** — Python-based auto-sync.

- **Status:** Very active (auto-commits every ~30 min via cron)
- **Hosting:** GitHub Pages or similar

---

**Owner:** [Eddie](/personas/eddie.md)

## Agent Workflows

For how agents interact with these repositories (audit patterns, delegation, branch protection), see [GitHub Workflow Patterns](/system/github-workflows.md).
