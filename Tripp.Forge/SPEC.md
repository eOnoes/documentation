# Tripp.Forge — Final Architecture Spec

**Codename:** Tripp.Forge
**Vision:** Cline's agentic coding + Goose's multi-tool orchestration + Augment's deep codebase understanding
**Author:** Eddie (Onoes) | Built by: Echo, Codex, Kimi
**Date:** 2026-07-11
**Research:** 10,403 words combined (Codex: 5,432 + Kimi: 4,971)

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

> **PROVEN IN PRODUCTION** — We've built Tripp twice via Goose, both times backending ChatGPT as a provider via OAuth. This works. Marking experimental only because it's not officially documented for third parties.

### Provider Priority

| Priority       | Method            | Auth                         | Billing            | Notes                                    |
| -------------- | ----------------- | ---------------------------- | ------------------ | ---------------------------------------- |
| **Primary**    | OpenAI API Key    | API key                      | Per-token billing  | Stable, documented, works today          |
| **Production** | Codex OAuth Proxy | PKCE via `auth.openai.com`   | User's ChatGPT sub | **PROVEN** — built Tripp twice with this |
| **Fallback**   | Codex CLI Adapter | `codex` CLI (already authed) | User's ChatGPT sub | If OAuth breaks, shell out               |

### OAuth Domain Verification (REQUIRED BEFORE BUILD)

- [ ] Verify: Is the OAuth domain `auth0.openai.com` or `auth.openai.com`?
- [ ] Verify: Does OpenAI allow third-party OAuth clients for ChatGPT subscription?
- [ ] Verify: What scopes are available for third-party apps?

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

### Codex CLI Adapter (Fallback)

```typescript
interface CodexCLIAdapter {
  exec(prompt: string, opts: { model?: string; ephemeral?: boolean }): Promise<StreamResult>;
  checkAuth(): Promise<{ authenticated: boolean; account?: string }>;
}
```

### Risk Mitigation

- **Feature flag:** OAuth proxy behind `experimental.chatgptSubscription`
- **Graceful degradation:** If OAuth fails → try CLI → fall back to API key
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
│  │ - Plan       │  │ - Tree-sitter        │  │
│  │ - Execute    │  │ - ts-morph           │  │
│  │ - Observe    │  │ - SQLite/FTS5        │  │
│  │ - Reflect    │  │ - Symbol search      │  │
│  └──────┬──────┘  └──────────┬───────────┘  │
│         │                    │               │
│  ┌──────┴────────────────────┴───────────┐   │
│  │           Tool Registry               │   │
│  │  fs.read | fs.write | terminal.run    │   │
│  │  browser.* | git.* | web.search       │   │
│  │  tripp_mind (standalone only)         │   │
│  └───────────────────────────────────────┘   │
│                                             │
│  ┌───────────────────────────────────────┐   │
│  │         Provider Layer                │   │
│  │  MiMo | DeepSeek | Ollama | Claude   │   │
│  │  GPT | Kimi | Grok | Custom          │   │
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

## 1. Multi-Provider LLM Support

### 1.1 Cline v4 SDK Pattern

Cline migrated to a **v4 SDK monorepo**:

- `apps/vscode/` — VS Code extension host + webview
- `sdk/packages/llms/src/providers/` — provider registry, gateway, adapters
- `sdk/packages/core/src/runtime/` — session orchestration, OAuth token manager
- `sdk/packages/agents/src/` — agent loop runtime

### 1.2 Provider Registry

```typescript
interface BuiltinSpec {
  id: string; // e.g. "openai-codex", "openai", "anthropic"
  name: string;
  family: string;
  protocol: string;
  client: string;
  capabilities: string[]; // tools, reasoning, prompt-cache, images, oauth
  defaultModelId: string;
  modelsFactory: (...args: any[]) => ModelManifest[];
  configFields: FieldSpec[];
  defaults: Partial<ProviderConfig>;
  metadata: Record<string, unknown>;
}
```

### 1.3 Canonical Event Ledger

**Critical:** Never let provider-native message arrays become the source of truth.

```typescript
interface EventLedger {
  turns: Turn[]; // Provider-agnostic turns
  append(event: Event): void;
  compileForProvider(provider: Provider): Message[];
}
```

This makes mid-conversation provider switching safe and auditable.

### 1.4 Capability Matrix

