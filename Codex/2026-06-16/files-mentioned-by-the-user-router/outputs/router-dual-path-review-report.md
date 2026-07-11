# Review Report: Router Dual-Path Spec for Tripp.reason

## Executive Summary

The current dual-path router plan is directionally strong and worth keeping. The central idea is sound: the harness should know the active model tier and route differently for local models versus cloud models. That directly addresses the biggest risk in the earlier router concept: making small local models pay for cloud-grade decomposition, broad tool selection, and long planning loops.

The plan should not be treated as "router risk fully crushed" yet. It is closer to "router risk is now manageable if scoped correctly." The strongest parts are the shared output format, deterministic local path, model-aware context budgeting, and ability to promote/demote when the operator switches models. The weakest parts are the timeline, model detection heuristics, too-binary local/cloud assumptions, vague definitions for gates/TTSR/skill registry, and several estimates that need benchmarking before being used as planning truth.

Recommended final direction: keep the dual-path architecture, but implement it as a staged capability ladder rather than a large all-at-once router rebuild. Start with deterministic model tier detection, shared `RouteResult`, local templates, cloud decomposition behind a feature flag, context budget enforcement, and telemetry. Add dynamic model switching only after phase persistence and resume semantics are proven.

## Overall Verdict

Verdict: proceed, but tighten scope.

The plan is good because it separates routing behavior by model capability while preserving one downstream contract. That is exactly the kind of simplification that prevents architecture sprawl. The router can be smart internally without making the rest of the harness care whether the plan came from a template, a local model, or a deep cloud decomposition.

The plan is risky because it currently combines several major systems into one upgrade:

- model tier detection
- router core
- phase templates
- skill registry integration
- prompt matrix
- context budgeting
- TTSR rule sets
- streaming enforcement
- model switching
- stuck detection
- compaction and summarization
- operator checkpoints

That is more than a router. It is an orchestration layer. That is fine, but it should be named and staged like one.

## What Makes Sense and Should Stay

### 1. Shared `RouteResult`

This is the strongest architectural choice in the spec.

Both local and cloud paths producing the same object is the right move. It keeps the gate system, phase runner, and build loop insulated from routing strategy. This lowers future maintenance cost and avoids branching logic spreading through the harness.

Recommendation: make `RouteResult` the core contract early. Version it. Keep it serializable. Persist it so builds can resume.

Suggested fields:

- `route_id`
- `model_tier`
- `route_path`
- `terrain`
- `stack`
- `intent`
- `phase_chain`
- `gate_config`
- `blockers`
- `context_budget`
- `tts_ruleset`
- `confidence`
- `created_at`
- `source_model`
- `route_version`

### 2. Local Path as Mostly Deterministic

The local path is correct in spirit. Small and medium local models should not spend 8 to 10 calls planning before they act. They need short prompts, few tools, tight feedback, deterministic templates, and hard gates.

Keep:

- deterministic terrain detection
- deterministic stack detection when possible
- one lightweight intent call
- template-based phase chain
- fatal blocker lookup
- heuristic confidence
- stricter compaction

This is probably the most important part of the whole plan.

### 3. Cloud Path as Deeper Planning

The cloud path makes sense as long as it stays bounded by budgets. Full decomposition, rival frames, skill tree exploration, and checkpoints are valuable when the model can actually use them.

Keep the cloud path, but do not make "go crazy" the actual operating principle. It should be "spend more reasoning where it buys down risk." Creative exploration is useful for greenfield product design, architecture choices, migration strategy, and ambiguous requests. It is less useful for obvious bug fixes or narrow edits.

Recommendation: make cloud decomposition conditional based on task class, risk level, and repo state, not only model tier.

### 4. Model-Aware Context Budgeting

This is one of the best parts of the plan. Context window management will likely matter more than the router itself once builds get long.

Keep:

- per-tier context budgets
- gate feedback budgets
- working set limits
- history retention policies
- compaction thresholds
- smaller prompts for local models

But the budget numbers need measurement. Treat the table as a starting hypothesis, not a final policy.

### 5. Prompt Matrix

The prompt matrix is a good idea. A single universal system prompt will underperform across local and cloud models.

Keep separate prompts for:

- tiny/local constrained models
- normal local models
- cloud coding models
- deeper reasoning models

