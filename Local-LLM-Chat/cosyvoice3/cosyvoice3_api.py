import base64
import io
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
RUNTIME_CACHE = ROOT / ".runtime-cache"
for cache_name in ("MPLCONFIGDIR", "HF_HOME", "TRANSFORMERS_CACHE", "XDG_CACHE_HOME"):
    os.environ.setdefault(cache_name, str(RUNTIME_CACHE / cache_name.lower()))
for cache_path in {Path(os.environ[name]) for name in ("MPLCONFIGDIR", "HF_HOME", "TRANSFORMERS_CACHE", "XDG_CACHE_HOME")}:
    cache_path.mkdir(parents=True, exist_ok=True)

import torch
import torchaudio
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response


REPO = ROOT / "CosyVoice"
MODEL_DIR = Path(os.environ.get("COSYVOICE3_MODEL_DIR", REPO / "pretrained_models" / "Fun-CosyVoice3-0.5B"))
DEFAULT_PROMPT_TEXT = os.environ.get("COSYVOICE3_PROMPT_TEXT", "You are a helpful assistant.<|endofprompt|>")

sys.path.append(str(REPO))
sys.path.append(str(REPO / "third_party" / "Matcha-TTS"))

from cosyvoice.cli.cosyvoice import AutoModel  # noqa: E402


def _candidate_reference_paths() -> list[Path]:
    user_home = Path.home()
    return [
        Path(os.environ["SCOUT_REFERENCE_AUDIO"]) if os.environ.get("SCOUT_REFERENCE_AUDIO") else None,
        user_home / "Downloads" / "video_project_2_pocket_tts_reference_30s_clean.wav",
        user_home / "Downloads" / "video_project_2_voice_reference_24k_mono.wav",
        user_home / "Downloads" / "LongPlayScoutCloneModel.ogg",
    ]


def default_reference_audio() -> Path | None:
    for candidate in _candidate_reference_paths():
        if candidate and candidate.exists():
            return candidate
    return None


VOICE_PRESETS = {
    "default": default_reference_audio,
    "scout": default_reference_audio,
    "qwen_chloe": default_reference_audio,
    "chloe": default_reference_audio,
}


app = FastAPI(title="Fun-CosyVoice3 local TTS", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_model = None


def model():
    global _model
    if _model is None:
        fp16 = os.environ.get("COSYVOICE3_FP16", "1") not in {"0", "false", "False"}
        _model = AutoModel(model_dir=str(MODEL_DIR), fp16=fp16)
    return _model


def resolve_voice(voice: str | None) -> Path:
    key = (voice or "default").strip()
    preset = VOICE_PRESETS.get(key.lower())
    if preset is not None:
        path = preset()
    else:
        path = Path(key)

    if not path or not path.exists():
        raise HTTPException(status_code=400, detail=f"Voice reference not found: {key}")
    return path


def instruction_prompt(instruct: str) -> str:
    text = instruct.strip()
    if not text:
        return ""
    if "<|endofprompt|>" in text:
        return text
    if text.lower().startswith("you are a helpful assistant"):
        return f"{text}<|endofprompt|>"
    return f"You are a helpful assistant. {text}<|endofprompt|>"


def synthesize(text: str, voice_path: Path, instruct: str | None, prompt_text: str | None = None) -> tuple[bytes, dict[str, Any]]:
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="text is required")

    cosyvoice = model()
    start = time.perf_counter()

    if instruct and instruct.strip():
        generator = cosyvoice.inference_instruct2(
            text,
            instruction_prompt(instruct),
            str(voice_path),
            stream=False,
        )
        mode = "instruct2"
    else:
        generator = cosyvoice.inference_zero_shot(
            text,
            prompt_text or DEFAULT_PROMPT_TEXT,
            str(voice_path),
            stream=False,
        )
        mode = "zero_shot"

    chunks = [item["tts_speech"].detach().cpu() for item in generator]
    if not chunks:
        raise HTTPException(status_code=500, detail="CosyVoice returned no audio")

    wav = torch.cat(chunks, dim=1)
    duration_s = wav.shape[1] / cosyvoice.sample_rate
    elapsed_s = time.perf_counter() - start

    buf = io.BytesIO()
    torchaudio.save(buf, wav, cosyvoice.sample_rate, format="wav")
    meta = {
        "mode": mode,
        "sample_rate": cosyvoice.sample_rate,
        "duration_s": duration_s,
        "elapsed_s": elapsed_s,
        "rtf": elapsed_s / duration_s if duration_s else None,
        "voice_path": str(voice_path),
        "cuda_available": torch.cuda.is_available(),
        "cuda_max_memory_allocated_mb": round(torch.cuda.max_memory_allocated() / 1024 / 1024, 1)
        if torch.cuda.is_available()
        else None,
    }
    return buf.getvalue(), meta


async def parse_tts_request(
    request: Request,
    text: str | None,
    voice: str | None,
    instruct: str | None,
    return_format: str | None,
    prompt_text: str | None,
    voice_upload: UploadFile | None,
) -> tuple[str, Path, str | None, str, str | None, tempfile.TemporaryDirectory | None]:
    temp_dir = None
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        payload = await request.json()
        text = payload.get("text", text)
        voice = payload.get("voice", voice)
        instruct = payload.get("instruct", instruct)
        return_format = payload.get("return_format", return_format)
        prompt_text = payload.get("prompt_text", prompt_text)

    if voice_upload is not None:
        suffix = Path(voice_upload.filename or "voice.wav").suffix or ".wav"
        temp_dir = tempfile.TemporaryDirectory(prefix="cosyvoice3_voice_")
        voice_path = Path(temp_dir.name) / f"reference{suffix}"
        voice_path.write_bytes(await voice_upload.read())
    else:
        voice_path = resolve_voice(voice)

    return text or "", voice_path, instruct, (return_format or "wav").lower(), prompt_text, temp_dir


@app.get("/health")
def health():
    ref = default_reference_audio()
    return {
        "ok": True,
        "model_dir": str(MODEL_DIR),
        "model_loaded": _model is not None,
        "default_reference_audio": str(ref) if ref else None,
        "cuda_available": torch.cuda.is_available(),
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }


@app.post("/v1/tts")
async def tts(
    request: Request,
    text: str | None = Form(default=None),
    voice: str | None = Form(default=None),
    instruct: str | None = Form(default=None),
    return_format: str | None = Form(default="wav"),
    prompt_text: str | None = Form(default=None),
    voice_upload: UploadFile | None = File(default=None),
):
    text, voice_path, instruct, return_format, prompt_text, temp_dir = await parse_tts_request(
        request, text, voice, instruct, return_format, prompt_text, voice_upload
    )
    try:
        wav_bytes, meta = synthesize(text, voice_path, instruct, prompt_text)
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()

    if return_format == "json":
        return JSONResponse({**meta, "audio_base64": base64.b64encode(wav_bytes).decode("ascii")})
    if return_format != "wav":
        raise HTTPException(status_code=400, detail="return_format must be wav or json")

    headers = {
        "X-CosyVoice-Mode": meta["mode"],
        "X-CosyVoice-Duration-S": f"{meta['duration_s']:.3f}",
        "X-CosyVoice-Elapsed-S": f"{meta['elapsed_s']:.3f}",
        "X-CosyVoice-RTF": f"{meta['rtf']:.3f}" if meta["rtf"] is not None else "",
    }
    return Response(wav_bytes, media_type="audio/wav", headers=headers)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("COSYVOICE3_PORT", "8789"))
    uvicorn.run(app, host="127.0.0.1", port=port)
