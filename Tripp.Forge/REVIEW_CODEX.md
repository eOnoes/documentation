# Codex Review of `SPEC.md`

**Review date:** 2026-07-10  
**Verdict:** Strong architecture summary, but not yet a build-ready final specification. The core direction is sound; the ChatGPT-subscription strategy must be corrected before implementation, and several details removed during the merge need to be restored.

## Ratings

| Dimension    |    Score | Rationale                                                                                                                                                                                                                                                                                                         |
| ------------ | -------: | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Completeness | **6/10** | Covers all major subsystems, but omits host contracts, persistence/recovery semantics, incremental indexing, retrieval, IPC protocol, testing, acceptance criteria, and operational requirements.                                                                                                                 |
| Correctness  | **6/10** | The canonical ledger, durable loop, privileged policy, Tree-sitter + semantic enrichment, MCP isolation, and Node sidecar choices are correct. The OAuth positioning is materially unsupported, the provider table overstates uniform capabilities, and the SQLite excerpt is incomplete as an executable design. |
| Buildability | **5/10** | A team could begin scaffolding from it, but would have to invent important contracts and safety behavior. The eight-week schedule also compresses too much cross-platform, provider, indexing, and security work into single-week phases.                                                                         |
| Overall      | **6/10** | Good architecture brief; not yet a sufficient source of truth for production development.                                                                                                                                                                                                                         |

## 1. Accuracy of the Codex findings

The spec accurately carries forward these central findings:

- A UI-independent TypeScript core shared by VS Code and Tauri.
- Canonical, provider-neutral conversation/event history rather than provider-native message arrays.
- A capability-aware provider layer; “OpenAI-compatible” is not treated as complete behavioral compatibility.
- An explicit, durable agent state machine rather than a recursive stream loop.
- Tool policy between selection and execution, with decisions based on resolved arguments.
- Tree-sitter for broad structural parsing and `ts-morph`/TypeScript semantics for priority languages.
- SQLite/FTS5 for derived index facts, with a Node sidecar rather than embedding JavaScript in Rust.
- Rust/Tauri as the desktop security and lifecycle boundary.

However, the merge drops several findings that were architectural requirements, not optional detail:

1. **Hexagonal host contracts are missing.** The original design explicitly separated `FileHost`, `ProcessHost`, `SecretHost`, and `EditorHost`. Without these, the “shared core” can easily acquire VS Code, Node, or Tauri dependencies.
2. **Crash semantics are missing.** The spec says “append-only event log” but does not say to persist before and after side effects or treat an interrupted mutation as **outcome unknown**. Blind replay could duplicate a command, commit, payment, or destructive write.
3. **The state machine is underspecified.** It lacks `awaiting-approval`, `paused`, `completed`, `failed`, cancellation, retry/attempt identity, and durable request/call IDs. The displayed loop returns to `IDLE` without defining terminal success or failure.
4. **Safe edit transactions were lost.** Base hashes, stale-write detection, multi-file preview, ordered application, verification, and rollback limited to Tripp-owned changes should be explicit.
5. **Indexer behavior was reduced to parser names and tables.** Incremental watch/debounce/hash flow, unsaved-buffer overlays, graph enrichment, hybrid retrieval, context packing, provenance, and retrieval evaluation are absent.
6. **Sidecar IPC requirements were removed.** The spec needs framed/versioned messages, request/run IDs, sequence numbers, cancellation, heartbeat, frame limits, authentication for loopback transport, and stderr-only logs.
7. **Database ownership was removed.** One process must own writes to each DB. Session state and derived per-project indexes should not be casually mixed or exposed as general SQL to the webview.
8. **Acceptance criteria and an evaluation harness were removed.** That makes “done” subjective and leaves provider normalization, retrieval quality, patch reliability, crash recovery, and security prone to silent regression.

## 2. Review of Kimi additions

### Cline v4 SDK: directionally sound, but pin and qualify it

