# Phase 1 Build Task — Tripp.Forge Core Foundation

## What We're Building

The core TypeScript engine for Tripp.Forge — a ground-up AI coding assistant.

## Working Directory

`C:\Users\eMitchell109\tripp-forge`

## Read First

- `SPEC.md` — The architecture spec (source of truth)
- `RESEARCH_CODEX.md` — Your research (5,432 words)
- `RESEARCH_KIMI.md` — Kimi's research (4,971 words)

## Phase 1 Tasks

### 1.1 Monorepo Setup

- Initialize pnpm workspace monorepo
- Create `packages/core/` — shared TypeScript engine
- Create `packages/vscode/` — VS Code extension scaffold
- Create `packages/shared/` — types and utilities
- Setup TypeScript, ESLint, Prettier configs
- Add `tsconfig.json` with project references

### 1.2 Canonical Event Ledger

- Implement `EventLedger` class with append-only event log
- Event types: turn_started, message_added, tool_requested, tool_approved, tool_executed, error_occurred, context_overflow, provider_switched
- Persist to SQLite (better-sqlite3)
- Survive restart (replay events)

### 1.3 Provider Adapter Interface

- Define `ProviderAdapter` interface (connect, complete, stream, disconnect)
- Implement `OpenAICompatibleAdapter` — works with ANY OpenAI-format API
- Implement `MiMoAdapter` — Xiaomi MiMo (api.xiaomimimo.com)
- Implement `OllamaAdapter` — local Ollama (127.0.0.1:11434)
- Implement `CapabilityMatrix` — track what each model supports

### 1.4 Basic Agent Loop

- Implement state machine: IDLE → THINKING → TOOL_CALL → OBSERVING → REFLECTING → IDLE
- Durable states (persist to disk after each event)
- Context window tracking
- Basic error recovery

### 1.5 Testing

- Unit tests for event ledger
- Unit tests for provider adapters
- Unit tests for agent loop
- Integration test: run agent loop with Ollama (if available)

## Constraints

- TypeScript only (no Rust yet)
- Use `better-sqlite3` for SQLite
- Use `zod` for schema validation
- Follow the spec EXACTLY — no shortcuts
- Write tests FIRST (TDD where possible)
- Document everything in README.md

## Model

Use `gpt-5.6-sol` for this task.

## Output

- Write all code to `C:\Users\eMitchell109\tripp-forge\`
- Create `PHASE1_COMPLETE.md` with:
  - What was built
  - File list with descriptions
  - How to run tests
  - Any issues encountered
  - Ready for Phase 2: YES/NO

## Important

- Follow the spec in SPEC.md — it's the source of truth
- The canonical event ledger is CRITICAL — don't skip it
- Provider adapters must work with OpenAI-compatible APIs out of the box
- Don't embed JS in Rust — we'll do that in Phase 6
