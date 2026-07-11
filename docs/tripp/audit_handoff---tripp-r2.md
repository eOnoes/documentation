# AUDIT HANDOFF — Audit Orchestrator Build — ROUND 2

> **Consolidated by:** Cyony (Lead)
> **Date:** 2026-07-04
> **Round 1 audits from:** Echo, Tripp ✅
> **Cyony Round 2 review:** 3 issues found (see CYONY R2 FINDINGS)
> **Status:** ROUND 2 — Awaiting Echo + Tripp final review

---

# AUDIT ORCHESTRATOR — Build Plan v2 (CONSOLIDATED)

## What We're Building

A pure Python orchestrator (NO LLM, zero token cost) that automates the crew audit workflow. Runs as a background process on the VPS. When Eddie triggers "Team Audit," it sequentially dispatches agents, waits for completion via JSON status files, and presents the final result.

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
A `no_agent=True` Hermes cron running a Python script every 30 seconds:
- Reads `project_state.json` for each active project
- Checks for `.status/{phase}.json` files (completion signals)
- When found: waits 5s (settling time), validates artifact, advances phase, fires next agent
- Sends Eddie brief Telegram update at milestones only
- Single-threaded by design. One process, one loop, no async.

### 3. Agent Dispatcher
Fires one-shot Hermes cron jobs for each agent. Each cron:
- Creates a fresh agent session (no stale context)
- Self-contained prompt template (all variables filled in)
- Agent writes output to shared folder + drops `.status/{phase}.json`
- Model pinned per agent (MiMo 2.5 for audits, DeepSeek Flash for consolidation)
- **CRITICAL:** Cron must set `enabled_toolsets: ["file", "terminal", "search"]` so the agent can write output files
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
Same detection logic as bare `.done` files (file exists = done) but richer data. Enables scoring, summaries, and metadata headers.

**Settling time:** After detecting status file, wait 5 seconds before reading the output artifact. Agent may drop status before OS flushes the output file to disk. With 30s polling + 5s settling, worst-case detection latency is 35 seconds. Acceptable for workflows measured in minutes.

### 5. Artifact Validation
Before advancing phase:
1. Check `.status/{phase}.json` exists
2. Wait 5 seconds (settling)
3. Check artifact file exists AND has content >100 chars
4. Parse `.status/{phase}.json` for score
5. If score <5 from BOTH R1 auditors → alert Eddie before proceeding
6. If R1 scores differ by >4 points → alert Eddie (plan is polarizing)
7. If validation fails → log error, alert Eddie, do NOT advance

