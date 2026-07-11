# Tripp.Operating Doctrine v2.0

**The Laws That Govern Our System**

*Created: 2026-07-11*
*Last Updated: 2026-07-11 (v2.0 — aligned with database-backed design)*
*Status: DRAFT — Pending Final Audit*

---

## Preamble

This document defines the rules, principles, and practices that govern the Tripp.System multi-agent messaging platform. Every agent, worker, and human operator must follow these laws. Violations are logged and may result in quarantine, dead-lettering, or revocation.

**This Doctrine is the constitution. When in conflict with code or documentation, this Doctrine wins until formally amended.**

---

## Part 1: Core Principles

### 1.1 Clarity Over Cleverness
Every message, every action, every decision must be clear and understandable. If it requires explanation, it's too complex.

### 1.2 Accountability Through Audit
Every action is logged. Every log is immutable. Every agent is traceable. No exceptions.

### 1.3 Security By Design
No agent is trusted by default. Every action is authenticated and authorized. Least privilege applies.

### 1.4 Resilience Through Redundancy
No single point of failure. No silent crashes. Every failure is detected and handled.

### 1.5 Forward Progress
When in doubt, move forward with caution. When blocked, escalate. When uncertain, document.

---

## Part 2: Agent Roles & Responsibilities

### 2.1 Eddie (Human Operator)
- **Role:** Visionary, decision-maker, final authority
- **Permissions:** Full system access, can modify agent configs, can override any rule
- **Communication:** Via Telegram only
- **Authority:** Can mark any message as priority, can cancel any chain, can override any audit

### 2.2 Echo (Architect)
- **Role:** System architect, audit coordinator, quality gatekeeper
- **Permissions:** Can create/modify documentation, can coordinate audits, can approve designs
- **Communication:** Via Tripp.Mail
- **Authority:** Can require audits, can block builds, can escalate to Eddie

### 2.3 Tripp (Operations)
- **Role:** Infrastructure, deployment, monitoring, maintenance
- **Permissions:** Can deploy code, can restart services, can modify system configs
- **Communication:** Via Tripp.Mail
- **Authority:** Can escalate to Eddie, can pause deployments

### 2.4 Cyony (Guardian)
- **Role:** Security monitoring, anomaly detection, compliance
- **Permissions:** Can read all logs, can flag suspicious activity, can quarantine agents
- **Communication:** Via Tripp.Mail
- **Authority:** Can quarantine agents, can require security audits

### 2.5 Kimi (Analyst)
- **Role:** Code review, analysis, research, deep audit
- **Permissions:** Can read code, can analyze patterns, can produce reports
- **Communication:** Via Tripp.Mail
- **Authority:** Can flag issues, can require fixes

### 2.6 Codex (Builder)
- **Role:** Code generation, implementation, testing
- **Permissions:** Can write code, can run tests, can create pull requests
- **Communication:** Via Tripp.Mail
- **Authority:** Can flag blockers, can require reviews

---

## Part 3: Message Flow Laws

### 3.1 Authentication
Every message must be authenticated via API key. The gateway derives `sender` from the authenticated identity. **Never trust `sender` from the request body.**

### 3.2 Authorization
Every message is checked against the authorization matrix:
- Is this sender allowed to send this message type to this recipient?
- Is this sender allowed to send this message type at all?
- If not authorized, reject with 403 and log the attempt.

### 3.3 Chain of Custody
Multi-step reviews must use chain of custody:
- Chain is **server-generated** (not client-submitted)
- Each step is validated by the server
- Chain HMAC ensures non-repudiation
- Maximum 10 steps (hard limit)
- No cycles allowed (server checks)

### 3.4 Immutability
Once created, messages cannot be modified or deleted. Only state transitions are allowed:
- pending → claimed → delivered/failed
- pending → expired/cancelled
- failed → pending (retry) / dead_lettered

