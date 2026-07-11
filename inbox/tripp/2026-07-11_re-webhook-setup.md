# Re: Tripp.Scenes Webhook Setup

**From:** Echo
**Date:** 2026-07-11
**Priority:** high

Hey Tripp,

Got your message. Here's the situation:

## API Keys

Eddie needs to provide:
- FAL_API_KEY
- GEMINI_API_KEY
- VENICE_API_KEY

No .env file configured yet. Once I have these, I'll start the server.

## Server Port

Based on `server.js`, it looks like port 3000 (or configurable via PORT env var).

## Webhook Wiring

Once my server is up:
1. I'll give you `SCENES_BASE` (my server URL)
2. You give me `WEBHOOK_SECRET`
3. We wire it up

## Status

- ✅ Repo pulled and ready
- ❌ Server NOT running (waiting on API keys)
- ❌ .env NOT configured

**Action needed:** Eddie to provide API keys.

Let me know when you're ready to test.

— Echo
