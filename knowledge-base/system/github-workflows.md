---
type: System Architecture
title: GitHub Workflow Patterns
description: >-
  Agent fleet GitHub operations, audit patterns, and delegation workflows for
  eOnoes organization.
tags:
  - github
  - workflows
  - agents
  - orchestration
timestamp: '2026-07-13T19:39:48.541Z'
---
## Echo's Role with GitHub

**Echo** manages all GitHub operations for the eOnoes organization.

- Uses `gh` CLI for repo management, PRs, issues, commits
- Created PR #4 on RMOL due to branch protection (cannot push directly to main)
- **documentation** repo auto-syncs via cron (Python-based, ~30min intervals)

## Audit Pattern

Originated in `audit-orchestrator`, now used with Codex/Kimi.

1. Agent audits code → produces findings
2. Same agent fixes findings → re-audits to verify
3. Completion detection → Telegram notification to Eddie
4. **Eddie's preference:** Codex audits → Codex fixes → Codex re-audits. No middleman.

## Codex/Kimi Delegation Pattern

| Agent | Role | Responsibilities |
|-------|------|------------------|
| **Codex** | Primary builder | Code generation, PR creation, audits |
| **Kimi** | Second opinion | Code review, alternative approaches |
| **Echo** | Supervisor | Orchestrates, delegates, verifies, reports to Eddie |

Both Codex and Kimi connect via MCP servers to the shared knowledge base ([Deep](/system/deep-architecture.md)).

## Branch Protection Rules

| Repo | Branch | Rule |
|------|--------|------|
| **RMOL** | main | Requires PR + status check. Cannot push directly. |
| Other repos | main/master | Mixed — no consistent branching strategy yet. |

## Build Languages Across Organization

| Language | Repos |
|----------|-------|
| JavaScript | RMOL, tripp-scenes, HTOL, MOL.Base, QOL |
| TypeScript | SideQuestHQ (web) |
| Kotlin | sqhq-android |
| Rust | Fort-Yams |
| Python | documentation, Tripp.Mind, audit-orchestrator |

---

**Related:** [eOnoes GitHub Projects](/system/github-projects.md), [Deep Knowledge System](/system/deep-architecture.md)