The described Cline monorepo/provider-registry lesson is sound: use manifests, a registry, normalized runtime events, and provider-specific edge adapters. The paths in the spec should be tied to an inspected commit or release because repository layout is not an API and may change.

The spec should not imply that Tripp.Forge can import or depend on Cline internals as a stable SDK unless package names, exported APIs, versions, and licenses are verified. Treat Cline as a reference implementation unless an actual supported package dependency is selected.

### Goose MCP: sound pattern, overstated wording

Goose clearly supports extensive MCP-based extensions and current releases continue to expand MCP transports and features. “MCP-first” is a reasonable architectural characterization, but it is not enough to define Tripp.Forge’s tool boundary.

The recommendation to treat each MCP server as a separate principal is correct. Restore the missing controls: server identity and namespacing, transport lifecycle, schema validation, capability negotiation, timeouts, cancellation, output caps, trust level, per-server network/filesystem policy, elicitation/sampling policy, and protection against tool-description prompt injection. Built-in tools and MCP tools should implement one normalized invocation/result protocol without granting MCP servers built-in trust.

### SQLite schema: useful sketch, not sound as the final schema

WAL, foreign keys, content hashes, symbols, chunks, FTS5, and graph edges are appropriate. `contentless_delete=1` is a real FTS5 option, available in SQLite 3.43+, so the packaged SQLite version must be pinned/tested.

The merged schema is incomplete and currently easy to misuse:

- It drops `PRAGMA busy_timeout`, schema migrations, `parse_version`, file size, stable symbol keys, byte ranges, qualified names, chunk hashes/ranges, edge confidence/evidence, and the imports table.
- `chunk_fts` is contentless but no rowid mapping, insert/delete synchronization, triggers, or repository write algorithm is specified. `symbol_name` and `file_uri` are duplicated denormalized fields with no synchronization rule.
- No indexes are defined for common joins/queries (`symbols.file_id`, names, edge endpoints/kind, chunks by file/symbol).
- `edges` cannot represent unresolved/file-level imports well, and nullable endpoints permit low-information rows without constraints.
- There is no schema version/migration table, rebuild strategy, corruption recovery, or transaction boundary for replacing all derived facts for one file.
- Storing `chunks.body` contradicts the earlier phrase “derived facts, not full file bodies” unless chunks are intentionally bounded excerpts. Clarify retention and duplication policy.

Recommendation: restore Kimi’s fuller schema as a starting migration, add explicit indexes and FTS synchronization, and label it **v0 draft subject to query-driven validation**, not the final schema.

## 3. Contradictions and inconsistencies

### Release blocker: ChatGPT subscription OAuth

The research says direct ChatGPT-subscription OAuth must remain experimental until OpenAI authorizes a Tripp.Forge client/integration path. The spec instead calls it the **primary** method and justifies it with “sanctioned by proximity” and “an understanding.” Hiring history is not technical or contractual authorization.

There is also an endpoint inconsistency: the spec uses `auth0.openai.com`, while Kimi’s research lists `auth.openai.com/oauth/authorize` and `/oauth/token`. More importantly, merely declaring “our own OAuth client” does not create a registered client ID or permitted redirect URI.

Required correction:

- Make official API-key access and/or a user-installed official Codex CLI integration the supported paths.
- Keep direct subscription OAuth disabled and experimental until OpenAI supplies written authorization, client registration details, scopes, endpoints, terms, and a compatibility commitment.
- Do not claim that `api.openai.com/v1` is subscription-backed via PKCE; ChatGPT subscription and API billing/auth are distinct products.
- Add a legal/product review gate and end-to-end auth conformance test before enabling it.

### Security-boundary contradiction

The Tauri section says Rust owns security and process management, but the Node sidecar diagram says Node owns tool execution. The tool-policy section says approval runs in the privileged host. These can coexist only if authority is explicit: Node may orchestrate and propose a normalized tool request, while the VS Code extension host or Rust host resolves, authorizes, and performs privileged filesystem/process operations. The sidecar must not bypass host policy with unrestricted Node APIs.

### Build-plan inconsistencies