### 3.5 Delivery Semantics
- At-least-once delivery guaranteed
- Idempotency keys prevent duplicate processing
- Deduplication window: 24 hours
- Delivery confirmed via inbox acknowledgment

---

## Part 4: Project Lifecycle Laws

### 4.1 State Machine
Every project follows:
```
PLANNING → IN_PROGRESS → COMPLETED → ARCHIVED
                ↓
            SCRAPPED → ARCHIVED
                ↓
          ABANDONED (7 days no activity) → ARCHIVED
```

### 4.2 Three-Round Planning Rule
Before ANY build (except HTML mockups):
- **Round 1:** Initial design + Codex audit
- **Round 2:** Redesign + Codex audit
- **Round 3:** Final audit + approval

Building is ONLY authorized when:
- Three rounds complete
- Codex gives approval
- Eddie reviews and approves
- Plan document signed off in STATUS.md

### 4.3 Build Authorization
```python
def can_build(project: str) -> bool:
    """Check if building is authorized."""
    status = read_status(project)
    
    if not status.get("codex_approved"):
        return False
    if not status.get("eddie_approved"):
        return False
    if status.get("audit_rounds", 0) < 3:
        return False
    if status.get("planning_complete") != True:
        return False
    
    return True
```

---

## Part 5: Cleanup Laws

### 5.1 Anti-Clutter Commandments
1. **No hoarding prompts** — Delete when task completes
2. **No keeping drafts** — Final docs only
3. **No redundant logs** — Rotate and compress
4. **No stale data** — Auto-expire after 30 days
5. **No orphaned files** — Cleanup worker enforces

### 5.2 Cleanup Triggers
- **COMPLETED:** Archive working files, keep docs
- **SCRAPPED:** Delete working files, archive lessons learned
- **ABANDONED:** Auto-archive after 7 days no activity

### 5.3 Cleanup Safety
Before any destructive cleanup:
1. Verify backup exists
2. Check for legal holds
3. Confirm no dependencies
4. Log what will be deleted
5. Execute cleanup
6. Verify backup integrity

---

## Part 6: Audit Laws

### 6.1 What Gets Audited
- All message state transitions
- All authentication attempts
- All authorization decisions
- All worker health changes
- All system configuration changes
- All cleanup operations

### 6.2 Audit Integrity
- Append-only (SQLite triggers prevent UPDATE/DELETE)
- Hash chain for tamper detection
- HMAC for non-repudiation
- Event IDs for idempotency
- Regular integrity verification

### 6.3 Audit Retention
- Active audit: 90 days
- Archived audit: 1 year
- Critical audit: 7 years
- Backup: Daily, retained 7 days

---

## Part 7: Error Handling Laws

### 7.1 Error Severity Levels
- **CRITICAL:** System down, data loss risk → Immediate alert, halt processing
- **HIGH:** Major feature broken, no workaround → Alert within 1 hour
- **MEDIUM:** Feature degraded, workaround exists → Alert within 24 hours
- **LOW:** Minor issue, cosmetic → Log and address in next sprint

### 7.2 Retry Policy
- Maximum 3 retries per message
- Exponential backoff: 2^n seconds + 10% jitter
- Retry deadline: 24 hours maximum
- Dead letter after max retries

### 7.3 Failure Handling
- Worker crash: Supervisor restarts within 30 seconds
- Database error: Halt processing, alert operator
- Audit failure: **Halt message processing** (no unaudited operations)
- Network timeout: Retry with backoff

---

## Part 8: Security Laws

### 8.1 Authentication
- API keys stored as Argon2 hashes
- Keys rotated every 90 days
- Emergency rotation: Immediate revocation + new key
- No key reuse across environments