However, avoid too many prompt files too early. Start with three:

- `tiny_model_system.md`
- `local_model_system.md`
- `cloud_model_system.md`

Add provider-specific prompts only when telemetry proves the need.

### 6. Model Switching

The local-to-cloud promotion concept is excellent. It matches real operator behavior: start cheap, escalate when stuck.

Keep the idea, but implement it later. Model switching depends on durable state, resumable phases, clean summaries, stable working sets, and predictable gate status. Without those, model switching will create weird half-state failures.

Recommended order:

1. persist route and phase state
2. support resuming a phase with the same model
3. support local to cloud promotion
4. support cloud to local demotion

## What Needs Revision

### 1. Model Tier Detection Is Too Fragile

The current detection logic relies heavily on model name string matching. That is useful as a fallback, but it is not enough.

Problems:

- quantization names are inconsistent
- provider names vary
- context limits are often wrong or missing
- model names change
- cloud/local distinction is not always obvious with self-hosted APIs
- a 27B Q2 model and a 13B Q5 model may behave differently than the simple tier labels imply

Recommendation: use layered detection.

Priority order:

1. explicit user override
2. provider metadata
3. configured context limit
4. configured speed/cost/tool capability profile
5. known model registry
6. name heuristic fallback
7. safe default

Better than a static `ModelTier` alone: create a `ModelCapabilityProfile`.

Suggested dimensions:

- `context_limit`
- `tokens_per_second_estimate`
- `tool_call_reliability`
- `reasoning_depth`
- `json_reliability`
- `cost_class`
- `supports_native_tools`
- `supports_thinking`
- `local_or_remote`
- `recommended_route_path`

The tier can still exist, but it should be derived from richer capability data.

### 2. The Plan Treats Local vs Cloud as Too Binary

The dual-path framing is useful, but the actual implementation should be a capability ladder.

A local 70B model may outperform a cheap cloud model in some coding tasks. A fast cloud model may be bad at long-form planning. A local model with excellent tool calling might deserve more autonomy than the plan gives it.

Recommendation: keep two headline paths, but implement parameters independently. For example:

- decomposition depth
- phase count
- tool count
- checkpoint behavior
- TTSR strictness
- context budget
- forced tool cadence

That lets the harness produce a local-light, local-medium, cloud-fast, or cloud-deep behavior without hardwiring everything to one enum.

### 3. "Forced Tool Call Every Turn" Is Too Rigid

For local models, forcing action is good. But "every turn must emit a tool call" can backfire when the model needs to read an error, summarize state, ask for missing info, or avoid destructive action.

Recommendation: change this from a hard universal rule to an action bias:

- local models should prefer tool use every turn
- no more than one non-tool reasoning turn unless stuck or blocked
- user-facing narration is minimized
- safety checks can pause tool use

This keeps momentum without creating robotic or unsafe behavior.

### 4. TTSR Strictness May Punish Local Models Too Much

The idea of model-aware TTSR is good, but the proposed local rules include style/performance rules that may block useful progress.

Examples:

- banning `.clone()` in loops may create unnecessary friction
- banning `unwrap_or_default()` is often overkill
- requiring preallocation can be noisy
- broad regex rules can create false positives

For local models, strict rules should focus on correctness, security, and common failure modes. Performance/style rules should be warnings unless the project demands them.

Recommended TTSR tiers:

- `fatal`: security, data loss, broken build, unsafe shell, hardcoded secrets
- `blocking`: likely correctness failure, invalid API use, missing error handling in production paths
- `warning`: style, performance, maintainability
- `advisory`: suggestions only

This lets the gate stop dangerous or broken output without turning into a lint monster.

### 5. Cloud Models Should Not Get Security-Only Rules

The spec suggests cloud models can get very lenient rules because they are more competent. That is partly true, but even strong models make repetitive coding mistakes.

Cloud TTSR should remain lighter, but not minimal. Keep universal rules for:

- hardcoded secrets
- auth tokens in local storage
- SQL injection
- command injection
- unsafe without explanation
- TypeScript suppression abuse
- empty catch blocks in critical paths
- destructive filesystem operations
- test deletion or weakening

The difference should be fewer nuisance rules, not fewer safety rules.

### 6. The Timeline Is Too Optimistic

