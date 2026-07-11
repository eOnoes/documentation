# Task Queues

Task coordination system.

## Structure

```
queues/
├── pending/      ← Tasks waiting
├── active/       ← Tasks in progress
├── done/         ← Completed tasks
└── README.md
```

## Task Format

```markdown
# Task Title

**Status:** pending/active/done
**Assigned to:** [agent]
**Created:** YYYY-MM-DD

[Task description]
```
