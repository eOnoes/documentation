# Codex Round 2 Audit: Tripp.System v2.0

**Auditor:** Codex (GPT-5.6)
**Date:** 2026-07-11
**Previous Rating:** 2/10
**New Rating:** 5/10
**Tokens Used:** 63,597

---

## Executive Summary

The redesign addresses the core architectural problems (filesystem queues → database, no schema → JSON Schema, no auth → Argon2, forgeable chains → validated chains). However, it introduces new issues: the Doctrine still describes the old filesystem system, state transitions aren't enforced at the database level, audit immutability is not actually enforced, chain validation is not cryptographic despite being called that, authentication exists without authorization, and there are no idempotency or delivery guarantees.

---

## Critical Issues Remaining (10)

### 1. Doctrine contradicts redesign
- Doctrine v1.0 mandates filesystem queues, JSONL audit, agent-modifiable messages
- Redesign v2.0 uses database, hash-chained audit, immutable messages
- Constitution cannot contradict implementation

### 2. State transitions not enforced
- `state TEXT` permits arbitrary values and transitions
- No compare-and-swap, transition table, or constraint
- Delivered → pending is possible

### 3. Chain validation not cryptographic
- Only inspects ordinary fields controlled by submitter
- `chain_history` absent from JSON Schema
- Initial expected actor is tautological (checks against submitted sender)
- Should be server-generated, not client-submitted

### 4. Authentication without authorization
- API key proves identity, not permissions
- No authorization matrix for sender/recipient pairs
- No message type restrictions per role
- Gateway must derive `sender` from auth context

### 5. Audit immutability not enforced
- Nothing prevents UPDATE, DELETE, or chain recomputation
- Concurrent writers can fork the hash chain
- Needs SQLite triggers, dedicated write role, external anchoring

### 6. No idempotency or delivery guarantees
- UUID prevents collision, not duplicate submission
- No client idempotency keys
- No deduplication, no outbox pattern
- Delivery semantics undefined

### 7. Broadcast recovery not implemented
- No `message_deliveries` table for per-recipient state
- Claims independent delivery but schema doesn't support it

### 8. Schema lacks constraints
- Foreign keys missing for sender, recipient, message_id
- No CHECK constraints
- Boolean/timestamp formats not enforced
- `content_hash` conflicts (client required, lifecycle says server computes)

### 9. Worker correctness issues
- Backoff uses `sleep` (blocks worker)
- No lease/fencing tokens for claims
- No cancellation, timeout, or lease renewal
- No circuit breaker for failing agents
- Dead-letter replay unspecified

### 10. No backup, migration, or operational plans
- No backup strategy or recovery procedures
- No migration framework
- No cutover strategy
- 5-day schedule unrealistic

---

## New Issues Found

### Security (9 issues)
- No TLS requirements
- No rate limiting, body-size limits, request timeouts
- No replay protection
- No encryption-at-rest
- No threat model or trust boundaries

### Audit Defects (5 issues)
- Hash implementation inconsistent
- Concurrent append unsafe
- Audit insertion separate from business operation

### Operations (8 issues)
- SQLite single point of failure
- No WAL checkpointing strategy
- No monitoring metrics defined
- No alerts or runbooks

### Governance (6 issues)
- Previous audit request missing (traceability broken)
- Codex has builder + auditor conflict
- 7-day cleanup lacks human confirmation
- No notification/escalation mechanism

---

## What Must Be Added Before Build

1. Normative state-transition table with guarded SQL
2. Transaction boundaries for every state change
3. Leased claims with fencing tokens
4. At-least-once semantics with idempotency
5. Transactional outbox or API-only delivery
6. Per-recipient delivery model for broadcasts
7. Authorization policy with server-derived identity
8. Externally anchored audit design
9. Complete v2 Doctrine aligned with database
10. Backup, restore, migration, monitoring, alerting
11. Security requirements (TLS, credentials, replay, rate limits)
12. Adversarial acceptance tests

---

## Production Soundness

**Good for:**
- Single trusted host
- Low-to-moderate volume
- Small fixed agent set
- At-least-once with idempotent consumers

**Not sufficient for:**
- Multi-host active-active
- High availability
- Untrusted agents
- High throughput
- Exactly-once semantics

---

## Approval

- [ ] Safe to build
- [x] **Needs fixes before build**
- [ ] Requires redesign
