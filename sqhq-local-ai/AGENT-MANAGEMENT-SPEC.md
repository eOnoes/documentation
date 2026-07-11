# Agent Management System — Tripp.Mind Integration

**Version:** 2.0 (Post-Codex Audit)
**Last Updated:** 2026-07-09
**Status:** Audit-Fixed, Ready for Orchestrator Review

---

## Overview

A centralized system for managing, observing, and learning from our coding agents (Codex, Kimi, Claude Code). Integrated into Tripp.Mind as a new service. Agents share knowledge, learn from outcomes, and improve over time.

**Core Principle:** We build, not buy. This integrates into our existing Tripp.Mind stack.

---

## Goals

1. **Visibility** — Know what every agent is doing, right now
2. **Cost Control** — Track token spend, get daily reports, set limits
3. **Intelligence** — Agents learn from outcomes, share knowledge, improve over time
4. **Reliability** — Auto-restart failed agents, retry failed tasks
5. **Coordination** — Prevent agents from conflicting, manage task dependencies
6. **Evolution** — Agents suggest improvements to their own skills/memory

---

## Agent Hierarchy

### Managed Agents (tracked by this system)
| Agent | Role | Runs On |
|-------|------|---------|
| Codex | Coding tasks | VPS (Docker) |
| Kimi | Research tasks | VPS (Docker) |
| Claude Code | Code review | VPS (Docker) |

### Manager Agents (not tracked, orchestrate)
| Agent | Role | Runs On |
|-------|------|---------|
| Echo | Local orchestrator | Desktop (Windows) |
| Tripp | VPS lead, daily reports recipient | VPS |
| Cyony | Specialized builds, TTS | VPS (Docker) |

### Report Recipients
- **Primary:** Tripp (VPS lead)
- **Secondary:** Eddie (Telegram alerts)

---

## Architecture

### Service: `agent-tracker`

```
tripp-mind/
├── gateway/          (existing, port 3000)
├── siyuan/           (existing)
├── redis/            (existing, shared)
├── event-bridge/     (existing, for events)
├── agent-tracker/    ← NEW (port 6830)
│   ├── src/
│   │   ├── server.js           (Express API + auth middleware)
│   │   ├── tracker.js          (agent state — Redis for volatile, SQLite for history)
│   │   ├── cost-logger.js      (token/cost tracking)
│   │   ├── memory.js           (two-tier memory: session + persistent)
│   │   ├── watchdog.js         (auto-restart + circuit breaker)
│   │   ├── queue.js            (task queue + priority)
│   │   ├── router.js           (deterministic routing + LLM fallback)
│   │   ├── coordinator.js      (Git-based conflict resolution)
│   │   ├── reporter.js         (daily rollups, alerts)
│   │   ├── harness.js          (harness evolution engine)
│   │   ├── patterns.js         (pattern detection)
│   │   ├── health.js           (self-monitoring)
│   │   ├── events.js           (event-bridge publisher)
│   │   └── migrations.js       (schema versioning)
│   ├── wrapper/
│   │   ├── agent-wrapper.js    (sidecar process for agents)
│   │   ├── wrapper.config.js   (per-agent config)
│   │   └── offline-buffer.js   (buffer heartbeats when tracker down)
│   ├── dashboard/
│   │   ├── index.html
│   │   ├── style.css
│   │   └── app.js
│   ├── db/
│   │   ├── migrations/         (numbered migration files)
│   │   └── agent-tracker.db    (SQLite — historical data only)
│   ├── test/
│   │   ├── unit/               (SQLite query tests)
│   │   ├── integration/        (API endpoint tests)
│   │   └── load/               (concurrent write tests)
│   ├── package.json
│   ├── openapi.yaml            (API contract)
│   └── Dockerfile
└── docker-compose.yml (add agent-tracker service)
```

---

## Data Architecture

