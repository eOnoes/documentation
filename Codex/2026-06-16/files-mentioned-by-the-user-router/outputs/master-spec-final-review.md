# Final Review: Tripp.Reason Router Master Spec

## Verdict

This master spec is substantially stronger than the earlier dual-path plan. It absorbed the important corrections: capability profiles instead of brittle tier-only routing, TOML registries, route persistence in Phase 1, telemetry early, three prompts instead of provider prompt sprawl, severity-tiered TTSR, conditional cloud decomposition, and a realistic-ish five-week plan.

My recommendation: approve this as the planning baseline, but make a few surgical edits before treating it as the single source of truth.

The architecture is now right. The main remaining risk is execution scope. Phase 1 is still too large, a few contracts are over-specified, and some examples still imply capabilities that will be hard to make reliable immediately.

## What Is Strong

### 1. The Core Architecture Is Correct

The line that should anchor the project is:

> Deterministic when the model is weak. Expansive when the model is strong. Contract-stable downstream. Budget-aware at runtime. Observable through telemetry. Resumable across phases. Overridable by the operator.

That is the right shape. It keeps the local path practical and lets cloud models add value without forcing every request through a heavy planner.

### 2. `ModelCapabilityProfile` Is the Right Upgrade

Moving from a simple `ModelTier` enum to `ModelCapabilityProfile` fixes a major weakness. Routing should be based on capabilities, not just names.

Keep:

- context limit
- tool-call reliability
- JSON reliability
- reasoning depth
- locality
- cost class
- recommended route path
- user override

Suggested tweak: keep a derived `ModelTier` only for display and coarse defaults. Do not let it become the primary routing input again.

### 3. `RouteResult` as the Stable Contract Is Exactly Right

This should be the center of the build. If the rest of the harness consumes `RouteResult`, the router can evolve internally without breaking gates, phase running, telemetry, or resume.

Strong choice:

- versioned
- serializable
- persistable
- includes model profile
- includes phase chain
- includes gate config
- includes blockers and context budget

Suggested tweak: do not store the whole `ModelCapabilityProfile` under a field named `model_tier`. Rename it to `model_profile`.

### 4. TOML Registries Are the Right Operational Choice

Models, templates, blockers, and TTSR rules should not require recompilation. TOML is a good fit because operators can read and edit it.

Keep the registry approach.

Important tweak: define merge precedence clearly:

1. built-in defaults
2. user-level config
3. project-level `.tripp/*`
4. runtime operator override

Project-level should usually beat user-level for templates/blockers/rules, while explicit runtime override beats everything.

### 5. The Prompt Matrix Is Finally Scoped Correctly

Three prompts is the right starting point:

- tiny
- local
- cloud

Provider quirks should live in provider dialect code, not prompt forks. That is a very good correction.

### 6. The Build Plan Is Much More Realistic Than Before

Five weeks is far more believable than two. It still may be optimistic, but it is no longer fantasy architecture.

The biggest improvement is the staged path:

- contracts first
- local MVP first
- TTSR/gates next
- cloud after local works
- promotion after persistence exists
- benchmark last

That sequence is sane.

## Fix Before Build

### 1. Phase 1 Is Still Too Big

Phase 1 currently includes:

- model profiler
- local path
- template registry
- blocker registry
- prompt manager
- context budget manager
- gate planner
- route state store
- telemetry
- phase runner
- integration into `Agent::reply()`
- local end-to-end build

That is a lot for 4-5 days.

Recommendation: split Phase 1 into two internal milestones.

Phase 1A: route generation only

- model profiler
- local path
- template registry
- blocker registry
- prompt manager
- `RouteResult` persistence
- `/route explain`

Phase 1B: execution

- phase runner
- gate planner
- minimal telemetry
- integration into agent loop
- one end-to-end build

This does not need to change the public five-week timeline. It just makes the first week less brittle.

### 2. Phase 0 Should Include Contract Tests

The spec says Phase 0 creates fixture definitions but no tests yet. I would change that.

Phase 0 should include lightweight tests for:

- TOML deserialization
- YAML serialization of `RouteResult`
- schema version round trip
- example model registry parses
- example template registry parses
- example blocker registry parses

These are cheap and will catch bad contract decisions immediately.

### 3. `RouteResult` and `RouteState` Need Clear Separation

The spec mostly separates them, but some responsibilities blur.

