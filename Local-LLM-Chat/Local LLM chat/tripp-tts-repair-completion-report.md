# Trippcore TTS Repair Completion Report

Date: 2026-06-22

## Result

The Trippcore Local TTS Worker provider pipeline is repaired end to end.

Local worker health is clean:

```text
ok: true
warnings: []
voices: chloe, cosy_chloe, index_chloe, dia_chloe
```

The full Cyony/cloud bridge path was verified from inside the Hermes container, including audio generation and MP3 fetch.

## What Was Fixed

### Provider Python Environment Isolation

The worker already had a provider environment helper:

```text
D:\Trippcore\services\tripp-tts-worker\src\tts\providerEnv.ts
```

It was not consistently wired into all provider subprocesses.

The following provider spawns now use the cleaned environment:

```text
D:\Trippcore\services\tripp-tts-worker\src\tts\pocketTts.ts
D:\Trippcore\services\tripp-tts-worker\src\tts\cosyVoice3Tts.ts
D:\Trippcore\services\tripp-tts-worker\src\tts\qwen3Tts.ts
D:\Trippcore\services\tripp-tts-worker\src\tts\indexTts2Tts.ts
D:\Trippcore\services\tripp-tts-worker\src\tts\diaTts.ts
```

This stopped Python package leakage from the parent/agent environment into provider runtimes.

### Pocket `chloe`

Pocket was failing because the `uvx pocket-tts` process imported incompatible Python packages from the wrong environment.

After provider env isolation and worker restart:

```text
chloe: passed
```

### IndexTTS2 `index_chloe`

IndexTTS2 was failing because its subprocess inherited incompatible Python/protobuf state.

After provider env isolation and worker restart:

```text
index_chloe: passed
```

It still emits a known `GenerationMixin` warning from `transformers`, but generation succeeds and returns audio.

### Dia `dia_chloe`

Dia had multiple issues:

1. Its venv depended on packages leaking from outside the venv.
2. The long Scout reference audio was too large for Dia's fixed decoder prompt window.
3. The Dia wrapper parsed a max-token option but did not pass it into generation.

Fixes applied:

- Reinstalled Dia project dependencies into:

```text
D:\Trippcore\runtimes\dia
```

- Patched:

```text
D:\Trippcore\services\tripp-tts-worker\scripts\dia-tts-generate.py
```

so it passes `max_tokens` into `model.generate`.

- Created a Dia-specific short reference:

```text
D:\Trippcore\voices\dia\scout-dia-ref-6s.wav
```

- Updated local worker `.env` to set:

```text
TRIPP_TTS_DIA_REF_AUDIO=D:\Trippcore\voices\dia\scout-dia-ref-6s.wav
```

No shared secret was printed or documented.

After repair:

```text
dia_chloe: passed
```

## Local Smoke Results

All voices generated MP3 audio locally and the returned audio URLs were fetched successfully.

| Voice | Result | Job ID | MP3 bytes |
|---|---:|---|---:|
| `chloe` | passed | `tts_20260622_184214_e0bbf8` | 33837 |
| `cosy_chloe` | passed | `tts_20260622_184218_34bf4d` | 62253 |
| `index_chloe` | passed | `tts_20260622_184245_bc065a` | 35988 |
| `dia_chloe` | passed | `tts_20260622_184313_78ae7b` | 67753 |

## Cloud/Cyony Bridge Smoke Results

Verified from inside the Hermes/Cyony container through the full path:

```text
Container 127.0.0.1:8788
-> container relay
-> VPS host bridge
-> VPS reverse SSH tunnel
-> Eddie Windows worker
```

Health checks passed from:

- VPS localhost
- VPS host bridge
- Hermes/Cyony container

Container helper generation passed:

| Voice/helper | Result | Job ID |
|---|---:|---|
| `chloe` | passed | `tts_20260622_184408_348e5d` |
| `cosy_chloe` | passed | `tts_20260622_184413_fb4e13` |
| `index_chloe` | passed | `tts_20260622_184437_48764e` |
| `dia_chloe` | passed | `tts_20260622_184504_4d9f5a` |
| old Qwen helper compatibility route | passed via `index_chloe` | `tts_20260622_184618_dd4431` |

The old Qwen helper now clearly reports that `qwen_chloe` is not live and routes to `index_chloe`.

## Validation

Worker validation passed after code changes:

```text
npm run validate
6 test files passed
34 tests passed
```

Dia runtime consistency check passed:

```text
No broken requirements found.
```

Final GPU state after smokes:

```text
191 MiB / 12282 MiB, 0% utilization
```

## Current Voice Guidance

| Voice | Current use |
|---|---|
| `chloe` | Production Pocket voice is restored. |
| `cosy_chloe` | Working expressive/instruction voice. |
| `index_chloe` | Working emotion-capable IndexTTS2 voice. |
| `dia_chloe` | Working experimental Dia voice using the shorter Dia-specific reference. |
| `qwen_chloe` | Still disabled; compatibility helpers route old Qwen calls to `index_chloe`. |

## Remaining Notes

No hard blocker remains for the stated goal.

Known caveats:

- IndexTTS2 still prints a `GenerationMixin` warning, but generation succeeds.
- Dia is slower and experimental.
- Dia now uses a 6-second reference clip because the previous 54-second reference exceeded Dia's fixed prompt window.
- Long-term improvement: add a real provider readiness endpoint or smoke script so `/health` cannot appear green while provider generation is broken.

