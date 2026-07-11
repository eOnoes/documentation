# Tripp.Forge — Architecture Plan

**Codename:** Tripp.Forge
**Vision:** Cline's agentic coding + Goose's multi-tool orchestration + Augment's deep codebase understanding
**Author:** Eddie (Onoes) | Built by: Echo, Codex, Kimi
**Date:** 2026-07-10

---

## Two Delivery Modes

| Mode                  | Tripp.Mind Link | Distribution            | Target User          |
| --------------------- | --------------- | ----------------------- | -------------------- |
| **VS Code Extension** | ❌ NEVER        | VS Code Marketplace     | Public / open source |
| **Standalone App**    | ✅ Private      | GitHub release / direct | Eddie + fleet only   |

The VS Code extension is the **public face** — clean, no fleet ties.
The standalone app is the **private power tool** — wired into Tripp.Mind, fleet knowledge, shared memory.

---

## ChatGPT Subscription Strategy

**The insight:** The OpenClaw creator was hired by OpenAI. The Codex OAuth pattern is sanctioned by proximity — not a formal contract, but an understanding.

### Provider Priority

| Priority     | Method            | Auth                         | Billing            | Notes                             |
| ------------ | ----------------- | ---------------------------- | ------------------ | --------------------------------- |
| **Primary**  | Codex OAuth Proxy | PKCE via `auth0.openai.com`  | User's ChatGPT sub | Native, fast. The "understanding" |
| **Fallback** | Codex CLI Adapter | `codex` CLI (already authed) | User's ChatGPT sub | If OAuth breaks, shell out        |
| **Export**   | OpenAI API Key    | API key                      | Per-token billing  | For sharing with non-sub users    |

### Codex OAuth Proxy (Primary)

```typescript
interface CodexOAuthConfig {
  clientId: string; // Our own OAuth client (NOT Cline's)
  redirectUri: string; // http://localhost:1455/auth/callback
  scopes: string[]; // openid profile email offline_access
  tokenStore: SecretStore; // OS keychain, not settings
}

// Flow:
// 1. Open browser → auth0.openai.com/u/login/authorize
// 2. Listen on localhost for callback
// 3. Exchange code for tokens (access + refresh)
// 4. Extract chatgpt_account_id from token claims
// 5. Proxy requests mimicking Codex CLI shape
// 6. Refresh before expiry, handle invalid_grant gracefully
```

**Key:** We use OUR OWN OAuth client ID, not Cline's. The OpenClaw relationship means OpenAI is likely to approve a legitimate third-party client for this use case.

### Codex CLI Adapter (Fallback)

```typescript
interface CodexCLIAdapter {
  // Spawn codex as subprocess
  exec(prompt: string, opts: { model?: string; ephemeral?: boolean }): Promise<StreamResult>;

  // Verify auth is configured
  checkAuth(): Promise<{ authenticated: boolean; account?: string }>;

  // Use --ephemeral for one-shot tasks
  // Use persistent session for multi-turn conversations
}
```

### Risk Mitigation

- **Feature flag:** OAuth proxy behind `experimental.chatgptSubscription`
- **Graceful degradation:** If OAuth fails → try CLI → fall back to API key
- **User notification:** Show clear status of which auth method is active
- **No scraping:** Never touch cookies, browser sessions, or local storage

---

## Core Architecture

```
┌─────────────────────────────────────────────┐
│              TRIPP.FORGE CORE                │
│  (TypeScript — shared between both modes)   │
│                                             │
│  ┌─────────────┐  ┌──────────────────────┐  │
│  │ Agent Loop   │  │ Context Engine       │  │
│  │ - Plan       │  │ - Codebase indexer   │  │
│  │ - Execute    │  │ - AST parser         │  │
│  │ - Observe    │  │ - Import graph       │  │
│  │ - Reflect    │  │ - Symbol search      │  │
│  └──────┬──────┘  └──────────┬───────────┘  │
│         │                    │               │
│  ┌──────┴────────────────────┴───────────┐   │
│  │           Tool Registry               │   │
│  │  file_read | file_write | terminal    │   │
│  │  search | browser | git | deploy      │   │
│  │  tripp_mind (standalone only)         │   │
│  └───────────────────────────────────────┘   │
│                                             │
│  ┌───────────────────────────────────────┐   │
│  │         Provider Layer                │   │
│  │  MiMo | DeepSeek | Ollama | Claude   │   │
│  │  GPT | Kimi | Custom                  │   │
│  └───────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
         │                       │
    ┌────┴────┐            ┌────┴────┐
    │ VS Code │            │Standalone│
    │Extension│            │   App    │
    │ (UI)    │            │  (Tauri) │
    └─────────┘            └─────────┘
```

