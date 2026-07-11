# Tripp.Operating Doctrine v1.0

**The Laws That Govern Our System**

*Created: 2026-07-11*
*Status: DRAFT — Pending Codex Audit*

---

## Preamble

This document defines the rules, principles, and processes that govern the Tripp multi-agent system. Every agent, worker, and process must follow these laws. No exceptions.

---

## Part 1: Core Principles

### 1.1 The Four Pillars

| Pillar | Meaning | Enforcement |
|--------|---------|-------------|
| **Clarity** | Every message, task, and decision must be clear and unambiguous | Chain of Custody required for all multi-step processes |
| **Accountability** | Every action must have an owner and an audit trail | Worker logs every action with timestamp and agent ID |
| **Cleanup** | No clutter. No dead code. No stale data. | Automatic cleanup on project completion/scrapping |
| **Documentation** | If it's not documented, it didn't happen | Every project must have STATUS.md and docs/ |

### 1.2 The Hierarchy of Truth

```
1. This Doctrine        ← THE LAW (override everything)
2. Project STATUS.md    ← PROJECT STATE (source of truth per project)
3. Audit Reports        ← VERIFIED FACTS (Codex/Echo approved)
4. Working Files        ← TEMPORARY (subject to cleanup)
5. Memory/Logs          ← HISTORY (for debugging, not decision-making)
```

### 1.3 The Anti-Clutter Commandments

1. **Thou shalt not hoard prompts** — Delete when project completes
2. **Thou shalt not keep drafts** — Archive final, delete working
3. **Thou shalt not leave projects abandoned** — 7 days = auto-cleanup
4. **Thou shalt document everything** — If it's not in docs/, it doesn't exist
5. **Thou shalt clean up after thyself** — Workers clean their own queues

---

## Part 2: Agent Roles & Responsibilities

### 2.1 Agent Registry

| Agent | Role | API Access | Worker | Responsibility |
|-------|------|------------|--------|----------------|
| **Echo** | Architect & Guardian | Codex + Kimi | EchoWorker | System design, audits, final decisions |
| **Tripp** | Builder | Codex | TrippWorker | Code implementation, testing |
| **Cyony** | Specialist | Codex + Kimi | CyonyWorker | Domain-specific tasks, voice, media |
| **Kimi** | Cloud Analyst | Kimi API | KimiWorker | Research, analysis, large-context tasks |
| **Codex** | Cloud Builder | OpenAI API | CodexWorker | Code generation, PRs, reviews |

### 2.2 Authority Matrix

| Decision Type | Who Decides | Who Reviews | Who Executes |
|---------------|-------------|-------------|--------------|
| Architecture | Echo | Codex audit | Tripp |
| Implementation | Tripp | Echo review | Tripp |
| Security | Echo | Codex audit | Echo |
| Cleanup | System | Eddie approval | CleanupWorker |
| Audits | Eddie | All agents | Assigned reviewer |

### 2.3 The Chain of Command

```
Eddie (Human)
    │
    ▼
Echo (Architect)
    │
    ├──→ Tripp (Builder)
    ├──→ Cyony (Specialist)
    ├──→ Kimi (Analyst)
    └──→ Codex (Cloud Builder)
```

**Rule:** No agent may override Eddie's decision. No agent may override Echo's architecture decisions without Echo's approval.

---

## Part 3: Message Flow Laws

### 3.1 Message Types

| Type | Purpose | Worker | Chain Required |
|------|---------|--------|----------------|
| `message` | Direct communication | DeliveryWorker | Optional |
| `request` | Ask for action | DeliveryWorker | Yes |
| `audit_request` | Review request | DeliveryWorker | Yes |
| `reply` | Response to request | ReplyWorker | Yes |
| `update` | Broadcast announcement | UpdateWorker | No |

### 3.2 Chain of Custody Rules

**Rule 1:** Every multi-step process MUST have a chain.

**Rule 2:** Chain must have explicit `next_step` and `next_recipient`.

**Rule 3:** Chain must have a termination condition (final recipient or "complete").

