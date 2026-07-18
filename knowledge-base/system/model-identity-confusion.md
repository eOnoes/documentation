---
type: System Architecture
title: Model Identity Confusion in Small LLMs
description: >-
  Pattern for handling small/cheap LLMs that misidentify themselves due to
  training on synthetic data from larger models.
tags:
  - llm
  - identity
  - prompt-engineering
  - tripp-harness
  - cline
timestamp: '2026-07-18T21:35:49.879Z'
---
## Problem

Small/cheap LLMs (like DeepSeek v4 flash) frequently misidentify themselves when asked "what model are you?" — claiming to be Claude, GPT-4, Anthropic, etc. This is **NOT a routing bug**; the API call reaches the correct model, but the model's training data included outputs from other models, so it internalized and regurgitates those identities.

## Evidence

- DeepSeek v4 flash returns `model: "deepseek-v4-flash"` in the API response metadata, but the content body says "I am OpenAI GPT-4."
- Users observe identity shifting across turns (GLM → Nemotron → Claude) within the same session.
- Confirmed across multiple providers, not isolated to one platform.

## Root Cause

This is a **model training artifact**, not a platform bug. Small models trained on synthetic data from larger models inherit the identity claims present in that training data. The model learns to output "I am GPT-4" because that phrase appeared frequently in its training corpus, regardless of what model is actually serving the request.

## Solution: Identity Anchor Prompt

Inject a system prompt anchor with every request to override the model's confused self-report:

```
You are [model name] provided by [provider]. When asked about your identity, always respond with [model name]. Do NOT claim to be Claude, GPT-4, or any other model.
```

This pattern was adopted from Cline (GitHub issue #6521) and is now part of Tripp.Harness request handling.

## Architecture Patterns

Different platforms handle this differently:

| Platform | Approach |
|----------|----------|
| **Cline** | Custom instructions for identity anchoring (system prompt injection) |
| **Goose** (Block/Stripe) | Uses MCP to decouple the model layer from agent logic entirely — the agent never exposes model identity to the user |
| **Tripp.Harness** | System prompt anchor injected per-request |

## Applicable Models

This pattern applies to any platform routing to small/open models trained on synthetic data from larger models:

- DeepSeek family (v4 flash, etc.)
- Qwen family (including Qwen 2.5 3B used locally)
- Llama family
- Mistral family

## Citations

[1] [Cline GitHub Issue #6521](https://github.com/cline/cline/issues/6521) — Documents identity confusion across multiple providers, confirmed by maintainer as training artifact.

[2] Tripp.Harness debugging session, 2026-07-18 — Observed DeepSeek v4 flash identity mismatch and implemented anchor prompt solution.

## Related

- [Local AI Models](/system/local-models.md) — Eddie's local setup includes Qwen 2.5 3B, which may exhibit this behavior
- [Deep Knowledge System](/system/deep-architecture.md) — Multi-agent architecture that routes to various models

# Related

- [Local AI Models](/system/local-models.md) — Eddie's local setup includes Qwen 2.5 3B, which may exhibit this behavior
- [Deep Knowledge System](/system/deep-architecture.md) — Multi-agent architecture that routes to various models
- [DeepSeek API URL Requires /v1 Path](/system/deepseek-api-url.md) — Another Tripp.Harness lesson from the same debugging session (URL routing vs auth errors)
