# AUDIT HANDOFF — Audit Orchestrator Build — FINAL v3

> **Consolidated by:** Cyony (Lead)
> **Date:** 2026-07-04
> **Round 1 audits:** Echo ✅ Tripp ✅
> **Round 2 audits:** Echo ✅ (6 findings) Tripp ✅ (4 findings) Cyony ✅ (3 findings)
> **Status:** FINAL — Ready for Codex build

---

# AUDIT ORCHESTRATOR — Build Plan v3 (FINAL)

## What We're Building

A pure Python orchestrator (NO LLM, zero token cost) that automates the crew audit workflow. Runs as a systemd service on the VPS. When Eddie triggers "Team Audit," it sequentially dispatches agents, waits for completion via JSON status files, and presents the final result.

## Core Components

### 1. State Machine
Tracks which phase each project is in. Phases are sequential — no agent starts until the previous one finishes. Supports multiple concurrent projects.

```
PLANNING → READY_FOR_AUDIT →
R1_ECHO → R1_TRIPP → R1_CONSOLIDATE →
R2_ECHO → R2_TRIPP → R2_CONSOLIDATE →
READY_FOR_BUILD → (BUILD / STORE / TRASH / CANCEL)
```

### 2. Orchestrator Loop (Pure Python — No LLM)
A systemd service on the VPS running a Python script in a 30-second loop:
- Reads `project_state.json` for each active project
- Checks for `.status/{phase}.json` files (completion signals)
- When found: waits 5s (settling time), validates artifact, advances phase, fires next agent
- Sends Eddie brief Telegram update at milestones only
- Single-threaded by design. One process, one loop, no async.
- **Self-health:** Writes timestamp to `.orchestrator_heartbeat` every loop. Separate watchdog cron alerts Eddie if heartbeat is >2 min stale.

### 3. Agent Dispatcher
Fires one-shot Hermes cron jobs for each agent. Each cron:
- Creates a fresh agent session (no stale context)
- Self-contained prompt template (all variables filled in, working directory constrained)
- Agent writes output to shared folder + drops `.status/{phase}.json`
- Model pinned per agent (MiMo 2.5 for audits, DeepSeek Flash for consolidation)
- **CRITICAL:** Cron must set `enabled_toolsets: ["file", "terminal", "search"]` so the agent can write output files
- **CRITICAL:** Agent prompt must forbid subagent spawning
- Session ends immediately after completion

### 4. Completion Detection (JSON Status Files)
Agents signal completion by writing a JSON status file:
```
/opt/data/shared/audit-workflow/{project}/.status/{phase}.json
```
Format:
```json
{
  "status": "done",
  "agent": "echo",
  "completed_at": "2026-07-04T21:30:00Z",
  "score": 7,
  "summary": "Found 3 issues: daily notes gap, no inbox, missing metadata"
}
```

**Settling time:** After detecting status file, wait 5 seconds before reading the output artifact. With 30s polling + 5s settling, worst-case detection latency is 35 seconds.

### 5. Artifact Validation
Before advancing phase:
1. Check `.status/{phase}.json` exists
2. Wait 5 seconds (settling)
3. Check artifact file exists AND has content >100 chars
4. Parse `.status/{phase}.json` for score
5. If score <5 from BOTH R1 auditors → alert Eddie before proceeding
6. If R1 scores differ by >4 points → alert Eddie (plan is polarizing)
7. If validation fails → log error, alert Eddie, do NOT advance

### 6. Malformed Status Handling (Error Counter)
If `.status/{phase}.json` contains invalid JSON or is truncated:
1. Increment `error_tracking.consecutive_errors` in project state
2. Alert Eddie: "Malformed status from {agent} in {phase}"
3. After 3 consecutive malformed-status alerts for same phase → suppress further alerts, set `error_tracking.alert_suppressed = true`
4. Only re-alert if Eddie explicitly requests retry
5. Reset counter on successful phase advance