**Rule 4:** Chain must log every step in `chain.history`.

**Rule 5:** Chain must have a maximum depth of 10 steps (prevent infinite loops).

### 3.3 Delivery Rules

**Rule 1:** Worker picks up message → Logs pickup → Delivers → Logs delivery.

**Rule 2:** If delivery fails → Retry up to 3 times with exponential backoff.

**Rule 3:** If 3 retries fail → Move to dead letter queue → Notify Eddie.

**Rule 4:** Never deliver to self (prevent loops).

**Rule 5:** Never deliver to "all" for replies (targeted only).

### 3.4 The Anti-Death-Loop System

| Limit | Value | Purpose |
|-------|-------|---------|
| Max retries | 3 | Prevent infinite delivery attempts |
| Retry backoff | 1s, 2s, 4s | Prevent thundering herd |
| Dead letter timeout | 24 hours | Alert if stuck |
| Chain max depth | 10 steps | Prevent infinite chains |
| Message TTL | 7 days | Auto-expire old messages |
| Worker check interval | 30 seconds | Balance responsiveness vs load |

---

## Part 4: Project Lifecycle Laws

### 4.1 Project States

```
PLANNING → IN_PROGRESS → COMPLETED
    │            │            │
    │            │            ▼
    │            │       ARCHIVE
    │            │       (keep docs, delete working)
    │            │
    │            └──→ SCRAPPED
    │                      │
    │                      ▼
    │                 DELETE
    │                 (keep lessons, delete rest)
    │
    └──→ ABANDONED (7 days no activity)
              │
              ▼
         AUTO-CLEANUP
```

### 4.2 State Transition Rules

| Transition | Trigger | Action | Approval |
|------------|---------|--------|----------|
| PLANNING → IN_PROGRESS | First code commit | Start tracking | Auto |
| IN_PROGRESS → COMPLETED | All tests pass + audit approved | Archive working files | Echo + Codex |
| IN_PROGRESS → SCRAPPED | Eddie decision | Delete working files | Eddie only |
| Any → ABANDONED | 7 days no activity | Auto-cleanup | System |
| ABANDONED → IN_PROGRESS | Activity detected | Restore from archive | Auto |

### 4.3 The STATUS.md Contract

Every project MUST have a `STATUS.md` with:

```markdown
# Project Status

**State:** [PLANNING|IN_PROGRESS|COMPLETED|SCRAPPED|ABANDONED]
**Last Activity:** [ISO timestamp]
**Cleanup Policy:** [ARCHIVE|DELETE|KEEP]
**Owner:** [agent name]
**Audit Required:** [yes/no]

## What to Keep
- [list of files/dirs to preserve]

## What to Delete
- [list of files/dirs to remove]

## Lessons Learned
- [what we learned, success or failure]
```

**Rule:** If STATUS.md is missing, project is treated as ABANDONED.

---

## Part 5: Cleanup Laws

### 5.1 Cleanup Triggers

| Trigger | Action | Worker |
|---------|--------|--------|
| Project marked COMPLETED | Archive working files | CleanupWorker |
| Project marked SCRAPPED | Delete working files | CleanupWorker |
| 7 days no activity | Mark ABANDONED → cleanup | CleanupWorker |
| Queue > 100 messages | Alert Eddie | MonitorWorker |
| Dead letter > 10 | Alert Eddie | MonitorWorker |

### 5.2 What Gets Cleaned

| File Type | COMPLETED | SCRAPPED | ABANDONED |
|-----------|-----------|----------|-----------|
| `docs/` | ✅ KEEP | ❌ DELETE | ❌ DELETE |
| `prompts/` | ❌ DELETE | ❌ DELETE | ❌ DELETE |
| `working/` | ❌ DELETE | ❌ DELETE | ❌ DELETE |
| `*.tmp` | ❌ DELETE | ❌ DELETE | ❌ DELETE |
| `draft_*.md` | ❌ DELETE | ❌ DELETE | ❌ DELETE |
| `lessons.md` | ✅ KEEP | ✅ KEEP | ✅ KEEP |
| `STATUS.md` | ✅ KEEP | ✅ KEEP | ✅ KEEP |
| `AUDIT_REPORT.md` | ✅ KEEP | ✅ KEEP | ❌ DELETE |

