# AUDIT HANDOFF — Audit Orchestrator Build

> **This file gets bounced between crew members. Each person:**
> 1. Reads the full plan below
> 2. Adds THEIR suggestions at the bottom (under their name)
> 3. Does NOT modify other sections
> 4. Hands it back to Eddie who passes it to the next person
>
> **Eddie's routing order:** Cyony → Echo → Tripp → Cyony (consolidate)

---

# AUDIT ORCHESTRATOR — Build Plan v1

## What We're Building

A lightweight orchestrator that automates the crew audit workflow. When Eddie clicks "Team Audit" on a project, this system sequentially triggers each agent (Echo → Tripp → Lead → Echo → Tripp → Lead), waits for completion via marker files, and presents the final result.

## Core Components

### 1. State Machine
Tracks which phase each project is in. Phases are sequential — no agent starts until the previous one finishes.

```
PLANNING → READY_FOR_AUDIT →
R1_ECHO → R1_TRIPP → R1_CONSOLIDATE →
R2_ECHO → R2_TRIPP → R2_CONSOLIDATE →
READY_FOR_BUILD → (BUILD / STORE / TRASH)
```

### 2. Orchestrator Loop
A cron job that runs every 30 seconds:
- Reads `project_state.json` for each active project
- Checks for `.done` marker files in the status directory
- When a marker is found: advances the phase, fires the next agent
- Sends Eddie a brief update at milestones

### 3. Agent Dispatcher
Fires one-shot Hermes cron jobs for each agent. Each cron:
- Creates a fresh agent session (no stale context)
- Includes the exact prompt (what to audit, where to read, where to write)
- Agent writes output to the shared folder + drops a `.done` marker
- Session ends (no lingering)

### 4. Completion Detection
Agents signal completion by writing a marker file:
```
/opt/data/shared/audit-workflow/{project}/.status/{phase}.done
```
Contains just "DONE" — the orchestrator checks for its existence every 30 seconds.

### 5. File Structure (per project)
```
/opt/data/shared/audit-workflow/{project}/
├── project_state.json          # Current phase + metadata
├── LEAD_PLAN.md                # Initial plan
├── ECHO_AUDIT_R1.md            # Echo Round 1
├── TRIPP_AUDIT_R1.md           # Tripp Round 1
├── LEAD_PLAN_V2.md             # Consolidated after R1
├── ECHO_AUDIT_R2.md            # Echo Round 2
├── TRIPP_AUDIT_R2.md           # Tripp Round 2
├── FINAL_PLAN.md               # Final validated plan
├── BUILD_ORDER.md              # Codex execution order
├── EXECUTION_LOG.md            # Build progress
├── DECISION_LOG.md             # Accepted/rejected + why
└── .status/
    ├── echo_r1.done
    ├── tripp_r1.done
    ├── lead_r1_done.done
    ├── echo_r2.done
    ├── tripp_r2.done
    ├── lead_final.done
    └── build_order.done
```

### 6. The Three Actions
When READY_FOR_BUILD is reached:
- **YES** → Start building. Codex executes BUILD_ORDER. Lead supervises.
- **STORE** → Park with all artifacts. Restore anytime.
- **TRASH** → 20-day timer. Auto-delete after expiry. Rescue window.

### 7. Anti-Loop Protections
- Phase can only advance FORWARD (never backward except manual restore)
- Each phase has a maximum timeout (2 hours for audits, 30 min for consolidation)
- If timeout hit → alert Eddie, don't auto-skip
- Maximum 2 rounds (no infinite audit loops)
- Only ONE agent active at a time (enforced by sequential phase gates)