---

## Component Breakdown

### 1. Agent Loop (Core)

The autonomous coding agent that drives everything:

```
User Prompt → Plan → Execute Tool → Observe Result → Reflect → Loop/Finish
```

- **Plan:** Break task into steps, decide which tools to use
- **Execute:** Call tools (read file, write code, run terminal, etc.)
- **Observe:** Parse tool output, check for errors
- **Reflect:** Did the step work? Do I need to adjust? Am I done?
- **Loop:** Continue until task is complete or user intervenes

Key difference from Cline/Goose:

- **Smart context injection** — doesn't dump whole files, uses the Context Engine to pull only relevant symbols
- **Multi-file awareness** — understands imports, dependencies, type chains
- **Self-healing** — if a tool call fails, reasons about why and retries differently

### 2. Context Engine (Core — Augment-style)

Deep codebase understanding without token waste:

- **Project indexer** — walks the codebase, builds symbol table
- **AST parser** — understands code structure, not just text
- **Import graph** — knows which files depend on which
- **Symbol search** — "find all usages of `authenticateUser`" → instant results
- **Diff awareness** — knows what changed since last commit
- **Relevance scoring** — when the agent needs context, pulls the MOST relevant files first

Storage: SQLite index per project (like Augment's local index)

### 3. Tool Registry (Core — Goose-style)

Pluggable tool system. Each tool is a module:

```typescript
interface Tool {
  name: string;
  description: string;
  parameters: Schema;
  execute(params: any): Promise<ToolResult>;
}
```

**Built-in tools:**

| Tool           | What it does                                       |
| -------------- | -------------------------------------------------- |
| `file_read`    | Read file contents with line numbers               |
| `file_write`   | Write/create files                                 |
| `file_edit`    | Targeted find-and-replace edits                    |
| `terminal`     | Run shell commands                                 |
| `search_files` | Search by filename or content                      |
| `web_search`   | Search the web                                     |
| `web_extract`  | Extract content from URLs                          |
| `browser`      | Navigate, click, type, screenshot                  |
| `git`          | Commit, push, pull, diff, log                      |
| `tripp_mind`   | Query Tripp.Mind knowledge graph (STANDALONE ONLY) |

**Custom tools:** Users can add their own tools via config.

### 4. Provider Layer (Core)

Multi-model support. Swap models mid-conversation.

| Provider    | Models                        | Notes               |
| ----------- | ----------------------------- | ------------------- |
| Xiaomi MiMo | mimo-v2.5, mimo-v2-omni       | Eddie's default     |
| DeepSeek    | deepseek-chat, deepseek-coder | Free tier available |
| Ollama      | Any local model               | Fully offline       |
| Anthropic   | Claude 3.5/4                  | Via API key         |
| OpenAI      | GPT-4o, o1, o3                | Via API key         |
| Kimi        | moonshot, kimi-k2.7           | Via API key         |
| Custom      | OpenAI-compatible             | Any endpoint        |

### 5. VS Code Extension (Public)

Clean, no fleet ties. distributable on marketplace.

**Features:**

- Side panel with chat interface
- Inline code suggestions (ghost text)
- Diff view for file edits
- Terminal integration (shows commands being run)
- File tree awareness
- Model selector (pick your provider)
- Tool approval (approve/deny each action)
- Context panel showing what files the agent is reading

**Tech:** VS Code Extension API, TypeScript, Webview panels

### 6. Standalone App (Private)

The full power tool with fleet integration.

**Built on:** Tauri 2.0 (Rust backend + React frontend)

**Extra features over VS Code extension:**

- **Tripp.Mind integration** — query the knowledge graph, pull shared memory
- **Fleet awareness** — see agent status, hand off tasks
- **Voice I/O** — TTS output via MiMo/Chatterbox
- **Session persistence** — SQLite local storage
- **Multi-workspace** — work on multiple projects simultaneously
- **Built-in browser** — for web tasks without external browser
- **Deployment tools** — push to VPS, manage Docker, etc.

---

## Data Flow

### VS Code Mode

```
User → VS Code Panel → Agent Core → Tools → Filesystem/Terminal
                         ↕
                    LLM Provider (API)
```

### Standalone Mode

```
User → Tauri Window → Agent Core → Tools → Filesystem/Terminal
                         ↕                    ↕
                    LLM Provider          Tripp.Mind API
                                            ↕
                                        SiYuan Graph
```

---

## Project Structure

```
tripp-forge/
├── packages/
│   ├── core/                  # Shared agent engine
│   │   ├── src/
│   │   │   ├── agent/         # Agent loop, planning, reflection
│   │   │   ├── context/       # Codebase indexing, AST, symbol search
│   │   │   ├── tools/         # Tool registry + built-in tools
│   │   │   ├── providers/     # LLM provider integrations
│   │   │   └── types/         # Shared TypeScript types
│   │   ├── package.json
│   │   └── tsconfig.json
│   │
│   ├── vscode/                # VS Code extension
│   │   ├── src/
│   │   │   ├── extension.ts   # Entry point
│   │   │   ├── panels/        # Side panel, settings
│   │   │   ├── views/         # Webview UI
│   │   │   └── commands/      # VS Code commands
│   │   ├── package.json       # Extension manifest
│   │   └── media/             # Icons, assets
│   │
│   └── standalone/            # Tauri standalone app
│       ├── src-tauri/         # Rust backend
│       ├── src/               # React frontend
│       │   ├── components/
│       │   ├── hooks/
│       │   ├── stores/
│       │   └── lib/
│       ├── tripp-mind/        # Tripp.Mind integration (PRIVATE)
│       └── package.json
│
├── tools/                     # Custom tool definitions
│   ├── file-tools.ts
│   ├── terminal-tools.ts
│   ├── browser-tools.ts
│   ├── git-tools.ts
│   └── tripp-mind-tools.ts    # Standalone only
│
├── ARCHITECTURE.md            # This file
├── package.json               # Monorepo root (pnpm workspaces)
└── pnpm-workspace.yaml
```

---

## Build Phases

### Phase 1: Foundation (Week 1)

- [ ] Monorepo setup (pnpm workspaces + TypeScript)
- [ ] Core agent loop (plan → execute → observe → reflect)
- [ ] File read/write/edit tools
- [ ] Terminal tool
- [ ] Basic provider layer (MiMo + Ollama)
- [ ] Simple CLI runner for testing

### Phase 2: Context Engine (Week 2)

- [ ] Project indexer (walk codebase, build symbol table)
- [ ] SQLite-based project index
- [ ] Symbol search ("find usages of X")
- [ ] Import graph builder
- [ ] Relevance scoring for context injection
- [ ] Diff awareness (git changes)

### Phase 3: VS Code Extension (Week 3)

- [ ] Extension scaffold + manifest
- [ ] Side panel UI (chat interface)
- [ ] Webview for agent output
- [ ] File edit diff views
- [ ] Terminal command display
- [ ] Tool approval system
- [ ] Model selector
- [ ] Extension packaging + local install test

### Phase 4: Advanced Tools (Week 4)

- [ ] Web search + extract tools
- [ ] Browser tool (Playwright-based)
- [ ] Git integration (commit, push, PR)
- [ ] Custom tool plugin system
- [ ] Multi-file edit orchestration

### Phase 5: Standalone App (Week 5-6)

- [ ] Tauri 2.0 scaffold (Rust + React)
- [ ] Port agent core to Tauri backend
- [ ] React UI (chat, file tree, diff view, terminal)
- [ ] Tripp.Mind integration (private)
- [ ] Session persistence (SQLite)
- [ ] Voice I/O (optional)
- [ ] Fleet awareness (optional)
- [ ] Build + package for distribution

### Phase 6: Polish & Ship (Week 7)

- [ ] Error handling, retry logic, edge cases
- [ ] Settings UI (providers, tools, preferences)
- [ ] Keyboard shortcuts
- [ ] Documentation
- [ ] VS Code Marketplace submission
- [ ] GitHub release for standalone

---

## What Makes Tripp.Forge Different

| Feature                      | Cline   | Goose   | Augment | **Tripp.Forge** |
| ---------------------------- | ------- | ------- | ------- | --------------- |
| VS Code native               | ✅      | ❌      | ✅      | ✅              |
| Standalone app               | ❌      | ✅      | ❌      | ✅              |
| Deep codebase index          | ❌      | ❌      | ✅      | ✅              |
| Multi-tool orchestration     | Partial | ✅      | Partial | ✅              |
| Tripp.Mind integration       | ❌      | ❌      | ❌      | ✅ (standalone) |
| Multi-provider (swap models) | ❌      | Partial | ❌      | ✅              |
| Fleet awareness              | ❌      | ❌      | ❌      | ✅ (standalone) |
| Self-healing agent loop      | Partial | ❌      | Partial | ✅              |
| Open source                  | ✅      | ✅      | ❌      | ✅ (extension)  |

---

## Open Questions

1. **Name:** Tripp.Forge confirmed? Or other options?
2. **Extension vs Standalone priority:** VS Code first (Week 3) or Standalone first?
3. **Licensing:** MIT for the extension? Proprietary for standalone?
4. **MVP scope:** What's the minimum viable first release?
5. **Model defaults:** Which models work without API keys? (Ollama local)

---

_Built with 🔥 by the Onoes fleet_