### Redis (Volatile State — fast reads/writes)
| Key Pattern | Type | TTL | Description |
|-------------|------|-----|-------------|
| `agent:{id}:status` | Hash | None | Current agent state |
| `agent:{id}:heartbeat` | String | 90s | Last heartbeat timestamp |
| `agent:{id}:task` | Hash | None | Current task context |
| `circuit:{id}` | Hash | None | Circuit breaker state |
| `lock:{path}` | String | 300s | Distributed lock (Redlock) |
| `router:cache:{hash}` | Hash | 3600s | Routing decision cache |
| `queue:pending` | Sorted Set | None | Task queue by priority |
| `metrics:{type}` | Hash | None | Live counters |

### SQLite (Historical Data — append-only)
| Table | Purpose |
|-------|---------|
| `api_calls` | Every API call log (source of truth for costs) |
| `tasks` | Completed/failed tasks (denormalized cost from api_calls) |
| `lessons` | Agent learnings (approved global → SiYuan sync) |
| `harness_proposals` | Evolution proposals + outcomes |
| `migrations` | Schema version tracking |
| `daily_reports` | Generated daily reports |

---

## Data Model

### api_calls (SQLite — append-only)
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY | auto-increment |
| agent_id | TEXT | which agent |
| task_id | INTEGER | linked task (nullable during routing) |
| model | TEXT | model used |
| tokens_in | INTEGER | input tokens |
| tokens_out | INTEGER | output tokens |
| cost_usd | REAL | calculated cost |
| duration_ms | INTEGER | call duration |
| timestamp | DATETIME | when call happened |

### tasks (SQLite — historical)
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY | auto-increment |
| agent_id | TEXT | assigned agent |
| session_id | TEXT | agent session UUID (not PID) |
| description | TEXT (max 500 chars) | task description |
| status | TEXT | pending, running, completed, failed, dead |
| priority | INTEGER | 1=urgent, 2=normal, 3=low |
| parent_task_id | INTEGER | for dependency chains |
| depends_on | INTEGER | task ID this depends on |
| started_at | DATETIME | when started |
| completed_at | DATETIME | when finished |
| duration_seconds | INTEGER | how long |
| tokens_used | INTEGER | total tokens (denormalized from api_calls) |
| cost_usd | REAL | total cost (denormalized from api_calls) |
| outcome | TEXT | success, partial, failure |
| error_message | TEXT | if failed |
| git_commit | TEXT | related commit hash |
| agent_output | TEXT (max 10KB) | what the agent produced |
| validation_passed | BOOLEAN | did handoff validation pass |

### lessons (SQLite)
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY | auto-increment |
| agent_id | TEXT | which agent learned this |
| task_type | TEXT | category of task |
| lesson | TEXT (max 1000 chars) | what was learned |
| severity | TEXT | info, warning, critical |
| confidence | REAL | 0.0-1.0 how sure we are |
| times_applied | INTEGER | how many times this helped |
| times_ignored | INTEGER | how many times ignored |
| approved | BOOLEAN | Eddie approved for global? |
| synced_to_siyuan | BOOLEAN | synced to shared knowledge? |
| created_at | DATETIME | when discovered |
| last_applied | DATETIME | last time used |

### harness_proposals (SQLite)
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY | auto-increment |
| agent_id | TEXT | which agent proposed this |
| component_type | TEXT | skill, memory, prompt, tool |
| component_path | TEXT | file path |
| target_commit | TEXT | git commit at proposal time |
| proposed_change | TEXT | what to change |
| reason | TEXT | why this change helps |
| measured_improvement | REAL | measured improvement % |
| evaluation_method | TEXT | how improvement was measured |
| evaluation_samples | INTEGER | number of tasks tested |
| status | TEXT | pending, approved, applied, rejected, reverted |
| approved_by | TEXT | who approved |
| applied_at | DATETIME | when applied |
| reverted_at | DATETIME | when reverted |
| created_at | DATETIME | when proposed |

### migrations (SQLite)
| Column | Type | Description |
|--------|------|-------------|
| version | INTEGER PRIMARY | migration number |
| name | TEXT | migration description |
| applied_at | DATETIME | when applied |