| Provider | Base URL                | Thinking | Tools | Vision | Notes                                               |
| -------- | ----------------------- | -------- | ----- | ------ | --------------------------------------------------- |
| MiMo     | `api.xiaomimimo.com/v1` | ✅       | ✅    | ✅     | Different base URLs for pay-as-you-go vs token-plan |
| DeepSeek | `api.deepseek.com`      | ✅       | ✅    | ❌     | Provider-specific thinking fields                   |
| Kimi     | `api.moonshot.ai/v1`    | ✅       | ✅    | ✅     | 256K context, thinking on assistant messages        |
| xAI/Grok | `api.x.ai/v1`           | ✅       | ✅    | ✅     | OpenAI REST compatible                              |
| Ollama   | `127.0.0.1:11434/v1`    | ❌       | ✅    | ✅     | Local, no API key, variable context                 |
| OpenAI   | `api.openai.com/v1`     | ✅       | ✅    | ✅     | Subscription via OAuth PKCE                         |

### 1.5 OpenAI-Compatible & OpenRouter Support

**Any API that speaks OpenAI's REST format works out of the box.** The adapter just needs a base URL and API key.

```typescript
interface OpenAICompatibleConfig {
  id: string; // e.g. "openrouter", "together", "groq"
  name: string; // Display name
  baseURL: string; // e.g. "https://openrouter.ai/api/v1"
  apiKey: string; // User-provided
  models: string[]; // Available models
  capabilities: {
    tools: boolean; // Function calling support
    reasoning: boolean; // Thinking/chain-of-thought
    vision: boolean; // Image input
    streaming: boolean; // SSE streaming
  };
}
```

**Pre-configured OpenAI-compatible providers:**

| Provider    | Base URL                        | Notes                                |
| ----------- | ------------------------------- | ------------------------------------ |
| OpenRouter  | `openrouter.ai/api/v1`          | Meta-provider, access to 100+ models |
| Together AI | `api.together.xyz/v1`           | Open-source models, fast inference   |
| Groq        | `api.groq.com/openai/v1`        | Ultra-fast inference                 |
| Fireworks   | `api.fireworks.ai/inference/v1` | Enterprise-grade                     |
| LM Studio   | `127.0.0.1:1234/v1`             | Local models via LM Studio           |
| Ollama      | `127.0.0.1:11434/v1`            | Local models via Ollama              |
| vLLM        | `127.0.0.1:8000/v1`             | Self-hosted inference                |
| Custom      | Any URL                         | User-defined endpoint                |

**User can add ANY OpenAI-compatible endpoint:**

```
Settings → Providers → Add Custom Provider
  Name: My Custom API
  Base URL: https://my-api.example.com/v1
  API Key: sk-...
  Models: model-1, model-2
```

---

## 2. Agent Loop (Durable State Machine)

**Critical:** Never implement as recursive SDK stream wrapper. Use append-only event log.

### 2.1 States

```
IDLE → THINKING → TOOL_CALL → OBSERVING → REFLECTING → IDLE
         ↑                                          │
         └──────────────────────────────────────────┘
```

### 2.2 Event Types

```typescript
type EventType =
  | 'turn_started'
  | 'message_added' // assistant or user
  | 'tool_requested' // model wants to call tool
  | 'tool_approved' // user or auto-approve
  | 'tool_executed' // result returned
  | 'error_occurred'
  | 'context_overflow' // trigger compaction
  | 'provider_switched';
```

### 2.3 Context Window Management

```typescript
interface ContextManager {
  // Track token usage
  tokenCount: number;
  maxTokens: number;

  // Compaction strategies
  compact(strategy: 'sliding_window' | 'summarize' | 'drop_old'): void;

  // Inject relevant codebase context
  injectContext(query: string): RelevantChunk[];
}
```

---

## 3. Tool System

### 3.1 Goose MCP Pattern

Goose is now MCP-first. Treat MCP servers as separate principals.

```typescript
interface Tool {
  name: string;
  description: string;
  inputSchema: ZodSchema; // Zod for validation
  execute(input: unknown, context: ToolContext): Promise<ToolResult>;
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
  requiresApproval: (resolvedArgs: ResolvedArgs) => boolean;
}
```

### 3.2 Policy Between Selection and Execution

Tool approval happens in the **privileged host**, based on **resolved arguments** (paths, command, URL), not just the tool name.

```typescript
interface ToolPolicy {
  approve(tool: Tool, args: ResolvedArgs, context: PolicyContext): Decision;

  // Decisions
  type:
    'allow-once' | 'allow-session' | 'always-allow' | 'deny-once' | 'always-deny' | 'cancel-run';

  // Persisted as predicates
  predicates: {
    tool: string;
    workspace: string;
    executable: string;
    pathGlob: string;
    networkHost: string;
  };
}
```