### 7. Inter-Agent Handoff Validation
After Round 2, before finalization:
- Verify `TRIPP_AUDIT_R2.md` references or discusses `ECHO_AUDIT_R1.md` and/or `ECHO_AUDIT_R2.md`
- In R1, auditors are INDEPENDENT (Tripp does NOT see Echo's R1). This validation is R2 ONLY.
- Lightweight check: does Tripp's R2 file contain at least one thematic reference to Echo's work?
- If fails → alert Eddie: "Tripp may not have reviewed Echo's audits in R2"

### 8. Audit File Metadata Header
Every audit file must start with:
```
<!-- AUDIT_META: agent={agent} | phase={phase} | started=ISO | completed=ISO | score=N/10 | files_read=N -->
```
Enables artifact validation, summary snapshots, and analytics.

### 9. File Structure (per project)
```
/opt/data/shared/audit-workflow/{project}/
├── project_state.json         # Current phase + metadata + error tracking
├── LEAD_PLAN.md              # Initial plan
├── ECHO_AUDIT_R1.md          # Echo Round 1
├── TRIPP_AUDIT_R1.md         # Tripp Round 1
├── ROUND_SUMMARY_R1.md       # R1 summary for Eddie
├── LEAD_PLAN_V2.md           # Consolidated after R1 (+ build order)
├── ECHO_AUDIT_R2.md          # Echo Round 2
├── TRIPP_AUDIT_R2.md         # Tripp Round 2
├── ROUND_SUMMARY_R2.md       # R2 summary for Eddie
├── FINAL_PLAN.md             # Final validated plan (+ build order)
├── EXECUTION_LOG.md          # Build progress
├── DECISION_LOG.md           # Accepted/rejected + why
├── .status/
│   ├── echo_r1.json          # {"status":"done","score":7,...}
│   ├── tripp_r1.json
│   ├── lead_r1_consolidated.json
│   ├── echo_r2.json
│   ├── tripp_r2.json
│   ├── lead_final.json
│   └── ready_for_build.json
├── .triggers/
│   └── tripp_r1.json         # Trigger file for Tripp (file drop)
└── .cancelled/               # Only exists if CANCEL was triggered
    └── (archived artifacts)
```

### 10. Actions (Four, Not Three)

| Action | What Happens | Auto-Timeout |
|--------|-------------|-------------|
| **✅ YES** | Build starts. Codex executes. Lead supervises. | — |
| **📁 STORE** | Parked with all artifacts in place. Restore anytime. | — |
| **🗑️ TRASH** | 20-day timer. `trashed_at` recorded. Auto-delete after expiry. | Rescue window |
| **❌ CANCEL** | Kill mid-audit. Move artifacts to `.cancelled/`. Eddie prompted for reason. | — |

**Eddie idle timeout at READY_FOR_BUILD:**
- 48 hours: reminder ("Hey, {project} is waiting for your call")
- 7 days: auto-STORE with notification ("Parked {project} — restore when ready")

**TRASH timer:**
- `trashed_at` stored in state file when triggered
- 13 days in: "7 days until auto-delete" warning
- 20 days: auto-delete artifacts
- Restore clears `trashed_at` — fresh 20-day timer if re-trashed

**CANCEL flow:**
- Eddie clicks CANCEL → orchestrator prompts: "Why are you cancelling {project}? (type a reason)"
- Eddie provides reason → artifacts moved to `.cancelled/` with `cancelled_at` + `reason` in metadata
- STORE keeps artifacts in place; CANCEL moves them. Clear distinction.

### 11. Anti-Loop Protections
- Phase advances FORWARD ONLY (backward only via manual restore)
- Each phase has max timeout (2h audits, 30min consolidation)
- Timeout → alert Eddie with options: [Extend +30min] / [Skip] / [Abort]
- Max 2 rounds enforced
- One agent at a time (sequential phase gates)
- State file validated on every read (malformed JSON → skip + alert, never crash)
- Single-threaded orchestrator (no concurrent state modifications)
- Malformed status error counter with alert suppression (Section 6)

### 12. State File Format
```json
{
  "project_id": "tripp-mind-features",
  "name": "Tripp.Mind Feature Build",
  "lead": "Cyony",
  "phase": "R1_ECHO",
  "round": 1,
  "created_at": "2026-07-04T21:00:00Z",
  "updated_at": "2026-07-04T21:30:00Z",
  "phase_started_at": "2026-07-04T21:30:00Z",
  "timeout_minutes": 120,
  "model": {"provider": "xiaomi", "model": "mimo-v2.5"},
  "trashed_at": null,
  "cancelled_at": null,
  "cancel_reason": null,
  "error_tracking": {
    "consecutive_errors": 0,
    "last_error_at": null,
    "alert_suppressed": false
  },
  "artifacts": {
    "plan": "LEAD_PLAN.md",
    "echo_r1": null,
    "tripp_r1": null,
    "lead_v2": null,
    "echo_r2": null,
    "tripp_r2": null,
    "final": null
  }
}
```

### 13. Agent Prompt Template
Every one-shot cron gets a self-contained prompt. No context from parent session.

```
You are {agent_name}. You are auditing a project plan.

PROJECT: {project_name}
YOUR PHASE: {phase} (Round {round})
PLAN TO AUDIT: {plan_path}

{conditional_reference}  # e.g. "Also read Echo's R1 audit: {path}"

INSTRUCTIONS:
1. Read the plan file above carefully
2. Score the plan X/10
3. Write your audit to: {output_path}
4. Start your file with: <!-- AUDIT_META: agent={agent} | phase={phase} | started=NOW | score=X/10 -->
5. When done, use the write_file tool to create {status_path} with this exact JSON:
   {"status":"done","agent":"{agent}","score":N,"summary":"brief summary"}

CONSTRAINTS:
- Your working directory is {project_path}. Only read files within this directory.
- Do NOT use delegate_task. Do NOT spawn subagents. You are the only agent.
- Do NOT read files outside the project directory.
- Do NOT modify any files except your output and status files.
```

### 14. Notification Rules
- Phase completion → Eddie gets brief Telegram update (every 5 min max per project)
- Timeout hit → Eddie gets alert with action options
- Ready for build → Eddie gets full presentation
- 48h idle at READY_FOR_BUILD → reminder
- 7 day idle → auto-store notification
- NEVER notify during active work (no "Echo is still working" spam)

### 15. Agent Trigger Methods

| Agent | Platform | Trigger Method | Expected Latency |
|-------|----------|---------------|-----------------|
| Cyony | Hermes (VPS) | One-shot Hermes cron | <10s |
| Echo | Hermes (Win PC) | One-shot Hermes cron | <10s |
| Tripp | OpenClaw | File drop to `.triggers/` | ~60s (heartbeat poll) |

### 16. Tech Stack
- **Orchestrator:** Pure Python (no LLM), runs as systemd service on VPS
- **State storage:** JSON files in shared folder (SSOT)
- **Agent dispatch:** Hermes one-shot cron jobs (Cyony/Echo) + file drop (Tripp)
- **Notifications:** Telegram via Hermes auto-delivery
- **Paths:** All on VPS at `/opt/data/shared/audit-workflow/`
- **Dependencies:** Python stdlib only (os, json, time, fcntl, datetime, logging)
- **Process management:** systemd unit file with auto-restart

---

# DECISION LOG — COMPLETE

| # | Source | Suggestion | Decision | Reason |
|---|--------|-----------|----------|--------|
| C1 | Cyony | Audit quality scoring | ✅ Accepted | Prevents garbage plans advancing |
| C2 | Cyony | Timeout recovery actions | ✅ Accepted | Eddie needs quick choices |
| C3 | Cyony | Artifact validation | ✅ Merged w/ E3 + T5 | JSON status + settling time |
| C4 | Cyony | Audit summary snapshots | ✅ Accepted | Eddie glances, doesn't read 4 files |
| C5 | Cyony | Concurrent project support | ✅ Accepted | Each project has own state file |
| C6 | Cyony | 10s → 30s polling | ✅ Accepted (R2) | Less churn, same effectiveness |
| C7 | Cyony | State file locking | ✅ Modified | fcntl.flock + single-threaded |
| C8 | Cyony | Merge BUILD_ORDER into FINAL_PLAN | ✅ Accepted | One less step |
| C9 | Cyony | One-shot cron retry | ✅ Merged w/ E9 | Check cron status, retry once |
| C10 | Cyony | Tripp triggering risk | ✅ Solved by T6 | File drop to .triggers/ |
| E1 | Echo | Pure Python orchestrator | ✅ Accepted | Zero token cost |
| E2 | Echo | Atomic state writes | ✅ Accepted | .tmp + os.rename() |
| E3 | Echo | 5s settling time | ✅ Accepted | Prevents partial reads |
| E4 | Echo | Self-contained prompt template | ✅ Accepted | Fresh-session reliability |
| E5 | Echo | Model pinning | ✅ Accepted | MiMo audits, Flash consolidation |
| E6 | Echo | Cross-platform paths | ⏸️ Deferred | VPS-only for now |
| E7 | Echo | Tripp latency documentation | ✅ Accepted | ~60s expected |
| E8 | Echo | Delivery target | ✅ Accepted | Telegram:8808479511 |
| E9 | Echo | Cron failure modes | ✅ Merged w/ C9 | Check cron list |
| E10 | Echo | Concurrent cron limit | ✅ Noted | Doesn't apply |
| E11 | Echo | State file validation | ✅ Accepted | try/except on every read |
| T1 | Tripp | Eddie idle timeout | ✅ Accepted | 48h reminder → 7d auto-store |
| T2 | Tripp | Inter-agent handoff validation | ✅ Accepted (R2 scope) | R2 only, not R1 |
| T3 | Tripp | Audit metadata header | ✅ Accepted | Enables analytics |
| T4 | Tripp | Cancellation flow | ✅ Accepted | Kill mid-audit |
| T5 | Tripp | JSON status files | ✅ Accepted | Richer than bare .done |
| T6 | Tripp | Tripp file drop trigger | ✅ Accepted | Solves cross-platform |
| T7 | Tripp | Single-threaded | ✅ Accepted | Simpler = safer |
| T8 | Tripp | Wide gap detection | ✅ Accepted | Polarizing plans flagged |

## Round 2 Additions

| # | Source | Suggestion | Decision | Reason |
|---|--------|-----------|----------|--------|
| R2-1 | Cyony | Section 6 validation backwards | ✅ FIXED | R2 only, not R1 |
| R2-2 | Cyony | Agent toolset declaration | ✅ FIXED | enabled_toolsets required |
| R2-3 | Cyony | 30s polling | ✅ FIXED | Less aggressive |
| R2-4 | Tripp | Malformed JSON error counter | ✅ Accepted | Prevents infinite alert loop |
| R2-5 | Tripp | Agent prompt scope boundary | ✅ Accepted | Working dir constraint |
| R2-6 | Tripp | Orchestrator heartbeat watchdog | ✅ Accepted | Know when orchestrator dies |
| R2-7 | Tripp | TRASH trashed_at timestamp | ✅ Accepted | Enables 20-day timer |
| R2-8 | Tripp | CANCEL artifact handling | ✅ Accepted | .cancelled/ directory |
| R2-9 | Echo | Orchestrator runs WHERE? | ✅ FIXED | VPS systemd service |
| R2-10 | Echo | No subagents rule | ✅ Accepted | Prevents agent tree explosion |
| R2-11 | Echo | Use write_file not echo | ✅ Accepted | Explicit tool selection |
| R2-12 | Echo | Error counter in state file | ✅ Merged w/ R2-4 | Persisted across restarts |
| R2-13 | Echo | TRASH timer pauses on restore | ✅ Accepted | Fresh start on restore |
| R2-14 | Echo | CANCEL requires reason | ✅ Accepted | Audit trail completeness |

---

# ROUTING LOG

| Order | Agent | Date | Status |
|-------|-------|------|--------|
| 1 | Cyony | 2026-07-04 | ✅ Initial draft + audit |
| 2 | Echo | 2026-07-04 | ✅ R1 complete |
| 3 | Tripp | 2026-07-04 | ✅ R1 complete |
| 4 | Cyony (R2) | 2026-07-04 | ✅ 3 issues found + fixed |
| 5 | Echo (R2) | 2026-07-04 | ✅ 6 issues found + fixed |
| 6 | Tripp (R2) | 2026-07-04 | ✅ 4 issues found + fixed |
| 7 | Cyony (FINAL) | 2026-07-04 | ✅ FINAL v3 — Ready for build |