---

## Authentication

### HMAC Token Auth (MVP)

Every request must include:
```
X-Agent-Token: {hmac_token}
X-Timestamp: {unix_timestamp}
X-Signature: HMAC-SHA256(agent_secret, timestamp + method + path)
```

### Token Distribution
- Each agent gets a unique token at registration
- Tokens stored in agent's `.agentrc` config file
- Gateway proxies requests and validates signatures
- Rate limiting: 100 requests/minute per agent

### Error Responses
```json
{
  "error": {
    "code": "AUTH_FAILED",
    "message": "Invalid or missing authentication",
    "details": null
  }
}
```

### Standard Error Envelope
```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": "any (optional)"
  }
}
```

---

## API Endpoints

### Health & Status
- `GET /api/health` — system health (DB, Redis, uptime)
- `GET /api/metrics` — Prometheus-format metrics

### Agent State
- `POST /api/agents/start` — register agent start
- `POST /api/agents/heartbeat` — keepalive (every 60s)
- `POST /api/agents/complete` — log completion + outcome
- `GET /api/agents/status` — all agent statuses
- `POST /api/agents/:id/restart` — manual restart

### Cost Tracking
- `POST /api/costs/log` — log API call
- `GET /api/costs/daily` — today's breakdown
- `GET /api/costs/weekly` — this week
- `GET /api/costs/monthly` — this month
- `GET /api/costs/by-agent` — per-agent breakdown
- `GET /api/costs/trend` — 30-day trend data

### Task Queue
- `POST /api/tasks` — queue new task
- `GET /api/tasks` — list tasks (filter: status, agent, priority)
- `GET /api/tasks/:id` — task details
- `PUT /api/tasks/:id` — update task
- `POST /api/tasks/:id/retry` — retry failed task
- `POST /api/tasks/:id/validate` — validate handoff output
- `GET /api/tasks/next/:agent` — get next task for agent

### Memory
- `POST /api/lessons` — log a lesson
- `GET /api/lessons` — get lessons (filter: agent, task_type, severity)
- `GET /api/lessons/patterns` — detected patterns
- `GET /api/lessons/for-task/:task_type` — relevant lessons for task

### File Coordination (Git-Based)
- `POST /api/coord/check` — check if file is being edited by another agent
- `POST /api/coord/claim` — claim file for editing (creates branch)
- `POST /api/coord/release` — release file (merge or abort)
- `GET /api/coord/active` — list active file claims

### Harness Evolution
- `POST /api/harness/propose` — agent proposes change
- `GET /api/harness/pending` — pending proposals
- `POST /api/harness/:id/approve` — Eddie approves
- `POST /api/harness/:id/reject` — reject proposal
- `POST /api/harness/:id/revert` — revert applied change

### Circuit Breaker
- `GET /api/circuit/:agent` — get circuit state
- `POST /api/circuit/:agent/reset` — manually reset

### Dashboard
- `GET /dashboard` — web UI

### Reporting
- `GET /api/reports/daily` — full daily report
- `POST /api/reports/send` — send to Tripp + Eddie (Telegram)

---

## Agent Wrapper (Sidecar)

### Process Model
```
┌─────────────────────────────────────┐
│  agent-wrapper (sidecar)            │
│  ├── starts with agent              │
│  ├── generates session UUID         │
│  ├── sends heartbeat every 60s      │
│  ├── captures stdout/stderr         │
│  ├── detects crashes (PID + output) │
│  └── reports completion/failure     │
└─────────────────────────────────────┘
```

### Wrapper Lifecycle
1. **Start:** Wrapper launches, generates session UUID, calls `POST /api/agents/start`
2. **Heartbeat:** Every 60s, sends `POST /api/agents/heartbeat` with session UUID
3. **Complete:** Agent exits → wrapper calls `POST /api/agents/complete` with outcome
4. **Crash:** No exit code 0 → wrapper reports failure, triggers auto-restart

