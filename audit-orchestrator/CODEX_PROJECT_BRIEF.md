# PROJECT BRIEF — Audit Orchestrator Service

> **For Codex:** Build this service per the audited spec below.
> **Supervisor:** Cyony (will review each phase before you proceed to next)
> **Spec status:** v3 FINAL — Audited twice by full crew (Cyony, Echo, Tripp)
> **Source:** `/opt/data/shared/audit-orchestrator/AUDIT_HANDOFF.md` (the full audited plan)

---

## What You're Building

A pure Python orchestrator (NO LLM, zero token cost) that automates crew audit workflows. Runs as a systemd service on the VPS at `/opt/data/shared/audit-workflow/`. When triggered, it sequentially dispatches agents, waits for completion via JSON status files, and presents the final result.

## Build Order (6 Phases — Do NOT skip ahead)

### Phase 1: State Machine Core
**Files:** `orchestrator/models.py`, `orchestrator/config.py`

Build the data layer:
- `AuditPhase` enum with all 12 phases
- `PHASE_ORDER` list (valid transitions)
- `PHASE_OWNER` dict (which agent per phase)
- `PHASE_ARTIFACTS` dict (which file per phase)
- `AuditProject` class with all fields from state file format (v3 — includes trashed_at, cancelled_at, cancel_reason, error_tracking)
- Methods: `advance()`, `get_next_agent()`, `get_dispatch_prompt()`, `trash()`, `cancel(reason)`, `restore()`, `days_until_removal()`, `to_dict()`, `from_dict()`
- `config.py` with all paths, timeouts, agent configs
- Atomic write helper: `atomic_write(path, content)` using .tmp + os.rename()
- File lock helper using fcntl.flock()

**Tests:** `tests/test_models.py`
- Phase advancement follows correct order
- Invalid transitions rejected
- get_next_agent() returns correct agent per phase
- get_dispatch_prompt() returns valid prompt with all variables filled
- trash() sets trashed_at, restore() clears it
- cancel() sets cancelled_at + reason, moves artifacts to .cancelled/
- days_until_removal() counts down correctly
- Serialization round-trip (to_dict → from_dict)
- Atomic write creates file safely
- Concurrent state file access handled by lock

**Done when:** All tests pass, model covers every field in the v3 state format.

---

### Phase 2: Completion Detection + Error Handling
**Files:** `orchestrator/detector.py`

Build the polling/checking logic:
- `check_completion(project_dir, phase)` — looks for `.status/{phase}.json`, waits 5s settling, validates
- `validate_artifact(project_dir, phase)` — checks artifact exists AND >100 chars
- `parse_status(project_dir, phase)` — reads JSON status file, returns parsed dict
- `validate_status_json(raw_content)` — catches malformed JSON, returns error info
- Error counter logic: increment on malformed status, suppress alerts after 3 consecutive, reset on phase advance
- Score validation: both R1 <5 → alert, R1 gap >4 → alert

**Tests:** `tests/test_detector.py`
- Detects completion when status file exists
- Handles malformed JSON gracefully
- Error counter increments correctly
- Alert suppression activates at 3
- Reset on phase advance
- Settling time respected (mock time.sleep)
- Artifact validation catches empty/small files
- Score validation flags low scores and wide gaps

**Done when:** All tests pass, error handling covers all edge cases from R2-4.

---

### Phase 3: Agent Dispatcher
**Files:** `orchestrator/dispatcher.py`

Build the agent trigger system:
- `trigger_hermes_agent(agent_name, prompt, project_id, phase, model)` — creates one-shot Hermes cron
  - `enabled_toolsets: ["file", "terminal", "search"]`
  - `model`: pinned per agent (MiMo 2.5 for audits, DeepSeek Flash for consolidation)
  - `deliver`: "local" (silent, no Telegram spam)
  - `schedule`: immediate (current ISO timestamp)
  - `name`: `{agent}-audit-{project_id}-{phase}`
- `trigger_tripp(project_dir, phase)` — drops trigger file to `.triggers/`
- `check_cron_status(cron_id)` — verify one-shot cron completed (not failed/timed out)
- Retry logic: if cron failed + no status file after 2x timeout → retry once, then alert Eddie

**Tests:** `tests/test_dispatcher.py`
- Hermes cron creation with correct parameters
- Model pinning works
- enabled_toolsets included
- Tripp file drop creates correct file at correct path
- Retry fires exactly once
- Dispatch prompt includes all required paths

**Done when:** All tests pass, prompt template matches v3 spec exactly.

---

### Phase 4: Notification System
**Files:** `orchestrator/notifier.py`