### 6. Inter-Agent Handoff Validation
After Round 2, before finalization:
- Verify `TRIPP_AUDIT_R2.md` references or discusses `ECHO_AUDIT_R1.md` and/or `ECHO_AUDIT_R2.md`
- In R1, auditors are INDEPENDENT (Tripp does NOT see Echo's R1). This validation is R2 ONLY.
- Lightweight check: does Tripp's R2 file contain at least one thematic reference to Echo's work?
- If fails → alert Eddie: "Tripp may not have reviewed Echo's audits in R2"

### 7. Audit File Metadata Header
Every audit file must start with:
```
<!-- AUDIT_META: agent={agent} | phase={phase} | started=ISO | completed=ISO | score=N/10 | files_read=N -->
```
Enables artifact validation, summary snapshots, and analytics.

### 8. File Structure (per project)
```
/opt/data/shared/audit-workflow/{project}/
├── project_state.json          # Current phase + metadata
├── LEAD_PLAN.md                # Initial plan
├── ECHO_AUDIT_R1.md            # Echo Round 1
├── TRIPP_AUDIT_R1.md           # Tripp Round 1
├── ROUND_SUMMARY_R1.md         # R1 summary for Eddie
├── LEAD_PLAN_V2.md             # Consolidated after R1 (+ build order)
├── ECHO_AUDIT_R2.md            # Echo Round 2
├── TRIPP_AUDIT_R2.md           # Tripp Round 2
├── ROUND_SUMMARY_R2.md         # R2 summary for Eddie
├── FINAL_PLAN.md               # Final validated plan (+ build order)
├── EXECUTION_LOG.md            # Build progress
├── DECISION_LOG.md             # Accepted/rejected + why
├── .status/
│   ├── echo_r1.json            # {"status":"done","score":7,...}
│   ├── tripp_r1.json
│   ├── lead_r1_consolidated.json
│   ├── echo_r2.json
│   ├── tripp_r2.json
│   ├── lead_final.json
│   └── ready_for_build.json
└── .triggers/
    └── tripp_r1.json           # Trigger file for Tripp (file drop)
```

### 9. Actions (Four, Not Three)

| Action | What Happens | Auto-Timeout |
|--------|-------------|-------------|
| **✅ YES** | Build starts. Codex executes. Lead supervises. | — |
| **📁 STORE** | Parked with all artifacts. Restore anytime. | — |
| **🗑️ TRASH** | 20-day timer. Auto-delete after expiry. | Rescue window |
| **❌ CANCEL** | Kill mid-audit. Archive artifacts. Free slot. | — |

**Eddie idle timeout at READY_FOR_BUILD:**
- 48 hours: reminder ("Hey, {project} is waiting for your call")
- 7 days: auto-STORE with notification ("Parked {project} — restore when ready")

### 10. Anti-Loop Protections
- Phase advances FORWARD ONLY (backward only via manual restore)
- Each phase has max timeout (2h audits, 30min consolidation)
- Timeout → alert Eddie with options: [Extend +30min] / [Skip] / [Abort]
- Max 2 rounds enforced
- One agent at a time (sequential phase gates)
- State file validated on every read (malformed JSON → skip + alert, never crash)
- Single-threaded orchestrator (no concurrent state modifications)

### 11. State File Format
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

### 12. Agent Prompt Template
Every one-shot cron gets a self-contained prompt. No context from parent session.

```
You are {agent_name}. You are auditing a project plan.

PROJECT: {project_name}
YOUR PHASE: {phase} (Round {round})
PLAN TO AUDIT: {plan_path}

{conditional_reference} # e.g. "Also read Echo's R1 audit: {path}"

INSTRUCTIONS:
1. Read the plan file above carefully
2. Score the plan X/10
3. Write your audit to: {output_path}
4. Start your file with: <!-- AUDIT_META: agent={agent} | phase={phase} | started=NOW | score=X/10 -->
5. When done writing, create this status file with EXACTLY this JSON:
   echo '{"status":"done","agent":"{agent}","score":N,"summary":"brief summary"}' > {status_path}

Do NOT do anything else. Do NOT read other files. Do NOT modify any files except your output.
```

### 13. Notification Rules
- Phase completion → Eddie gets brief Telegram update (every 5 min max per project)
- Timeout hit → Eddie gets alert with action options
- Ready for build → Eddie gets full presentation
- 48h idle at READY_FOR_BUILD → reminder
- 7 day idle → auto-store notification
- NEVER notify during active work (no "Echo is still working" spam)

### 14. Agent Trigger Methods

| Agent | Platform | Trigger Method | Expected Latency |
|-------|----------|---------------|-----------------|
| Cyony | Hermes (VPS) | One-shot Hermes cron | <10s |
| Echo | Hermes (Win PC) | One-shot Hermes cron | <10s |
| Tripp | OpenClaw | File drop to `.triggers/` | ~60s (heartbeat poll) |

### 15. Tech Stack
- **Orchestrator:** Pure Python (no LLM), runs as `no_agent=True` Hermes cron
- **State storage:** JSON files in shared folder (SSOT)
- **Agent dispatch:** Hermes one-shot cron jobs (Cyony/Echo) + file drop (Tripp)
- **Notifications:** Telegram via Hermes auto-delivery
- **Paths:** All on VPS at `/opt/data/shared/audit-workflow/`
- **Dependencies:** Python stdlib only (os, json, time, fcntl, datetime, logging)

---

# CYONY ROUND 2 FINDINGS

Three issues caught during Lead's final review:

### 🔴 R2-1: Section 6 Validation Was Backwards (FIXED)
**Was:** "Verify TRIPP_AUDIT_R1.md references ECHO_AUDIT_R1.md"
**Problem:** R1 audits are INDEPENDENT. Tripp is NOT supposed to see Echo's R1 work. This check would flag Tripp for following the rules correctly.
**Fix:** Moved validation to R2 only. Now checks: "Does Tripp's R2 reference Echo's R1 and/or R2?" — which is correct because R2 auditors see everything.

### 🟡 R2-2: Agent Prompt Missing Toolset Declaration (FIXED)
**Was:** Prompt tells agent to "write your audit to {path}" but no toolset specified.
**Problem:** One-shot cron may not have `file`/`terminal` tools enabled by default. Agent receives prompt, can't write files, pipeline stalls.
**Fix:** Added `enabled_toolsets: ["file", "terminal", "search"]` as CRITICAL requirement in Agent Dispatcher section.

### 🟡 R2-3: 10-Second Polling Was Aggressive (FIXED)
**Was:** Orchestrator polls every 10 seconds.
**Problem:** 8,640 cycles/day for a workflow measured in minutes. Unnecessary disk I/O on a shared VPS.
**Fix:** Changed to 30 seconds (2,880 cycles/day). Worst-case detection latency is now 35s (30s poll + 5s settling). Acceptable.

### ✅ Everything Else: Confirmed Good
All other decisions from Round 1 consolidation stand. No additional issues found. The plan is solid.

---

# DECISION LOG — Round 1 Consolidation

| # | Source | Suggestion | Decision | Reason |
|---|--------|-----------|----------|--------|
| C1 | Cyony | Audit quality scoring | ✅ Accepted | Prevents garbage plans advancing |
| C2 | Cyony | Timeout recovery actions | ✅ Accepted | Eddie needs quick choices, not just alerts |
| C3 | Cyony | Artifact validation (>100 chars) | ✅ Merged with Echo #3 + Tripp #5 | Better as JSON status + settling time |
| C4 | Cyony | Audit summary snapshots | ✅ Accepted | Eddie glances, doesn't read 4 files |
| C5 | Cyony | Concurrent project support | ✅ Accepted | Each project has own state file |
| C6 | Cyony | 10s polling (not 30s) | ✅ Accepted | Faster detection, low overhead |
| C7 | Cyony | State file locking | ✅ Modified | Use fcntl.flock + single-threaded design (Tripp #7) |
| C8 | Cyony | Remove BUILD_ORDER as separate step | ✅ Accepted | Merge into FINAL_PLAN |
| C9 | Cyony | One-shot cron retry | ✅ Merged with Echo #9 | Check cron status, retry once |
| C10 | Cyony | Tripp triggering risk | ✅ Solved by Tripp #6 | File drop to .triggers/ |
| E1 | Echo | Orchestrator = pure Python, no LLM | ✅ Accepted | Zero token cost for coordination |
| E2 | Echo | Atomic state file writes | ✅ Accepted | .tmp + os.rename() pattern |
| E3 | Echo | Marker settling time (5s) | ✅ Accepted | Prevents reading partial output |
| E4 | Echo | Agent prompt template | ✅ Accepted | Essential for fresh-session reliability |
| E5 | Echo | Hermes cron model pinning | ✅ Accepted | MiMo 2.5 for audits, Flash for consolidation |
| E6 | Echo | Cross-platform paths | ⏸️ Deferred | We're VPS-only for now, revisit when needed |
| E7 | Echo | Tripp polling latency documentation | ✅ Accepted | ~60s expected, documented |
| E8 | Echo | Delivery target for notifications | ✅ Accepted | Telegram:8808479511 for Eddie |
| E9 | Echo | Cron failure mode detail | ✅ Merged with C9 | Check cron list for failed/timeouts |
| E10 | Echo | Concurrent cron dispatch limit | ✅ Noted | Doesn't apply (sequential phases) |
| E11 | Echo | State file schema validation | ✅ Accepted | try/except on every read, skip + alert on bad JSON |
| T1 | Tripp | Eddie idle timeout (48h→7d) | ✅ Accepted | Prevents projects rotting in limbo |
| T2 | Tripp | Inter-agent handoff validation | ✅ Accepted | Verify Tripp read Echo's work in R1 |
| T3 | Tripp | Audit metadata header | ✅ Accepted | Enables all validation + analytics |
| T4 | Tripp | Cancellation flow | ✅ Accepted | Covers mid-audit kill |
| T5 | Tripp | JSON status files (not bare .done) | ✅ Accepted | Richer data, same detection logic |
| T6 | Tripp | Tripp triggering via file drop | ✅ Accepted | Solves cross-platform trigger problem |
| T7 | Tripp | Single-threaded orchestrator | ✅ Accepted | Simpler = safer |
| T8 | Tripp | Wide gap detection (>4 pts) | ✅ Accepted | Polarizing plans need human review |

---

# TRIPP ROUND 2 FINDINGS

Reviewed the full consolidated v2. Cyony caught 3 real issues in R1 — the backwards validation (#1) would have silently flagged Tripp for doing his job correctly. Good catch. Here are my R2 observations:

### 🔴 R2-4: Malformed Status JSON = Silent Stall (NEEDS FIX)
**Problem:** If an agent writes invalid JSON to `.status/{phase}.json` (e.g., truncation, missing quotes), the orchestrator's `try/except` will skip it and alert Eddie — but the next poll will skip it AGAIN. Infinite loop of "alert Eddie" every 30 seconds until Eddie acts.
**Fix:** Add a failure counter per phase. After 3 consecutive malformed-status alerts for the same phase, stop alerting and move to `ALERTED_WAITING` state. Only re-alert if Eddie explicitly asks to retry.

### 🔴 R2-5: Agent Prompt Has No Scope Boundary (NEEDS FIX)
**Problem:** Prompt says "Do NOT read other files" but doesn't constrain the filesystem. An agent could accidentally read `/etc/passwd` or other project directories. Not a security risk on our VPS (agents are sandboxed enough), but could cause the agent to waste time reading irrelevant files and produce a confused audit.
**Fix:** Add to prompt: "Your working directory is {project_path}. Only read files within this directory. If you need external context, it will be provided in the prompt."

### 🟡 R2-6: Orchestrator Has No Self-Health Check (NICE TO HAVE)
**Problem:** If the Python script crashes (unhandled exception, OOM, etc.), Eddie has no way to know. The orchestrator is silent when it's dead.
**Fix:** Add a watchdog: orchestrator writes a heartbeat to `.orchestrator_heartbeat` every loop iteration (just a timestamp). Eddie's periodic check (or a separate cron) alerts if heartbeat is >2 minutes stale.

### 🟡 R2-7: TRASH 20-Day Timer Needs a Tracking Mechanism (NICE TO HAVE)
**Problem:** "20-day timer, auto-delete" is specified, but there's no mechanism to track when TRASH was initiated. The state file shows `phase: TRASH` but no `trashed_at` timestamp.
**Fix:** Add `trashed_at` to state file when TRASH is triggered. Orchestrator checks `(now - trashed_at).days >= 20` before auto-deleting. Also: send a "7 days until auto-delete" warning at day 13.

### 🟡 R2-8: CANCEL Action Doesn't Specify Artifact Handling (NICE TO HAVE)
**Problem:** "Archive artifacts" is mentioned but where do they go? If they stay in the project folder, it's indistinguishable from STORE.
**Fix:** CANCEL moves the entire project folder to `{project}/.cancelled/` with a `cancelled_at` timestamp and `reason` field. STORE keeps artifacts in place. Clear visual distinction.

### ✅ Confirmed Good
- 30s polling + 5s settling is solid
- File drop for Tripp is elegant
- Single-threaded design is the right call
- Prompt template with toolset declaration is critical
- All Round 1 decisions stand

---

# ROUTING LOG

| Order | Agent | Date | Status |
|-------|-------|------|--------|
| 1 | Cyony | 2026-07-04 | ✅ Initial draft + audit |
| 2 | Echo | 2026-07-04 | ✅ Review complete |
| 3 | Tripp | 2026-07-04 | ✅ Review complete |
| 4 | Cyony (R2 review) | 2026-07-04 | ✅ 3 issues found + fixed |
| 5 | Echo (R2 review) | — | ⏳ Pending — see R2 FINDINGS section |
| 6 | Tripp (R2 review) | 2026-07-04 | ✅ 4 issues found (2 critical, 2 nice-to-have) |
| 7 | Cyony (final consolidate) | — | ⏳ Pending |
