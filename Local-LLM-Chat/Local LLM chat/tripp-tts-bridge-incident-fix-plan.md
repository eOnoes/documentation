# Trippcore TTS Bridge Incident and Fix Plan

Date: 2026-06-22

## Executive Summary

Cyony/Scout is on the cloud side, and her report that "the workers are down" is understandable, but the bridge itself is mostly alive.

The cloud path can reach the local Windows TTS worker through the existing private bridge. `/health` returns cleanly from:

- Eddie's Windows PC at `http://127.0.0.1:8788`
- Hostinger VPS through the reverse SSH tunnel
- VPS host bridge at `http://172.16.1.1:8879`
- Hermes/Cyony container through its local relay at `http://127.0.0.1:8788`

The real failure is provider runtime generation on the Windows worker. `/health` is green because it checks worker/config visibility, but actual `/v1/tts` generation fails for several Python-backed providers when they import libraries or load model files.

## Current Live Voice Status

| Voice alias | Provider | Status | Notes |
|---|---|---|---|
| `chloe` | Pocket TTS | Failing | Import/runtime pollution around Python packages. |
| `cosy_chloe` | CosyVoice3 | Working | Generated a successful MP3 during testing. |
| `index_chloe` | IndexTTS2 | Failing | Python dependency conflict around protobuf/tensorboard and possible `transformers` drift. |
| `dia_chloe` | Dia | Failing | Model loader cannot find expected `model.safetensors`. |
| `qwen_chloe` | Qwen3 | Disabled | Disabled intentionally to free VRAM for Dia experiments. |

## What Was Verified

### Local Windows Worker

`GET /health` on `http://127.0.0.1:8788` returned:

- `ok: true`
- voices: `chloe`, `cosy_chloe`, `index_chloe`, `dia_chloe`
- warnings: `[]`

This proves the Node worker process is running and the worker config loads.

### VPS Reverse Tunnel

The reverse SSH tunnel is running:

```text
Hostinger 127.0.0.1:8788 -> Eddie PC 127.0.0.1:8788
```

Hostinger can call the worker health endpoint through the tunnel.

### VPS Host Bridge

The host bridge is listening:

```text
172.16.1.1:8879 -> 127.0.0.1:8788
```

Health through `http://172.16.1.1:8879/health` returned cleanly.

### Hermes/Cyony Container

The container relay is present and the container can see the worker health endpoint through `http://127.0.0.1:8788/health`.

The container service is up, and helper scripts exist in `/opt/data/`.

## Important Cloud Helper Fix Already Applied

The cloud helper scripts were stale. They still advertised and called `qwen_chloe`, but the live worker no longer exposes `qwen_chloe`.

Updated behavior:

- Main helper now supports current live aliases:
  - `chloe`
  - `index_chloe`
  - `cosy_chloe`
  - `dia_chloe`
- Compatibility aliases were added:
  - `qwen`
  - `qwen_chloe`
- Those old Qwen aliases now route to `index_chloe` instead of calling a dead voice alias.

This removes one cloud-side failure mode, but `index_chloe` still needs local Windows Python/runtime repair before it can generate successfully.

## Actual Generation Test Results

Authenticated generation was tested locally against the Windows worker.

| Voice | Result | Approx. time | Finding |
|---|---:|---:|---|
| `chloe` | Failed | 2.6 sec | Pocket import failure. |
| `cosy_chloe` | Passed | 47.1 sec | MP3 generated successfully. |
| `index_chloe` | Failed | 17.9 sec | Python dependency conflict. |
| `dia_chloe` | Failed | 4.0 sec | Missing model file expected by Dia loader. |

## Failure Details

### Pocket TTS: `chloe`

Observed failure class:

```text
ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'
```

The Pocket command uses `uvx pocket-tts generate ...`.

The log shows Pocket is importing pieces from:

```text
C:\Users\eMitchell109\AppData\Local\hermes\hermes-agent\venv\Lib\site-packages
```

That indicates Python environment contamination. The child process launched by the worker is inheriting Python-related environment state from the Hermes/Codex process or shell, so `uvx` is not getting a clean isolated Python package environment.

Expected fix:

- Sanitize Python-related environment variables when spawning provider child processes.
- Remove or override inherited values such as:
  - `PYTHONPATH`
  - `PYTHONHOME`
  - `VIRTUAL_ENV`
  - `CONDA_PREFIX`
  - possibly user-site package leakage
- Rerun Pocket generation.
- If still broken, clear/rebuild the `uvx` cache for `pocket-tts`.

### IndexTTS2: `index_chloe`

Observed failure class:

```text
TypeError: Descriptors cannot be created directly.
```

The stack goes through TensorBoard protobuf imports.

The IndexTTS2 runtime currently reports:

```text
transformers=4.52.1
torch=2.8.0+cu128
numpy=1.26.2
```

There were also earlier visible errors/warnings around `GenerationMixin`, which usually means the installed `transformers` version is too new for that model code path.

Expected fix:

- Sanitize inherited Python env for the IndexTTS2 subprocess.
- Pin/reinstall compatible versions inside:

```text
D:\Trippcore\repos\index-tts\.venv
```

Likely targets:

```text
protobuf==3.20.*
transformers<4.50
```

Do not install these globally. Keep them inside the IndexTTS2 venv.

After repair:

