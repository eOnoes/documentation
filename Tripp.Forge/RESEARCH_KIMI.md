# Tripp.Forge Technical Research Report — Kimi

**Research date:** 2026-07-11  
**Scope:** Ground-up design of Tripp.Forge — a public VS Code extension and private Tauri 2.0 standalone app sharing a TypeScript agent core.  
**Sources inspected:** Cline `cline/cline` (v4 SDK monorepo, commit-range c. July 2026), Goose `block/goose` (now AAIF), VS Code Extension API docs, Tauri 2.0 docs, MiMo/DeepSeek/Kimi/xAI/Ollama/OpenAI API docs.  
**Companion documents:** `ARCHITECTURE.md`, `RESEARCH_CODEX.md`.

---

## Executive Summary

Tripp.Forge should be built as a **host-agnostic TypeScript core** with thin adapters for VS Code and Tauri. The most important architectural decisions are:

1. **Canonical event ledger.** Never let provider-native message arrays become the source of truth. Persist provider-agnostic turns and compile them per provider on every call. This makes mid-conversation provider switching safe and auditable.
2. **Capability matrix per resolved model.** "OpenAI-compatible" is a transport dialect, not a behavioral guarantee. Each model needs a snapshot of context size, tool mode, reasoning echo rules, vision, and rate-limit behavior.
3. **Policy between selection and execution.** Tool approval must happen in the privileged host, based on resolved arguments (paths, command, URL), not just the tool name.
4. **Durable state machine for the agent loop.** Plan → execute → observe → reflect should be persisted states with append-only events. Never implement the loop as a recursive SDK stream wrapper.
5. **Tree-sitter baseline + ts-morph enrichment.** Use Tree-sitter for fast, cross-language structural indexing; use ts-morph for precise TypeScript/JavaScript symbols and references. Store derived facts in SQLite/FTS5, not full file bodies.
6. **Node sidecar in Tauri.** Run the same TypeScript core as a long-lived sidecar in the standalone app. Rust should own security, lifecycle, secrets, and IPC — not duplicate the agent.

This report expands on `RESEARCH_CODEX.md` with fresh findings from the Cline v4 SDK, Goose's current MCP-first architecture, and up-to-date provider quirks.

---

## 1. Multi-Provider LLM Support

### 1.1 What Cline actually does today

Cline has migrated to a **v4 SDK monorepo**. The old `src/core/api/providers/*.ts` paths are stale; the implementation now lives in:

- `apps/vscode/` — VS Code extension host + webview
- `sdk/packages/llms/src/providers/` — provider registry, gateway, adapters
- `sdk/packages/core/src/runtime/` — session orchestration, OAuth token manager
- `sdk/packages/agents/src/` — agent runtime loop

#### Provider registry

Providers are declared in `sdk/packages/llms/src/providers/builtins.ts` as `BuiltinSpec` entries:

```typescript
interface BuiltinSpec {
  id: string; // e.g. "openai-codex", "openai", "anthropic"
  name: string;
  family: string;
  protocol: string;
  client: string;
  capabilities: string[]; // tools, reasoning, prompt-cache, images, oauth, ...
  defaultModelId: string;
  modelsFactory: (...args: any[]) => ModelManifest[];
  configFields: FieldSpec[];
  defaults: Partial<ProviderConfig>;
  metadata: Record<string, unknown>;
}
```

A factory creates the handler:

```typescript
// sdk/packages/llms/src/providers.ts
export function createHandler(config: ProviderConfig): ApiHandler {
  const normalized = withNormalizedProviderId(config);
  if (hasRegisteredHandler(normalized.providerId)) {
    const handler = getRegisteredHandler(normalized.providerId, normalized);
    if (handler) return handler;
  }
  return createGatewayApiHandler(normalized); // openai-compatible fallback
}
```

Cline's `GatewayApiHandler` (`sdk/packages/llms/src/providers/compat.ts`) normalizes arbitrary configs into a unified `ApiStream`, mapping text, reasoning, tool-call, usage, and finish events. This is the right pattern: **normalize centrally, specialize at the edge**.

#### ChatGPT subscription / OpenAI Codex OAuth

Cline's `openai-codex` provider is distinct from ordinary OpenAI API-key access. It is a ChatGPT-subscription path:

- Authorization endpoint: `https://auth.openai.com/oauth/authorize`
- Token endpoint: `https://auth.openai.com/oauth/token`
- PKCE `S256`
- Local callback server on `localhost:1455`
- Scopes: `openid profile email offline_access`
- Extracts `chatgpt_account_id` from JWT claim path `https://api.openai.com/auth`
- Base URL: `https://chatgpt.com/backend-api/codex`

Key files:

- `sdk/packages/core/src/auth/codex.ts` — `loginOpenAICodex`, `refreshOpenAICodexToken`
- `sdk/packages/core/src/auth/provider-auth-registry.ts` — registered auth handlers
- `sdk/packages/core/src/runtime/orchestration/runtime-oauth-token-manager.ts` — single-flight refresh, 5-minute buffer, `invalid_grant` handling
- `apps/vscode/src/extension.ts` — URI handler for deep links

