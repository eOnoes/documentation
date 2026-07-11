# PROJECT BRIEF — Audit Orchestrator Service

> **For Codex/Kimi:** Build this service. Read the spec, ask questions if needed, then execute.
> **Supervisor:** Cyony (will review each phase before you proceed)
> **Source spec:** AUDIT_HANDOFF.md (the crew-audited version)

---

## Executive Summary

Build a lightweight Python orchestrator that automates crew audit workflows. It runs as a background process on the VPS, polls for completion markers, and triggers agents sequentially via one-shot Hermes cron jobs.

## Architecture

```
orchestrator/
├── orchestrator.py          # Main loop + state machine
├── dispatcher.py            # Agent trigger logic (Hermes cron API)
├── notifier.py              # Eddie Telegram notifications
├── models.py                # Project + Phase data classes
├── config.py                # Paths, timeouts, agent configs
├── tests/
│   ├── test_state_machine.py
│   ├── test_completion.py
│   └── test_dispatcher.py
└── README.md                # How to run + configure
```

## Implementation Phases

### Phase 1: State Machine (core logic)
**Files:** `models.py`, `config.py`

Build the `AuditProject` class:
- Fields: project_id, name, lead, phase, round, created_at, updated_at, phase_started_at, artifacts, trashed_at
- Methods: advance(), get_next_agent(), get_dispatch_prompt(), trash(), days_until_removal(), to_dict(), from_dict()
- Phase enum: PLANNING, READY_FOR_AUDIT, R1_ECHO, R1_TRIPP, R1_CONSOLIDATE, R2_ECHO, R2_TRIPP, R2_CONSOLIDATE, READY_FOR_BUILD, BUILDING, STORED, TRASHED
- Phase order array (defines valid transitions)
- Phase owner mapping (which agent owns which phase)
- Phase artifact mapping (which file each phase produces)
- Serialization to/from JSON (for project_state.json)

**Tests:**
- Test phase advancement follows correct order
- Test that invalid transitions are rejected
- Test get_next_agent() returns correct agent per phase
- Test get_dispatch_prompt() returns valid prompt per phase
- Test trash() sets correct timer
- Test days_until_removal() counts down correctly

### Phase 2: Completion Detection
**Files:** `orchestrator.py` (part 1)

Build the polling loop:
- Check every 10 seconds for .done marker files
- For each active project: read project_state.json, check if current phase's .done marker exists
- When marker found: validate the artifact file exists AND has content (>100 chars)
- If valid: advance phase, clean up marker, log transition
- If invalid (empty artifact): alert Eddie, don't advance
- Timeout detection: if phase_started_at + timeout_minutes < now → timeout alert
- File locking: use fcntl.flock() to prevent concurrent state modifications

**Tests:**
- Test marker detection works
- Test artifact validation catches empty files
- Test timeout detection fires at correct time
- Test file locking prevents concurrent writes
- Test state file is not corrupted by partial writes (atomic write pattern)

### Phase 3: Agent Dispatcher
**Files:** `dispatcher.py`

Build the agent trigger system:
- `trigger_agent(agent_name, prompt, project_id)` function
- For Hermes agents (Cyony, Echo): create one-shot cron via Hermes API
  - Schedule: immediate (ISO timestamp = now)
  - Prompt: the audit prompt from get_dispatch_prompt()
  - Deliver: local (silent)
  - Name: `{agent}-audit-{project_id}-{phase}`
- For OpenClaw agents (Tripp): drop file to Tripp's known pickup path
  - File: `/opt/data/shared/audit-workflow/{project}/TRIPP_DISPATCH.md`
  - Content: the audit prompt
  - Tripp's watcher picks it up
- Retry logic: if no .done marker after 2x timeout → retry once
- If retry fails → alert Eddie with options

**Tests:**
- Test Hermes cron creation with correct parameters
- Test retry logic fires exactly once
- Test dispatch prompt includes all required paths
- Test Tripp file drop creates correct file at correct path

### Phase 4: Notification System
**Files:** `notifier.py`

Build Eddie notification logic:
- `notify_phase_complete(project_name, phase, agent)` → brief Telegram message
- `notify_timeout(project_name, phase, agent)` → alert with options
- `notify_ready_for_build(project_name)` → full presentation with action buttons
- `notify_error(project_name, error)` → error alert
- Rate limiting: max 1 notification per 5 minutes per project (prevent spam)
- Format: short, scannable, emoji-led

**Tests:**
- Test notification format is correct
- Test rate limiting prevents spam
- Test timeout notification includes options

### Phase 5: Main Orchestrator Loop
**Files:** `orchestrator.py` (complete)

Wire everything together:
- Startup: scan shared folder for active projects, load state
- Main loop (every 10s):
  1. Check each active project for completion markers
  2. If phase complete → advance, dispatch next agent, notify Eddie
  3. If timeout → alert Eddie, wait for response
  4. If error → log, alert, continue
- Graceful shutdown: save state, finish current cycle
- Logging: append to `{project}/EXECUTION_LOG.md`

### Phase 6: Action Handlers
**Files:** `orchestrator.py` (part 3)

Build the YES/STORE/NO handlers:
- `action_yes(project_id)`: phase → BUILDING, trigger Codex with FINAL_PLAN + BUILD_ORDER
- `action_store(project_id)`: phase → STORED, notify Eddie "Parked"
- `action_trash(project_id)`: phase → TRASHED, start 20-day timer
- `action_restore(project_id)`: phase → back to READY_FOR_BUILD (from STORED or TRASHED)
- `cleanup_expired_trash()`: delete artifacts for projects trashed > 20 days ago

## Technical Requirements

- **Language:** Python 3.13
- **Dependencies:** Minimal — stdlib + requests (for Hermes API calls)
- **File locking:** fcntl.flock() for state file safety
- **Atomic writes:** Write to .tmp, then os.rename() for crash safety
- **Logging:** Python logging module → file + stdout
- **No database:** JSON files only (SSOT pattern)
- **Path constants:** All paths in config.py, no hardcoded paths in logic

## Path Constants (config.py)

```python
PROJECTS_DIR = "/opt/data/shared/audit-workflow"
SHARED_DIR = "/opt/data/shared"
TRIPP_PICKUP = "/opt/data/shared/tripp-dispatch"
HERMES_API = "http://localhost:18790"  # or wherever Hermes gateway runs
DEFAULT_AUDIT_TIMEOUT = 120  # minutes
DEFAULT_CONSOLIDATION_TIMEOUT = 30  # minutes
TRASH_RETENTION_DAYS = 20
MARKER_CHECK_INTERVAL = 10  # seconds
```

## Completion Criteria

- [ ] All Phase 1-6 tests pass
- [ ] Can create a project, run full 2-round audit, reach READY_FOR_BUILD
- [ ] Timeout detection works (tested with 1-minute timeout)
- [ ] Trash + 20-day timer works
- [ ] Restore from STORED works
- [ ] Notifications reach Eddie on Telegram
- [ ] No data loss on crash (atomic writes + state recovery)
- [ ] Can handle 2+ concurrent projects
