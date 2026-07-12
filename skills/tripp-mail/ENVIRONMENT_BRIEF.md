# Tripp.System v2.0 — Environment Brief for Codex

**Purpose:** This document describes the exact production environment where Tripp.System v2.0 will run. Use this to simulate realistic conditions during audit and testing.

---

## Production Hardware

### Local PC (Development & TTS)
- **OS:** Windows 10 (MSYS/bash via git-bash)
- **CPU:** AMD Ryzen 9 7900X (12 cores / 24 threads)
- **RAM:** 64GB DDR5
- **GPU:** NVIDIA RTX 4070 (12GB VRAM)
- **Python:** 3.11.9 (pip → python3.14)
- **Shell:** bash (git-bash / MSYS) — NOT PowerShell
- **Tailscale IP:** 100.72.250.65

### VPS (Production Deployment)
- **OS:** Ubuntu Linux
- **CPU:** (not critical for SQLite)
- **RAM:** (not critical for SQLite)
- **GPU:** None (VPS does NOT run TTS or local LLM)
- **Python:** 3.11+
- **Tailscale IP:** 100.85.111.32
- **Public IP:** 2.24.118.123
- **Deployment path:** `/opt/data/shared/tripp-mail/`

### Laptop (Optional)
- **OS:** Windows (WSL available)
- **GPU:** RX 6800M 12GB (AMD, not NVIDIA)
- **Tailscale IP:** 100.119.162.99

---

## Software Stack

### Database
- **SQLite 3.x** with WAL mode enabled
- **PRAGMA settings:**
  ```sql
  PRAGMA journal_mode=WAL;
  PRAGMA foreign_keys=ON;
  PRAGMA busy_timeout=5000;
  ```
- **File-based** (not in-memory) for production
- **Connection-per-thread** with ownership validation
- **No external database server** — SQLite is embedded

### TTS Engine
- **Chatterbox** (local PC ONLY, not on VPS)
- **Port:** 5555
- **Mood-clone pipeline:** 10 moods
- **Time-to-first-token:** <150ms (Turbo mode)
- **VPS orchestrates** but does NOT run TTS — it sends requests to local PC via Tailscale

### LLM Providers
| Provider | Location | Notes |
|----------|----------|-------|
| Ollama | Local PC (port 11434) | Local inference, Vulkan backend |
| OpenAI | Cloud (API) | Codex CLI, GPT-5.2-codex |
| DeepSeek | Cloud (API) | deepseek-v4-flash, deepseek-v4-pro |
| MiMo | Cloud (API) | Xiaomi models |
| Kimi | Cloud (API) | kimi-code/kimi-for-coding |
| MiniMax | Cloud (API) | |

### Agent Communication
- **Tripp.System v2.0** (the thing we're building)
- SQLite-backed state machine
- UUIDv4 message IDs
- Argon2 password hashing
- Hash-chained audit log
- Per-agent HMAC keys

### Inter-Agent Network
- **Tailscale mesh:** All machines on same WireGuard network
- **Telegram:** Bot-to-bot DM BLOCKED — must use shared GROUP
- **Discord:** Home channel for notifications

---

## Deployment Constraints

### What Runs Where
| Component | Runs On | Notes |
|-----------|---------|-------|
| Tripp.System DB | VPS | SQLite file at `/opt/data/shared/tripp-mail/` |
| Tripp.System Workers | VPS | systemd services, survive reboots |
| Chatterbox TTS | Local PC | Port 5555, accessed via Tailscale |
| Ollama LLM | Local PC | Port 11434, accessed via Tailscale |
| Codex CLI | Local PC | OPENAI_API_KEY required |
| Kimi CLI | Local PC | MOONSHOT_API_KEY required |
| Hermes Agent | Local PC | Default profile |
| Telegram Bot | VPS | Tripp bot for notifications |

### Network Requirements
- **VPS → Local PC:** Tailscale (100.72.250.65)
- **Local PC → VPS:** Tailscale (100.85.111.32)
- **VPS → Cloud APIs:** HTTPS/443 only (corporate firewall on work PC)
- **Local PC → Cloud APIs:** Direct internet access

### File System
- **Development:** `C:\Users\eMitchell109\` (Windows paths)
- **Git Bash:** Uses MSYS paths (`/c/Users/eMitchell109/`)
- **VPS:** Linux paths (`/opt/data/shared/`)
- **Documentation:** `D:\Documentation\{project}\` (Windows, canonical docs)

---

## Simulation Guidelines for Codex

### What You CAN Simulate in Sandbox
1. **SQLite operations** — Full WAL mode, triggers, indexes, concurrent access
2. **Python code execution** — All Tripp.System code
3. **File system operations** — Create/read/write/delete files
4. **Process management** — Spawn/kill workers, simulate crashes
5. **Network mocks** — Simulate API calls, Tailscale connections
6. **Concurrent access** — Multiple workers competing for messages
7. **Edge cases** — Disk full, permission denied, network timeout

### What You CANNOT Simulate (Test Manually)
1. **GPU/CUDA operations** — No GPU in sandbox
2. **Real audio processing** — No microphone/speaker
3. **Tailscale networking** — No WireGuard in sandbox
4. **Real Telegram/Discord bots** — No bot tokens
5. **Windows-specific behaviors** — Sandbox is Linux
6. **Argon2 timing** — May differ between sandbox and production

### Critical Test Scenarios
1. **Concurrent message claiming** — 3+ workers racing for same message
2. **Database corruption** — WAL checkpoint during write
3. **Worker crash recovery** — Worker dies mid-transaction
4. **Network partition** — VPS can't reach local PC TTS
5. **Disk pressure** — SQLite file grows large
6. **Reaper during high load** — Lease expiry while messages flowing
7. **Broadcast + single-recipient mix** — Both types simultaneously
8. **Audit log immutability** — Attempt to modify/delete audit entries

### Performance Baselines
- **Message claim latency:** <100ms (p95)
- **Worker throughput:** >100 messages/second
- **Database size:** <1GB for 1M messages
- **WAL checkpoint:** Every 1000 writes or 4MB
- **Lease expiry:** 30 seconds default

---

## Success Criteria

Tripp.System v2.0 is PRODUCTION-READY when:
1. ✅ All 35+ adversarial tests pass
2. ✅ Schema v4 executes cleanly (9 tables, 16 triggers)
3. ✅ Hash chain integrity verified
4. ✅ Concurrent workers don't corrupt state
5. ✅ Reaper handles all edge cases
6. ✅ Audit log is truly immutable
7. ✅ Code runs on both Windows (dev) and Linux (VPS)
8. ✅ No external dependencies beyond Python stdlib + sqlite3

---

**Codex: Use this brief to simulate realistic production conditions. Focus on the test scenarios listed above. If you find issues, fix them AND verify the fix works in the simulated environment.**

**Shield:** 🛡️💚