The runtime token manager (`RuntimeOAuthTokenManager`) deduplicates concurrent refreshes per `storageProviderId`, refreshes with a 5-minute buffer, and throws `OAuthReauthRequiredError` on `invalid_grant`. The host calls `syncOAuthCredentials(session)` before every turn and has a `runWithAuthRetry` path that restores baseline messages and replays the turn after a forced refresh.

**Critical for Tripp.Forge:** Cline uses its own OAuth client ID. Do not copy it. Direct ChatGPT subscription support should be behind an `experimental.chatgptSubscription` flag until OpenAI authorizes Tripp.Forge's own client. Safe fallbacks are public OpenAI API keys and a user-installed official Codex CLI adapter.

#### Provider switching mid-conversation

Cline switches providers by mutating `AgentConfig` for the _next_ turn, not inside an active stream:

```typescript
// sdk/packages/core/src/runtime/host/local-runtime-host.ts
async updateSessionConnection(sessionId: string, rawUpdates: SessionConnectionUpdate) {
  const updates = normalizeConnectionUpdate(rawUpdates);
  const session = this.getSessionOrThrow(sessionId);
  if (updates.providerId !== undefined) session.config.providerId = updates.providerId;
  if (updates.modelId !== undefined) session.config.modelId = updates.modelId;
  // ... baseUrl, headers, reasoning, thinking ...
  session.agent.updateConnection({ ... });
}
```

The conversation transcript is retained in `ConversationStore`; the new model receives the full replay. There is no KV-cache rewind at this layer.

### 1.2 Recommended canonical provider architecture for Tripp.Forge

Separate four concerns:

```typescript
type ProviderId = string;

interface ProviderManifest {
  id: ProviderId;
  displayName: string;
  auth: Array<'api-key' | 'oauth-pkce' | 'oauth-browser' | 'host-cli' | 'none'>;
  transports: Array<'chat-completions' | 'responses' | 'anthropic-messages'>;
  defaultBaseUrl: string;
  models: ModelManifest[]; // refreshed, cached, bundled fallback list
}

interface ModelCapabilities {
  contextTokens: number;
  maxOutputTokens?: number;
  tools: 'native' | 'prompt-emulated' | 'none';
  parallelTools: boolean;
  vision: boolean;
  reasoning:
    | false
    | {
        controls: string[]; // e.g. ['thinking','reasoning_effort']
        returnsTrace: boolean; // assistant message has reasoning_content
        requiresEcho: boolean; // must send reasoning_content back on tool turns
      };
  usageInStream: boolean;
  supportsSystemRole: boolean;
  supportsDeveloperRole: boolean;
  supportsResponsesApi: boolean;
}

interface ProviderAdapter {
  listModels(signal: AbortSignal): Promise<ModelManifest[]>;
  stream(req: CanonicalRequest, signal: AbortSignal): AsyncIterable<LlmEvent>;
  classifyError(error: unknown): ProviderError;
}

type LlmEvent =
  | { type: 'text-delta'; text: string }
  | { type: 'reasoning-delta'; text: string }
  | { type: 'tool-call-start'; id: string; name: string }
  | { type: 'tool-call-args-delta'; id: string; json: string }
  | { type: 'tool-call-end'; id: string }
  | { type: 'usage'; input: number; output: number; cached?: number }
  | { type: 'finish'; reason: 'stop' | 'tool-calls' | 'length' | 'cancelled' };
```

Adapter responsibilities:

- Assemble fragmented streamed tool JSON.
- Generate or repair missing tool-call IDs per provider constraints.
- Normalize finish reasons.
- Emit usage independently of content chunks.
- Translate canonical turns into the provider's dialect.

### 1.3 OpenAI-compatible provider specifics

| Provider            | Base URL                                                                                                                    | Auth                        | Notable adapter requirements                                                                                                                                                                                             |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------- | --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Xiaomi MiMo**     | Pay-as-you-go: `https://api.xiaomimimo.com/v1`; Token Plan: region-specific `https://token-plan-{region}.xiaomimimo.com/v1` | API key (`sk-*` or `tp-*`)  | Detect key prefix to pick base URL. Anthropic-format path `/anthropic` available. Preserve `reasoning_content` on tool turns.                                                                                            |
| **DeepSeek**        | `https://api.deepseek.com`                                                                                                  | Bearer                      | `thinking` + `reasoning_effort` via `extra_body`. **Must echo `reasoning_content` back on tool turns.** Strip temperature/top_p when thinking enabled. Legacy `deepseek-chat`/`deepseek-reasoner` deprecated 2026-07-24. |
| **Kimi / Moonshot** | `https://api.moonshot.ai/v1`                                                                                                | Bearer                      | `thinking` via `extra_body`; `partial` on assistant messages. Up to 128 tools; tool names must match `^[a-zA-Z_][a-zA-Z0-9-_]{2,63}$`; `strict` defaults true; emit `tool_choice: "auto"` explicitly.                    |
| **xAI / Grok**      | `https://api.x.ai/v1`                                                                                                       | Bearer (`xai-...`) or OAuth | Use `x-grok-conv-id` header for cache affinity. Strip `stop`/`presencePenalty`/`frequencyPenalty` for reasoning models. `grok-4.20-multi-agent` needs a separate endpoint.                                               |
| **Ollama**          | `http://127.0.0.1:11434/v1`                                                                                                 | Dummy key                   | Responses API is non-stateful. Tools/vision/reasoning are model-dependent. Discover models via `GET /v1/models`. Context via Modelfile `num_ctx`.                                                                        |
| **OpenAI**          | `https://api.openai.com/v1`                                                                                                 | API key or OAuth            | Responses API is stateful (`previous_response_id`); Chat Completions is stateless. `developer` role replaces `system` for o1+. Built-in tools via Responses API.                                                         |

