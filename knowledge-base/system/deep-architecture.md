---
type: System Architecture
title: Deep Knowledge System
description: >-
  Multi-agent knowledge system with shared brain architecture, formerly known as
  understory.
resource: 'http://100.72.250.65:3800'
tags:
  - knowledge-system
  - multi-agent
  - architecture
timestamp: '2026-07-13T16:44:06.566Z'
---
**Deep** (formerly understory) is a multi-agent knowledge system with a shared brain architecture.

**Dashboard:** http://100.72.250.65:3800 (Tripp brand colors)

## Core Components

### Atlas (Librarian)
The knowledge curator and librarian inside Deep.

- **Brain:** Ollama cloud model `qwen3.5:397b-cloud` (397B parameters)
- **Cost:** Zero VRAM (cloud), yearly subscription
- **Tools:** `memory_query`, `memory_add`, `memory_update`, `memory_status`, `memory_maintain`
- **Enrichment Pipeline:** `ingest_knowledge` MCP tool (Phases 1-3 built 2026-07-13)

### Enrichment Pipeline
Built to reduce Atlas cloud token costs by 80-95%.

- **How it works:** Local token munchers extract symbols; cloud brain only processes summaries
- **Munchers:** `jcodemunch-mcp` (code), `jdocmunch-mcp` (docs)
- **Muncher venv:** `D:/Documentation/munch-venv/`
- **Flow:** Agent report → MCP server → Router → Muncher (LOCAL) → Enricher → Deep KB

### Agent Fleet

| Agent | Role | Platform |
|-------|------|----------|
| **Echo** | Supervisor | Local Hermes on PC |
| **Tripp** | Supervisor | OpenClaw on VPS |
| **Cyony** | Supervisor | Hermes on VPS Docker |
| **Codex** | Builder | OpenAI coding agent |
| **Kimi** | Builder | Moonshot coding agent |
| **Atlas** | Librarian | Inside Deep |

## Key Decisions

1. **Adopt, don't rebuild** — Used understory code as foundation
2. **One central writer, many readers** — Codex audit recommendation
3. **Enrich-before-create rule** — Always check existing KB before adding (see [enrich over create rule](/log.md))
4. **Voice config = YAML** — Not stored in knowledge graph
5. **Bot tokens never handled by agents** — Eddie self-configures all tokens

## Networking

All devices connected via Tailscale mesh VPN using WireGuard protocol (<1ms overhead between devices).

- **PC ↔ Laptop latency:** 4-47ms (measured)
- **Laptop local LLM:** 55 tok/s with near-zero network penalty

See [Eddie's technical setup](/personas/eddie.md) for device IPs and hardware details.

# Deep Knowledge System

**Deep** (formerly understory) is a multi-agent knowledge system with a shared brain architecture.

**Dashboard:** http://100.72.250.65:3800 — styled with [Tripp Brand Identity](/system/tripp-brand.md) colors.