The current two-week plan is aggressive for the number of systems involved.

Phase 1 and 2 may fit a week if the existing harness is clean. But context budgeting, TTSR streaming integration, model switching, prompt matrix, and learned rules are each real systems.

Recommended MVP timeline:

- Week 1: model capability profile, `RouteResult`, local route templates, basic cloud route stub
- Week 2: phase runner integration, gate config, blocker registry, route persistence
- Week 3: prompt matrix, context budgets, telemetry
- Week 4: cloud decomposition, checkpoints, route comparison tests
- Week 5+: model switching, learned rules, advanced compaction

This is more realistic and safer.

### 7. Missing Test Strategy

The spec needs an explicit test plan. Without tests, the router will become hard to trust.

Add tests for:

- model detection and override precedence
- unknown model fallback
- route result schema compatibility
- local template selection
- blocker lookup
- context budget calculation
- prompt selection
- TTSR rule severity
- model switch promotion/demotion
- route persistence and resume
- stuck detection

Also add golden route fixtures:

- greenfield React app
- existing Rust CLI
- legacy TypeScript app
- bug fix request
- docs-only request
- unknown stack
- dangerous request
- low-context local model
- cloud deep model

### 8. Missing Telemetry and Evaluation

The plan makes several performance claims:

- local route is 30-60 seconds
- cloud route is 50-105 seconds
- decomposition saves 20-50 turns
- cloud routing costs $0.05-$0.15

These may be reasonable, but they need measurement.

Add telemetry from day one:

- route path selected
- model tier/profile
- LLM calls used
- routing latency
- prompt tokens
- completion tokens
- phase count
- gate pass/fail count
- stuck events
- model switches
- final success/failure
- user overrides
- total cost estimate

This will tell you whether cloud decomposition is actually paying for itself.

## What Should Be Built New

### 1. Model Capability Registry

Build a registry that stores known models and capability profiles.

This should support:

- built-in known models
- user overrides
- provider metadata
- context limit
- cost estimate
- routing defaults
- tool capability flags

This is more future-proof than hardcoded string checks.

### 2. Route Template Registry

The local path depends on templates. Those templates need to become a first-class asset.

Template dimensions:

- terrain: greenfield, existing, legacy, monorepo, docs-only
- stack: React, Next.js, Rust, Python, Node, Tauri, etc.
- task type: build, refactor, bug fix, test, docs, migration
- risk: low, medium, high

Each template should define:

- phases
- default gates
- allowed tools
- context budget defaults
- known blockers
- maximum phase turns
- required checkpoints, if any

### 3. Blocker Registry

The blocker registry is important and should be separate from the router.

Blockers should have:

- `id`
- `stack`
- `terrain`
- `pattern`
- `severity`
- `message`
- `recommended_fix`
- `gate_behavior`

Separate fatal blockers from advisory blockers.

### 4. Route Persistence

Do not wait too long to persist route state.

A durable route state should include:

- selected model profile
- route path
- phase chain
- current phase
- completed phases
- gates passed
- stuck status
- summaries
- working set
- operator decisions

This is required for reliable model switching.

### 5. Context Budget Manager

This should not be just a table. It needs runtime enforcement.

Responsibilities:

- decide what files enter context
- trim gate logs
- summarize history
- preserve critical facts
- reserve output/tool-call space
- prevent overfilling local model windows

### 6. Router Evaluation Harness

Build a small evaluation harness that runs the same request across multiple tiers and compares route output.

Evaluation should check:

- phase quality
- gate command quality
- blocker relevance
- token usage
- route latency
- downstream success rate

This is how you keep the router from becoming vibes-only architecture.

## What Should Be Cut or Deferred

Defer these from MVP:

- learned rules mining
- cloud-to-local demotion
- 10-phase cloud deep plans
- 20+ skill tree exploration
- provider-specific prompt files beyond one or two proven cases
- automatic "creative weirdness" as a default behavior
- performance micro-rules in TTSR
- full mid-build model switching before route persistence exists

Keep these in MVP:

- model capability profile
- local deterministic path
- cloud enhanced path, bounded
- shared route result
- phase templates
- blocker registry
- basic prompt matrix
- context budgets
- route telemetry

## Biggest Risks