**Recommendation:** Build the canonical ledger around the **Chat Completions message shape** because it is the lowest common denominator. Use Responses API only as a transport specialization for OpenAI/xAI when built-in tools or statefulness are needed, and translate back to the canonical ledger.

### 1.4 Keys, OAuth, rate limits, and failover

**Secrets**

- VS Code: `ExtensionContext.secrets` (`SecretStorage`).
- Tauri: Rust `keyring` crate → OS credential vault.
- Never store keys in settings, conversation history, or logs.

**Rate limiting**

- Per-provider token bucket + concurrency semaphore.
- Parse `Retry-After` and provider-specific reset headers.
- Retry only safe failures: 408, 429, 5xx, network reset before definitive completion. Use full-jitter exponential backoff.
- Do not retry 400/401/403 or deterministic tool failures.

**Failover**

- Only at model-call boundaries.
- Recompile canonical history for the fallback provider.
- Require user-approved routing policy before moving private code to a different provider.
- Maintain a model ladder: Tier A (frontier hosted), Tier B (alternate vendor), Tier C (local Ollama).

---

## 2. VS Code Extension Architecture

### 2.1 Host/UI split

Run privileged logic in the Node extension host. The webview is an untrusted presentation client that communicates by message passing.

```text
React Webview
  ↕ versioned request/event protocol
Extension Controller
  ├─ AgentCore
  ├─ VsCodeFileHost / TerminalHost / SecretHost / EditorHost
  ├─ Index worker
  └─ SQLite worker or repository
```

Cline's structure:

- `apps/vscode/src/extension.ts` — activation, URI handler, webview registration
- `apps/vscode/src/hosts/vscode/VscodeWebviewProvider.ts` — sidebar webview
- `apps/vscode/webview-ui/src/App.tsx` — React UI
- `apps/vscode/src/core/controller/index.ts` — large orchestrator
- `apps/vscode/src/hosts/vscode/terminal/` — terminal manager, process, registry
- `apps/vscode/src/hosts/vscode/VscodeDiffViewProvider.ts` — diff via virtual document scheme `cline-diff`

### 2.2 Webview side panel

Use `WebviewViewProvider` for a persistent Activity Bar panel:

```typescript
export class TrippForgeSidebarProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'trippForge.sidebar';
  private _view?: vscode.WebviewView;

  constructor(private readonly _extensionUri: vscode.Uri) {}

  resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken,
  ) {
    this._view = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri],
    };
    webviewView.webview.html = this._getHtml(webviewView.webview);

    webviewView.webview.onDidReceiveMessage(async (msg) => {
      // validate msg.v, msg.type, msg.id
      await this._handleUiRequest(msg);
    });
  }
}
```

Register:

```typescript
context.subscriptions.push(
  vscode.window.registerWebviewViewProvider(TrippForgeSidebarProvider.viewType, provider, {
    webviewOptions: { retainContextWhenHidden: true },
  }),
);
```

Message envelopes need versioning, correlation IDs, validation (Zod), cancellation, and backpressure. Set a strict CSP with a per-render nonce.

### 2.3 Inline suggestions (ghost text)

Use `languages.registerInlineCompletionItemProvider`:

```typescript
const provider: vscode.InlineCompletionItemProvider = {
  provideInlineCompletionItems: async (document, position, context, token) => {
    const prefix = document.getText(new vscode.Range(new vscode.Position(0, 0), position));
    const suffix = document.getText(
      new vscode.Range(position, document.positionAt(document.getText().length)),
    );

    const completion = await fastModel.complete(prefix, suffix, {
      language: document.languageId,
      uri: document.uri.toString(),
      token,
    });

    if (!completion) return [];
    const item = new vscode.InlineCompletionItem(completion);
    item.range = new vscode.Range(position, position);
    return [item];
  },
};

context.subscriptions.push(
  vscode.languages.registerInlineCompletionItemProvider({ pattern: '**' }, provider),
);
```

Design completions as a separate low-latency path: debounce 100–250 ms, cancel on edit/move, cache by `(uri, version, position, normalized prefix hash)`, and target sub-second first token.

### 2.4 Diff views and applying edits

Use a virtual document content provider for the proposed side:

```typescript
const originalUri = document.uri;
const proposedUri = vscode.Uri.parse(`tripp-forge-diff:${originalUri.path}?version=${Date.now()}`);

// Content provider registered earlier
vscode.workspace.registerTextDocumentContentProvider('tripp-forge-diff', {
  provideTextDocumentContent(uri) {
    return proposalStore.get(uri.query)?.proposedContent ?? '';
  },
});

await vscode.commands.executeCommand(
  'vscode.diff',
  originalUri,
  proposedUri,
  `${path.basename(originalUri.path)} — Tripp.Forge`,
);
```

