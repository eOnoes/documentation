---
type: System Architecture
title: Local AI Models
description: >-
  Eddie's local LLM setup: Bonsai 27B primary, Qwen 2.5 3B backup, Fish Speech
  TTS — with machine specs, file locations, and run commands.
tags:
  - llm
  - local-inference
  - bonsai
  - llama-cpp
timestamp: '2026-07-17T20:34:25.940Z'
---
Eddie runs local LLMs on two machines. After extensive benchmarking, all other models were removed and the setup consolidated to TWO models plus TTS.

## Model Inventory

| Model | Quant | Size | Purpose |
|-------|-------|------|---------|
| **Bonsai 27B** | Q2_0 (Ternary) | 6.7GB | Primary model — text, vision, thinking, tool calling |
| **Qwen 2.5 3B** | Q4_K_M | 1.8GB | Fast backup — quick tasks, 17.2 tok/s |
| **Fish Speech** | S2-Pro NF4 | remote | TTS only — voice synthesis at 100.72.250.65:8880 |

### Deleted Models
All of the following were benchmarked and removed (Bonsai replaced them all):
- Nemotron 4B, Nemotron 9B
- Gemma4 Uncensored
- Llama 3.2 3B
- Ornith 9B
- All local Ollama models (only cloud models remain in Ollama now)

## Machine Specs

### PC (Primary)
- **GPU:** NVIDIA RTX 4070 12GB VRAM
- **RAM:** 64GB DDR5
- **CPU:** AMD Ryzen 9 7900X
- **OS:** Windows 10/11
- **Username:** eMitchell109

### Laptop (Secondary)
- **GPU:** AMD Radeon RX 6800M 12GB VRAM
- **RAM:** 16GB DDR5
- **CPU:** AMD Ryzen 9 6900HX
- **OS:** Windows 11
- **Username:** Emitc (NOT eMitchell109)
- **Tailscale IP:** 100.119.162.99

## File Locations

Both machines mirror this structure:

```
D:\models\
├── bonsai\
│   ├── Ternary-Bonsai-27B-Q2_0.gguf          (6.7GB — main model)
│   └── Ternary-Bonsai-27B-mmproj-Q8_0.gguf   (629MB — vision projector)
├── qwen25-3b\
│   └── Qwen2.5-3B-Instruct-Q4_K_M.gguf       (1.8GB — fast backup)
└── moss-tts\                                   (MOSS TTS — legacy, not primary)
```

## Llama.cpp Binaries

**CRITICAL:** Standard llama.cpp CANNOT run Bonsai's ternary quantization. You MUST use PrismML builds for Bonsai.

| Machine | Binary | Path | Use For |
|---------|--------|------|---------|
| **PC** | CUDA build | `D:\llama-cuda\llama-server.exe` | All standard models + Bonsai |
| **Laptop** | HIP build | `C:\Users\Emitc\llama-hip\llama-server.exe` | Standard models (Qwen, etc.) |
| **Laptop** | PrismML Vulkan | `C:\Users\Emitc\prism-vulkan\llama-server.exe` | **Bonsai ONLY** (ternary quant) |

On PC, the CUDA build at `D:\llama-cuda\` works for Bonsai because PrismML merged ternary support into their CUDA fork. On laptop, you must use the Vulkan build at `C:\Users\Emitc\prism-vulkan\`.

## How to Run Bonsai

### Text only
```bash
# PC
D:\llama-cuda\llama-server.exe -m D:\models\bonsai\Ternary-Bonsai-27B-Q2_0.gguf -c 4096 --host 0.0.0.0 --port 8080