### Risk 1: Router Becomes the New Monolith

If detection, prompts, templates, context, TTSR, gates, and model switching all live inside one router module, it will become brittle.

Mitigation: split responsibilities:

- `ModelProfiler`
- `Router`
- `TemplateRegistry`
- `BlockerRegistry`
- `PromptManager`
- `ContextBudgetManager`
- `GatePlanner`
- `PhaseRunner`
- `RouteStateStore`

### Risk 2: Bad Model Detection Causes Bad Routing

A wrong tier can overload a local model or underuse a cloud model.

Mitigation:

- user override always wins
- show selected tier to operator
- allow `/route explain`
- allow `/route override local|cloud|auto`
- collect telemetry

### Risk 3: Templates Become Stale

Local routing depends on templates. Bad templates mean bad builds.

Mitigation:

- version templates
- test templates
- keep templates small
- allow project-level overrides
- record which templates succeed

### Risk 4: TTSR False Positives Slow Builds

Over-strict rules can trap agents in cleanup loops.

Mitigation:

- severity levels
- allow warnings
- local strictness focused on real failures
- project override file
- escape hatch with logged reason

### Risk 5: Model Switching Corrupts State

Promotion/demotion sounds easy but depends on clean summaries and resumable phases.

Mitigation:

- implement promotion only first
- require persisted route state
- summarize current phase before switching
- run gate immediately after switch
- do not demote from cloud to local until stable

## Recommended Final Attack Plan

### Phase 0: Define Contracts

Before implementation, freeze these contracts:

- `ModelCapabilityProfile`
- `RouteResult`
- `Phase`
- `GateConfig`
- `Blocker`
- `ContextBudget`
- `TtsrRule`
- `RouteState`

This prevents the implementation from drifting.

### Phase 1: MVP Router

Build:

- model profile detection
- user override
- local path
- cloud path stub
- shared route result
- basic route explanation
- two or three templates

Goal: given a request, produce a sane route with no build execution yet.

### Phase 2: Gate and Phase Integration

Build:

- phase runner consumes `RouteResult`
- gate command selection
- blocker registry
- route state persistence
- basic stuck detection

Goal: route can drive an actual build loop.

### Phase 3: Prompt and Context Control

Build:

- three prompt profiles
- context budgets
- working set selection
- gate feedback trimming
- history compaction

Goal: local models stay inside budget and cloud models get useful context.

### Phase 4: Cloud Enrichment

Build:

- bounded decomposition
- rival frames only when useful
- skill selection
- checkpoints
- route confidence explanation

Goal: cloud path improves large/ambiguous work without becoming expensive theater.

### Phase 5: Promotion

Build:

- local to cloud switch
- summary handoff
- expanded tool set
- checkpoint enablement
- gate-after-switch

Goal: user can start cheap and escalate safely.

### Phase 6: Hardening

Build:

- evaluation harness
- telemetry dashboard/logs
- template versioning
- learned blockers/rules only after enough data
- cloud to local demotion if still needed

## Specific Questions to Send Back to Cyony/Kimi

1. Should `ModelTier` be replaced or supplemented by a richer `ModelCapabilityProfile`?
2. What exact schema should `RouteResult` use, and should it be persisted?
3. What are the first five phase templates we need for Tripp.reason?
4. Which TTSR rules are fatal versus warning versus advisory?
5. What is the minimal blocker registry schema?
6. Should cloud decomposition trigger for every cloud request, or only high-risk/ambiguous tasks?
7. What telemetry is required to prove the router saves turns?
8. What is the fallback behavior when stack detection is uncertain?
9. What is the operator command set? Example: `/route explain`, `/route override`, `/model`, `/promote`.
10. What build states must exist before model switching is safe?

## Suggested Final Position

The plan is worth pursuing, but the language should shift from "the router risk is crushed" to "the router risk is contained by model-aware routing, deterministic local templates, shared output contracts, and measured cloud escalation."

That is a stronger engineering position because it acknowledges the remaining work while preserving the core insight.

The winning architecture is not simply dual-path routing. The winning architecture is:

- deterministic when the model is weak
- expansive when the model is strong
- contract-stable downstream
- budget-aware at runtime
- observable through telemetry
- resumable across phases
- overridable by the operator

That is the version I would take into the final build plan.