Apply with `WorkspaceEdit` after checking base version/hash:

```typescript
const edit = new vscode.WorkspaceEdit();
edit.replace(originalUri, range, replacement);
const success = await vscode.workspace.applyEdit(edit);
```

For stale files, perform a three-way merge (`base`, `current`, `proposed`) and show conflicts. Never overwrite from an old snapshot.

### 2.5 Terminal integration

For visible commands, use a real `Terminal` and shell integration's `executeCommand` when available:

```typescript
const terminal = vscode.window.createTerminal('Tripp.Forge');
terminal.show();
terminal.shellIntegration?.executeCommand('npm test');
```

For captured non-interactive jobs, spawn a child process in the extension host and stream bounded stdout/stderr. Track shell, cwd, env delta, start/end, exit/signal, and truncation. Support cancellation by terminating the process tree.

**Remote workspaces:** use `vscode.Uri` / `workspace.fs`, not local `fsPath`. Set `"extensionKind": ["workspace"]` in `package.json` if the extension must run where files live.

### 2.6 Performance and activation

- Activate on contributed view/commands, not `*`.
- Bundle extension and webview separately with esbuild/Vite.
- Keep parsing, embeddings, and SQLite work off the event loop using workers/child processes.
- Dispose every command, provider, watcher, terminal listener, and webview listener through `context.subscriptions`.

---

## 3. Tool System Design (Goose-style)

### 3.1 What Goose demonstrates

Goose (now under the Agentic AI Foundation) is Rust-first but its architecture is highly portable. Key concepts:

- **Extension config enum** (`crates/goose/src/agents/extension.rs`):
  - `stdio` — external command
  - `sse` / `streamable_http` — HTTP/SSE endpoint
  - `builtin` — separate MCP server
  - `platform` — in-process privileged extension
  - `frontend` — UI-resident tools
  - `inline_python` — Python via `uvx`

- **Extension manager** (`crates/goose/src/agents/extension_manager.rs`):
  - Spawns transports
  - `fetch_all_tools()` with prefixing (`{ext}__{tool}`)
  - `dispatch_tool_call()` routes to owning client
  - `available_tools` allow-list

- **MCP client abstraction** (`crates/goose/src/agents/mcp_client.rs`):
  - `list_tools`, `call_tool`, `read_resource`, `subscribe`
  - Advertises roots, sampling, extensions, elicitation

- **Permission model** (`crates/goose/src/config/permission.rs`, `crates/goose/src/permission/`):
  - Persistent levels: `AlwaysAllow`, `AskBefore`, `NeverAllow`
  - Runtime choices: `AllowOnce`, `AlwaysAllow`, `DenyOnce`, `AlwaysDeny`
  - Inspector pipeline: permission, security, egress, adversary, repetition
  - SmartApprove: LLM-based read-only detection, cached per tool

- **Tool schemas**:
  - JSON Schema inputs (via `schemars` in Rust; `zod-to-json-schema` in TS)
  - Typed output structs
  - `CallToolResult` with `content: Vec<Content>`, `is_error`, `structured_content`

### 3.2 Recommended TypeScript tool contract

```typescript
type Effect = 'read' | 'write' | 'execute' | 'network' | 'credential';

interface ToolContext {
  runId: string;
  callId: string;
  workspaceRoots: URL[];
  signal: AbortSignal;
  emit(event: ToolProgress): void;
  hosts: HostCapabilities;
}

interface Tool<I extends z.ZodTypeAny, O extends z.ZodTypeAny> {
  manifest: {
    name: string; // stable, namespaced: fs.read
    version: string;
    description: string;
    input: I;
    output: O;
    effects: Effect[];
    idempotency: 'safe' | 'conditional' | 'unsafe';
    defaultRisk: 'low' | 'medium' | 'high' | 'critical';
  };
  preview(input: z.infer<I>, ctx: ToolContext): Promise<ActionPreview>;
  execute(input: z.infer<I>, ctx: ToolContext): Promise<z.infer<O>>;
}
```

The registry rejects duplicate `(name, version)`, converts Zod to JSON Schema (`zod-to-json-schema`), and advertises only tools the selected model and host can use.

### 3.3 Execution pipeline

```text
model call → assemble args → Zod parse → canonicalize paths/command
→ preview/diff → policy evaluation → approval → execute with deadline
→ output validation → artifact storage/truncation → audit event → observation
```

### 3.4 Approval policy

Risk derives from **effects + resolved arguments**:

- Reading `.env` is higher risk than reading `README.md`.
- `git status` differs from `git push --force`.
- A write outside the workspace is critical.

Decisions: `allow-once`, `allow-session`, `always-allow` (persisted scoped rule), `deny-once`, `always-deny`, `cancel-run`.

Persist rules as predicates: tool + workspace + command executable + path glob + network host.

Hard guardrails remain even in auto-approve mode:

- workspace-root containment after symlink resolution;
- protected paths and secret-file detection;
- no recursive delete, force push, credential export, or privilege escalation without explicit critical approval;
- command timeout/output limits and process-tree cancellation;
- network domain policy for browser/fetch tools.

