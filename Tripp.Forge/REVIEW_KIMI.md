# Tripp.Forge SPEC Review — Kimi

**Date:** 2026-07-11  
**Spec reviewed:** `SPEC.md` (merged from `RESEARCH_CODEX.md` + `RESEARCH_KIMI.md` + `ARCHITECTURE.md`)

---

## 1. Are Kimi's findings accurately represented?

**Yes, with minor drift.** The spec correctly captures the architectural conclusions I emphasized:

- ✅ **Canonical event ledger** as the single source of truth, compiled per-provider.
- ✅ **Capability matrix per resolved model** rather than assuming "OpenAI-compatible" means identical.
- ✅ **Policy between selection and execution** based on resolved arguments, not just tool name.
- ✅ **Durable state machine** for the agent loop, not a recursive SDK wrapper.
- ✅ **Tree-sitter + ts-morph** indexing strategy with SQLite/FTS5 storage of derived facts.
- ✅ **Node sidecar in Tauri** instead of embedding JS in Rust.
- ✅ **Host contracts** (`FileHost`, `ProcessHost`, `SecretHost`, `EditorHost`) pattern, though the monorepo layout is simplified.
- ✅ **Tool execution pipeline** (Zod parse → preview → policy → approval → execute → audit).
- ✅ **Multi-provider adapter normalization** (`ApiStream` / `LlmEvent` shape).

**Minor drift / simplifications:**

- My research recommended an explicit **Phase 0 — Contracts and fixtures** before any UI work. The spec drops Phase 0 entirely and starts with monorepo + ledger. That is workable but loses the "build the replay harness first" safety net.
- My proposed monorepo shape (`apps/`, `packages/protocol`, `agent-core`, `providers`, `tools`, `indexer`, `host-contracts/`, `ui/`, `sidecars/forge-agent/`) is flattened into `packages/core`, `packages/vscode`, `packages/shared`, `apps/standalone/`. This is not wrong, but it collapses the host-contract abstraction and makes it easier for host-specific code to leak back into the core.
- The retrieval scoring formula in the spec drops `confidence`, `evidence`, and `imports` tables I specified; the simplified schema is fine as a v1, but it should be labeled a minimal starting point, not a final schema.

---

## 2. Are Codex's additions sound?

### Pitfalls list (§6)

The merged list of 10 pitfalls is a reasonable "greatest hits" compression of Codex's 20 and Kimi's 20. The top risks are covered. However, important items from both research docs were dropped:

- **No evaluation harness** — both docs listed this; without it provider adapters, retrieval, and patch reliability will regress silently.
- **Prompt injection granting authority** — both docs emphasized this; the spec only alludes to it in guardrails.
- **Logs containing source/secrets** — both docs listed this; the spec mentions keychain but not log redaction.
- **Blind tool retries / outcome unknown** — the durable state machine handles this conceptually, but it is not explicit in the pitfalls.
- **Using `sendText` as reliable execution** — dropped; the tool table says terminal.run should stream, but the VS Code terminal integration section does not repeat this warning.
- **Whole-file prompt dumps** — dropped; the spec says "inject relevant codebase context" but does not repeat the hard budget/retrieval discipline.

**Verdict:** Sound as a headline list, but incomplete. A "residual risks" appendix should call out the dropped items.

### Phased plan (§7)

Codex's phased plan was:

- Phase 0 — Contracts and fixtures
- Phase 1 — Safe vertical slice (VS Code)
- Phase 2 — Provider and tool breadth
- Phase 3 — Context engine
- Phase 4 — Standalone
- Phase 5 — Hardening

The spec converts this into an **8-week linear schedule**:

- It deletes Phase 0.
- It splits provider breadth and OpenAI OAuth into Week 6.
- It squeezes Tauri standalone into Week 7.
- It puts Marketplace submission in Week 8.

**Verdict:** Overly optimistic for a ground-up build of this scope. The 8-week framing is likely to create pressure to ship before hardening. I would restore Phase 0, make Weeks 5–8 into phases without fixed calendar dates, and add explicit evaluation/chaos-testing milestones before any submission.

### OAuth strategy (top of spec + §ChatGPT Subscription Strategy)

This is the most concerning Codex-derived addition. The spec states:

> _"The OpenClaw creator was hired by OpenAI. The Codex OAuth pattern is sanctioned by proximity — not a formal contract, but an understanding."_

Neither research document said this. Both research documents said the opposite:

- Codex: _"A third-party product needs an OAuth client and permitted integration path issued for that product. Until OpenAI authorizes Tripp.Forge's flow, support one or both of: public OpenAI API keys … and/or a user-installed official Codex CLI adapter."_
- Kimi: _"Direct ChatGPT subscription support should be behind an `experimental.chatgptSubscription` flag until OpenAI authorizes Tripp.Forge's own client."_

The spec does include the feature flag and fallback ladder, which is good. But the "sanctioned by proximity / understanding" framing is speculative and could lead to legal/product risk if Eddie interprets it as permission to ship the OAuth proxy broadly.

**Verdict:** Structurally sound (feature flag + fallback to CLI/API key), but the introductory claim is unsupported by either research doc and should be removed or heavily qualified.

---

## 3. Contradictions between the research documents

The two research docs are largely aligned. The spec introduces the only real contradictions:

| Topic                             | Kimi research                                                                                                                                     | Codex research                                                       | Spec                                                                     |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| **ChatGPT OAuth authorization**   | Experimental flag until OpenAI authorizes Tripp.Forge's own client                                                                                | Needs OAuth client/permitted integration path issued for the product | Claims an "understanding" exists via OpenClaw/OpenAI proximity           |
| **Build sequence**                | Phase 0 contracts first; phases not calendar-fixed                                                                                                | Phase 0 contracts first; phases not calendar-fixed                   | 8-week calendar schedule, no Phase 0                                     |
| **Monorepo structure**            | `apps/vscode`, `apps/desktop`, `packages/protocol`, `agent-core`, `providers`, `tools`, `indexer`, `host-contracts`, `ui`, `sidecars/forge-agent` | Same as Kimi                                                         | `packages/core`, `packages/vscode`, `packages/shared`, `apps/standalone` |
| **OAuth token endpoint**          | `auth.openai.com`                                                                                                                                 | Not specified in detail                                              | `auth0.openai.com` (different subdomain; needs verification)             |
| **Provider manifest `transport`** | `transports: Array<...>` (plural)                                                                                                                 | `transport: string` (singular)                                       | Not specified as an interface in the spec body                           |

**Notable:** The spec uses `auth0.openai.com/u/login/authorize` for the OAuth proxy. My research listed `auth.openai.com/oauth/authorize`. These may be equivalent in practice (OpenAI uses Auth0 under the hood), but the spec should not introduce a new domain without a source citation. If `auth0.openai.com` came from Codex, it was not in the version I read.

---

## 4. Spec rating

| Dimension        | Score | Rationale                                                                                                                                                                                                                                                           |
| ---------------- | ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Completeness** | 7/10  | Core architecture, provider layer, tool system, indexing, Tauri, and VS Code are present. Missing: Phase 0, evaluation harness, log redaction policy, prompt-injection defenses, host-contracts package, acceptance criteria, and a realistic schedule.             |
| **Correctness**  | 7/10  | Technical patterns are correct. Deduction for the unsupported "sanctioned by proximity" OAuth claim, the `auth0.openai.com` domain uncertainty, and the over-stated OpenAI "Subscription via OAuth PKCE" capability matrix entry before authorization is confirmed. |
| **Buildability** | 6/10  | The architecture is buildable, but the 8-week schedule is not. The simplified monorepo layout will create refactoring work later. Dropping Phase 0 means the team will build UI before a replay/test harness, which historically produces brittle early code.       |

**Overall: 7/10** — A solid merged spec that needs a risk-qualified OAuth section, restoration of Phase 0, a realistic phase plan, and an appendix of residual risks.

---

## 5. Gaps and risks we missed (or that the spec downplays)

### High-priority gaps

1. **No acceptance criteria section.** Both research docs ended with explicit acceptance criteria. The spec should preserve them as a checklist before any phase is considered done.

2. **Evaluation harness is absent from the build plan.** Provider conformance tests, retrieval benchmarks, patch regression tests, and agent success metrics need to exist before scaling providers or shipping.

3. **Log and telemetry redaction policy.** Secrets are correctly sent to the keychain, but the spec does not say how to keep source code, file paths, and credentials out of logs/telemetry.

4. **Prompt-injection and tool-authority boundaries.** Tool outputs (files, web pages, MCP results) must not be able to trigger approvals or rewrite policy.

5. **Remote VS Code support.** My research noted the extension host may run over SSH/WSL/Container while the webview is local. The spec does not address this beyond a one-line note.

6. **MCP server lifecycle and security.** The spec says "treat MCP servers as separate principals" but does not define how they are spawned, sandboxed, updated, or disconnected.

7. **Browser tool packaging.** Playwright download, browser binaries, and isolated profile management are not in the build phases but will consume real engineering time.

8. **SQLite packaging for VS Code.** `better-sqlite3` native binaries must be rebuilt for VS Code's target platforms. This is mentioned in research but missing from the spec schedule.

### Product/legal risks

9. **ChatGPT subscription OAuth.** The spec should explicitly state: _"Do not enable the OAuth proxy for public users until OpenAI has issued Tripp.Forge its own OAuth client and approved the integration."_ The current wording is too permissive.

10. **VS Code Marketplace policy.** AI extensions that run arbitrary shell commands, browser automation, or external OAuth flows face scrutiny. The spec should include a compliance checkpoint before submission.

### Architectural risks

11. **Flattened monorepo.** `packages/core` will likely become a grab-bag. Restoring `packages/agent-core`, `packages/providers`, `packages/tools`, `packages/indexer`, and `packages/host-contracts` will pay off within the first month.

12. **Two UI implementations drifting apart.** The spec reuses the core but does not mandate a shared `packages/ui` component library. Without it, VS Code and Tauri chat/diff/approval UIs will diverge.

13. **Context compaction is underspecified.** The spec lists strategies but not triggers, budgets, or how to preserve pending approvals and failed attempts during compaction.

---

## 6. Recommended fixes before development starts

1. **Remove or qualify the "sanctioned by proximity" language.** Replace with the explicit authorization condition from the research.
2. **Restore Phase 0** (contracts, fixtures, replay harness, security model).
3. **Replace the 8-week calendar** with milestone-based phases that include hardening before submission.
4. **Add an acceptance criteria section** sourced from both research docs.
5. **Add a residual-risks appendix** with the dropped pitfalls (eval harness, prompt injection, log redaction, etc.).
6. **Clarify the OAuth domain** (`auth.openai.com` vs `auth0.openai.com`) with a source or TODO.
7. **Split `packages/core` into the agreed packages** to preserve host-independence.
8. **Add a shared UI package** to keep VS Code and Tauri interfaces aligned.
9. **Include an evaluation/benchmark workstream** in every phase after Phase 0.

---

**Bottom line:** The spec is a competent merge and a good starting point, but it is more optimistic and less rigorous than either research report. A one-hour editing pass to fix the OAuth framing, restore Phase 0, and add residual risks would raise it from a 7 to a 9.
