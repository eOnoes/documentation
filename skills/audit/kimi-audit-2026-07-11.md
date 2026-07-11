# Kimi Audit: Tripp.System v2.0

**Auditor:** Kimi (kimi-code/kimi-for-coding)
**Date:** 2026-07-11T19:10:17Z
**Codex Rating:** 5/10
**Your Rating:** 5/10

---

## Agreement with Codex

Codex's Round 2 critique is directionally correct. I agree with all 10 critical issues and most of the secondary findings.

- **Doctrine/implementation mismatch:** DOCTRINE.md v1.0 still mandates filesystem queues, JSONL audit, agent-modifiable messages. A constitution that contradicts the implementation is a governance failure.
- **State transitions unenforced:** state TEXT with no CHECK constraint means any value or transition is possible.
- **Auth without authz:** API key proves identity, not permissions.
- **Audit immutability not enforced:** Hash chain is computed but nothing prevents UPDATE/DELETE.
- **No idempotency/delivery semantics:** UUIDs prevent collisions, not duplicate submissions.
- **Broadcast recovery not implemented:** No message_deliveries table.
- **Schema lacks constraints:** No foreign keys, CHECK constraints, or content hash canonicalization.
- **Worker correctness issues:** Backoff uses sleep, no lease tokens, no circuit breaker.
- **No operational plan:** No backup, migration, monitoring, or runbooks.

---

## Disagreements with Codex

- **Chain validation framing:** Codex says "not cryptographic" but content_hash IS cryptographic. The issue is chain-of-custody needs non-repudiation (signatures), not just integrity.
- **Broadcast severity:** Critical if broadcasts are required, but redesign doesn't explicitly claim broadcast support.

---

## Issues Codex Missed (20!)

### Critical Missing Concepts
1. **No inbox/consumption model** — No table for tracking what's been read/acknowledged
2. **Claim lease timeouts** — Worker can crash and leave message in 'claimed' forever
3. **No transaction boundaries** — UPDATE messages and INSERT audit are separate operations
4. **No message expiration enforcement** — expires_at exists but no worker removes expired messages
5. **No retry deadline** — Transient outage could leave message retrying for days

### Code Bugs
6. **worker.retry_count undefined** — Supervisor references attribute that doesn't exist
7. **Audit hash double-hashing** — previous_hash hashed twice redundantly
8. **WorkerSupervisor blocks start()** — Health check loop runs synchronously
9. **Sleep not interruptible** — Shutdown can't interrupt worker in retry_with_backoff

### Missing Specifications
10. **Content hash canonicalization undefined** — Which fields? What order? What encoding?
11. **No API contract/OpenAPI** — Phase 3 says "create REST API" but no spec
12. **request/emergency types dropped** — Doctrine requires them, schema omits them
13. **Agent registry has filesystem baggage** — inbox_dir, queue_dir in DB design

### Operational Gaps
14. **SQLite threading model unspecified** — Python connections can't share across threads
15. **No WAL checkpointing strategy** — Database grows unbounded
16. **No schema migration framework** — schema_version column but no migration tool
17. **No compromised-agent containment** — No row-level security or least privilege
18. **No graceful degradation for audit failure** — What if audit service can't write?
19. **No idempotency in audit log itself** — Same event logged twice produces two records
20. **No broadcast recipient representation** — recipient enum excludes "all"

---

## Minimum Changes to Build

### Must Fix (Non-negotiable)
1. Rewrite DOCTRINE.md v2.0 aligned with database design
2. Enforce state transitions at DB level (CHECK constraints + transition table)
3. Add authorization policy (server-derived sender, allowed pairs matrix)
4. Add message_deliveries and inbox tables
5. Implement lease-based claims with timeouts
6. Wrap every state change + audit in single transaction
7. Fix audit design (remove double-hash, add triggers)
8. Define delivery semantics (at-least-once, idempotency keys)
9. Fix worker supervisor bugs
10. Add operational basics (backup, migration, monitoring)
11. Add security baseline (TLS, rate limits, replay protection)
12. Canonicalize content hash specification
13. Add adversarial/concurrency tests

---

## Approval

- [ ] Safe to build
- [x] **Needs fixes**
- [ ] Requires redesign

**Reasoning:** Architecture is sound. Issues are fixable within current frame. No full redesign needed, but listed minimum changes must be completed and re-audited before building.