- Run direct wrapper smoke.
- Run worker `/v1/tts` smoke with `voice=index_chloe`.
- Confirm generated MP3 can be fetched through `/v1/audio/...`.

### Dia: `dia_chloe`

Observed failure class:

```text
FileNotFoundError: D:\TrippCore\models\dia\Dia-1.6B-0626\model.safetensors
```

This is different from the Pocket/Index dependency pollution. Dia is looking for a model file that does not exist where the loader expects it.

Expected fix:

- Inspect `D:\Trippcore\models\dia\Dia-1.6B-0626`.
- Confirm whether model weights are:
  - missing,
  - named differently,
  - stored under a nested snapshot directory,
  - partially downloaded,
  - or incompatible with the installed Dia repo loader.
- Either:
  - move/symlink/copy the expected file into place if the correct weights already exist, or
  - redownload the Dia model into the expected local layout.

Also check Dia runtime versions:

```text
D:\Trippcore\runtimes\dia
transformers=5.12.1
torch=2.6.0+cu126
numpy=2.4.6
```

`transformers 5.x` and `numpy 2.4.x` may be too new for some model stacks, but the immediate hard failure is missing `model.safetensors`.

### CosyVoice3: `cosy_chloe`

CosyVoice3 is currently the only non-Pocket experimental provider that generated successfully during testing.

Observed:

- MP3 generated successfully.
- No bridge/auth problem.
- It is currently the safest direct-mood voice while Pocket/Index/Dia are repaired.

## Most Likely Root Cause

There are two root causes:

1. Python environment contamination from the parent process into provider subprocesses.
2. Dia model directory does not match what the Dia loader expects.

The contamination issue explains why multiple providers suddenly broke after a restart or install. Provider subprocesses can accidentally import packages from the wrong Python environment if variables like `PYTHONPATH` or `VIRTUAL_ENV` leak into them.

## Recommended Fix Order

### 1. Stabilize the worker spawn environment

Add a shared helper in the Node worker for provider subprocess environment construction.

Behavior:

- Start from `process.env`.
- Remove Python environment contamination variables.
- Preserve non-secret operational variables needed for model cache paths if configured.
- Set safe defaults where needed.

Suggested variables to remove for Python provider child processes:

```text
PYTHONPATH
PYTHONHOME
VIRTUAL_ENV
CONDA_PREFIX
CONDA_DEFAULT_ENV
PYTHONSTARTUP
PYTHONUSERBASE
```

Optional additional guard:

```text
PYTHONNOUSERSITE=1
```

Be careful with `PYTHONNOUSERSITE`: it can help isolation, but if any provider depends on user-site packages, it may reveal more missing packages. That is usually good, because each provider should own its runtime.

Apply this to:

- Pocket TTS subprocess
- CosyVoice3 subprocess
- IndexTTS2 subprocess
- Dia subprocess
- Qwen if re-enabled later

### 2. Fix Pocket

After spawn env cleanup:

- Rerun `chloe` generation.
- If still failing, rebuild the `uvx` cache for `pocket-tts`.
- Keep Pocket on CPU unless CUDA support is intentionally revisited.

### 3. Fix IndexTTS2

Inside:

```text
D:\Trippcore\repos\index-tts\.venv
```

Pin likely compatibility packages:

```text
protobuf==3.20.*
transformers<4.50
```

Then run:

- direct wrapper smoke,
- worker `/v1/tts` smoke,
- cloud/container helper smoke.

### 4. Fix Dia model layout

Inspect/redownload:

```text
D:\Trippcore\models\dia\Dia-1.6B-0626
```

Make sure the loader can find the expected model weight file:

```text
model.safetensors
```

Then run Dia direct and worker-level smoke.

### 5. Cloud regression smoke

From inside the Hermes/Cyony container, smoke:

- `chloe`
- `cosy_chloe`
- `index_chloe`
- `dia_chloe`

Use short text. Confirm audio file fetch works, not just `/health`.

## Temporary Operational Recommendation

Until repairs are complete:

- Use `cosy_chloe` for mood/instruction-capable voice generation.
- Avoid `qwen_chloe`; it is disabled.
- Avoid `index_chloe` until the IndexTTS2 runtime is repaired.
- Avoid `dia_chloe` until the Dia model layout is repaired.
- Do not trust `/health` alone as provider readiness.

## Better Health Checks To Add

The current `/health` endpoint is useful but shallow. Add a second endpoint or script that reports provider generation readiness.

Recommended:

```text
GET /health
```

Keep as lightweight config/process health.

Add:

```text
GET /health/providers
```

or:

```text
npm run smoke:providers
```

This should check:

- provider runtime path exists,
- required model files exist,
- critical Python packages import,
- optional tiny generation smoke if explicitly requested.

The provider readiness report should distinguish:

- configured,
- importable,
- model files present,
- generation verified.

That would prevent this exact situation where `/health` is green while providers fail at generation time.

## Safety Notes

- Do not print, log, reveal, or commit `TRIPP_TTS_SHARED_SECRET`.
- Keep the Windows worker bound to `127.0.0.1`.
- Do not open public firewall ports for the worker.
- Keep the VPS listener bound to `127.0.0.1` unless there is a deliberate, reviewed security change.
- Use only voices Eddie owns or has permission to use.
- No minors, non-consensual impersonation, public-figure deception, fraud, harassment, or illegal content.