- Phase 2 says `fs.write`, while the tool table specifies `fs.patch`; choose the safer structured patch API and define whether raw write exists.
- Phase 3 promises an embedding pipeline even though the research recommends lexical/symbol/graph retrieval first and optional embeddings later.
- Phase 4 promises inline suggestions, which require a separate latency/cancellation/context design not specified elsewhere.
- The project structure collapses the researched package boundaries into `core`, `vscode`, and `shared`, weakening dependency enforcement and incorrectly places the VS Code extension under `packages` rather than as an app/host.
- The date says 2026-07-11 although this review environment date is 2026-07-10; correct it if unintended.

## 4. Additional gaps and risks

### Must resolve before coding the vertical slice

1. Define versioned protocol DTOs and host contracts, plus dependency rules that keep core UI/host-independent.
2. Define durable run/event storage, idempotency keys, crash recovery, cancellation, and outcome-unknown handling.
3. Define the exact privilege boundary for VS Code and Tauri, including remote workspaces and symlink/junction/case-normalization behavior on Windows.
4. Replace the OAuth strategy with an authorized support matrix.
5. Add acceptance tests for one complete safe flow: prompt → context → model → approval → version-checked patch → verification → restart/replay.

### High-priority design gaps

- Provider stream normalization, tool-call assembly, reasoning/thinking preservation, usage/cost accounting, retry classes, rate limits, model discovery, and conformance fixtures.
- Prompt-injection threat model for repository content, web pages, tool results, and MCP metadata.
- Secret redaction and data classification for logs, telemetry, crash reports, prompts, and persisted artifacts.
- Workspace trust, untrusted repositories, ignored files, secret files, binaries, large files, generated code, and `.gitignore`/`.forgeignore` semantics.
- Process isolation, environment-variable filtering, PTY behavior, process-tree termination, and Windows command resolution.
- Node sidecar packaging across Windows/macOS/Linux, native module ABI/signing/notarization, upgrades, protocol compatibility, and rollback.
- VS Code extension-host responsiveness: parsing, SQLite, embeddings, and large output handling must run off the extension host thread.
- SQLite backup/migration/corruption recovery and separate ownership for `state.db` versus rebuildable project indexes.
- Remote VS Code, WSL, SSH, containers, multi-root workspaces, and URI schemes other than local file paths.
- Accessibility, secure webview CSP, theme integration, diff UX, approval fatigue, and audit-history UX.
- License/SBOM review for Cline/Goose-derived ideas, Tree-sitter grammars, Playwright browsers, native SQLite/vector extensions, Monaco, and distribution artifacts.
- Privacy defaults and an explicit statement that the public extension contains no Tripp.Mind code, endpoints, schemas, feature flags, or discoverable private hooks—not merely no active connection.

### Schedule risk

Eight weeks is plausible only for a narrow prototype with one host, one or two providers, read/search plus structured patch, lexical indexing, and limited platform support. It is not credible for a hardened public Marketplace extension plus a cross-platform signed Tauri application, seven providers, OAuth, MCP, browser automation, deep indexing, inline completion, security testing, and production packaging.

Use milestone gates instead of calendar-only phases. Ship the VS Code vertical slice first; prove replay, policy, stale-write protection, and provider fixtures; then add indexing breadth and desktop packaging.

## 5. Recommended disposition

Approve the architectural direction, but change the document status from **Final Architecture Spec / source of truth** to **Architecture Draft v0.2** until these gates are met:

1. Subscription OAuth is removed as the supported primary path or formally authorized.
2. Host contracts and the privilege boundary are specified.
3. Durable event/recovery semantics and safe edit transactions are restored.
4. The SQLite/FTS write and migration design is executable and tested against the packaged SQLite build.
5. Sidecar IPC, database ownership, threat model, acceptance criteria, and evaluation plan are included.
6. Scope and schedule are reduced or resourced with explicit platform/provider test matrices.

With those corrections, the design should move to roughly **8/10 completeness, 8/10 correctness, and 7/10 buildability**.