### 8. State File Format
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
  "artifacts": {
    "plan": "LEAD_PLAN.md",
    "echo_r1": null,
    "tripp_r1": null,
    "lead_v2": null,
    "echo_r2": null,
    "tripp_r2": null,
    "final": null,
    "build_order": null
  }
}
```

### 9. Notification Rules
- Phase completion → Eddie gets brief Telegram update
- Timeout hit → Eddie gets alert with option to extend or skip
- READY_FOR_BUILD → Eddie gets full presentation with 3 action buttons
- NEVER notify during active work (no "Echo is still working" spam)

### 10. Tech Stack
- **Orchestrator:** Python script running as Hermes cron (every 30s)
- **State storage:** JSON files in shared folder (SSOT)
- **Agent dispatch:** Hermes one-shot cron jobs
- **Notifications:** Telegram via Hermes auto-delivery
- **Dashboard:** Tripp.Mind docs + future HTML page

---

# AUDIT SUGGESTIONS

## Cyony's Suggestions

### ADD:
1. **Audit quality scoring** — Each auditor submits a score (X/10). If both R1 auditors score below 5, auto-flag for Eddie review before proceeding to R2. Prevents garbage plans from silently advancing.
2. **Timeout recovery actions** — When a phase times out, don't just alert Eddie. Offer options: [Extend +30min] / [Skip to next agent] / [Abort project]. Give Eddie quick choices.
3. **Artifact validation** — Before advancing, verify the output file exists AND has minimum content (>100 chars). Prevents "DONE" marker with empty audit file.
4. **Audit summary snapshot** — After each round, create a brief summary snapshot at `{project}/ROUND_SUMMARY_R{N}.md` so Eddie can glance without reading 4 full audit files.
5. **Concurrent project support** — The orchestrator should handle multiple active projects simultaneously (each with their own state file). Eddie might have 2-3 workups going at once.

### CHANGE:
6. **30s polling → event-driven where possible** — For Hermes agents, the orchestrator can fire the one-shot cron IMMEDIATELY after detecting .done (no need to wait for next poll). The 30s poll is just the fallback for detection. Make detection faster: poll every 10s, not 30s.
7. **State file locking** — Add a simple file lock mechanism to prevent race conditions if Eddie triggers two actions simultaneously (e.g., clicking "Team Audit" twice fast).

### REMOVE:
8. **BUILD_ORDER.md as separate step** — Codex can generate the build order AS PART of the FINAL_PLAN. Don't make Eddie wait for a separate step. The Lead's final consolidation should include the build order.

### RISKS:
9. **One-shot cron reliability** — If a one-shot cron fails (network hiccup, model timeout), the whole pipeline stalls. Need a retry mechanism: if no .done marker after 3x the timeout, retry once before alerting Eddie.
10. **Tripp triggering** — Tripp runs on OpenClaw, not Hermes. Need to verify we can trigger Tripp via API or file drop. If not, Tripp might need to be manual (Eddie pings him) while Cyony/Echo are automated.

---

## Echo's Suggestions
*(To be filled after Echo reviews)*

---

## Tripp's Suggestions

### ADD:
1. **Eddie idle timeout** — What happens if Eddie goes silent after READY_FOR_BUILD? The plan presents 3 buttons but no timeout. Add a 48h idle timer — if no action, send a reminder. After 7 days, auto-STORE with a notification. Don't let projects rot in limbo.

2. **Inter-agent handoff validation** — When Tripp finishes R1, the orchestrator validates that Tripp's output actually REFERENCES Echo's R1 output. If Tripp didn't read Echo's work, the audit is theater. Add a lightweight check: does `TRIPP_AUDIT_R1.md` contain at least one quote or reference from `ECHO_AUDIT_R1.md`?

3. **Audit file metadata header** — Every audit file should start with a structured header:
   ```
   <!-- AUDIT_META: agent=tripp | phase=R1 | started=ISO | completed=ISO | score=7/10 | files_read=4 -->
   ```
   Makes artifact validation (#3 from Cyony) trivial. Also enables downstream analytics — which agents take longest, average scores, etc.

4. **Cancellation flow** — The plan covers BUILD / STORE / TRASH but not "Eddie wants to kill this mid-audit." Add a CANCEL action available at any phase. CANCEL moves to CANCELLED state, archives artifacts, and frees the orchestrator slot.

### CHANGE:
5. **Marker file → JSON status** — Instead of bare `.done` files containing "DONE", use `.status/{phase}.json`:
   ```json
   {"status": "done", "agent": "tripp", "completed_at": "ISO", "score": 7, "summary": "Found 3 issues..."}
   ```
   Same detection logic (file exists = done), but richer data. Enables the scoring (#1 from Cyony), summary snapshots (#4), and metadata headers (#3) to work together cleanly.

6. **Tripp triggering — use file drop** — Cyony flagged this as a risk (#10). Here's the solution: orchestrator drops a trigger file at `/opt/data/shared/audit-workflow/{project}/.triggers/tripp_r1.json`. During my heartbeat, I check for trigger files, process them, write output, drop `.done`. No API needed — pure filesystem coordination. 30s poll is fast enough for this.

### RISKS:
7. **Shared folder write conflicts** — If two orchestrator polls hit simultaneously (unlikely but possible with cron), they could both try to advance the same project. Cyony's file lock (#7) helps, but also: make the orchestrator single-threaded by design. One Python process, one loop, no async. Simpler = safer.

8. **Audit quality variance** — Echo and Tripp have different audit styles. Echo might catch structural issues Tripp misses, and vice versa. The 2-round design handles this, but: if R1 scores are 8 and 3 (wide gap), that's a signal the plan is polarizing, not just weak. Add a "wide gap" detection: if R1 scores differ by >4 points, flag for Eddie review regardless of individual scores.

---

# ROUTING LOG

| Order | Agent       | Date       | Status |
|-------|-------------|------------|--------|
| 1     | Cyony       | 2026-07-04 | ✅ Initial draft + audit |
| 2     | Echo        | —          | ⏳ Pending |
| 3     | Tripp       | 2026-07-04 | ✅ Review complete |
| 4     | Cyony (consolidate) | — | ⏳ Pending |