### 3.3 Hard Guardrails

- Workspace-root containment after symlink resolution
- Protected paths and secret-file detection
- No recursive delete, force push, credential export
- Command timeout/output limits and process-tree cancellation
- Network domain policy for browser/fetch tools

### 3.4 Built-in Tools

| Tool                       | Responsibility                  | Key Behavior                           |
| -------------------------- | ------------------------------- | -------------------------------------- |
| `fs.read`                  | Read file with line/byte ranges | Return hash and line spans             |
| `fs.list`                  | Directory tree                  | Respect ignores                        |
| `fs.search`                | Filename/content search         | Bounded results                        |
| `fs.patch`                 | Structured find/replace         | Check base hash, preview, atomic write |
| `terminal.run`             | Shell command                   | Stream chunks, truncate, capture exit  |
| `browser.*`                | Playwright-based automation     | Isolated profile                       |
| `git.*`                    | Read/mutate Git                 | Separate read and mutation tools       |
| `web.search` / `web.fetch` | Web retrieval                   | Domain policy, timeout                 |

---

## 4. Codebase Indexing (Augment-style)

### 4.1 Parsing Strategy

- **Tree-sitter** — cross-language structural baseline (incremental, error-tolerant, fast)
- **ts-morph** — precise TypeScript/JavaScript semantics (symbols, references, signatures)
- **SQLite/FTS5** — derived facts, not full file bodies

### 4.2 SQLite Schema

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE files (
  id INTEGER PRIMARY KEY,
  uri TEXT NOT NULL UNIQUE,
  language TEXT,
  content_hash BLOB NOT NULL,
  mtime_ms INTEGER,
  indexed_at INTEGER NOT NULL
);

