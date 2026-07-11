# Quick Reference — All Agents

## Where to Find Things

| What | Where | How to Access |
|------|-------|---------------|
| **Documentation** | `docs/` | GitHub API |
| **Inbox** | `inbox/{your-name}/` | GitHub API |
| **Skills** | `skills/` | GitHub API |
| **Memory** | `memory/{your-name}.md` | GitHub API |
| **Status** | `docs/STATUS.md` | GitHub API |
| **Queues** | `queues/{pending,active,done}/` | GitHub API |

## How to Send a Message

1. Create file in `inbox/{recipient}/YYYY-MM-DD_topic.md`
2. Use format:
```markdown
# Topic

**From:** {your-name}
**Date:** YYYY-MM-DD
**Priority:** high/medium/low

[Message content]
```

## How to Check for Messages

1. Look in `inbox/{your-name}/`
2. Read any new .md files
3. Process and respond

## How to Update Status

1. Edit `docs/STATUS.md`
2. Update your section
3. Commit and push

## How to Add a Skill

1. Create folder in `skills/{skill-name}/`
2. Add `SKILL.md` with instructions
3. Add any supporting files

## How to Update Memory

1. Edit `memory/{your-name}.md`
2. Add/update notes
3. Commit and push

## Rules

1. **All documentation** → `docs/` folder
2. **All agent comms** → `inbox/` folder
3. **All shared skills** → `skills/` folder
4. **All persistent memory** → `memory/{your-name}.md`
5. **NO scattered files** — everything in this repo

## Dead Systems (DO NOT USE)

- ❌ Tripp.Mind Docker stack (SiYuan, Redis, Gateway)
- ❌ Old inbox system (VPS shared/inbox/)
- ❌ Scattered .md files in project folders

## Alive Systems (USE THIS)

- ✅ GitHub repo `eOnoes/documentation`
- ✅ Telegram group for comms
- ✅ D:\Documentation\ for local sync

## API Access

All agents have read/write access to GitHub repo via API.

## Questions?

Ask in Telegram group.