### 3.5 Built-in tools

| Tool                       | Responsibility                  | Key behavior                                                     |
| -------------------------- | ------------------------------- | ---------------------------------------------------------------- |
| `fs.read`                  | Read file with line/byte ranges | Return hash and line spans                                       |
| `fs.list`                  | Directory tree                  | Respect ignores                                                  |
| `fs.search`                | Filename/content search         | Bounded results                                                  |
| `fs.patch`                 | Structured find/replace         | Check base hash, preview, atomic write, verify                   |
| `terminal.run`             | Shell command                   | Prefer executable/args, stream chunks, truncate, capture exit    |
| `browser.*`                | Playwright-based automation     | Isolated profile, restrict `file:`/localhost/private nets        |
| `git.*`                    | Read/mutate Git                 | Separate read and mutation tools; show staged diff before commit |
| `web.search` / `web.fetch` | Web retrieval                   | Domain policy, timeout, content truncation                       |

Treat MCP servers as separate principals. Validate their advertised schemas, namespace tools by server, cap output, and request approval based on annotations plus local policy.

---

## 4. Codebase Indexing (Augment-style)

### 4.1 Evidence boundary

Augment's exact production indexer is proprietary. The architecture below is an Augment-style outcome built from established open-source components.

### 4.2 Parsing strategy

Use **Tree-sitter** as the cross-language structural baseline. It is incremental, error-tolerant, and fast. Use **ts-morph** (or the TypeScript compiler API) in a worker for precise TypeScript/JavaScript semantics: resolved symbols, aliases, references, signatures, and tsconfig project semantics.

`@typescript-eslint/parser` is optimized for lint rules, not durable code graphs. Avoid it as the indexer foundation.

### 4.3 SQLite schema

Use `better-sqlite3` in Node (FTS5 built-in, supports `sqlite-vec`). Use WAL mode, foreign keys, prepared statements, one writer queue, and migrations.

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;

CREATE TABLE files (
  id INTEGER PRIMARY KEY,
  uri TEXT NOT NULL UNIQUE,
  language TEXT,
  content_hash BLOB NOT NULL,
  mtime_ms INTEGER,
  size_bytes INTEGER,
  parse_version INTEGER NOT NULL,
  indexed_at INTEGER NOT NULL
);

CREATE TABLE symbols (
  id INTEGER PRIMARY KEY,
  file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  stable_key TEXT NOT NULL,
  name TEXT NOT NULL,
  qualified_name TEXT,
  kind TEXT NOT NULL,
  start_byte INTEGER NOT NULL,
  end_byte INTEGER NOT NULL,
  start_line INTEGER NOT NULL,
  end_line INTEGER NOT NULL,
  signature TEXT,
  doc TEXT,
  exported INTEGER NOT NULL DEFAULT 0,
  UNIQUE(file_id, stable_key)
);