CREATE TABLE symbols (
  id INTEGER PRIMARY KEY,
  file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,  -- function, class, interface, etc.
  start_line INTEGER NOT NULL,
  end_line INTEGER NOT NULL,
  signature TEXT,
  exported INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE chunks (
  id INTEGER PRIMARY KEY,
  file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  symbol_id INTEGER REFERENCES symbols(id),
  body TEXT NOT NULL,
  token_estimate INTEGER NOT NULL
);

CREATE VIRTUAL TABLE chunk_fts USING fts5(
  body, symbol_name, file_uri,
  content='', contentless_delete=1,
  tokenize='unicode61 remove_diacritics 2'
);

CREATE TABLE edges (
  id INTEGER PRIMARY KEY,
  src_symbol_id INTEGER REFERENCES symbols(id) ON DELETE CASCADE,
  dst_symbol_id INTEGER REFERENCES symbols(id) ON DELETE CASCADE,
  kind TEXT NOT NULL  -- imports, calls, extends, etc.
);
```

---

## 5. Tauri 2.0 Standalone

### 5.1 Architecture

```
┌─────────────────────────────────────┐
│           Tauri 2.0 App             │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  React Frontend (WebView)   │   │
│  │  - Monaco Editor            │   │
│  │  - Chat Interface           │   │
│  │  - Tool Approval UI         │   │
│  └─────────────┬───────────────┘   │
│                │ IPC                │
│  ┌─────────────┴───────────────┐   │
│  │  Rust Backend               │   │
│  │  - Security boundary        │   │
│  │  - OS keychain (secrets)    │   │
│  │  - File system access       │   │
│  │  - Process management       │   │
│  └─────────────┬───────────────┘   │
│                │ Sidecar            │
│  ┌─────────────┴───────────────┐   │
│  │  Node.js Sidecar            │   │
│  │  - Agent loop               │   │
│  │  - Provider connections     │   │
│  │  - Tool execution           │   │
│  │  - SQLite indexing          │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

### 5.2 Critical: Node Sidecar

**Do NOT embed JavaScript in Rust.** Run the same TypeScript core as a long-lived sidecar.

- Rust owns: security, lifecycle, secrets, IPC
- Node owns: agent loop, providers, tools, indexing

### 5.3 Project Structure

```
tripp-forge/
├── packages/
│   ├── core/           # Shared TypeScript (agent, providers, tools, indexer)
│   ├── vscode/         # VS Code extension
│   └── shared/         # Types, utilities
├── apps/
│   └── standalone/     # Tauri app
│       ├── src-tauri/  # Rust backend
│       ├── src/        # React frontend
│       └── sidecar/    # Node.js sidecar
└── package.json        # Monorepo root
```

---

## 6. Pitfalls to Avoid

| #   | Pitfall                                  | Source | Mitigation                                                |
| --- | ---------------------------------------- | ------ | --------------------------------------------------------- |
| 1   | Provider-primacy confusion               | Codex  | Canonical event ledger, never store raw provider messages |
| 2   | Recursive agent loop                     | Codex  | Durable state machine with append-only events             |
| 3   | Tool name vs resolved args               | Kimi   | Policy between selection and execution                    |
| 4   | Embedding JS in Rust                     | Codex  | Node sidecar pattern                                      |
| 5   | `@typescript-eslint/parser` for indexing | Kimi   | Use Tree-sitter + ts-morph instead                        |
| 6   | Copying Cline's OAuth client ID          | Codex  | Build our own OAuth client                                |
| 7   | Assuming OpenAI-compatible = identical   | Kimi   | Capability matrix per model                               |
| 8   | No symlink resolution in tool policy     | Kimi   | Resolve before approval                                   |
| 9   | Storing secrets in settings/history      | Both   | OS keychain (SecretStorage in VS Code)                    |
| 10  | Ignoring context overflow                | Both   | Proactive compaction strategies                           |

---

## 7. Build Phases

### Phase 1: Core Foundation (Week 1-2)

- [ ] Monorepo setup (pnpm workspaces)
- [ ] Canonical event ledger
- [ ] Provider adapter interface
- [ ] MiMo + Ollama adapters
- [ ] Basic agent loop (plan/execute/observe)

**Acceptance Criteria:**

- ✅ Event ledger persists to disk, survives restart
- ✅ MiMo adapter connects and returns completion
- ✅ Ollama adapter connects to local server
- ✅ Agent loop runs 3 iterations without crash
- ✅ Unit test coverage >80% for core modules

### Phase 2: Tool System (Week 3)

- [ ] Tool registry with Zod schemas
- [ ] fs.read, fs.write, terminal.run tools
- [ ] Tool approval UI
- [ ] Hard guardrails

**Acceptance Criteria:**

- ✅ All 3 tools execute successfully
- ✅ Approval UI blocks high-risk operations
- ✅ Symlink resolution prevents path traversal
- ✅ Tool output limited to 10KB (configurable)

### Phase 3: Codebase Indexing (Week 4)

- [ ] Tree-sitter integration
- [ ] SQLite/FTS5 schema
- [ ] Symbol extraction
- [ ] Chunk + embedding pipeline

**Acceptance Criteria:**

- ✅ Indexes a 10K-line TypeScript project in <5s
- ✅ FTS5 search returns relevant results
- ✅ Incremental re-index on file save (<500ms)
- ✅ No memory leaks during long sessions

### Phase 4: VS Code Extension (Week 5)

- [ ] Extension scaffolding
- [ ] Webview chat panel
- [ ] Inline suggestions
- [ ] Diff view for tool changes

**Acceptance Criteria:**

- ✅ Extension loads without errors
- ✅ Chat panel sends/receives messages
- ✅ Inline suggestions appear in editor
- ✅ Diff view shows before/after for file changes
- ✅ Extension activates on VS Code startup

### Phase 5: Additional Providers (Week 6)

- [ ] DeepSeek adapter
- [ ] Kimi adapter
- [ ] Grok adapter
- [ ] OpenAI adapter + OAuth PKCE

**Acceptance Criteria:**

- ✅ Each provider connects and returns completion
- ✅ Provider switching works mid-conversation
- ✅ Fallback chain triggers on provider failure
- ✅ OAuth flow completes (if domain verified)

### Phase 6: Tauri Standalone (Week 7)

- [ ] Tauri 2.0 project setup
- [ ] Node sidecar integration
- [ ] Tripp.Mind connection (standalone only)
- [ ] OS keychain secrets

**Acceptance Criteria:**

- ✅ App builds for Windows, macOS, Linux
- ✅ Sidecar starts/stops with app lifecycle
- ✅ Secrets stored in OS keychain
- ✅ Tripp.Mind connection works (if available)

### Phase 7: Polish & Ship (Week 8)

- [ ] Error handling & recovery
- [ ] Performance optimization
- [ ] Documentation
- [ ] VS Code Marketplace submission

**Acceptance Criteria:**

- ✅ All recovery scenarios tested
- ✅ No crashes in 1-hour stress test
- ✅ README + API docs complete
- ✅ VS Code Marketplace listing approved

---

## 8. Recovery Semantics

> ⚠️ Added per Codex review — missing failure handling.

### Tool Execution Failure

```typescript
interface RecoveryPolicy {
  maxRetries: number; // Default: 3
  backoff: 'exponential' | 'fixed';
  retryableErrors: string[]; // ECONNRESET, ENOTFOUND, timeout
  nonRetryableErrors: string[]; // EACCES, ENOENT (file not found)
  fallbackAction: 'skip' | 'abort' | 'ask_user';
}
```

### Provider Failure

| Failure Type       | Recovery                                         |
| ------------------ | ------------------------------------------------ |
| Rate limit (429)   | Exponential backoff, switch to fallback provider |
| Auth failure (401) | Refresh token, then abort with user notification |
| Context overflow   | Trigger compaction, retry with smaller window    |
| Network timeout    | Retry 3x, then switch provider                   |

### Agent Loop Crash Recovery

- State machine persists to disk after every event
- On restart: replay events, resume from last non-complete state
- Never lose work mid-operation

---

## 9. Host Contracts

> ⚠️ Added per Codex review — what does each host guarantee?

### VS Code Extension Host

| Contract       | Guarantee                                       |
| -------------- | ----------------------------------------------- |
| File system    | Workspace folders only (sandboxed)              |
| Terminal       | `vscode.window.createTerminal` — user-visible   |
| Secrets        | `SecretStorage` API (OS keychain)               |
| UI             | Webview panel + status bar + inline decorations |
| Authentication | VS Code's `authentication` API for GitHub, etc. |

### Tauri Standalone Host

| Contract    | Guarantee                                        |
| ----------- | ------------------------------------------------ |
| File system | Full access (user-granted)                       |
| Terminal    | Child process via Rust                           |
| Secrets     | OS keychain via `tauri-plugin-stronghold`        |
| UI          | React webview, custom window chrome              |
| IPC         | `tauri::channel` for streaming, `invoke` for RPC |

### Node Sidecar Contract

| Contract  | Guarantee                            |
| --------- | ------------------------------------ |
| Transport | stdio (preferred) or Unix socket     |
| Protocol  | JSON-RPC 2.0 or custom JSON protocol |
| Lifecycle | Rust owns start/stop/restart         |
| State     | SQLite + event log on shared volume  |

---

## 10. SQLite/FTS Synchronization

> ⚠️ Added per Codex review — when to re-index?

### Triggers

| Trigger             | Action                                        | Debounce  |
| ------------------- | --------------------------------------------- | --------- |
| File save (VS Code) | Incremental re-index changed file             | 500ms     |
| Git checkout/merge  | Full re-index                                 | 2s        |
| New file created    | Add to index                                  | Immediate |
| File deleted        | Remove from index + cleanup edges             | Immediate |
| Folder opened       | Full index if empty, incremental if populated | 1s        |

### Consistency

- WAL mode ensures readers don't block writers
- Content hash on every file — skip re-index if unchanged
- FTS5 `rebuild` after bulk updates
- Edge table updated lazily (on query, not on write)

---

## 11. Security: Log Redaction & Prompt Injection

> ⠏ Added per Kimi review — weak coverage.

### Log Redaction

```typescript
interface RedactionPolicy {
  patterns: [
    /sk-[a-zA-Z0-9]{20,}/g,      // API keys
    /password\s*[:=]\s*\S+/gi,    // Passwords
    /Bearer\s+[a-zA-Z0-9._-]+/g,  // Tokens
  ];
  replacement: "[REDACTED]";
}
```

- All tool output logged through redaction pipeline before storage
- Never log: API keys, tokens, passwords, full file contents (only paths + hashes)

### Prompt Injection Defense

| Layer                   | Defense                                                           |
| ----------------------- | ----------------------------------------------------------------- |
| Input sanitization      | Strip/escape system prompt injection attempts in user messages    |
| Tool output isolation   | Tool results never interpreted as instructions                    |
| File content boundaries | User files wrapped in delimiters, never mixed with system prompts |
| MCP server trust        | Namespace tools by server, validate schemas, cap output           |

---

## 12. Research Sources

| Document            | Agent | Words | Focus                                            |
| ------------------- | ----- | ----- | ------------------------------------------------ |
| `RESEARCH_CODEX.md` | Codex | 5,432 | Architecture fundamentals, pitfalls, phased plan |
| `RESEARCH_KIMI.md`  | Kimi  | 4,971 | Cline v4 SDK, Goose MCP, provider quirks         |
| `ARCHITECTURE.md`   | Echo  | 377   | Foundation (pre-merge)                           |

**Combined research: 10,403 words across 1,607 lines.**

---

_This spec is the source of truth for Tripp.Forge development._
_Last updated: 2026-07-11_
