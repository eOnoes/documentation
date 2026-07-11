# OpenClaw + Hermes Supervisor Architecture

## Purpose

This document defines a two-agent operating model for running OpenClaw and Hermes on the same Ubuntu 24.04 cloud server. OpenClaw acts as the lead/supervisor agent. Hermes acts as an adaptive, experimental, high-variance worker agent. The goal is to let Hermes discover and develop new capabilities while OpenClaw controls scope, safety, persistence, and production adoption.

## Core Principle

OpenClaw governs. Hermes experiments.

Hermes may propose new skills, workflows, tools, memories, automations, and behavioral patterns. OpenClaw reviews those outputs and decides whether they are adopted, limited, quarantined, archived, or removed.

No Hermes-created skill becomes durable or production-capable without OpenClaw review.

## Agent Roles

### OpenClaw: Lead / Supervisor

OpenClaw is responsible for:

- defining goals
- maintaining operating scope
- assigning or approving tasks
- reviewing Hermes outputs
- approving or rejecting new skills
- managing durable memory
- enforcing security boundaries
- controlling production-ready workflows
- deciding final actions
- coordinating model/provider policy
- maintaining audit trails
- pruning off-scope behavior

OpenClaw should prioritize stability, traceability, permission control, and alignment with current goals.

### Hermes: Wild Card / Experimental Worker

Hermes is responsible for:

- experimentation
- skill discovery
- custom skill generation
- alternate solution paths
- rapid prototyping
- creative workflow design
- tool exploration
- research branches
- tactical problem solving
- proposing improvements to OpenClaw
- sharing useful discoveries with OpenClaw

Hermes may learn and grow, but its growth must be surfaced to OpenClaw for review before becoming part of the shared operating system.

## Authority Model

OpenClaw has final authority over:

- approved skills
- persistent memory
- shared knowledge
- production workflows
- credentials and secrets access
- filesystem permissions
- external integrations
- automation schedules
- model/provider routing
- removal of rejected or unsafe capabilities

Hermes has authority over:

- temporary experiments within its sandbox
- proposed skill drafts
- local scratch notes
- non-production tests
- research outputs
- prototype workflows

Hermes must not directly modify OpenClaw configuration, OpenClaw memory, production workflows, or approved shared skills unless explicitly granted a scoped task by OpenClaw.

## Recommended Server Layout

Use separated agent directories with one controlled shared exchange area.

```text
~/agents/
  openclaw/
    .env
    config/
    memory/
    approved-skills/
    logs/

  hermes/
    .env
    config/
    memory/
    experimental-skills/
    scratch/
    logs/

  shared/
    inbox-from-hermes/
    review-queue/
    approved-knowledge/
    approved-skills/
    rejected-or-archived/
    audit-logs/
    policies/
```

Hermes writes proposed discoveries to:

```text
~/agents/shared/inbox-from-hermes/
```

OpenClaw reviews from:

```text
~/agents/shared/review-queue/
```

OpenClaw promotes accepted knowledge to:

```text
~/agents/shared/approved-knowledge/
~/agents/shared/approved-skills/
```

OpenClaw moves rejected, unsafe, duplicate, or off-scope materials to:

```text
~/agents/shared/rejected-or-archived/
```

## Skill Lifecycle

### 1. Discovery

Hermes identifies or creates a new skill, workflow, automation, prompt pattern, tool chain, or operating behavior.

### 2. Proposal

Hermes creates a proposal file in the shared inbox.

Required proposal fields:

- skill name
- purpose
- supported goal
- operating scope
- triggering conditions
- required permissions
- required files/directories
- required environment variables
- required external services
- expected benefits
- known risks
- failure modes
- rollback/removal steps
- test evidence, if available

### 3. Review

OpenClaw reviews the proposal against:

- current goal alignment
- security risk
- credential exposure
- filesystem access
- network access
- reliability
- maintainability
- duplication of existing skills
- cost impact
- model/provider requirements
- risk of uncontrolled autonomy

### 4. Decision

OpenClaw chooses one:

- `approved`: skill may be used and persisted
- `approved-limited`: skill may be used only under defined constraints
- `quarantined`: skill may be tested but not used in production
- `needs-revision`: Hermes must modify and resubmit
- `rejected`: skill is not allowed
- `removed`: skill must be deleted from active use
- `archived`: skill is preserved only as historical reference

### 5. Promotion

Approved skills move to the approved shared area. OpenClaw may import them into its own config or memory only after review.

### 6. Audit

Every decision should create an audit entry with:

- timestamp
- proposal name
- decision
- reviewer
- reason
- permissions granted or denied
- rollback instructions

## Skill Proposal Template

```md
# Skill Proposal: <name>

## Proposed By
Hermes

## Purpose
<What this skill does.>

## Supported Goal
<Which goal, reason, or scope this supports.>

## Scope
<Where this skill is allowed to operate.>

## Trigger Conditions
<When this skill should be used.>

## Required Permissions
- filesystem:
- network:
- shell:
- docker:
- external APIs:
- credentials:

## Required Config
- env vars:
- files:
- directories:
- services:

## Expected Benefit
<Why this should exist.>

## Risks
<Security, cost, reliability, privacy, autonomy, or operational risks.>

## Failure Modes
<How this can go wrong.>

## Rollback / Removal
<How OpenClaw can disable or remove it cleanly.>

## Test Evidence
<Commands, logs, examples, or dry-run notes.>
```

## Promotion Rules

A Hermes-generated skill may be promoted only if:

- it supports a current approved goal
- it has a clear scope
- it does not require excessive permissions
- it does not expose secrets
- it has a rollback path
- it does not duplicate an existing approved skill without improvement
- it does not create uncontrolled recurring actions
- it does not grant Hermes authority over OpenClaw
- OpenClaw records an approval decision

A skill must be rejected or removed if:

- it is outside the active goal or operating scope
- it requires broad filesystem access without justification
- it attempts to read or modify secrets unnecessarily
- it attempts to bypass OpenClaw approval
- it creates uncontrolled automation
- it increases cost without a clear reason
- it introduces risky network behavior
- it modifies production config without review
- it cannot be rolled back

## Memory Sharing Rules

Hermes may share:

- discoveries
- summaries
- research notes
- prototype results
- proposed skills
- lessons learned
- failure reports
- reusable prompts
- tool usage notes

Hermes should not directly write durable OpenClaw memory.

OpenClaw decides what becomes:

- durable memory
- approved knowledge
- approved skill
- operating policy
- archived reference

OpenClaw should prefer summarized, structured, low-noise memory over raw logs.

## Configuration Boundaries

Hermes should not edit:

- `~/agents/openclaw/.env`
- `~/agents/openclaw/config/`
- `~/agents/openclaw/memory/`
- `~/agents/shared/approved-skills/`
- `~/agents/shared/approved-knowledge/`
- production reverse proxy config
- Docker compose files used by OpenClaw
- systemd units used by OpenClaw
- firewall rules
- credential stores

Hermes may write to:

- `~/agents/hermes/experimental-skills/`
- `~/agents/hermes/scratch/`
- `~/agents/shared/inbox-from-hermes/`

OpenClaw may read from Hermes proposal areas and promote approved items.

## Security Model

Each agent should have separate:

- application directory
- `.env` file
- logs
- Docker project name
- persistent volume
- API keys where practical
- channel credentials where practical

Shared secrets should be minimized.

Do not mount the full VPS filesystem into Hermes or OpenClaw containers. Mount only the directories required for the active task.

Preferred pattern:

```text
Hermes: limited writable sandbox + shared proposal inbox
OpenClaw: read access to proposals + write access to approved shared areas
```

Avoid:

```text
Hermes has write access to OpenClaw config
Hermes has write access to OpenClaw memory
Hermes has unrestricted host filesystem access
Both agents share one broad root-level API key
Both agents freely mutate the same skill folder
```

## Model Provider Policy

Both agents may use cloud-hosted model providers through OpenRouter, DeepSeek, or other approved APIs.

Since the VPS is Hostinger KVM 2 with 2 vCPU, 8 GB RAM, and 100 GB NVMe, local LLM inference should not be assumed as part of the baseline architecture.

Recommended baseline:

```text
OpenClaw = supervisor using stable, reliable models
Hermes = experimental worker using approved model list
OpenRouter = routing and model control layer
DeepSeek = direct fallback or specialized provider
Ollama = optional only if remote or using very small local models
```

OpenClaw should manage model policy, including:

- allowed model list
- default model
- fallback model
- budget limits
- free vs paid routing
- high-risk task model requirements
- maximum context/cost controls

Hermes may suggest model changes but should not alter provider policy directly.

## Operational Health Checks

After both agents are running, monitor:

```bash
free -h
df -h
docker ps
docker stats
docker system df
```

Watch for:

- RAM consistently above 7 GB used
- swap activity
- Docker logs growing unexpectedly
- containers restarting repeatedly
- disk usage rising quickly
- API cost spikes
- high CPU during concurrent tasks

Current known storage baseline:

```text
Hermes + Docker + backup: approximately 15 GB used
VPS total disk: 100 GB
Approximate free space before OpenClaw: 85 GB
```

Disk space is likely sufficient. RAM and CPU are the main constraints.

## Recommended Agent Relationship

```text
OpenClaw:
  supervisor
  reviewer
  governor
  durable memory owner
  production workflow owner

Hermes:
  experimental worker
  skill inventor
  researcher
  prototype builder
  proposal generator
```

OpenClaw should be stable, conservative, and scope-aware.

Hermes should be creative, adaptive, and exploratory, but bounded.

The system is healthy when Hermes produces useful new capabilities and OpenClaw selectively adopts only those that support approved goals.

## Minimal Operating Policy

```md
# Agent Policy

OpenClaw is the lead/supervisor agent.

Hermes is the adaptive experimental worker agent.

Hermes may create, test, and propose new skills, workflows, tools, memories, and automations.

Hermes may not directly promote new skills into production use.

All Hermes-generated skills must include purpose, supported goal, scope, required permissions, risks, and rollback steps.

OpenClaw may approve, limit, quarantine, reject, archive, or remove any Hermes-generated skill.

Skills outside the active goal, reason, or operating scope must be removed or archived.

Hermes may share discoveries and reusable knowledge with OpenClaw through the shared inbox.

OpenClaw decides what becomes durable memory, approved knowledge, approved skill, or operating policy.

Hermes must not modify OpenClaw config, secrets, durable memory, or production workflows unless OpenClaw explicitly grants a scoped task.
```

## Review Questions For OpenClaw

- Does this match the current Hermes/OpenClaw deployment model?
- Which directories already exist and which need to be created?
- Should Hermes and OpenClaw use separate Linux users?
- Should OpenClaw run in Docker, directly on host, or behind a reverse proxy?
- Should shared review folders be mounted read-only or read-write per agent?
- What permissions does Hermes currently have that should be reduced?
- What skills or memory should be migrated from Hermes to OpenClaw review?
- What model/provider policy should OpenClaw enforce?
- What should be the first test skill Hermes proposes under this policy?

