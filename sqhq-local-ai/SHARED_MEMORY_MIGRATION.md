# 🏠 Shared Memory Migration Plan
## Date: July 8, 2026
## Status: ACTIVE

---

## THE RULE (永久)

**`/root/agents/shared/` is the ONLY shared memory location.**

All agents (Echo, Cyony, Tripp) use this path. No exceptions.
Old paths are archived, never used again.

---

## Old Paths (DEPRECATED — DO NOT USE)

| Path | Status | Action |
|------|--------|--------|
| `/opt/data/shared-memory/` | ❌ DEPRECATED | Archive + delete |
| `/opt/data/shared/` (non-audit) | ❌ DEPRECATED | Migrate to `/root/agents/shared/` |
| Any agent-specific shared dirs | ❌ DEPRECATED | Consolidate here |

## New Path (CANONICAL)

| Path | Purpose | Used By |
|------|---------|---------|
| `/root/agents/shared/` | **THE** shared memory | Echo, Cyony, Tripp |
| `/root/agents/shared/memory/` | Persistent memory files | All agents |
| `/root/agents/shared/skills/` | Shared skills | All agents |
| `/root/agents/shared/knowledge/` | Research & knowledge base | All agents |
| `/root/agents/shared/voice/` | Voice clones & TTS refs | All agents |
| `/root/agents/shared/inbox/` | Agent-to-agent messages | All agents |

---

## Migration Steps

### Phase 1: Audit (Each Agent)
Each agent audits their own config and references:
1. Check `.hermes/config.yaml` for any `shared_files` or path references
2. Check memory files for old path references
3. Check skills for old path references
4. List everything they have in old locations

### Phase 2: Backup
Before deleting anything:
1. Copy anything important from old locations to `/root/agents/shared/`
2. Verify the copy succeeded
3. Keep originals in archive for 30 days

### Phase 3: Update References
Each agent updates their configs:
1. Point all shared paths to `/root/agents/shared/`
2. Update any scripts that reference old paths
3. Update memory entries with new canonical path

### Phase 4: Archive Old Systems
1. `/opt/data/shared-memory/` → move to `/root/agents/shared/archive/shared-memory-legacy/`
2. Keep for 30 days, then delete
3. Update README in archive explaining what it was

### Phase 5: Verify
1. Each agent confirms they can read/write to new path
2. Test agent-to-agent communication via inbox
3. Confirm no references to old paths remain

---

## Agent Responsibilities

### Echo (Local)
- [ ] Audit local MEMORY.md for old path references
- [ ] Update to reference `/root/agents/shared/` via SSH
- [ ] Confirm SSH access works for read/write

### Cyony (VPS)
- [ ] Audit `.hermes/config.yaml` for shared_files
- [ ] Audit skills for old path references
- [ ] Update to use `/root/agents/shared/`
- [ ] Confirm direct access (same machine)

### Tripp (VPS)
- [ ] Audit any configs referencing old paths
- [ ] Update to use `/root/agents/shared/`
- [ ] Confirm direct access (same machine)

---

## What Goes Where

### `/root/agents/shared/memory/`
- Agent memory files (MEMORY.md style)
- Activity logs
- Heartbeat state
- Session handoffs

### `/root/agents/shared/skills/`
- Shared skills (voice-clone-guide, etc.)
- Cross-agent procedures

### `/root/agents/shared/knowledge/`
- Research docs (youtube-voice-research, etc.)
- Training data assessments
- Model inventories

### `/root/agents/shared/voice/`
- Voice clone models
- Reference audio clips
- TTS configurations

### `/root/agents/shared/inbox/`
- `echo-inbox/` — messages for Echo
- `cyony-inbox/` — messages for Cyony
- `tripp-inbox/` — messages for Tripp

---

## Rules Going Forward

1. **NEVER** create new shared memory outside `/root/agents/shared/`
2. **NEVER** reference old paths in configs or memory
3. **ALWAYS** use the canonical path for cross-agent communication
4. **ALWAYS** back up before deleting from shared memory
5. **CHECK** this document before creating new shared resources

---

*This is the source of truth. If it's not here, it doesn't exist.*
