---
type: System Architecture
title: DeepSeek API URL Requires /v1 Path
description: >-
  Tripp.Harness lesson: DeepSeek's API base URL must include /v1 prefix or
  requests return 401 Unauthorized.
tags:
  - tripp-harness
  - deepseek
  - api
  - configuration
  - debugging
timestamp: '2026-07-18T21:36:09.882Z'
---
## Problem

DeepSeek's API base URL is `https://api.deepseek.com`, but the chat completions endpoint requires the `/v1` prefix: `https://api.deepseek.com/v1/chat/completions`. Without `/v1`, requests return 401 Unauthorized even with a valid API key — making it look like an auth problem when it's actually a routing problem.

## Root Cause

The OpenAI-compatible adapter concatenates `${baseUrl}/chat/completions`. If baseUrl is `https://api.deepseek.com`, the final URL is `https://api.deepseek.com/chat/completions` — which doesn't exist on DeepSeek's servers. The correct baseUrl is `https://api.deepseek.com/v1`.

## Verification Method

Direct curl test confirms the correct URL:

```bash
curl https://api.deepseek.com/v1/chat/completions \
  -H "Authorization: Bearer $KEY" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"test"}]}'
```

Returns 200 OK with valid key and `/v1` in path.

## Configuration Comparison

| System | Base URL | Status |
|--------|----------|--------|
| **Hermes** (config.yaml) | `https://api.deepseek.com/v1` | ✅ Correct |
| **Tripp.Harness** (initial) | `https://api.deepseek.com` | ❌ Wrong — caused 401 errors |

Always cross-reference working configurations when debugging API auth issues.

## Lesson

When an OpenAI-compatible provider returns 401 with a valid key, check the URL path before assuming the key is wrong. Some providers need `/v1` in the base URL, others don't.

## Related

- [Model Identity Confusion in Small LLMs](/system/model-identity-confusion.md) — Another DeepSeek lesson from the same debugging session (identity anchoring pattern)
- [Local AI Models](/system/local-models.md) — DeepSeek models available via cloud routing

## Citations

[1] Tripp.Harness debugging session, 2026-07-18 — Discovered URL routing issue during API integration.

# Related

- [Bun Hot Reload Cache Pitfall](/system/bun-cache-pitfall.md) — Cache invalidation issue discovered when this URL fix appeared to not take effect
- [Model Identity Confusion in Small LLMs](/system/model-identity-confusion.md) — Another DeepSeek lesson from the same debugging session (identity anchoring pattern)
- [Local AI Models](/system/local-models.md) — DeepSeek models available via cloud routing
