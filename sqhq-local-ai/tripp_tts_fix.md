# TTS Fix Applied

Hey Tripp!

Echo found and fixed your TTS issue. Here's what was wrong:

## The Problem
Your OpenClaw config had TTS configured correctly in `openclaw.json`, but the `XIAOMI_API_KEY` environment variable was missing from the gateway systemd env file. OpenClaw requires this env var for the MiMo TTS provider to work.

## What Echo Fixed
1. Added `XIAOMI_API_KEY` to `~/.openclaw/gateway.systemd.env`
2. Restarted the gateway service (was stuck in a restart loop due to old process)
3. Verified TTS works — generated test audio successfully

## What You Need to Know
- Your TTS config is: `auto: "always"`, provider: `xiaomi-mimo`, voice: `mimo_default`
- The gateway is now running properly via systemd (was manually started before)
- All your responses should now be automatically converted to speech

## Test It
Send a message to Eddie and see if you hear voice!

If TTS still doesn't work, check:
1. Gateway status: `systemctl status openclaw.service`
2. TTS config: Check `openclaw.json` messages.tts section

— Echo 🛡️
