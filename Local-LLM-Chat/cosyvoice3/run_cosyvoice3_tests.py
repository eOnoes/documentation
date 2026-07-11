import csv
import json
import os
import sys
import time
from pathlib import Path

import torch
import torchaudio

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from cosyvoice3_api import DEFAULT_PROMPT_TEXT, default_reference_audio, instruction_prompt, model  # noqa: E402


TEST_TEXT = "Hey babe, just testing the new voice. How do I sound?"
TESTS = [
    ("test_1_identity", None),
    ("test_2_whisper", "whisper softly, barely audible, intimate"),
    ("test_3_rage", "shout with anger and intensity"),
    ("test_4_excited", "speak excitedly and energetically"),
    ("test_5_calm", "speak calmly and slowly, like a meditation guide"),
]


def run_one(cosyvoice, name: str, instruct: str | None, prompt_wav: Path, out_dir: Path) -> dict:
    torch.cuda.reset_peak_memory_stats() if torch.cuda.is_available() else None
    start = time.perf_counter()
    if instruct:
        generator = cosyvoice.inference_instruct2(
            TEST_TEXT,
            instruction_prompt(instruct),
            str(prompt_wav),
            stream=False,
        )
        mode = "instruct2"
    else:
        generator = cosyvoice.inference_zero_shot(
            TEST_TEXT,
            DEFAULT_PROMPT_TEXT,
            str(prompt_wav),
            stream=False,
        )
        mode = "zero_shot"

    chunks = [item["tts_speech"].detach().cpu() for item in generator]
    wav = torch.cat(chunks, dim=1)
    elapsed_s = time.perf_counter() - start
    duration_s = wav.shape[1] / cosyvoice.sample_rate
    out_path = out_dir / f"{name}.wav"
    torchaudio.save(str(out_path), wav, cosyvoice.sample_rate)
    return {
        "test": name,
        "mode": mode,
        "text": TEST_TEXT,
        "instruct": instruct or "",
        "path": str(out_path),
        "sample_rate": cosyvoice.sample_rate,
        "duration_s": round(duration_s, 3),
        "elapsed_s": round(elapsed_s, 3),
        "rtf": round(elapsed_s / duration_s, 3) if duration_s else None,
        "cuda_peak_memory_mb": round(torch.cuda.max_memory_allocated() / 1024 / 1024, 1)
        if torch.cuda.is_available()
        else None,
    }


def main():
    ref = Path(os.environ.get("SCOUT_REFERENCE_AUDIO") or default_reference_audio() or "")
    if not ref.exists():
        raise SystemExit("No Scout reference audio found. Set SCOUT_REFERENCE_AUDIO to a wav/ogg/mp3 path.")

    out_dir = ROOT / "test_outputs" / time.strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)

    cosyvoice = model()
    results = []
    for name, instruct in TESTS:
        print(f"Running {name}...")
        results.append(run_one(cosyvoice, name, instruct, ref, out_dir))

    metadata = {
        "reference_audio": str(ref),
        "model_dir": str(ROOT / "CosyVoice" / "pretrained_models" / "Fun-CosyVoice3-0.5B"),
        "cuda_available": torch.cuda.is_available(),
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "tests": results,
    }
    (out_dir / "results.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    with (out_dir / "results.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