Recommended distinction:

- `RouteResult`: immutable plan produced by router
- `RouteState`: mutable execution state produced by phase runner

Do not mutate `RouteResult` during the build. If a model switch requires changes, create a new `RouteResult` version linked to the old route id, or store a transition event in `RouteState`.

Suggested fields:

- `RouteResult.parent_route_id: Option<String>`
- `RouteState.route_history: Vec<String>`

This will make promotion/debugging much cleaner.

### 4. TTSR `applicable_tiers: Vec<ModelCapabilityProfile>` Is Too Heavy

Rules should not embed full model profiles. That will make config noisy and matching awkward.

Use one of these instead:

- `applicable_route_paths: ["local", "cloud_light"]`
- `applicable_model_tags: ["local_small", "cloud_fast"]`
- `min_tool_reliability`
- `max_json_reliability`

Keep rule targeting lightweight.

### 5. The Prompt Text Still Has One Bad Hard Rule

`tiny_model_system.md` says:

> Every turn MUST call a tool.

The master spec elsewhere adopts action bias and allows one non-tool turn. The prompt should match that.

Change it to:

> Prefer a tool call every turn. You may use one brief non-tool turn per phase only when blocked, unsafe to proceed, or missing required information.

This prevents the tiny prompt from contradicting the capability ladder.

### 6. CloudDeep Example Conflicts With "Local Only"

The CloudDeep example says:

> Build a finance tracker... Local only. No cloud. /route deep

Then routes to `claude-4`. That could confuse future readers. The user means local-only app data, not local-only model execution, but the wording is overloaded.

Change to:

> Local-data app. No cloud sync. /route deep

Small fix, but worth making.

### 7. SQLite Browser Blocker Needs More Precision

The blocker says:

> SQLite in the browser requires sql.js or better-sqlite3, not native SQLite.

`better-sqlite3` is Node-side, not browser-side. The earlier wording could cause confusion.

Better:

> Browser-only apps should use IndexedDB or sql.js/SQLite WASM. Node/Electron/Tauri/server contexts may use better-sqlite3, rusqlite, or sqlx depending on runtime.

This matters because Tripp will use blockers as steering instructions.

### 8. Cost/Time Numbers Should Be Marked as Estimates

The spec lists route costs and times with confidence. Keep them, but label them as benchmark targets until measured.

Suggested wording:

> Initial estimate, to be validated by Phase 5 benchmark.

Telemetry should decide whether the numbers survive.

### 9. "All Participants Review" Could Stall You

The spec says contracts are frozen after all parties review. Good spirit, but avoid making it a process trap.

Use this rule:

- Eddie approves the product/operator contract.
- Builder approves implementation feasibility.
- Reviewers can object on schema-breaking risks.
- Silence after a defined review window means proceed.

Otherwise Phase 0 can become a discussion loop.

## Build Readiness Score

I would score it:

- Architecture: 9/10
- Scope control: 7/10
- Contract quality: 8/10
- Testability: 7/10
- Timeline realism: 7/10
- Operator usability: 8/10
- Implementation risk: medium-high, but now manageable

Overall: 8/10, ready after the surgical edits above.

## My Recommended Final Edits

Before build, update the master spec with these changes:

1. Rename `RouteResult.model_tier` to `RouteResult.model_profile`.
2. Add config merge precedence.
3. Split Phase 1 into 1A route generation and 1B execution.
4. Add Phase 0 contract parsing/round-trip tests.
5. Keep `RouteResult` immutable; put build mutations in `RouteState`.
6. Replace TTSR `applicable_tiers: Vec<ModelCapabilityProfile>` with route/model tags.
7. Change tiny prompt from forced tool call to action bias.
8. Clarify the CloudDeep "local only" example.
9. Fix the SQLite browser blocker wording.
10. Mark cost/time/turn-savings numbers as benchmark targets.

## Final Position

This is no longer just a router idea. It is a practical orchestration design for Tripp.Reason.

I would proceed with it, but I would be disciplined about Phase 0 and Phase 1. The temptation will be to wire everything into the agent loop immediately. Resist that for a few days. Freeze the contracts, parse the registries, generate routes, persist them, and make `/route explain` boringly reliable first.

Once route generation is stable, the rest has a real foundation.

The build should start with contracts and fixtures, not agent-loop surgery.