CREATE TABLE chunks (
  id INTEGER PRIMARY KEY,
  file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  symbol_id INTEGER REFERENCES symbols(id) ON DELETE SET NULL,
  start_byte INTEGER NOT NULL,
  end_byte INTEGER NOT NULL,
  token_estimate INTEGER NOT NULL,
  content_hash BLOB NOT NULL,
  body TEXT NOT NULL
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
  src_file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  dst_file_id INTEGER REFERENCES files(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  confidence REAL NOT NULL,
  evidence TEXT
);

CREATE TABLE imports (
  id INTEGER PRIMARY KEY,
  file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  raw_specifier TEXT NOT NULL,
  resolved_file_id INTEGER REFERENCES files(id) ON DELETE SET NULL,
  is_type_only INTEGER DEFAULT 0,
  names TEXT
);
```

### 4.4 Incremental indexing

```text
file event
  → ignore/binary/size filter (.gitignore + .forgeignore)
  → debounce 300–1000 ms
  → compute content hash
  → skip if hash matches
  → parse (Tree-sitter baseline + optional ts-morph enrichment)
  → extract symbols / edges / chunks
  → in transaction:
      DELETE old facts for file
      INSERT new symbols, chunks, edges, FTS rows
      UPDATE files.content_hash
```

Overlay unsaved editor buffers in memory keyed by `(uri, version)`. Reconcile watcher state against hashes periodically because events can be lost.

### 4.5 Relevance scoring

Use hybrid retrieval with explainable features, then diversify with Maximal Marginal Relevance:

```text
score = 0.30 * normalized_BM25
      + 0.20 * symbol_exact_or_prefix
      + 0.15 * semantic_similarity
      + 0.12 * graph_proximity
      + 0.08 * active_file_proximity
      + 0.06 * git_recency_or_changed
      + 0.04 * path_prior
      + 0.03 * test_source_pair
      - duplication_penalty
      - generated_large_file_penalty
```

Normalize each feature per query. First resolve explicit paths/symbols, then lexical/semantic candidates, graph-expand the best seeds, rerank, and apply MMR.

### 4.6 Context packing

- Repository map: compact skeleton for active area.
- Full bodies: only for the few symbols being edited.
- Signatures: for neighbors (callers, callees, types).
- Line-ranged evidence: for references/tests.

Every chunk carries URI, line span, hash, token estimate, and reason selected.

---

## 5. Agent Loop Design

### 5.1 Durable state machine

Model plan/execute/observe/reflect as persisted states:

```typescript
type RunState =
  | { tag: 'planning' }
  | { tag: 'calling-model'; requestId: string }
  | { tag: 'awaiting-approval'; callId: string }
  | { tag: 'executing-tool'; callId: string; attempt: number }
  | { tag: 'observing'; callId: string }
  | { tag: 'reflecting' }
  | { tag: 'paused'; reason: string }
  | { tag: 'completed' }
  | { tag: 'failed'; error: SerializedError };
```

Append events before/after side effects. On restart, replay to the last durable boundary. An `executing-tool` event without a completion is **"outcome unknown,"** not permission to repeat.

### 5.2 Recommended loop

1. **Plan:** create/update a short structured plan for multi-step work. Identify acceptance checks and risk.
2. **Select context:** retrieve to a hard input budget; do not dump whole files.
3. **Act:** request one or a small parallel set of independent, read-only tools. Serialize writes.
4. **Observe:** normalize result, diagnostics, file hashes, exit status, and new facts.
5. **Reflect:** compare against plan and acceptance checks; update hypotheses.
6. **Verify:** run focused tests/typecheck/lint and inspect diffs before declaring completion.
7. **Finish or pause:** summarize changes, evidence, remaining risk, and blockers.

### 5.3 Self-healing

Classify failures and apply bounded recovery:

| Failure class                   | Recovery                                                      |
| ------------------------------- | ------------------------------------------------------------- |
| Schema error                    | One model repair with validation diagnostics                  |
| Stale edit                      | Refresh base, replan/three-way merge                          |
| Command failure                 | Expose exit/stderr, at most two materially different attempts |
| Provider transient              | Adapter retry policy; no duplicate side effects               |
| Context overflow                | Compact/retrieve less and retry once                          |
| Repeated identical action/error | Stop and request user input                                   |

Track budgets: maximum turns, model calls, tool calls, wall time, estimated cost, repeated failures, changed files. A circuit breaker pauses when exceeded.

### 5.4 Context window management

Reserve the window before packing:

```text
input budget = model context
             - reserved output
             - system/tool schemas
             - safety margin (5–10%)
```

Use four-tier memory:

- Immutable run brief and user constraints.
- Recent canonical turns verbatim.
- Rolling, versioned summary of older turns.
- External artifacts/index references fetched on demand.

Never summarize away pending approvals, failed attempts, file hashes, user decisions, or acceptance criteria.

### 5.5 Multi-file edits

Create an `EditTransaction` with base hashes for all files, ordered patch operations, proposed results, and validation commands. Preview all changes, acquire approvals, check bases again, apply through the host, and roll back only Tripp-owned changes if application fails. After apply, re-index changed files synchronously before verification.

---

## 6. Tauri 2.0 Standalone App

### 6.1 Recommended process architecture

```text
React/Vite Webview
  ↕ Tauri commands + Channel<DesktopEvent>
Rust shell/security host
  ├─ capabilities, keychain, dialogs, updater, sidecar lifecycle
  ├─ filesystem/process commands with scoped policy
  └─ Node sidecar: forge-agent
       ├─ shared TypeScript AgentCore
       ├─ provider streaming
       ├─ tool registry / Playwright
       └─ owns index + session SQLite
```

Use a Node sidecar compiled/bundled as a platform binary. Communicate over framed JSON-RPC on stdin/stdout or a loopback socket with ephemeral bearer token, protocol version, request ID, sequence number, cancellation, heartbeat, and max frame size. Reserve stderr for logs so stdout framing cannot be corrupted.

**Why not `deno_core`:** embedding V8 in Rust increases binary size, build complexity, native-module incompatibility, sandbox design work, and debugging burden. Use a sidecar to maximize reuse of the same TypeScript core.

### 6.2 Tauri project structure

```text
apps/desktop/
├── package.json
├── vite.config.ts
├── index.html
├── src/                        # React frontend
│   ├── App.tsx
│   ├── components/
│   ├── hooks/
│   ├── stores/
│   └── lib/
└── src-tauri/
    ├── Cargo.toml
    ├── tauri.conf.json
    ├── capabilities/
    │   └── default.json
    ├── binaries/               # sidecar executables
    └── src/
        └── lib.rs
```

### 6.3 IPC and streaming

Commands for request/response:

```rust
#[tauri::command]
async fn start_run(prompt: String, state: State<'_, ForgeState>) -> Result<RunHandle, String> {
  // dispatch to sidecar / core
}
```

Channels for streaming:

```rust
#[derive(Clone, Serialize)]
#[serde(tag = "event")]
enum ForgeEvent {
  Started { runId: String },
  TextDelta { runId: String, text: String },
  ToolCall { runId: String, callId: String, name: String, args: Value },
  ApprovalRequired { runId: String, callId: String, preview: Value },
  Finished { runId: String },
}

#[tauri::command]
async fn run_stream(prompt: String, on_event: Channel<ForgeEvent>) -> Result<(), String> {
  // run core and send events through channel
}
```

### 6.4 SQLite ownership

Use separate databases or clear prefixes:

- `state.db`: workspaces, conversations, run events, plans, approvals, settings metadata.
- Per-project `index.db`: files, symbols, graph, chunks, retrieval metadata.
- Optional `cache.db`: model lists, token estimates, disposable caches.

One process should own each database's writes. The Tauri SQL plugin (`tauri-plugin-sql`) is convenient but exposing general SQL to the webview weakens layering. Prefer sidecar/Rust repository commands.

### 6.5 Security

Capabilities file example:

```json
{
  "$schema": "../gen/schemas/desktop-schema.json",
  "identifier": "main-capability",
  "windows": ["main"],
  "permissions": [
    "core:default",
    {
      "identifier": "fs:allow-read-text-file",
      "allow": [{ "path": "$HOME/projects/**" }]
    },
    {
      "identifier": "shell:allow-execute",
      "allow": [{ "name": "binaries/forge-agent", "sidecar": true }]
    }
  ]
}
```

- Grant only required commands/plugins to the main window.
- Scope filesystem/shell access.
- Disable remote navigation.
- Use a strict CSP.
- Rust must still validate paths and arguments; frontend validation is convenience only.

### 6.6 Ollama in Tauri

Do not bundle Ollama initially. Detect/connect at `http://127.0.0.1:11434`, offer install/start guidance, discover models, and let users configure another endpoint. Bundling model runtimes creates size, update, GPU, license, and security obligations.

---

## 7. Unified Monorepo Architecture

### 7.1 Recommended top-level shape

```text
tripp-forge/
├── apps/
│   ├── vscode/                 # VS Code extension host + webview UI
│   └── desktop/                # Tauri React app
├── packages/
│   ├── protocol/               # versioned DTOs/events, no host dependencies
│   ├── agent-core/             # state machine, context budget, checkpoints
│   ├── providers/              # normalized provider adapters and manifests
│   ├── tools/                  # schemas, registry, policy, built-ins
│   ├── indexer/                # parsers, graph, SQLite repository, retrieval
│   ├── host-contracts/         # FileHost, ProcessHost, SecretHost, EditorHost...
│   └── ui/                     # reusable React chat/tool/diff components
├── sidecars/
│   └── forge-agent/            # Node executable used by desktop
├── tools/                      # custom tool definitions
├── package.json                # pnpm workspaces
└── pnpm-workspace.yaml
```

### 7.2 Host contracts

Define interfaces that the core calls, implemented differently by VS Code and Tauri:

```typescript
interface FileHost {
  read(uri: URL, range?: ByteRange): Promise<FileReadResult>;
  write(uri: URL, content: string, opts: WriteOptions): Promise<FileWriteResult>;
  list(dir: URL): Promise<DirEntry[]>;
  watch(glob: string, cb: (event: FileEvent) => void): Disposable;
}

interface ProcessHost {
  spawn(cmd: string, args: string[], opts: SpawnOptions): Promise<ProcessSession>;
}

interface SecretHost {
  get(key: string): Promise<string | undefined>;
  set(key: string, value: string): Promise<void>;
  delete(key: string): Promise<void>;
}

interface EditorHost {
  showDiff(original: URL, proposed: string, title: string): Promise<void>;
  applyEdit(edits: FileEdit[]): Promise<boolean>;
  open(uri: URL, range?: LineRange): Promise<void>;
}
```

The core remains UI-independent; the same recorded run can replay in VS Code and Tauri.

---

## 8. Library Recommendations

| Area               | Primary choice                                            | Notes                                   |
| ------------------ | --------------------------------------------------------- | --------------------------------------- |
| Schemas/protocol   | `zod`, `zod-to-json-schema`                               | Validate all boundaries.                |
| IDs                | `nanoid` or UUIDv7                                        | Stable, sortable run/event IDs.         |
| Provider transport | `@ai-sdk/openai-compatible`, official `openai`            | Hidden behind adapters.                 |
| Parsing            | `tree-sitter`, `tree-sitter-typescript`                   | Broad incremental structure.            |
| TS semantics       | `ts-morph`                                                | Run in worker; cache projects.          |
| Database           | `better-sqlite3` in Node sidecar/extension worker         | Native packaging tests required.        |
| Search             | SQLite FTS5 + optional `sqlite-vec`                       | Start lexical/graph-first.              |
| Graph              | SQLite adjacency tables                                   | Avoid graph DB until scale proves need. |
| Process/PTY        | `execa`, `node-pty`                                       | Test process-tree termination.          |
| Browser            | `playwright-core`                                         | Separate process/profile.               |
| Git                | `simple-git` or direct `git` spawn                        | CLI is source of truth.                 |
| Patching           | `diff`, `diff-match-patch`                                | Add base hashes and merge path.         |
| VS Code UI         | React + VS Code webview-compatible tokens                 | Theme and accessibility first.          |
| Desktop UI         | React, Vite, Monaco, TanStack Query, Zustand              | Lazy-load heavy modules.                |
| Rust               | `tauri`, `serde`, `tokio`, `thiserror`, `keyring`, `sqlx` | Rust owns security/OS boundary.         |
| Observability      | OpenTelemetry with opt-in exporter                        | Redact aggressively.                    |

---

## 9. Pitfalls to Avoid

1. **Equating ChatGPT subscription with API credits.** They are different products/auth paths.
2. **Treating compatible APIs as identical.** Reasoning controls, tool streaming, images, usage, IDs, and errors differ.
3. **Provider objects leaking into history.** Persist canonical turns/events.
4. **Recursive agent loops.** Use a durable state machine.
5. **Approval in the UI only.** Policy must execute in the privileged host.
6. **Approving a tool name rather than resolved intent.** Canonical paths, command/cwd, URL, diff, and secrets determine risk.
7. **Blind tool retries.** A timeout does not prove a side effect failed.
8. **Whole-file prompt dumps.** Retrieve symbol/range context with provenance.
9. **Tree-sitter-only semantic claims.** Augment with compiler/LSP facts.
10. **Embedding everything first.** Lexical + symbols + graph is cheaper and often stronger.
11. **Blocking the VS Code extension host.** Parsing, embeddings, SQLite writes belong in workers.
12. **Using `sendText` as reliable execution.** Prefer shell integration or managed process.
13. **Stale edit overwrite.** Every proposal needs a base hash/version.
14. **Two SQLite writers/implementations.** Assign ownership; use IPC repositories.
15. **Unframed sidecar stdout.** Logs will corrupt the protocol.
16. **Broad Tauri capabilities.** The webview should not receive generic fs/shell/SQL power.
17. **Bundling Ollama/models by default.** Size, licensing, GPU, updates, attack surface.
18. **Prompt injection granting authority.** Repository/web/tool content is data.
19. **Logs containing source/secrets.** Default to metadata and hashes.
20. **No evaluation harness.** Provider conformance, retrieval quality, and patch reliability will regress invisibly.

---

## 10. Suggested Build Sequence

### Phase 0 — Contracts and fixtures

- Define canonical messages/events, host contracts, tool schemas, error taxonomy, capability manifests.
- Build scrubbed provider-stream fixtures and a replay adapter.
- Establish security model, data classification, and telemetry defaults.

### Phase 1 — Safe vertical slice (VS Code)

- VS Code chat webview → agent state machine → one API-key/OpenAI-compatible adapter.
- Read/search tools, approval pipeline, canonical ledger, cancellation, bounded output.
- Proposed single-file patch → VS Code diff → version-checked apply → verification.

### Phase 2 — Provider and tool breadth

- MiMo, DeepSeek, Kimi, xAI, Ollama manifests/adapters and conformance tests.
- Terminal, Git, multi-file edit transactions, checkpoints.
- Provider switching at turn boundaries and planner/executor roles.
- Investigate authorized ChatGPT/Codex subscription route; keep it isolated.

### Phase 3 — Context engine

- Tree-sitter workers, SQLite/FTS schema, TS semantic enrichment, import graph.
- Retrieval explanations and repository benchmark.
- Incremental/watch/unsaved-overlay correctness and large-repo load tests.

### Phase 4 — Standalone

- Tauri React shell, scoped capabilities, keychain, Node sidecar packaging.
- Versioned framed IPC with channels, durable session/event storage, Monaco/diff/terminal.
- Ollama discovery and private Tripp.Mind tools registered only in the desktop composition root.

### Phase 5 — Hardening

- Crash/restart and outcome-unknown recovery; remote VS Code; cross-platform packaging.
- Prompt-injection, symlink escape, command injection, secret redaction, malicious MCP tests.
- Provider chaos tests, cost/rate budgets, retrieval/agent evals.

---

## 11. Acceptance Criteria

The architecture is working when:

- The same recorded run can replay in VS Code and Tauri without UI dependencies in the core.
- Changing providers between turns requires only recompilation of canonical history.
- Every side effect has a validated schema, resolved preview, policy decision, approval/audit record, and outcome.
- A crash during a tool call resumes safely without repeating an uncertain mutation.
- A stale multi-file proposal cannot overwrite user edits.
- Retrieval can explain why each chunk was selected and meets measured recall/token targets.
- The extension host remains responsive during initial indexing.
- The Tauri webview cannot invoke arbitrary filesystem, shell, database, or sidecar operations.
- Secrets never enter settings, conversation history, telemetry, or default logs.
- Provider fixtures cover the incompatibilities that "OpenAI-compatible" hides.

---

## 12. Primary References

- Cline repository: https://github.com/cline/cline
- Goose repository: https://github.com/block/goose (now AAIF)
- VS Code Extension API: https://code.visualstudio.com/api/references/vscode-api
- VS Code Webview guide: https://code.visualstudio.com/api/extension-guides/webview
- Tauri 2.0: https://v2.tauri.app/
- Tauri sidecars: https://v2.tauri.app/develop/sidecar/
- Tauri SQL plugin: https://v2.tauri.app/plugin/sql/
- Tree-sitter: https://tree-sitter.github.io/tree-sitter/
- MiMo API: https://mimo.mi.com/docs/en-US/quick-start/first-api-call
- DeepSeek API: https://api-docs.deepseek.com/
- Kimi API: https://platform.kimi.ai/docs/api/overview
- xAI API: https://docs.x.ai/developers/quickstart
- Ollama OpenAI compatibility: https://docs.ollama.com/api/openai-compatibility
- OpenAI API: https://platform.openai.com/docs/api-reference
