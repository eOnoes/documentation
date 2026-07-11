# Tripp.Forge Technical Research Report

**Research date:** 2026-07-10  
**Scope:** Ground-up TypeScript agent core shared by a public VS Code extension and a private Tauri 2 desktop application  
**Source snapshots:** Cline `c5f146a41896ec26d915b6227cf5ec06162f8f49`; Goose `9cec9f2f4f1f5d5c9bfce351423539b7f313dc9f`

## Executive recommendation

Build Tripp.Forge as a hexagonal monorepo: a UI-independent TypeScript core owns conversations, provider normalization, the agent state machine, tool policy, and context selection; thin host adapters expose filesystem, process, editor, secrets, browser, and persistence capabilities for VS Code and Tauri. Do not let the React UI, VS Code API, Tauri IPC, a provider SDK, or raw tool implementations become the orchestration layer.

The most consequential design choices are:

1. Use a canonical internal LLM event protocol and capability matrix. Treat OpenAI compatibility as a transport dialect, not a promise of identical tools, reasoning, images, streaming, or usage accounting.
2. Make every agent transition durable and replayable. The loop should be an explicit state machine, not a recursive function around an SDK stream.
3. Put policy between tool selection and tool execution. Validate arguments, resolve paths, compute risk, request approval, execute, truncate/store output, and audit every invocation.
4. Use Tree-sitter for broad, incremental structural indexing, augmented by language services for precise references in priority languages. Store derived facts in SQLite/FTS5; keep file text on disk.
5. Run the shared TypeScript core as a long-lived Node sidecar in Tauri. Rust should own the security boundary, process lifecycle, OS integration, secrets, and high-throughput IPC—not duplicate the agent in Rust or embed a JavaScript engine prematurely.

Recommended top-level shape:

```text
apps/
  vscode/             extension host + webview UI
  desktop/            React/Vite UI + src-tauri
packages/
  protocol/           versioned DTOs/events, no host dependencies
  agent-core/         run state machine, context budget, checkpoints
  providers/          normalized provider adapters and manifests
  tools/              schemas, registry, policy, built-ins
  indexer/            parsers, graph, SQLite repository, retrieval
  host-contracts/     FileHost, ProcessHost, SecretHost, EditorHost...
  ui/                 reusable React chat/tool/diff components
sidecars/
  forge-agent/        Node executable used by desktop
```

## 1. Multi-provider LLM support

### What Cline currently demonstrates

Cline no longer models all providers as a single `OpenAI` client with a changed base URL. Its current SDK has provider identifiers, manifests/model metadata, a factory registry, normalized gateway handling, and routing rules for provider-specific options. Its tests explicitly cover OpenAI-compatible DeepSeek and Kimi-specific `thinking` behavior. This is the right lesson to copy: normalize centrally, specialize at the edge.

Cline's ChatGPT subscription integration is a distinct `openai-codex` provider, separate from ordinary OpenAI API-key access and from invoking a locally installed Codex CLI. At the inspected commit it:

- opens an OpenAI OAuth authorization-code flow with PKCE;
- listens on a localhost callback (`http://localhost:1455/auth/callback`), with manual code fallback;
- requests `openid profile email offline_access`;
- stores access token, refresh token, expiry, email, and ChatGPT account ID;
- refreshes before expiry, keeps a still-valid token during transient refresh errors, and logs out on likely `invalid_grant`;
- extracts `chatgpt_account_id` from token claims for the account header used by the Codex backend.

Cline's changelog and CLI documentation explicitly label this provider “OpenAI Codex (ChatGPT subscription).” This is **not** the public OpenAI API: normal OpenAI API use is authenticated with API keys and billed independently ([OpenAI API authentication](https://platform.openai.com/docs/api-reference/authentication), [Cline CLI providers](https://github.com/cline/cline/blob/main/docs/cline-cli/overview.mdx)).

Important product/legal caveat: do not copy Cline's OAuth client ID or private backend assumptions. A third-party product needs an OAuth client and permitted integration path issued for that product. Until OpenAI authorizes Tripp.Forge's flow, support one or both of:

- public OpenAI API keys via the documented API; and
- a user-installed official Codex CLI adapter that invokes the CLI as a subprocess, subject to its documented interface and terms.

Put direct ChatGPT subscription OAuth behind an experimental feature flag until its authorization and stability are confirmed. Never scrape ChatGPT cookies or reuse browser session tokens.

### Canonical provider architecture

Separate four concerns:

```typescript
type ProviderId = string;

interface ProviderManifest {
  id: ProviderId;
  displayName: string;
  auth: Array<'api-key' | 'oauth-pkce' | 'none' | 'host-cli'>;
  transport: 'responses' | 'chat-completions' | 'anthropic-messages' | 'custom';
  baseUrl?: string;
  models: ModelManifest[];
}

interface ModelCapabilities {
  contextTokens: number;
  maxOutputTokens?: number;
  tools: 'native' | 'prompt-emulated' | 'none';
  parallelTools: boolean;
  vision: boolean;
  reasoning: false | { controls: string[]; returnsTrace: boolean };
  usageInStream: boolean;
  supportsSystemRole: boolean;
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

The provider adapter must assemble fragmented streamed tool JSON, generate/repair missing tool-call IDs, normalize finish reasons, and emit usage independently of content chunks. Persist the canonical events, plus an encrypted/redacted raw-response diagnostic only when the user opts in.

### OpenAI-compatible providers

Use `@ai-sdk/openai-compatible` or the official `openai` TypeScript client for the wire format, but wrap either behind `ProviderAdapter`. The Vercel AI SDK is convenient for streaming and tool normalization; the official client exposes provider-native APIs sooner. Keep the wrapper narrow enough to change libraries.

Current official endpoints and notable differences:

| Provider             | Base URL                                                     | Recommended adapter notes                                                                                                                                                                                                                             |
| -------------------- | ------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Xiaomi MiMo          | `https://api.xiaomimimo.com/v1`                              | OpenAI- and Anthropic-compatible. Pay-as-you-go and token-plan products use different base URLs/credentials. Pass model-specific reasoning controls only when declared. [MiMo quick start](https://mimo.mi.com/docs/en-US/quick-start/first-api-call) |
| DeepSeek             | `https://api.deepseek.com` (`/v1` is also commonly accepted) | OpenAI-compatible but has provider-specific thinking/reasoning fields and model lifecycle changes. Do not hard-code old model aliases. [DeepSeek API docs](https://api-docs.deepseek.com/)                                                            |
| Kimi/Moonshot global | `https://api.moonshot.ai/v1`                                 | Chat Completions compatible; `thinking` is a provider extension and `partial` belongs on assistant messages. [Kimi API overview](https://platform.kimi.ai/docs/api/overview)                                                                          |
| xAI/Grok             | `https://api.x.ai/v1`                                        | Official docs advertise OpenAI REST compatibility. Maintain capability metadata instead of assuming every OpenAI field. [xAI quickstart](https://docs.x.ai/developers/quickstart)                                                                     |
| Ollama               | `http://127.0.0.1:11434/v1`                                  | No meaningful API key, local model discovery, variable context, model-dependent tools/vision. Responses support is not fully stateful; prefer local history. [Ollama compatibility](https://docs.ollama.com/api/openai-compatibility)                 |

Provider configuration should be data-driven but allow code hooks:

```typescript
const kimi: ProviderManifest = {
  id: 'moonshot',
  displayName: 'Kimi',
  auth: ['api-key'],
  transport: 'chat-completions',
  baseUrl: 'https://api.moonshot.ai/v1',
  models: [], // refreshed, cached with ETag/TTL; bundled fallback list
};
```

Maintain adapter conformance tests using recorded, scrubbed streams for text, tools, parallel calls, reasoning, images, cancellation, empty usage chunks, malformed JSON, 401, 429, and context overflow. Cline's changelog shows why: real compatible endpoints have returned final usage chunks with null/empty choices, inconsistent reasoning content, and invalid tool IDs.

### Switching providers mid-conversation

Never persist only a provider-native message array. Persist a canonical conversation ledger and compile it for the selected provider on every turn.

```typescript
interface TurnRecord {
  id: string;
  role: 'user' | 'assistant' | 'tool';
  parts: CanonicalPart[];
  providerAtCreation?: string;
  modelAtCreation?: string;
  createdAt: number;
}
```

On switch:

1. End or cancel the active stream; never hot-swap inside one response.
2. Validate the target model against conversation requirements (vision, native tools, context size).
3. Recompile canonical turns into its dialect. Strip unsupported reasoning traces and translate tool results.
4. Re-tokenize with a provider/model-specific estimator and compact if necessary.
5. Insert an internal boundary event recording old/new provider and model. Do not inject a prose message unless the model needs one.
6. Preserve stable Tripp tool call IDs, while adapters map them to provider constraints.

Offer separate model roles—`planner`, `executor`, `fast`, and `embedding`—rather than one global selection. Pin each run step to a resolved provider/model snapshot so a settings change cannot mutate an in-flight call.

### Keys, OAuth, rate limits, and failover

- VS Code: store secrets in `ExtensionContext.secrets` (`SecretStorage`), not settings/global state. Secret storage is platform-backed and not settings-synced ([VS Code API](https://code.visualstudio.com/api/references/vscode-api)).
- Tauri: expose a Rust secret-store command backed by the OS credential vault (for example `keyring`); SQLite stores only credential references and non-secret metadata.
- Redact `Authorization`, cookies, signed URLs, query tokens, and tool environment values from logs.
- Use a per-provider/account token bucket plus a concurrency semaphore. Parse `Retry-After` and rate-limit headers when present.
- Retry only safe failures: 408/429/5xx/network reset before a definitive completion. Use full-jitter exponential backoff and a retry budget. Never blindly retry a tool execution.
- Failover only at a model-call boundary. Record the fallback and recompile context. Do not silently move private code to another provider; require a user-approved routing policy.
- Use idempotency keys when a provider supports them. Deduplicate stream reconnects by request/run ID.

## 2. VS Code extension architecture

### Host/UI split

Run privileged logic in the Node extension host. The webview is an untrusted presentation client: it cannot access the VS Code API directly and communicates by messages ([Webview guide](https://code.visualstudio.com/api/extension-guides/webview)).

```text
React Webview
  ↕ versioned request/event protocol
Extension Controller
  ├─ AgentCore
  ├─ VsCodeFileHost / TerminalHost / SecretHost / EditorHost
  ├─ Index worker
  └─ SQLite worker or repository
```

Contribute an Activity Bar view container with a `WebviewViewProvider` for persistent chat. Allow the view to move to the panel/secondary sidebar and make CSS responsive. Use a separate `WebviewPanel` or normal editor tab only for wide artifacts. VS Code's UX guidance recommends native views where possible and webviews only for custom UI ([Webviews UX](https://code.visualstudio.com/api/ux-guidelines/webviews), [Workbench](https://code.visualstudio.com/api/extension-capabilities/extending-workbench)).

Message envelopes need versioning, correlation, validation, cancellation, and backpressure:

```typescript
const UiRequest = z.discriminatedUnion('type', [
  z.object({ v: z.literal(1), type: z.literal('run.start'), id: z.string(), prompt: z.string() }),
  z.object({
    v: z.literal(1),
    type: z.literal('approval.resolve'),
    id: z.string(),
    decision: z.enum(['allow-once', 'deny']),
  }),
  z.object({ v: z.literal(1), type: z.literal('run.cancel'), runId: z.string() }),
]);
```

Set a strict Content Security Policy with a per-render nonce; restrict `localResourceRoots`; convert resources with `webview.asWebviewUri`; validate every incoming message. Preserve UI state in the extension, not only `getState()` in the webview. Debounce persisted draft/scroll data.

### Inline suggestions

Register `languages.registerInlineCompletionItemProvider` to return `InlineCompletionItem`s; this is the supported ghost-text API ([Programmatic language features](https://code.visualstudio.com/api/language-extensions/programmatic-language-features)).

Design completion as a separate low-latency path, not the agent loop:

- debounce roughly 100–250 ms and cancel on every edit/cursor move;
- send prefix, suffix, language, nearby imports, and a small retrieved context budget;
- cache by `(document URI, version, position, normalized prefix hash)`;
- suppress in comments/strings when inappropriate, large files, secrets, and generated/minified paths;
- target sub-second first token; use the configured `fast` model;
- collect acceptance telemetry only with explicit privacy controls.

### Diffs and applying edits

Use a virtual document content provider for the proposed side and execute `vscode.diff(originalUri, proposedUri, title)`. Keep proposals in a transaction object containing original file hash/version, base content reference, structured edits, and proposed content.

Apply with `WorkspaceEdit` after checking the base version. Text-only workspace edits have all-or-nothing behavior, but mixed file operations may not; stage and validate first ([VS Code API](https://code.visualstudio.com/api/references/vscode-api)). For stale files, perform a three-way merge (`base`, `current`, `proposed`) and show conflicts. Do not overwrite from an old snapshot.

Prefer deterministic edits:

1. exact range edits tied to document version;
2. unified patches with context and fuzz limits;
3. whole-file replacement only for new/small files.

Create a run checkpoint before the first mutation. Keep “accept all,” per-file accept, per-hunk review, reject, undo, and open-diff actions.

### Terminal integration

For visible user commands, create a pseudoterminal or a regular `Terminal`; use shell integration's `executeCommand` when available so exit codes and execution boundaries are observable. `sendText` is a fallback and does not reliably prove completion. For noninteractive captured jobs, use a child process/task adapter in the extension host and stream bounded stdout/stderr to the UI.

Never concatenate untrusted arguments into a shell string when direct spawn is possible. Track shell, cwd, environment delta, start/end, exit/signal, and truncation. Support cancellation by terminating the process tree. Remote workspaces matter: the workspace extension host may run over SSH/WSL/Container while the webview is local ([Remote extensions](https://code.visualstudio.com/api/advanced-topics/remote-extensions)). Use `Uri`/`workspace.fs`, not assumptions about local `fsPath`.

### Extension performance

- Activate on contributed view/commands, not `*`.
- Bundle extension and webview separately with esbuild/Vite.
- Keep parsing, embeddings, and SQLite work off the extension-host event loop using workers/child processes.
- Watch files with VS Code APIs and coalesce bursts; honor excludes and `.gitignore` plus explicit `.forgeignore`.
- Dispose every command, provider, watcher, terminal listener, and webview listener through `context.subscriptions`.

## 3. Tool system design

### What to adopt from Goose

Goose is Rust-first, not a Zod TypeScript reference implementation. Its reusable architectural idea is extension through MCP plus explicit permissions. At the inspected commit its permission vocabulary includes `always_allow`, `allow_once`, `cancel`, `deny_once`, and `always_deny`, scoped to an extension or a tool. Tripp.Forge should support MCP as an extension protocol, while using Zod for first-party TypeScript tools. Do not load third-party code into the privileged core merely because it can register a function.

### Tool contract and registry

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

The registry rejects duplicate `(name, version)`, converts Zod to JSON Schema (for example `zod-to-json-schema` or Zod's current JSON-schema support), and advertises only tools the selected model and host can use. Keep schemas shallow, descriptions precise, enums bounded, and outputs structured. Tool output is untrusted data and must be delimited/typed before returning it to the model.

Execution pipeline:

```text
model call → assemble args → Zod parse → canonicalize paths/command
→ preview/diff → policy evaluation → approval → execute with deadline
→ output validation → artifact storage/truncation → audit event → observation
```

### Approval policy

Risk derives from effects **and resolved arguments**, not the tool name. Reading `.env` is higher risk than reading `README.md`; `git status` differs from `git push --force`; a write outside the workspace is critical.

Suggested decisions: `allow-once`, `allow-session` (exact rule), `always-allow` (persisted scoped rule), `deny-once`, `always-deny`, and `cancel-run`. Persist rules as predicates such as tool + workspace + command executable + path glob + network host. Show the exact normalized action, cwd/paths, environment changes, diff/command, and whether credentials/network are involved.

Hard guardrails remain even in auto-approve mode:

- workspace-root containment after symlink resolution;
- protected paths and secret-file detection;
- no recursive delete, force push, credential export, or privilege escalation without explicit critical approval;
- command timeout/output limits and process-tree cancellation;
- network domain policy for browser/fetch tools.

Treat MCP servers as separate principals. Validate their advertised schemas, namespace tools by server, cap output, and request approval based on annotations plus local policy. An MCP `readOnlyHint` is a hint, not proof.

### Built-in tools

**Files:** provide `fs.read` with line/byte ranges, `fs.list`, `fs.search`, `fs.patch`, and `fs.create`. Avoid a generic arbitrary write. Return hashes and line spans. `fs.patch` accepts a structured patch, checks the base hash, produces a preview, writes atomically through the host, then re-reads to verify.

**Terminal:** accept `{ executable?, args?, commandLine?, cwd, timeoutMs, envDelta }`. Prefer executable/args. Stream sequenced chunks, store full output as an artifact, and return a bounded tail plus exit metadata. Interactive commands require a visible PTY and user takeover.

**Browser:** run Playwright in a separate process/context. Default to isolated profiles; allow a user-owned persistent profile only with explicit opt-in. Split navigation/snapshot/click/type/download. Restrict `file:`, custom schemes, localhost/private networks as policy dictates. Page text is prompt-injection-capable and never grants tool authority.

**Git:** use `simple-git` or spawn `git` with arrays; do not reimplement Git. Separate read tools (`status`, `diff`, `log`) from mutations (`stage`, `commit`, `checkout`, `push`). Require cleanly defined repo root and show staged diff before commit. Never hide hooks, overwrite user changes, or auto-force-push.

## 4. Codebase indexing and retrieval

### Evidence boundary

Augment's exact production indexer, ranking model, and storage layout are proprietary; public product behavior is not enough to assert its internal implementation. The architecture below is an Augment-style outcome built from established components, not a claim about Augment source code.

### Parsing strategy

Use Tree-sitter as the cross-language structural baseline. It is incremental, fast enough for editor use, and remains useful with syntax errors ([Tree-sitter introduction](https://tree-sitter.github.io/tree-sitter/)). Use language-specific query files to extract definitions, imports, calls, docstrings, and scopes.

For TypeScript/JavaScript, add the TypeScript compiler API or `ts-morph` worker for resolved symbols, aliases, references, and tsconfig project semantics. `@typescript-eslint/parser` is optimized for ESLint ASTs and is not the best foundation for a persistent cross-language graph. For other high-value languages, optionally consume LSP definition/reference results. Keep a common fact model so precise facts can supersede heuristic ones.

Pipeline:

```text
file event → ignore/binary/size filter → content hash
→ parse worker → symbols/chunks/import specs → resolver
→ graph edges → lexical index → optional embeddings → atomic DB commit
```

Index saved content immediately; overlay unsaved editor buffers in memory keyed by document version. On rename/delete, update facts in a transaction. Periodically reconcile watcher state against hashes because file events can be lost.

### SQLite schema

Use WAL mode, foreign keys, prepared statements, one writer queue, read connections, and migrations. `better-sqlite3` is simple and fast in Node but its native binary must be packaged for VS Code targets and the Tauri sidecar; `libsql` adds unnecessary network semantics for the local index. Rust/Tauri may use `sqlx`, but the index should have one owning process to avoid two implementations.

```sql
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
  start_byte INTEGER NOT NULL, end_byte INTEGER NOT NULL,
  start_line INTEGER NOT NULL, end_line INTEGER NOT NULL,
  signature TEXT, doc TEXT, exported INTEGER NOT NULL DEFAULT 0,
  UNIQUE(file_id, stable_key)
);

CREATE TABLE edges (
  src_symbol_id INTEGER REFERENCES symbols(id) ON DELETE CASCADE,
  dst_symbol_id INTEGER REFERENCES symbols(id) ON DELETE CASCADE,
  src_file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  dst_file_id INTEGER REFERENCES files(id) ON DELETE CASCADE,
  kind TEXT NOT NULL, confidence REAL NOT NULL, evidence TEXT,
  UNIQUE(src_file_id, dst_file_id, kind, evidence)
);

CREATE TABLE chunks (
  id INTEGER PRIMARY KEY,
  file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  symbol_id INTEGER REFERENCES symbols(id) ON DELETE SET NULL,
  start_byte INTEGER NOT NULL, end_byte INTEGER NOT NULL,
  token_estimate INTEGER NOT NULL, content_hash BLOB NOT NULL
);

CREATE VIRTUAL TABLE chunk_fts USING fts5(
  chunk_id UNINDEXED, path, symbol, signature, body,
  tokenize='unicode61 remove_diacritics 2'
);
```

Also store unresolved imports and aliases. Do not store duplicate full file bodies in ordinary tables; reconstruct chunks from byte ranges after verifying the content hash. Embeddings belong in a separate versioned table keyed by chunk hash/model; use a SQLite vector extension only if packaging is reliable, otherwise keep a compact HNSW side index and rebuild it from SQLite metadata.

### Import graph

Resolution is language/project-specific. For TS/JS honor `tsconfig` paths, package exports, module resolution mode, monorepo workspaces, `.d.ts`, and extension substitution via TypeScript APIs. Store both the raw specifier and resolved file, with resolver version/confidence. Model file-to-file imports separately from symbol-level calls/references. Compute reverse edges on query, not as duplicated facts.

Useful graph operations:

- direct definitions/references;
- one-hop importers/imports;
- bounded caller/callee expansion;
- shortest dependency path;
- personalized PageRank or simple degree prior per repository;
- changed-file impact via reverse graph traversal.

Cap traversal depth and fan-out; generated hubs and barrel files otherwise flood context.

### Retrieval and relevance scoring

Use hybrid retrieval with explainable features, then diversify:

```text
score = 0.30 * lexical_BM25
      + 0.22 * symbol_exact_or_prefix
      + 0.15 * semantic_similarity
      + 0.12 * graph_proximity
      + 0.08 * active_file_proximity
      + 0.06 * git_recency_or_changed
      + 0.04 * path_prior
      + 0.03 * test_source_pair
      - duplication_penalty
      - generated_or_large_file_penalty
```

Normalize each feature per query; raw BM25 and cosine scores are not directly additive. First resolve explicit paths/symbols, then lexical/semantic candidates, graph-expand the best seeds, rerank, and apply maximal marginal relevance so ten near-identical chunks do not consume the budget. Log feature contributions for evaluation.

Context packing should include a compact repository map, full bodies only for the few symbols being edited, signatures for neighbors, and line-ranged evidence for references/tests. Every chunk carries URI, line span, hash, reason selected, and token estimate. Re-read changed files just before tool use.

Evaluate retrieval with a repository benchmark: issue/commit pairs, target files/symbols, recall@k, MRR, tokens-to-first-relevant, edit success, and latency. Without this, ranking weights are aesthetics.

## 5. Agent loop

### Durable state machine

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

Append events before/after side effects. On restart, replay to the last durable boundary; an `executing-tool` event without a completion is “outcome unknown,” not permission to repeat. This supports pause/resume, UI reconnect, Tauri sidecar restart, and audit.

Recommended loop:

1. **Plan:** create/update a short structured plan only for multi-step work. Identify acceptance checks and risk.
2. **Select context:** retrieve to a hard input budget; do not let the model browse an unbounded dump.
3. **Act:** request one or a small parallel set of independent, read-only tools. Serialize writes.
4. **Observe:** normalize result, diagnostics, file hashes, exit status, and new facts.
5. **Reflect:** compare against the plan and acceptance checks; update hypotheses, not a long hidden diary.
6. **Verify:** run focused tests/typecheck/lint and inspect diffs before declaring completion.
7. **Finish or pause:** summarize changes, evidence, remaining risk, and approvals/blockers.

### Self-healing without loops

Classify failures: invalid arguments, stale file, permission denied, missing executable, command failure, timeout, transient provider, rate limit, context overflow, or policy denial. Each class has a bounded recovery strategy.

- Schema error: one model repair with validation diagnostics.
- Stale edit: refresh base, replan/three-way merge; never overwrite.
- Command failure: expose exit/stderr, allow at most two materially different attempts.
- Provider transient: adapter retry policy; no duplicate side effects.
- Context overflow: compact/retrieve less and retry once.
- Repeated identical action/error fingerprint: stop and request user input.

Track budgets: maximum turns, model calls, tool calls, wall time, estimated cost, repeated failures, and changed files. A circuit breaker pauses when exceeded. “Reflect” should produce a small structured record (`goalStatus`, `evidence`, `nextAction`, `confidence`, `failureFingerprint`) rather than unlimited tokens.

### Context window management

Reserve the window before packing:

```text
input budget = model context
             - reserved output
             - system/tool schemas
             - safety margin (5–10%)
```

Use a four-tier memory:

- immutable run brief and user constraints;
- recent canonical turns verbatim;
- rolling, versioned summary of older turns;
- external artifacts/index references fetched on demand.

Never summarize away pending approvals, failed attempts, file hashes, user decisions, or acceptance criteria. Tool outputs are stored as artifacts; the model receives a bounded excerpt and handle. Re-summarize from canonical history, not from the prior summary alone, to limit drift. Token counters are provider-specific and estimates need a safety margin.

### Multi-file edits

Create an `EditTransaction` with base hashes for all files, ordered patch operations, proposed results, and validation commands. Preview all changes, acquire approvals, check bases again, apply through the host, and roll back only Tripp-owned changes if application fails. Never roll back unrelated user modifications. After apply, re-index changed files synchronously before verification.

## 6. Tauri 2 standalone

### Recommended process architecture

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

Use a Node sidecar compiled/bundled as a platform binary (for example Node SEA or `pkg` if its current limitations are acceptable). Communicate over framed JSON-RPC on stdin/stdout or a loopback socket with an ephemeral bearer token. Include protocol version, request ID, run ID, sequence number, cancellation, heartbeat, and maximum frame size. Keep logs on stderr so stdout framing cannot be corrupted.

Why not `deno_core`: embedding V8 in Rust increases binary size, build complexity, native-module incompatibility, sandbox design work, and debugging burden. It is justified only if eliminating the sidecar process becomes a measured requirement. A sidecar maximizes reuse of the same TypeScript core and Node ecosystem used by VS Code.

Tauri supports bundling external binaries as sidecars ([Embedding external binaries](https://v2.tauri.app/develop/sidecar/)). Do not bundle Ollama initially. Detect/connect to the user's service at `127.0.0.1:11434`, offer install/start guidance, discover models, and let users configure another endpoint. Bundling model runtimes/models creates major size, update, GPU, license, and security obligations.

### React application structure

Use Vite + React + TypeScript, TanStack Query for request/cache state, and Zustand or a reducer for ephemeral run/UI state. Do not mirror the complete durable run ledger in multiple stores; subscribe to ordered events and derive views.

Recommended panels: conversations, chat/plan timeline, tool/approval cards, editor (Monaco), proposed diff, terminal output, context inspector, provider/settings. Lazy-load Monaco and Playwright/browser UI. Reuse `packages/ui`, but keep transport hooks (`useVsCodeBridge`, `useTauriBridge`) host-specific.

### IPC and security

Tauri commands are appropriate for request/response and can be async. Tauri `Channel`s are the recommended mechanism for ordered streaming; events are JSON-oriented and not intended for high-throughput ordered data ([Calling Rust](https://v2.tauri.app/develop/calling-rust/), [Calling frontend](https://v2.tauri.app/develop/calling-frontend/)).

Expose coarse, typed commands such as `start_run`, `resolve_approval`, `cancel_run`, and `open_workspace`, not `run_arbitrary_command`. Generate TypeScript bindings from Rust DTOs with Specta/tauri-specta or verify shared JSON schemas in CI. Sequence every event and support snapshot/resume after gaps.

Tauri v2 capabilities are part of the security boundary: grant only required commands/plugins to the main window, scope filesystem/shell access, disable remote navigation, and use a strict CSP. The runtime authority checks whether a webview origin may invoke a command ([Tauri runtime authority](https://v2.tauri.app/security/runtime-authority/)). Rust must still validate paths and arguments; frontend validation is convenience only.

### SQLite ownership

Use separate databases or clear table prefixes for:

- `state.db`: workspaces, conversations, run events, plans, approvals, settings metadata;
- per-project `index.db`: files, symbols, graph, chunks, retrieval metadata;
- optional `cache.db`: model lists, token estimates, disposable caches.

The official Tauri SQL plugin provides frontend access through `sqlx` and transactional migrations ([Tauri SQL plugin](https://v2.tauri.app/plugin/sql/)), but exposing general SQL to the webview weakens layering. Prefer sidecar/Rust repository commands. One process should own each database's writes. Enable WAL, `busy_timeout`, foreign keys, migrations, backups before destructive migrations, and corruption recovery by rebuilding derived indexes.

## 7. Library recommendations

| Area               | Primary choice                                                      | Notes                                                                      |
| ------------------ | ------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Schemas/protocol   | `zod`, JSON Schema conversion                                       | Validate all UI, provider, tool, sidecar boundaries.                       |
| IDs                | UUIDv7 or `nanoid`                                                  | Stable sortable run/event IDs; never rely on provider IDs.                 |
| Provider transport | `@ai-sdk/openai-compatible`, official `openai`/provider SDKs        | Hidden behind adapters; use native SDK where compatibility loses features. |
| Parsing            | `tree-sitter` bindings + curated grammars                           | Broad incremental structure. Pin grammar ABI/versions.                     |
| TS semantics       | TypeScript compiler API or `ts-morph`                               | Run in worker; cache projects.                                             |
| Database           | `better-sqlite3` in Node sidecar/extension worker                   | Simple local ownership; plan native packaging tests.                       |
| Search             | SQLite FTS5/BM25 + optional embeddings                              | Start lexical/graph-first; add embeddings after evaluation.                |
| Graph              | SQLite adjacency tables                                             | Avoid a graph database until scale proves need.                            |
| Process/PTY        | `execa`/native spawn, `node-pty` for interactive                    | Native packaging and process-tree termination tests required.              |
| Browser            | `playwright-core`                                                   | Separate process/profile; browser download is a packaging decision.        |
| Git                | `simple-git` or direct `git` spawn                                  | Git CLI is the source of truth.                                            |
| Patching/diff      | `diff`, `diff-match-patch` or a maintained unified-diff parser      | Add strict base hashes and three-way merge.                                |
| VS Code UI         | React + VS Code webview UI-compatible tokens/components             | Theme and accessibility first; avoid unsupported DOM assumptions.          |
| Desktop UI         | React, Vite, Monaco, TanStack Query, Zustand/reducer                | Lazy-load heavy modules.                                                   |
| Rust               | `tauri`, `serde`, `tokio`, `thiserror`, `keyring`, `sqlx` as needed | Rust owns security/OS boundary.                                            |
| Observability      | OpenTelemetry with local opt-in exporter                            | Correlate run/request/tool IDs; redact aggressively.                       |

## 8. Pitfalls to avoid

1. **Equating ChatGPT subscription with API credits.** They are different products/auth paths. Do not promise subscription support without an authorized OAuth/CLI route.
2. **Treating compatible APIs as identical.** Reasoning controls, tool streaming, images, usage chunks, IDs, context limits, and errors differ.
3. **Provider objects leaking into history.** It makes switching/migration brittle; persist canonical turns/events.
4. **Recursive agent loops.** They are hard to cancel, resume, audit, and recover. Use a durable state machine.
5. **Approval in the UI only.** Policy must execute in the privileged host immediately before the action.
6. **Approving a tool name rather than resolved intent.** Canonical paths, command/cwd, URL, diff, and secrets determine risk.
7. **Blind tool retries.** A timeout does not prove a side effect failed; mark outcome unknown.
8. **Whole-file prompt dumps.** Retrieve symbol/range context with provenance and hard token budgets.
9. **Tree-sitter-only semantic claims.** It provides syntax, not fully resolved types/references; augment it with compiler/LSP facts.
10. **Embedding everything first.** Lexical + symbols + graph is cheaper, explainable, and often stronger for identifiers. Benchmark before adding complexity.
11. **Blocking the VS Code extension host.** Parsing, embeddings, SQLite writes, and large diffs belong in workers.
12. **Using `sendText` as reliable command execution.** Prefer shell integration or a managed process and capture exit state.
13. **Stale edit overwrite.** Every proposal needs a base hash/version and merge path.
14. **Two SQLite writers/implementations.** Assign ownership; use IPC repositories.
15. **Unframed sidecar stdout.** Logs will corrupt the protocol. Frame messages and reserve stderr for logs.
16. **Broad Tauri capabilities.** The webview should not receive generic filesystem/shell/SQL power.
17. **Bundling Ollama/models by default.** Size, licensing, GPU detection, updates, and attack surface outweigh convenience early on.
18. **Prompt injection granting authority.** Repository/web/tool content is data; only the user/policy layer grants actions.
19. **Logs containing source/secrets.** Default to metadata and hashes; make content diagnostics explicit and temporary.
20. **No evaluation harness.** Provider conformance, retrieval quality, patch reliability, and agent success will regress invisibly.

## 9. Build sequence

### Phase 0 — contracts and fixtures

- Define canonical messages/events, host contracts, tool schemas, error taxonomy, and capability manifests.
- Build scrubbed provider-stream fixtures and a replay adapter.
- Establish security model, data classification, and telemetry defaults.

### Phase 1 — safe vertical slice

- VS Code chat webview → agent state machine → one API-key/OpenAI-compatible adapter.
- Read/search tools, approval pipeline, canonical ledger, cancellation, bounded output.
- Proposed single-file patch → VS Code diff → version-checked apply → verification.

### Phase 2 — provider and tool breadth

- MiMo, DeepSeek, Kimi, xAI, Ollama manifests/adapters and conformance tests.
- Terminal, Git, multi-file edit transactions, checkpoints.
- Provider switching at turn boundaries and planner/executor roles.
- Investigate authorized ChatGPT/Codex subscription route; keep it isolated.

### Phase 3 — context engine

- Tree-sitter workers, SQLite/FTS schema, TS semantic enrichment, import graph.
- Retrieval explanations and repository benchmark.
- Incremental/watch/unsaved-overlay correctness and large-repo load tests.

### Phase 4 — standalone

- Tauri React shell, scoped capabilities, keychain, Node sidecar packaging.
- Versioned framed IPC with channels, durable session/event storage, Monaco/diff/terminal.
- Ollama discovery and private Tripp.Mind tools registered only in the desktop composition root.

### Phase 5 — hardening

- Crash/restart and outcome-unknown recovery; remote VS Code; Windows/macOS/Linux packaging.
- Prompt-injection, symlink escape, command injection, secret redaction, malicious MCP tests.
- Provider chaos tests, cost/rate budgets, retrieval/agent evals, accessibility and performance budgets.

## 10. Acceptance criteria for the architecture

The design is working when:

- the same recorded run can replay in VS Code and Tauri without UI dependencies in the core;
- changing providers between turns requires only recompilation of canonical history;
- every side effect has a validated schema, resolved preview, policy decision, approval/audit record, and outcome;
- a crash during a tool call resumes safely without repeating an uncertain mutation;
- a stale multi-file proposal cannot overwrite user edits;
- retrieval can explain why each chunk was selected and meets measured recall/token targets;
- the extension host remains responsive during initial indexing;
- the Tauri webview cannot invoke arbitrary filesystem, shell, database, or sidecar operations;
- secrets never enter settings, conversation history, telemetry, or default logs;
- provider fixtures cover the incompatibilities that “OpenAI-compatible” hides.

## Primary references

- [Cline repository](https://github.com/cline/cline) and [Cline changelog](https://github.com/cline/cline/blob/main/CHANGELOG.md)
- [Goose repository](https://github.com/block/goose) and [custom extensions documentation](https://github.com/block/goose/blob/main/documentation/docs/tutorials/custom-extensions.md)
- [VS Code AI extensibility](https://code.visualstudio.com/api/extension-guides/ai/ai-extensibility-overview), [Webviews](https://code.visualstudio.com/api/extension-guides/webview), and [VS Code API](https://code.visualstudio.com/api/references/vscode-api)
- [Tauri 2 calling Rust](https://v2.tauri.app/develop/calling-rust/), [sidecars](https://v2.tauri.app/develop/sidecar/), [SQL plugin](https://v2.tauri.app/plugin/sql/), and [runtime authority](https://v2.tauri.app/security/runtime-authority/)
- [Tree-sitter](https://tree-sitter.github.io/tree-sitter/)
- [MiMo API](https://mimo.mi.com/docs/en-US/quick-start/first-api-call), [DeepSeek API](https://api-docs.deepseek.com/), [Kimi API](https://platform.kimi.ai/docs/api/overview), [xAI API](https://docs.x.ai/developers/quickstart), and [Ollama compatibility](https://docs.ollama.com/api/openai-compatibility)
