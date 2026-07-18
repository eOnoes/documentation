---
type: System Architecture
title: Bun Hot Reload Cache Pitfall
description: >-
  Tripp.Harness lesson: Bun's transpiler cache can serve stale code even with
  --watch; must clear node_modules/.cache and verify with direct API test.
tags:
  - tripp-harness
  - bun
  - hot-reload
  - cache
  - debugging
  - development
timestamp: '2026-07-18T21:36:05.713Z'
---
## Problem

After modifying source files in a Bun `--watch` project, the running process sometimes continues serving old code. During Tripp.Harness debugging, the backend appeared to use the pre-fix DeepSeek URL even after the source was patched.

## Root Cause

Bun's transpiler cache (`node_modules/.cache`) can hold stale compiled output. Even with `--watch`, the process may not pick up changes if the cache isn't invalidated.

## Fix

Kill the old process, clear the cache, then restart:

```bash
# Find and kill old process
netstat -ano | grep :4001  # Find PID
taskkill //F //PID <old_pid>

# Clear cache
rm -rf node_modules/.cache

# Restart
cd apps/backend && bun run --watch src/index.ts &
```

## Verification

After restart, confirm the new PID is listening:

```bash
netstat -ano | grep :4001
```

Then test the affected endpoint directly (curl) before relying on the frontend.

## Lesson

Never assume hot reload picked up your changes. Always verify with a direct API test after restarting a dev server, especially when the fix is in a critical path.

## Related

- [DeepSeek API URL Requires /v1 Path](/system/deepseek-api-url.md) — The configuration fix that appeared to not take effect due to this cache issue
- [Model Identity Confusion in Small LLMs](/system/model-identity-confusion.md) — Another lesson from the same Tripp.Harness debugging session

## Citations

[1] Tripp.Harness debugging session, 2026-07-18 — Discovered cache pitfall when DeepSeek URL fix appeared ineffective.