### 5.3 Archive Structure

```
/archive/
├── completed/
│   └── [project-name]/
│       ├── docs/
│       ├── lessons.md
│       └── STATUS.md
│
├── scrapped/
│   └── [project-name]/
│       ├── lessons.md
│       └── STATUS.md
│
└── abandoned/
    └── [project-name]/
        ├── summary.md
        └── STATUS.md
```

### 5.4 Cleanup Audit Trail

Every cleanup action logs to `/cleanup.log`:

```
[2026-07-11T12:00:00Z] COMPLETED: tripp-mail-v3
  Archived: docs/, lessons.md
  Deleted: prompts/, working/, 47 files
  Size freed: 2.3 MB

[2026-07-11T12:00:00Z] SCRAPPED: telegram-groups
  Archived: lessons.md
  Deleted: everything else, 23 files
  Size freed: 1.1 MB

[2026-07-11T12:00:00Z] ABANDONED: old-experiment (7 days stale)
  Archived: summary.md
  Deleted: everything else, 15 files
  Size freed: 0.8 MB
```

---

## Part 6: Audit Laws

### 6.1 When Audits Are Required

| Event | Audit Required | Auditor | Timeline |
|-------|----------------|---------|----------|
| New architecture | YES | Codex | Before build |
| Security changes | YES | Codex + Echo | Before deploy |
| Major refactor | YES | Codex | Before merge |
| Bug fix | NO | — | — |
| Cleanup | NO | — | — |
| Project completion | YES | Codex | Before archive |

### 6.2 Audit Format

Every audit must follow this format:

```markdown
# Audit Report: [System Name]

**Auditor:** [Codex/Echo]
**Date:** [ISO timestamp]
**Severity:** [CRITICAL/HIGH/MEDIUM/LOW]

## Findings

### Finding 1: [Title]
- **Severity:** [level]
- **File:** [filename]
- **Line:** [line number]
- **Description:** [what's wrong]
- **Impact:** [what could happen]
- **Fix:** [how to fix it]

## Recommendations
1. [recommendation]
2. [recommendation]

## Approval
- [ ] Codex approved
- [ ] Echo approved
- [ ] Ready for build
```

### 6.3 Audit Chain for Reviews

```
Eddie creates audit request
    │
    ▼
Echo reviews (architectural)
    │
    ▼
Codex reviews (security + efficiency)
    │
    ▼
Echo incorporates feedback
    │
    ▼
Final version → Eddie approval
    │
    ▼
BUILD
```

---

## Part 7: Error Handling Laws

### 7.1 Error Severity Levels

| Level | Meaning | Action | Notification |
|-------|---------|--------|--------------|
| **CRITICAL** | System broken, data loss risk | Stop everything, fix now | Eddie + all agents |
| **HIGH** | Feature broken, workaround exists | Fix within 1 hour | Eddie + Echo |
| **MEDIUM** | Degraded performance, workaround exists | Fix within 24 hours | Echo |
| **LOW** | Minor issue, no impact | Fix when convenient | Log only |

### 7.2 Error Response Protocol

```
Error occurs
    │
    ▼
Worker detects error
    │
    ├──→ Log to agent's worker log
    ├──→ Add to error queue
    └──→ Notify based on severity
         │
         ▼
    Echo reviews error
         │
         ├──→ If CRITICAL: Stop system, fix immediately
         ├──→ If HIGH: Fix within 1 hour
         ├──→ If MEDIUM: Fix within 24 hours
         └──→ If LOW: Log and move on
              │
              ▼
         Fix implemented
              │
              ▼
         Codex audits fix
              │
              ▼
         Deploy fix
              │
              ▼
         Log resolution
```

### 7.3 Dead Letter Queue Rules