Build Eddie notification logic:
- `notify_phase_complete(project_name, phase, agent)` — brief Telegram update
- `notify_timeout(project_name, phase, agent)` — alert with [Extend]/[Skip]/[Abort]
- `notify_ready_for_build(project_name)` — full presentation with YES/STORE/TRASH/CANCEL
- `notify_idleReminder(project_name, hours_idle)` — 48h reminder
- `notify_idle_autostore(project_name)` — 7 day auto-store
- `notify_error(project_name, error_type, details)` — error alert
- `notify_cancellation_prompt(project_name)` — "Why are you cancelling?"
- Rate limiting: max 1 notification per 5 min per project
- Format: short, scannable, emoji-led

**Tests:** `tests/test_notifier.py`
- Notification format correct
- Rate limiting prevents spam
- Timeout notification includes options
- Cancellation prompt triggers before archival

**Done when:** All tests pass.

---

### Phase 5: Main Orchestrator Loop
**Files:** `orchestrator/main.py`, `orchestrator/orchestrator.py`

Wire everything together:
- Startup: scan `/opt/data/shared/audit-workflow/` for active projects, load state
- Main loop (30s interval):
  1. Write heartbeat timestamp to `.orchestrator_heartbeat`
  2. Check each active project for completion markers
  3. If phase complete → validate → advance → dispatch next → notify Eddie
  4. If timeout → alert Eddie with options, wait
  5. If error → log + alert + continue
  6. Check Eddie idle timeout at READY_FOR_BUILD (48h reminder, 7d auto-store)
  7. Check TRASH timers (13d warning, 20d delete)
- Graceful shutdown: save state, finish current cycle
- Logging: append to `{project}/EXECUTION_LOG.md` + Python logging to file
- systemd unit file: `audit-orchestrator.service` with auto-restart

**Tests:** `tests/test_orchestrator.py`
- Startup scans and loads projects
- Main loop advances phase on completion
- Timeout detection works (tested with 1-min timeout)
- Eddie idle timeout triggers reminder and auto-store
- TRASH timer warning and delete work
- Heartbeat file updated every loop
- Graceful shutdown saves state
- Can handle 2+ concurrent projects
- Malformed state file doesn't crash orchestrator

**Done when:** All tests pass, orchestrator runs as systemd service.

---

### Phase 6: Action Handlers + Restore + Cleanup
**Files:** `orchestrator/actions.py`

Build the Eddie action system:
- `action_yes(project_id)` — phase → BUILDING, trigger Codex with FINAL_PLAN
- `action_store(project_id)` — phase → STORED
- `action_trash(project_id)` — phase → TRASHED, set trashed_at
- `action_cancel(project_id, reason)` — phase → CANCELLED, move artifacts to .cancelled/
- `action_restore(project_id)` — from STORED/TRASHED → back to READY_FOR_BUILD, clear trashed_at
- `cleanup_expired_trash()` — delete artifacts for projects trashed >20 days
- `action_extend_timeout(project_id)` — add 30 min to current phase timeout

**Tests:** `tests/test_actions.py`
- YES transitions to BUILDING
- STORE preserves artifacts in place
- TRASH sets trashed_at, restore clears it
- CANCEL moves artifacts to .cancelled/ with reason
- Restore from TRASH gives fresh state
- Cleanup deletes expired trash
- Extend timeout adds 30 minutes

**Done when:** All tests pass.

---

## Final Directory Structure

```
audit-orchestrator/
├── orchestrator/
│   ├── __init__.py
│   ├── models.py          # Phase 1
│   ├── config.py          # Phase 1
│   ├── detector.py        # Phase 2
│   ├── dispatcher.py      # Phase 3
│   ├── notifier.py        # Phase 4
│   ├── main.py            # Phase 5 (entry point)
│   ├── orchestrator.py    # Phase 5 (loop logic)
│   └── actions.py         # Phase 6
├── tests/
│   ├── test_models.py     # Phase 1
│   ├── test_detector.py   # Phase 2
│   ├── test_dispatcher.py # Phase 3
│   ├── test_notifier.py   # Phase 4
│   ├── test_orchestrator.py # Phase 5
│   └── test_actions.py    # Phase 6
├── audit-orchestrator.service  # systemd unit
├── requirements.txt       # (should be empty — stdlib only)
└── README.md              # How to run + configure
```

## Technical Requirements
- Python 3.13
- stdlib ONLY (os, json, time, fcntl, datetime, logging, pathlib)
- No external dependencies
- All tests must pass before moving to next phase
- Cyony reviews each phase before you proceed

## Completion Criteria
- [ ] All 6 phases built
- [ ] All tests pass (run `python -m pytest tests/ -v`)
- [ ] Orchestrator runs as systemd service
- [ ] Can create project → run 2-round audit → reach READY_FOR_BUILD
- [ ] Timeout detection + recovery works
- [ ] TRASH + restore + 20-day cleanup works
- [ ] CANCEL with reason works
- [ ] Notifications reach Eddie on Telegram
- [ ] No data loss on crash (atomic writes + state recovery)
- [ ] Can handle 2+ concurrent projects