# Laptop (MUST use PrismML Vulkan build)
C:\Users\Emitc\prism-vulkan\llama-server.exe -m D:\models\bonsai\Ternary-Bonsai-27B-Q2_0.gguf -c 4096 --host 0.0.0.0 --port 8080
```

### Text + Vision (image input)
```bash
# Add --mmproj flag
D:\llama-cuda\llama-server.exe -m D:\models\bonsai\Ternary-Bonsai-27B-Q2_0.gguf --mmproj D:\models\bonsai\Ternary-Bonsai-27B-mmproj-Q8_0.gguf -c 4096 --host 0.0.0.0 --port 8080
```

### Performance flags
- `-ngl 0` = CPU only (no GPU offload) — use if GPU is needed for other tasks
- `-ngl 99` = full GPU offload (default, fastest)
- `-c 4096` = context size (adjust based on VRAM — 2048 is safe, 8192 needs headroom)
- `--host 0.0.0.0` = allow network access (for Hermes/Tailscale)

## Performance Benchmarks

| Machine | Model | Speed | Notes |
|---------|-------|-------|-------|
| Laptop (Vulkan) | Bonsai 27B | **20.36 tok/s** | PrismML Vulkan build |
| PC (CUDA) | Bonsai 27B | ~50+ tok/s (est.) | Not officially benchmarked yet |
| Laptop | Qwen 2.5 3B | **17.2 tok/s** | Standard HIP build |
| Laptop | Llama 3.2 3B | 15.2 tok/s | Deleted — weak reasoning |
| Laptop | Nemotron 4B | 10.3 tok/s | Deleted — outclassed |
| Laptop | Gemma4 Uncensored | 9.5 tok/s | Deleted — no vision |
| Laptop | Nemotron 9B | 3.7 tok/s | Deleted — too slow |
| Laptop | Ornith 9B | 3.5 tok/s | Deleted — too slow |

## Bonsai 27B Capabilities

- **Text generation** — full 27B-class reasoning at 1.58 bits/weight
- **Vision** — multimodal via mmproj file (screenshots, documents, camera)
- **Thinking mode** — toggle via `thinking_budget_tokens` (0=off, -1=unlimited)
- **Tool calling** — OpenAI-compatible API with function calling
- **Context** — up to 262,144 tokens
- **License** — Apache 2.0

## MANDATORY RULE: Unload When Done

**When any agent finishes using a local model, they MUST kill the llama-server process to free GPU VRAM.**

Eddie's GPU has 12GB VRAM. Leaving Bonsai loaded (~7.3GB with mmproj) blocks other GPU tasks (Fish Speech, Ollama, etc.). Always clean up.

```bash
# Windows — kill all llama-server instances
taskkill /F /IM llama-server.exe

# Or kill by port
netstat -ano | findstr :8080
taskkill /F /PID <PID>
```

## Ollama (Cloud Models Only)

After cleanup, only cloud models remain in Ollama:
- qwen3.5:397b-cloud, kimi-k2.6:cloud, deepseek-v4-pro:cloud, etc.
- No local Ollama models — Bonsai replaced them all

## SSH Access (for agents)

```bash
# Laptop via Tailscale
ssh laptop-echo
# or
ssh Emitc@100.119.162.99

# PC — local, no SSH needed
# Path: C:\Users\eMitchell109\
```

## Version Control

Both machines should stay in sync. When updating models or binaries:
1. Download on PC first (faster internet)
2. SCP to laptop: `scp <file> laptop-echo:"D:/models/bonsai/"`
3. Verify both machines have matching files

## Agent Decision Tree

When an agent needs local inference:

1. Is it a simple/fast task? → Use **Qwen 2.5 3B** (17.2 tok/s)
2. Is it complex/reasoning/vision? → Use **Bonsai 27B** (20+ tok/s)
3. Is it TTS/voice? → Use **Fish Speech** at 100.72.250.65:8880
4. After task is done → **KILL llama-server** immediately

## Related

- [Deep Knowledge System](/system/deep-architecture.md) — Multi-agent architecture that uses these local models
- [Eddie](/personas/eddie.md) — User who owns and operates this setup
- [Muncher MCP Package Versions](/system/muncher-versions.md) — Local token munchers that preprocess before cloud inference