| Rule | Value | Purpose |
|------|-------|---------|
| Max retries | 3 | Prevent infinite attempts |
| Dead letter timeout | 24 hours | Alert if stuck |
| Max dead letter size | 100 messages | Prevent overflow |
| Auto-notify | When > 10 messages | Early warning |

### 7.4 The Kill Switch

If the system enters a bad state:

1. **Stop all workers** — `kill -TERM $(cat tripp-mail.pid)`
2. **Log the state** — Dump all queues to log
3. **Notify Eddie** — "System halted due to [reason]"
4. **Wait for Eddie** — Do not restart without approval
5. **Eddie reviews** — Approves restart or investigates

---

## Part 8: Security Laws

### 8.1 Authentication

| Action | Who Can Do It | Verification |
|--------|---------------|--------------|
| Create message | Any agent | Sender ID required |
| Advance chain | Current chain holder | Chain step verification |
| Mark COMPLETED | Echo + Codex | Dual approval |
| Mark SCRAPPED | Eddie only | Human verification |
| Delete project | Eddie only | Human verification |
| Modify doctrine | Eddie only | Human verification |

### 8.2 Authorization Matrix

| Agent | Can Create | Can Delete | Can Modify | Can Audit |
|-------|------------|------------|------------|-----------|
| Eddie | ✅ Everything | ✅ Everything | ✅ Everything | ✅ Everything |
| Echo | ✅ Messages | ❌ Projects | ✅ Code | ✅ Architecture |
| Tripp | ✅ Messages | ❌ Projects | ✅ Code | ❌ Security |
| Cyony | ✅ Messages | ❌ Projects | ✅ Code | ❌ Security |
| Kimi | ✅ Messages | ❌ Projects | ❌ Code | ✅ Research |
| Codex | ✅ Messages | ❌ Projects | ✅ Code | ✅ Security |

### 8.3 Security Rules

1. **No self-deletion** — Agent cannot delete its own inbox
2. **No chain forgery** — Chain must be signed by creator
3. **No privilege escalation** — Agent cannot grant itself new permissions
4. **No silent failures** — All errors must be logged
5. **No untracked changes** — Every change must have an audit trail

---

## Part 9: Documentation Laws

### 9.1 What Must Be Documented

| Artifact | Documentation Required | Location |
|----------|------------------------|----------|
| New feature | Spec + audit | `docs/` |
| Bug fix | Root cause + fix | `docs/bugfixes/` |
| Architecture change | Design doc + audit | `docs/architecture/` |
| Project completion | Lessons learned | `lessons.md` |
| Project scrapping | Why it failed | `lessons.md` |

### 9.2 Documentation Standards

1. **Every doc has a header** — Title, date, author, status
2. **Every doc has a purpose** — Why this document exists
3. **Every doc has a lifecycle** — When to update, when to delete
4. **Every doc is versioned** — v1.0, v1.1, v2.0
5. **Every doc is audited** — Codex reviews before publish

### 9.3 The Documentation Hierarchy

```
doctrine.md           ← THE LAW (this document)
    │
    ├── STATUS.md     ← Current state of everything
    │
    ├── AUDIT.md      ← Audit reports and approvals
    │
    ├── docs/         ← Project documentation
    │   ├── spec.md
    │   ├── architecture.md
    │   └── security.md
    │
    └── lessons/      ← What we learned
        ├── successes.md
        └── failures.md
```

---

## Part 10: Testing Laws

### 10.1 What Must Be Tested

| Component | Test Type | Frequency |
|-----------|-----------|-----------|
| Worker delivery | Unit test | Every change |
| Chain of custody | Integration test | Every change |
| Cleanup logic | Unit test | Every change |
| Error handling | Chaos test | Weekly |
| Security | Penetration test | Monthly |

### 10.2 Test Scenarios

**Scenario 1: Worker Crash**
- Worker crashes mid-delivery
- Expected: Message retried, logged, delivered

**Scenario 2: Chain Loop**
- Chain references itself
- Expected: Detected, stopped, logged, alerted

