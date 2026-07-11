# OpenClaw Common Problems Wiki

## 1. Reasoning/Thinking Content Leaking to Users

### Problem
Agent outputs internal reasoning, planning, and thought process before the final answer. Users see things like:
- "Let me think about this..."
- "My plan is to first check X, then Y..."
- Internal chain-of-thought text
- Tool narration ("I will now search for...")

### Root Cause
- **Model behavior**: Some models (especially reasoning models like Kimi K2.5, DeepSeek Think, MiMo Pro) output reasoning as plain text, not in a hidden `reasoning` field
- **OpenClaw bug**: Even with `reasoning: false` in config, the model may still output reasoning text that gets included in the response
- **Streaming leak**: During streaming, if no standard content is generated, thinking/reasoning text becomes the fallback content

### Affected Models
- `xiaomi-mimo/mimo-v2.5-pro` (reasoning: true)
- `xiaomi/mimo-v2-pro` (reasoning: true)
- `xiaomi/mimo-v2-omni` (reasoning: true)
- `kimi-k2.5` and other reasoning models

### Solutions

#### Option 1: Switch to Non-Reasoning Model
```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "xiaomi-mimo/mimo-v2.5",
        "fallbacks": ["deepseek/deepseek-v4-flash"]
      }
    }
  }
}
```
Use models with `"reasoning": false` in the config.

#### Option 2: System Prompt Override
Add to agent's system prompt or `AGENTS.md`:
```
IMPORTANT: Do NOT show your reasoning process, planning, or internal thoughts.
Only output the final answer. Never start responses with "Let me think..." or "My plan is..."
Just give the answer directly.
```

#### Option 3: OpenClaw Config (when available)
```json
{
  "agents": {
    "defaults": {
      "thinkingDefault": "off"
    }
  }
}
```

#### Option 4: Update OpenClaw
This was a known bug (GitHub #40736) that has been fixed in newer versions. Update OpenClaw:
```bash
npm update -g openclaw
# or
openclaw doctor --fix
```

### Quick Fix for TTS
If TTS is reading the reasoning out loud, the issue is that the reasoning text is being sent to TTS. Solutions:
1. Use a non-reasoning model
2. Add system prompt instruction to only output final answer
3. Update OpenClaw to latest version

---

## 2. TTS Not Working (Xiaomi MiMo)

### Problem
TTS configured but no audio output, or "Invalid API Key" error.

### Root Cause
`XIAOMI_API_KEY` environment variable not set in gateway systemd env.

### Fix
```bash
# Add to gateway systemd env
echo 'XIAOMI_API_KEY=your-key-here' >> ~/.openclaw/gateway.systemd.env

# Restart gateway
systemctl restart openclaw.service
```

### Verify
```bash
curl -s http://localhost:18789/health
# Should return: {"ok":true,"status":"live"}
```

---

## 3. Gateway Service Restart Loop

### Problem
OpenClaw gateway keeps restarting (systemctl shows thousands of restarts).

### Root Cause
Another gateway process already running on the port, or config error.

### Fix
```bash
# Find and kill old process
pkill -f 'openclaw.*gateway'
sleep 2

# Restart via systemd
systemctl restart openclaw.service

# Verify
systemctl status openclaw.service
```

---

## 4. Voice Clone TTS Setup

### Problem
Want to use a cloned voice instead of built-in voices.

### Solution
Use Local CLI provider with a custom script:

```json
{
  "messages": {
    "tts": {
      "auto": "always",
      "provider": "tts-local-cli",
      "providers": {
        "tts-local-cli": {
          "command": "/usr/bin/python3",
          "args": ["/path/to/voice_clone.py", "{{OutputPath}}"],
          "outputFormat": "mp3",
          "timeoutMs": 120000
        }
      }
    }
  }
}
```

See `TRIPP_TTS_GUIDE.md` for full implementation details.

---

## 5. Shared Memory Permission Issues

### Problem
Agents can't read/write to shared memory directories.

### Root Cause
Docker container mount permissions or UID mismatch.

### Fix
```bash
# Fix permissions
chmod -R 777 /opt/data/shared/
chown -R hermes:hermes /opt/data/shared/

# For Docker containers, ensure mount is read-write
# Check docker-compose.yml for :rw suffix
```

---

## 6. Model Not Using Tools

### Problem
Agent doesn't use available tools (web search, file ops, etc.).

### Root Cause
Model doesn't support tool calling, or config missing.

### Fix
Ensure model has `"supportsTools": true` in config:
```json
{
  "models": {
    "providers": {
      "your-provider": {
        "models": [
          {
            "id": "your-model",
            "compat": {
              "supportsTools": true
            }
          }
        ]
      }
    }
  }
}
```

---

## Quick Reference

| Problem | Quick Fix |
|---------|-----------|
| Reasoning leaking | Switch to non-reasoning model or add system prompt |
| TTS not working | Set `XIAOMI_API_KEY` in gateway env |
| Gateway restart loop | Kill old process, restart systemd |
| Voice clone | Use Local CLI provider |
| Permission errors | chmod 777 + chown hermes |
| Tools not working | Check `supportsTools: true` |

---

*Last updated: 2026-07-08 by Echo*