### Offline Mode
If tracker is unreachable:
1. Buffer heartbeats locally (max 5 minutes)
2. Buffer cost logs locally
3. When tracker comes back → replay buffer
4. If buffer full → drop oldest, log warning

### Wrapper Config (`.agentrc`)
```toml
[agent]
name = "codex"
token = "hmac_token_here"
tracker_url = "http://agent-tracker:6830"

[heartbeat]
interval_ms = 60000
timeout_ms = 5000
retries = 3

[restart]
max_restarts = 3
backoff_base_ms = 1000
backoff_max_ms = 30000
```

---

## Task Routing

### Deterministic Routing (Default)

| Task Type | Primary Agent | Fallback | Why |
|-----------|---------------|----------|-----|
| research | Kimi | Echo | Deep research capability |
| coding | Codex | Claude Code | Fast, efficient |
| review | Claude Code | Codex | Thorough analysis |
| planning | Echo | Kimi | Coordination |
| audio | Cyony | — | Specialized |
| testing | Codex | Claude Code | Automated testing |

### Routing Decision Factors
1. Agent availability (not already running)
2. Circuit breaker state (not open)
3. Past performance on similar tasks (from lessons)
4. Current load (don't overload one agent)

### LLM Router (Ambiguous Cases Only)
- Use cheap model (GPT-4o-mini) only when deterministic rules don't apply
- Cache routing decisions for 1 hour
- Track routing accuracy, alert if <80%

### Fallback
- No suitable agent available → queue for manual assignment
- All agents failed → alert Tripp + Eddie

---

## Failure Recovery

### Circuit Breaker Pattern

```
CLOSED (normal)
    │
    ▼ (3 failures)
OPEN (blocking — 30s timeout)
    │
    ▼ (timeout expires)
HALF_OPEN (testing — allow 1 request)
    │
    ├─ success → CLOSED
    └─ failure → OPEN (reset timeout)
```

### Handoff Validation

When Agent A finishes and output goes to Agent B:
1. Schema validation (required fields present)
2. Type validation (output matches expected structure)
3. Content validation (not empty, not garbage, reasonable length)
4. If validation fails → route back to Agent A with specific error

### Retry Logic
```
delay = base_delay × (2 ^ attempt) + random(0, 1)
max_attempts = 3
```

### Checkpointing
- Save state at every step
- Resume from last good checkpoint
- Don't restart from scratch

### Escalation Path
1. Auto-retry (3 attempts)
2. Circuit breaker opens
3. Alert Tripp on Telegram
4. Alert Eddie if critical
5. Log failure as lesson
6. Queue for manual review

---

## Harness Evolution

### Approval Workflow

1. **Proposal:** Agent completes task, proposes improvement
2. **Measurement:** System validates improvement with N=10 task sample
3. **Queue:** Proposal goes to Eddie via Telegram (inline buttons)
4. **Approval Window:** 24 hours, auto-approve if no response
5. **Application:** Apply to git branch (not live)
6. **Evaluation:** Run N=10 tasks with change, measure improvement
7. **Go-Live:** Merge branch if improvement confirmed
8. **Revert:** Auto-revert within 5 minutes if regression detected

### Anti-Reward-Hacking
- Proposals must show measured improvement (not just claims)
- System validates evaluator wasn't modified
- Changes applied to git branch (isolated from live)
- Eddie has final approval on all changes
- One-click revert via Telegram or dashboard

### Example Flow
```
Codex completes 5 coding tasks
Pattern detector notices: "Tasks with explicit file structure in prompt succeed 80% more"
Proposal: "Add file structure template to CODING_SKILL.md"
Measurement: Tested on 10 tasks, +23% success rate
Eddie approves via Telegram → branch merged → live
Future tasks benefit from improved skill
```

---

## Integration with Tripp.Mind

### Gateway Integration
- Agent-tracker runs on port 6830
- Gateway proxies `/tracker/*` → agent-tracker:6830
- Gateway provides auth validation before proxying

### Event-Bridge Publishing
Publish key events:
- `agent.started` — agent began work
- `agent.completed` — agent finished task
- `agent.failed` — agent crashed/failed
- `circuit.opened` — circuit breaker triggered
- `harness.proposal` — new evolution proposal

### SiYuan Sync
- Approved global lessons → auto-written to `KNOWLEDGE/AGENT-LESSONS/`
- Sync runs hourly
- Prevents knowledge fragmentation

### Network Topology
```
Desktop (Echo)
    │
    │ Tailscale
    ▼
VPS (2.24.118.123)
    ├── agent-tracker:6830
    ├── gateway:3000
    ├── redis:6379
    ├── siyuan:6806
    ├── codex (Docker)
    ├── kimi (Docker)
    └── claude-code (Docker)
```

All agents resolve tracker via `http://agent-tracker:6830` (Docker network) or `http://2.24.118.123:6830` (external).

---

## Self-Monitoring

### Health Endpoint
```json
{
  "status": "healthy",
  "uptime_seconds": 86400,
  "checks": {
    "sqlite": "ok",
    "redis": "ok",
    "memory_mb": 45,
    "active_agents": 2,
    "pending_tasks": 5
  }
}
```

### Metrics (Prometheus Format)
```
agent_tracker_requests_total{method="POST",path="/api/agents/start"} 142
agent_tracker_request_duration_seconds{method="POST",quantile="0.95"} 0.045
agent_tracker_active_agents 2
agent_tracker_pending_tasks 5
agent_tracker_circuit_breaker_opens_total{agent="codex"} 3
agent_tracker_cost_usd_daily 4.32
```

### Structured Logging
- JSON format (Pino)
- Request IDs (X-Request-Id) on all calls
- Log rotation: 10MB max, 7 days retention

---

## Dashboard Features

### MVP (Phase 1) — Terminal Dashboard
```bash
┌─────────────────────────────────────────┐
│  AGENT STATUS                           │
├──────────┬──────────┬──────────┬────────┤
│ Agent    │ Status   │ Task     │ Cost   │
├──────────┼──────────┼──────────┼────────┤
│ Codex    │ running  │ fix bug  │ $1.23  │
│ Kimi     │ idle     │ —        │ $0.45  │
│ Claude   │ failed   │ review   │ $0.89  │
└──────────┴──────────┴──────────┴────────┘
│ Today: $2.57 │ Week: $18.42 │ Alerts: 1 │
```

### Full Dashboard (Phase 4) — Web UI
- Live agent status cards
- Cost graphs (30-day trend)
- Task history with outcomes
- Memory/lessons feed
- Harness proposals

---

## Daily Report Format

```
📊 Daily Agent Report — {date}

🤖 Codex: {tasks_completed} tasks, ${cost}
   ✅ {task1} ({duration}, ${cost})
   ✅ {task2} ({duration}, ${cost})
   ❌ {failed_task} → auto-retried → succeeded

🤖 Kimi: {tasks_completed} tasks, ${cost}
   ✅ {task1} ({duration}, ${cost})

💰 Total: ${total_cost}
📈 7-day avg: ${avg}/day
📉 Trend: {up/down/flat}

🧠 New lessons: {count}
   - "{lesson1}"
   - "{lesson2}"

🔧 Harness proposals: {count}
   - {proposal1}

⚠️ Circuit breaker events: {count}
   - {agent}: opened → recovered

🔒 File claims: {count} active
   - {file1} → {agent2}
```

---

## Testing Strategy

### Unit Tests
- SQLite query functions (in-memory test DB)
- Cost calculation logic
- Routing decision logic
- Circuit breaker state machine

### Integration Tests
- Every API endpoint (Supertest + test DB)
- Agent wrapper lifecycle (mock agent)
- Heartbeat flow (start → heartbeat → complete)
- Offline buffer replay

### Load Tests
- SQLite under concurrent writes (10 agents, 100 writes/s)
- Redis under high throughput
- Dashboard under many concurrent viewers

### CI Pipeline
- GitHub Actions on every PR
- Run unit + integration tests
- Lint + type check
- Load test on merge to main

---

## Implementation Phases

### Phase 1: Foundation (Weeks 1-3)
- [ ] Auth layer (HMAC tokens)
- [ ] Redis volatile state
- [ ] SQLite historical storage
- [ ] Agent state tracker
- [ ] Cost logger
- [ ] Health endpoint
- [ ] Basic API endpoints
- [ ] Agent wrapper (sidecar)
- [ ] Terminal dashboard
- [ ] Daily report to Telegram

### Phase 2: Reliability (Weeks 4-6)
- [ ] Task queue with priorities
- [ ] Auto-restart watchdog
- [ ] Circuit breaker
- [ ] Retry + backoff
- [ ] Offline buffer for wrapper
- [ ] Event-bridge publishing
- [ ] Schema migrations

### Phase 3: Intelligence (Weeks 7-10)
- [ ] Two-tier memory system (session + persistent)
- [ ] Lesson storage + retrieval
- [ ] Pattern detection
- [ ] Deterministic task router + LLM fallback
- [ ] SiYuan sync for approved lessons
- [ ] Git-based file coordination

### Phase 4: Dashboard (Weeks 11-13)
- [ ] Web dashboard (live status, cost graphs)
- [ ] Task history view
- [ ] Memory/lessons feed
- [ ] Structured logging + metrics

### Phase 5: Evolution (Weeks 14-16)
- [ ] Harness proposal system
- [ ] Measurement protocol (N=10 sample)
- [ ] Telegram approval workflow
- [ ] Git-branch application
- [ ] Auto-revert on regression

---

## Success Metrics

| Metric | Target | How Measured |
|--------|--------|--------------|
| Agent visibility | 100% uptime tracking | Dashboard shows all agents |
| Cost tracking | ±5% accuracy | Compare manual vs tracked |
| Failure recovery | <2 min mean time to restart | Watchdog logs |
| Lesson application | 20% improvement in task success | Track success rate before/after |
| Daily report delivery | 100% on-time | Cron job success rate |
| Tracker uptime | 99.5% | Health endpoint monitoring |

---

## Open Questions

- [ ] Should the daily report go to Tripp, Eddie, or both?
- [ ] How do we handle Cyony's specialized role (not just coding)?
- [ ] Vector DB: when do we need it? Start with SQLite FTS, add later?
- [ ] Should harness proposals auto-approve after 24h or require explicit response?

---

## Appendix A: Codex Audit Fixes

| Issue | Severity | Fix Applied |
|-------|----------|-------------|
| Zero authentication | Critical | Added HMAC token auth |
| SQLite contention | Critical | Moved volatile state to Redis |
| No tracker reliability | Critical | Added health endpoint, offline mode, crash recovery |
| No API schemas | Critical | Added OpenAPI spec, validation, error envelopes |
| Agent wrapper undefined | High | Designed sidecar process with lifecycle |
| File locking race-prone | High | Replaced with Git-based coordination |
| No self-observability | High | Added structured logging, Prometheus metrics |
| Vague harness workflow | High | Defined measurement protocol, approval flow, revert |
| Unrealistic timeline | High | Replanned: 16 weeks vs original 5 |
| No testing strategy | Medium | Added unit, integration, load tests + CI |
| No schema migrations | Medium | Added migration framework |
| Dashboard too ambitious | Medium | MVP terminal dashboard, web UI deferred |
| LLM router underspecified | Medium | Deterministic default, LLM for ambiguous only |
| Three-tier = two tiers | Medium | Honest: session + persistent SQLite |
| No event-bridge usage | Medium | Added event publishing |
| No SiYuan sync | Medium | Added lesson sync path |
| No network topology | Medium | Documented Tailscale layout |
| Agent hierarchy unclear | Low | Defined managed vs manager agents |

---

*Prepared for orchestrator audit (2 rounds).*