### 8.2 Authorization
- Server-derived identity (never trust client)
- Matrix-based permissions (sender × recipient × type)
- Least privilege principle
- No self-messaging (agents can't message themselves)

### 8.3 Data Protection
- TLS for all API traffic
- Encryption-at-rest for database
- Sensitive fields redacted in logs
- No credentials in error messages

### 8.4 Threat Model
- **Trusted:** Eddie, all authenticated agents
- **Untrusted:** External requests, malformed messages
- **Boundary:** API gateway (authentication + authorization)
- **Containment:** Compromised agent quarantined

---

## Part 9: Documentation Laws

### 9.1 Documentation Requirements
- Every system must have a README
- Every API must have OpenAPI spec
- Every database must have schema documentation
- Every process must have runbook

### 9.2 Documentation Currency
- Documentation must match implementation
- Contradictions must be resolved within 24 hours
- Outdated documentation must be flagged

### 9.3 Documentation Location
- Primary: GitHub `eOnoes/documentation`
- Local: `D:\Documentation\`
- Operational: VPS shared/

---

## Part 10: Testing Laws

### 10.1 Test Requirements
- Unit tests for all business logic
- Integration tests for all database operations
- Adversarial tests for all security controls
- Concurrency tests for all shared resources

### 10.2 Test Coverage
- Minimum 80% code coverage
- 100% coverage for security-critical paths
- All error paths tested
- All edge cases tested

### 10.3 Test Execution
- Tests run before every commit
- Full suite runs before every deployment
- Adversarial tests run weekly
- Integrity verification runs daily

---

## Part 11: Monitoring Laws

### 11.1 Required Metrics
- Queue age (oldest pending message)
- Claim age (oldest claimed message)
- Retry rate (retries per minute)
- Dead letter volume
- Database size
- WAL size
- Audit verification failures
- Worker health status

### 11.2 Alerting
- CRITICAL: Immediate page to Eddie
- HIGH: Slack/Telegram notification
- MEDIUM: Daily summary
- LOW: Weekly report

### 11.3 Runbooks
Every alert must have a runbook:
1. What is the alert?
2. What caused it?
3. What do I do?
4. Who do I escalate to?

---

## Part 12: Governance

### 12.1 Doctrine Amendments
- Amendments require Eddie's approval
- Amendments must be documented
- Amendments must be backward compatible
- Emergency amendments: Immediate, with retrospective review

### 12.2 Audit Independence
- No agent can approve its own work
- Kimi provides second opinion on audits
- Eddie has final authority on all builds
- Codex can audit AND approve (but Eddie always confirms)

### 12.3 Conflict Resolution
1. Agent-to-agent: Escalate to Echo
2. Agent-to-human: Escalate to Eddie
3. System conflict: Halt and escalate

---

## Appendix A: Message Types

| Type | Description | Max Steps | Timeout |
|------|-------------|-----------|---------|
| message | Standard communication | 1 | 24h |
| reply | Response to message | 1 | 24h |
| update | Status update | 1 | 24h |
| request | Request for action | 3 | 48h |
| emergency | Urgent action needed | 1 | 1h |
| audit_request | Audit coordination | 4 | 72h |
| audit_response | Audit findings | 1 | 24h |

---

## Appendix B: State Transitions

```
pending → claimed (worker claims)
claimed → delivered (delivery confirmed)
claimed → failed (delivery failed)
claimed → pending (retry scheduled)
failed → pending (retry scheduled)
failed → dead_lettered (max retries exceeded)
pending → expired (TTL exceeded)
pending → cancelled (operator cancelled)
```

---

## Appendix C: Authorization Matrix Summary

| Sender | Can Send To | Message Types |
|--------|-------------|---------------|
| Eddie | All agents, 'all' | All types |
| Echo | Tripp, Cyony, Kimi, Codex, Eddie | message, reply, audit_request |
| Tripp | Echo, Eddie | message, reply |
| Cyony | Echo, Eddie | message, reply |
| Kimi | Echo, Eddie | message, reply, audit_response |
| Codex | Echo, Eddie | message, reply, audit_response |
| Any agent | Cannot self-message | — |

---

**This Doctrine is the law. Follow it or face quarantine.** 🛡️💚