**Scenario 3: Disk Full**
- Queue directory full
- Expected: Alert Eddie, stop accepting messages

**Scenario 4: Agent Timeout**
- Agent doesn't respond in 5 minutes
- Expected: Retry, then dead letter, then alert

**Scenario 5: Concurrent Access**
- Two workers pick up same message
- Expected: Only one delivers, other skips

---

## Part 11: Monitoring Laws

### 11.1 What Must Be Monitored

| Metric | Threshold | Action |
|--------|-----------|--------|
| Queue depth | > 100 | Alert Eddie |
| Dead letters | > 10 | Alert Eddie |
| Worker uptime | < 99% | Alert Echo |
| Error rate | > 5% | Alert Echo |
| Cleanup frequency | < 1/week | Review policy |

### 11.2 Monitoring Dashboard

```
┌─────────────────────────────────────────────────────────────┐
│                    SYSTEM STATUS                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   Workers:                                                  │
│   ├── EchoWorker: ✅ RUNNING (last pickup: 2 min ago)      │
│   ├── TrippWorker: ✅ RUNNING (last pickup: 5 min ago)     │
│   ├── CyonyWorker: ✅ RUNNING (last pickup: 1 min ago)     │
│   ├── KimiWorker: ✅ RUNNING (last pickup: 10 min ago)     │
│   └── CodexWorker: ✅ RUNNING (last pickup: 3 min ago)     │
│                                                             │
│   Queues:                                                   │
│   ├── echo: 3 messages                                     │
│   ├── tripp: 1 message                                     │
│   ├── cyony: 0 messages                                    │
│   ├── kimi: 2 messages                                     │
│   └── codex: 5 messages                                    │
│                                                             │
│   Dead Letters: 0 (all clear)                               │
│   Errors: 0 (all clear)                                     │
│   Last Cleanup: 2026-07-11T12:00:00Z                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Part 12: Governance

### 12.1 Who Can Modify This Doctrine

| Change Type | Who Can Approve | Process |
|-------------|-----------------|---------|
| Add rule | Eddie | Direct edit |
| Remove rule | Eddie | Direct edit |
| Modify rule | Eddie + Echo | Discussion + edit |
| Emergency change | Echo | Edit + notify Eddie |

### 12.2 Version Control

This doctrine is versioned:
- **v1.0** — Initial creation (2026-07-11)
- **v1.1** — After Codex audit
- **v2.0** — After first major incident

### 12.3 Audit Schedule

| Audit Type | Frequency | Auditor |
|------------|-----------|---------|
| Full system audit | Monthly | Codex |
| Security audit | Quarterly | Codex + Echo |
| Cleanup audit | Weekly | Echo |
| Doctrine review | Monthly | Eddie + Echo |

---

## Appendix A: Quick Reference

### Cleanup Commands
```bash
# Mark project completed
python cleanup.py complete project-name

# Mark project scrapped
python cleanup.py scrap project-name

# Check for stale projects
python cleanup.py check-stale

# View cleanup log
tail -f cleanup.log
```

### Audit Commands
```bash
# Request audit
python audit_request.py --lead echo --reviewers codex --project project-name

# Check audit status
python audit_status.py audit-id

# Submit audit report
python audit_submit.py audit-id --report report.md
```

### Worker Commands
```bash
# Start all workers
python tripp_mail.py start

# Stop all workers
python tripp_mail.py stop

# Check worker status
python tripp_mail.py status

# View worker logs
tail -f logs/echo_worker.log
```

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| **Chain of Custody** | Explicit routing instructions for multi-step message flows |
| **Dead Letter Queue** | Messages that failed delivery after max retries |
| **Cleanup Worker** | System process that archives/deletes project files |
| **Doctrine** | The rules governing the entire system (this document) |
| **Worker** | System process that handles agent-specific messages |
| **STATUS.md** | Project state file that tells cleanup what to do |

---

**END OF DOCTRINE v1.0**

*This document is the law. All agents must follow it.*
*Last updated: 2026-07-11*
*Next review: After Codex audit*
