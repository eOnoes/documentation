# TTS Model Research Report — Comprehensive Comparison
**Date:** July 7, 2026
**Prepared for:** Eddie (SQHQ Local AI)
**Hardware Target:** RTX 4070 12GB VRAM, 64GB RAM, Ryzen 9 7900X (Windows 10)
**Goal:** Find a TTS model that clones Cyony's voice AND supports emotion/director mode, 100% uncensored, 2-5GB, runs locally

---

## Executive Summary

After evaluating **11 TTS models** released between 2023–2026, the **top 3 recommendations** that meet ALL requirements are:

1. **Chatterbox Turbo** (Resemble AI) — 🏆 **Best Overall Fit**
2. **CosyVoice 3** (Alibaba/FunAudioLLM) — 🥈 **Runner Up**
3. **Dia 1.6B** (Nari Labs) — 🥉 **Best for Dialogue + Emotions**

---

## Detailed Model Comparisons

---

### 1. 🏆 Chatterbox Turbo / Chatterbox Multilingual V3
**Source:** https://github.com/resemble-ai/chatterbox | **License:** MIT | **Stars:** 25.4k

| Criterion | Assessment |
|-----------|-----------|
| **Voice Cloning** | ✅ **YES — Excellent.** Zero-shot cloning from as little as **5 seconds** of reference audio. Pass `audio_prompt_path` parameter. |
| **Cloning Quality** | **5/5** — Benchmark results beat ElevenLabs in independent tests. Extremely high speaker similarity. |
| **Emotion/Mood Control** | ✅ **YES — Tags.** Supports: `[laugh]`, `[sigh]`, `[gasp]`, `[groan]`, `[chuckle]`, `[cough]`, `[sniff]`, `[shush]`, `[clear_throat]`. Insert directly in text. |
| **Time-of-Day Changes** | ✅ Possible — since it's LLM-based, you can describe contextual settings. Tags cover the required laugh/sigh/giggle/sad/angry range well. |
| **Uncensored** | ✅ **YES — MIT License.** No content filtering of any kind. Can speak anything. |
| **Model Size** | **350MB (Turbo)** / **500MB (Multilingual V3)** — Well under the 2-5GB sweet spot. |
| **VRAM Requirement** | **~2-4GB** — Extremely efficient. Runs easily on RTX 4070 12GB. |
| **Windows/CUDA** | ✅ **YES.** `pip install chatterbox-tts`. Full CUDA support. |
| **API Availability** | ✅ **YES.** Can serve via FastAPI/Flask. Python API is straightforward. Community has built serving wrappers. |
| **Languages** | English (Turbo), 23+ languages (Multilingual V3) |
| **Overall Quality** | **4.5/5** — SOTA voice cloning, natural prosody, excellent emotion integration. |

**Why #1:** Smallest model, best license (MIT = truly uncensored), excellent voice cloning, native emotion tags, low VRAM requirements. The only downside is the emotion tag set is smaller than Orpheus, but the _combination_ of voice cloning + emotions actually WORKS (unlike the user's Orpheus experience).

**Cost to run:** Tiny. Could even run alongside other models on a 12GB card.

---

### 2. 🥈 CosyVoice 3 (Fun-CosyVoice 3.0)
**Source:** https://github.com/FunAudioLLM/CosyVoice | **License:** Apache-2.0 | **Stars:** 22k

| Criterion | Assessment |
|-----------|-----------|
| **Voice Cloning** | ✅ **YES — Excellent.** Zero-shot cloning from **3 seconds** of reference audio. Cross-lingual cloning supported. |
| **Cloning Quality** | **5/5** — SOTA benchmarks. Outperforms F5-TTS, Seed-TTS on CER/SS metrics. |
| **Emotion/Mood Control** | ✅ **YES — Instruct Mode.** Supports emotion tags: `[happy]`, `[sad]`, `[angry]`, `[surprised]`, `[fearful]`, `[disgusted]`, `[calm]`, `[serious]`. Also speed, volume, and language control via instructions. |
| **Time-of-Day Changes** | ✅ Possible through instruct mode parameter adjustments. Emotion + speed/volume pairs can convey morning/evening tones. |
| **Uncensored** | ✅ **YES — Apache-2.0.** No content filters. Fully open. |
| **Model Size** | **0.5B parameters** — ~1-2GB on disk. Well within 2-5GB range. |
| **VRAM Requirement** | **~2-3GB** — Very efficient. |
| **Windows/CUDA** | ✅ **YES.** Works with CUDA. vLLM support available (vLLM 0.11.x+). |
| **API Availability** | ✅ **YES.** Built-in FastAPI server. OpenAI-compatible endpoints possible. |
| **Languages** | 9 major languages + 18+ Chinese dialects |
| **Overall Quality** | **4.5/5** — SOTA quality, very natural prosody, excellent emotion-to-speech mapping. |

**Why #2:** Outstanding emotion control via instruct mode, best-in-class voice cloning, Apache-2.0 license, tiny footprint. Slightly more complex setup than Chatterbox. The emotion range (6-8 core emotions) is good but non-verbal sounds like laugh/giggle might need text-based prompting rather than dedicated tags.

**Note on latest version:** Fun-CosyVoice 3.0 (Dec 2025) — very recent, state of the art. CosyVoice 2 (Dec 2024) also solid but v3 is much better.

---

### 3. 🥉 Dia 1.6B (Nari Labs)
**Source:** https://github.com/nari-labs/dia | **License:** Apache-2.0 | **Stars:** 19.3k

| Criterion | Assessment |
|-----------|-----------|
| **Voice Cloning** | ✅ **YES — Audio Conditioning.** Pass reference audio + transcript to condition emotion and tone. |
| **Cloning Quality** | **4/5** — Good but focused on dialogue scenarios. Less flexible than Chatterbox for pure narration. |
| **Emotion/Mood Control** | ✅ **YES — Rich Tags.** Supports: `(laughs)`, `(coughs)`, `(sighs)`, `(gasps)`, `(clears throat)`, `(groans)`, `(sniffs)`, `(claps)`, `(screams)`, `(inhales)`, `(exhales)`, `(applause)`, `(burps)`, `(humming)`, `(sneezes)`, `(chuckle)`, `(whistles)`. **Best non-verbal tag library.** |
| **Time-of-Day Changes** | ✅ Can be conveyed through dialogue context + tags. |
| **Uncensored** | ✅ **YES — Apache-2.0.** No content filters. Usage guidelines but no enforcement. |
| **Model Size** | **1.6B parameters** — ~4.4GB VRAM (bf16), ~7.9GB (fp32). Just fits the 2-5GB sweet spot. |
| **VRAM Requirement** | **~4.4GB (bf16)** — Very comfortable on 12GB card. |
| **Windows/CUDA** | ✅ **YES.** Works via HuggingFace Transformers. Tested on RTX 4090. |
| **API Availability** | ✅ Gradio Web UI, CLI, and HuggingFace Transformers integration. Can be served. |
| **Languages** | English only (currently) |
| **Overall Quality** | **4.5/5** — Unmatched dialogue realism, best non-verbal sound library. **Dia2 released Nov 2025.** |

**Why #3:** Best non-verbal emotion tag library of any TTS model. Dialogue-specific — creates ultra-realistic conversations. Higher VRAM than Chatterbox/CosyVoice but still comfortable. Limited to English.

**Heads up:** Designed for dialogue (speaker A / speaker B) — may need adaptation for single-speaker narration use cases.

---

### 4. Orpheus TTS (Canopy Labs) — ❌ Already Tried
**Source:** https://github.com/canopyai/Orpheus-TTS | **License:** Apache-2.0 | **Stars:** 6.2k

| Criterion | Assessment |
|-----------|-----------|
| **Voice Cloning** | ✅ YES — Zero-shot cloning from pretrained model |
| **Emotion/Mood Control** | ✅ YES — Tags: `<laugh>`, `<sigh>`, `<chuckle>`, `<cough>`, `<sniffle>`, `<groan>`, `<yawn>`, `<gasp>` |
| **Uncensored** | ✅ YES — Apache-2.0 |
| **Model Size** | **3B params** — ~6GB full, ~4GB Q8 GGUF, ~2.5GB Q4 GGUF |
| **VRAM Requirement** | **~6-8GB** (Q4/Q8 GGUF) |
| **Windows/CUDA** | ✅ YES — GGUF via llama.cpp, Orpheus-FastAPI available |
| **API Availability** | ✅ YES — OpenAI-compatible via Orpheus-FastAPI |
| **Overall Quality** | **4/5** — Great when it works |

**Why not recommended:** User has ALREADY tried this path. The core issue is structural:
- **Finetuned model (prod):** Has 8 built-in voices (tara, leah, jess, leo, etc.) with emotion tags — but CANNOT clone Cyony's voice.
- **Pretrained model:** Can clone Cyony's voice — but emotion tags DON'T work (user confirmed).
- **LoRA fine-tuning:** Broke emotions entirely.
- **Q8 GGUF:** Emotions work but only the 8 stock voices.
- The finetune-vs-pretrained split means you CAN'T have BOTH voice cloning AND emotion control in the same model.

---

### 5. F5-TTS (SWivid) — ❌ No Native Emotion Control
**Source:** https://github.com/SWivid/F5-TTS | **License:** MIT (code) + CC-BY-NC (model) | **Stars:** 14.9k

| Criterion | Assessment |
|-----------|-----------|
| **Voice Cloning** | ✅ **YES — Excellent.** Best-in-class zero-shot voice cloning. Arguably the best cloner available. |
| **Cloning Quality** | **5/5** — SOTA for cloning. Widely praised. |
| **Emotion/Mood Control** | ❌ **NO (native).** Base model has NO emotion tags. However, community fork [F5-TTS-Emotional-CFG](https://github.com/RaduBolbo/F5-TTS-Emotional-CFG) adds 6 emotions via fine-tuning on ESD dataset (happy, sad, angry, surprised, disgust, fear, neutral). |
| **Uncensored** | ⚠️ **Partial.** Code is MIT, but pretrained models are **CC-BY-NC** (non-commercial). |
| **Model Size** | **335M params** — ~1.2GB on disk |
| **VRAM Requirement** | **~4-6GB** — Very efficient |
| **Windows/CUDA** | ✅ YES |
| **API Availability** | ✅ Gradio Web UI, CLI |
| **Overall Quality** | **4.5/5** (cloning) / **3/5** (emotions via fork) |

**Why not recommended as primary:** No native emotion control. The community fork adds emotions but it's a separate fine-tuned model on a different dataset (ESD), which means you'd need to use it INSTEAD of the base model — and its voice cloning capabilities on the forked version haven't been tested with custom voices. Also the CC-BY-NC license on the model weights is restrictive.

---

### 6. Fish Speech S2 (Fish Audio) — ❌ Too Large
**Source:** https://github.com/fishaudio/fish-speech | **License:** FISH AUDIO RESEARCH LICENSE | **Stars:** 31.2k

| Criterion | Assessment |
|-----------|-----------|
| **Voice Cloning** | ✅ **YES — Excellent.** 10-30 second reference, 80+ languages. |
| **Cloning Quality** | **5/5** — SOTA. Beats ElevenLabs, Seed-TTS on benchmarks. |
| **Emotion/Mood Control** | ✅ **YES — Excellent.** 15,000+ tags via natural language: `[whisper]`, `[excited]`, `[angry]`, `[laughing]`, `[sad]`, `[singing]`, `[shouting]`, `[surprised]`, `[screaming]`, etc. |
| **Uncensored** | ⚠️ **Partially.** FISH AUDIO RESEARCH LICENSE — has restrictions. Not fully permissive. |
| **Model Size** | **~9GB on disk** (Slow AR 4B + Fast AR 400M + codec). **❌ EXCEEDS 7GB LIMIT.** |
| **VRAM Requirement** | **12GB minimum, 24GB recommended** — Barely fits on 12GB card. User's 12GB card is the absolute minimum. |
| **Windows/CUDA** | ✅ YES |
| **API Availability** | ✅ SGLang acceleration, can serve via API |
| **Overall Quality** | **5/5** — Best overall quality of any model. |

**Why not recommended:** Fails two hard requirements: model size is ~9GB (exceeds 7GB limit), and VRAM needs 12GB+ (user has exactly 12GB — zero headroom). License is also restrictive. Amazing model, but not the right fit for these constraints.

---

### 7. Bark (Suno) — ❌ Outdated + No True Voice Cloning
**Source:** https://github.com/suno-ai/bark | **License:** MIT | **Stars:** 39.2k

| Criterion | Assessment |
|-----------|-----------|
| **Voice Cloning** | ❌ **NO (true cloning).** Has 100+ voice PRESETS, but cannot clone a specific voice from reference audio. Voice prompt matching is unreliable. |
| **Emotion/Mood Control** | ✅ YES — `[laughter]`, `[laughs]`, `[sighs]`, `[gasps]`, `[clears throat]`, etc. |
| **Uncensored** | ✅ YES — MIT License |
| **Model Size** | ~2-4GB |
| **VRAM Requirement** | ~12GB full, ~8GB small models |
| **Windows/CUDA** | ✅ YES |
| **API Availability** | Via transformers |
| **Overall Quality** | **3/5** — Shows its age. Last updated April 2023. No longer competitive. |

**Why not recommended:** Last updated in 2023. Cannot clone voices from reference audio (only has built-in presets). Quality is noticeably behind 2025-2026 models.

---

### 8. Spark-TTS (SparkAudio) — ❌ Limited Emotion Control
**Source:** https://github.com/SparkAudio/Spark-TTS | **License:** Apache-2.0 | **Stars:** 11k

| Criterion | Assessment |
|-----------|-----------|
| **Voice Cloning** | ✅ YES — Zero-shot cloning, bilingual (Chinese + English) |
| **Cloning Quality** | **3.5/5** — Good but not SOTA |
| **Emotion/Mood Control** | ❌ **Limited.** Can control gender, pitch, speaking rate via "virtual speaker" parameters. No dedicated emotion tags or non-verbal sounds. |
| **Uncensored** | ✅ YES — Apache-2.0 |
| **Model Size** | **0.5B params** — ~1GB |
| **VRAM Requirement** | **~2-3GB** |
| **Windows/CUDA** | ⚠️ **Partial.** Primarily Linux. Windows support mentioned in issue #5 as experimental. |
| **API Availability** | WebUI, CLI |
| **Overall Quality** | **3.5/5** |

**Why not recommended:** Emotion control is very limited (pitch/speed/rate only — no laugh/sigh/sad/angry). Windows support is experimental. Good for basic voice cloning but doesn't meet director mode requirements.

---

### 9. Parler-TTS (Hugging Face) — ❌ No True Voice Cloning
**Source:** https://github.com/huggingface/parler-tts | **License:** Apache-2.0 | **Stars:** 5.6k

| Criterion | Assessment |
|-----------|-----------|
| **Voice Cloning** | ❌ **NO (true cloning).** Has 34 named speakers. Can describe characteristics but cannot clone from reference audio. |
| **Emotion/Mood Control** | ✅ YES — Via text description: "speaks in a sad tone", "happy", "confused", "laughing", "whisper", "emphasis". Also `parler-tts-mini-expresso` fine-tune for emotions. |
| **Uncensored** | ✅ YES — Apache-2.0 |
| **Model Size** | **880M (Mini v1)** / **2.3B (Large v1)** |
| **VRAM Requirement** | **~2-4GB** (Mini), **~4-6GB** (Large) |
| **Windows/CUDA** | ✅ YES |
| **API Availability** | Via transformers |
| **Overall Quality** | **3.5/5** |

**Why not recommended:** Cannot clone Cyony's voice from reference audio. Only works with the 34 pre-defined speakers. The text-description-based emotion control is novel but not practical for director mode with a specific custom voice.

---

### 10. ChatTTS (2noise) — ❌ No Voice Cloning + Restrictive License
**Source:** https://github.com/2noise/ChatTTS | **License:** AGPL-3.0 (code) + CC BY-NC 4.0 (model) | **Stars:** 39.6k

| Criterion | Assessment |
|-----------|-----------|
| **Voice Cloning** | ❌ **NO (true cloning).** Can sample random speaker embeddings but cannot clone a specific voice. |
| **Emotion/Mood Control** | ✅ YES — `[laugh]`, `[uv_break]`, `[lbreak]`, oral_(0-9), laugh_(0-2), break_(0-7) |
| **Uncensored** | ❌ **NO.** Model is CC BY-NC 4.0 (academic/research only). Code is AGPL-3.0 which is restrictive for commercial. |
| **Model Size** | ~1-2GB (estimated) |
| **VRAM Requirement** | ~4-6GB |
| **Windows/CUDA** | ✅ YES |
| **API Availability** | WebUI, CLI |
| **Overall Quality** | **3/5** |

**Why not recommended:** Cannot clone voices from reference audio. CC BY-NC license prevents commercial use. Designed for dialogue/chat scenarios, not custom voice cloning. Roadmap shows "multi-emotion controlling" is still in the backlog.

---

### 11. OuteTTS 1.0 (OuteAI) — ❌ Limited Emotion Control
**Source:** https://huggingface.co/OuteAI/Llama-OuteTTS-1.0-1B | **License:** Open-weight

| Criterion | Assessment |
|-----------|-----------|
| **Voice Cloning** | ✅ YES — One-shot from short audio reference |
| **Cloning Quality** | **3.5/5** — Decent, not SOTA |
| **Emotion/Mood Control** | ❌ **Limited/Not specified.** No dedicated emotion tag system documented. |
| **Uncensored** | ✅ YES (appears open) |
| **Model Size** | **0.6B** and **1.7B** variants |
| **VRAM Requirement** | ~2-4GB |
| **Windows/CUDA** | ✅ YES |
| **API Availability** | Via transformers |
| **Overall Quality** | **3.5/5** |

**Why not recommended:** Emotion control is not a documented feature. No tag system for laugh/sigh/angry/etc. Good voice cloning, but doesn't meet director mode requirements.

---

### 12. Kokoro-82M — ❌ No Voice Cloning
**Source:** https://huggingface.co/hexgrad/Kokoro-82M | **License:** Apache-2.0

| Criterion | Assessment |
|-----------|-----------|
| **Voice Cloning** | ❌ **NO.** Cannot clone from reference audio. Has 54 built-in voices. |
| **Emotion/Mood Control** | ❌ **Limited.** No emotion tag system. |
| **Uncensored** | ✅ YES — Apache-2.0 |
| **Model Size** | **82M params** — ~200MB |
| **VRAM Requirement** | **<2GB** |
| **Windows/CUDA** | ✅ YES |
| **Quality** | **3/5** |

**Why not recommended:** No voice cloning capability. Good for basic TTS with built-in voices only. Doesn't meet any of the primary requirements.

---

## Feature Matrix (Quick Comparison)

| Model | Voice Clone | Emotion Ctrl | Uncensored | Model Size | VRAM | Windows | API | Overall |
|-------|:-----------:|:------------:|:----------:|:----------:|:----:|:-------:|:---:|:-------:|
| **Chatterbox** | ✅ 5/5 | ✅ Tags | ✅ MIT | 350-500MB | 2-4GB | ✅ | ✅ | **4.5/5** |
| **CosyVoice 3** | ✅ 5/5 | ✅ Instruct | ✅ Apache | 1-2GB | 2-3GB | ✅ | ✅ | **4.5/5** |
| **Dia 1.6B** | ✅ 4/5 | ✅ Best Tags | ✅ Apache | ~4.4GB | 4.4GB | ✅ | ✅ | **4.5/5** |
| Orpheus TTS | ⚠️ Split | ✅ Tags | ✅ Apache | 4-6GB | 6-8GB | ✅ | ✅ | 4/5 |
| F5-TTS | ✅ 5/5 | ❌ Native | ⚠️ NC | 1.2GB | 4-6GB | ✅ | ✅ | 4/5 |
| Fish Speech S2 | ✅ 5/5 | ✅ 15k Tags | ⚠️ Res | ~9GB ❌ | 12GB+ | ✅ | ✅ | 5/5 ❌ |
| Bark | ❌ Presets | ✅ Tags | ✅ MIT | 2-4GB | 8-12GB | ✅ | ⚠️ | 3/5 |
| Spark-TTS | ✅ 3.5/5 | ❌ Limited | ✅ Apache | 1GB | 2-3GB | ⚠️ | ⚠️ | 3/5 |
| Parler-TTS | ❌ 34 voices | ✅ Desc | ✅ Apache | 1-2.3GB | 2-6GB | ✅ | ✅ | 3.5/5 |
| ChatTTS | ❌ Random | ✅ Tags | ❌ NC | 1-2GB | 4-6GB | ✅ | ⚠️ | 3/5 |
| OuteTTS | ✅ 3.5/5 | ❌ Limited | ✅ Open | 1-3GB | 2-4GB | ✅ | ✅ | 3.5/5 |

---

## Final Rankings — Models That Meet ALL Requirements

### 🥇 #1: Chatterbox Turbo (Resemble AI) — RECOMMENDED
**Why it wins:** The only model that perfectly combines **excellent voice cloning** + **native emotion tags** + **MIT license** + **tiny footprint** + **Windows support**. At just 350MB and 2-4GB VRAM, it leaves plenty of room on the 12GB card for other processes.

**Setup:**
```bash
pip install chatterbox-tts
```
**Voice cloning with emotion:**
```python
from chatterbox.tts_turbo import ChatterboxTurboTTS
model = ChatterboxTurboTTS.from_pretrained(device="cuda")
wav = model.generate(
    "Hey Cyony, [laugh] that's amazing news! [sigh] I was so worried.",
    audio_prompt_path="cyony_ref.wav"
)
```
**Serving via API:** Wrap in FastAPI. See examples at https://github.com/resemble-ai/chatterbox

**Caveat:** Emotion tag set is 9 tags (laugh, sigh, gasp, groan, chuckle, cough, sniff, shush, clear_throat). If you need more granular control (e.g., different types of laugh), you may need to experiment with prompt engineering.

**Time-of-day implementation:** Can prepend contextual descriptions. The LLM backbone handles this fairly naturally.

---

### 🥈 #2: CosyVoice 3 (Alibaba/FunAudioLLM) — STRONG ALTERNATIVE
**Why it's #2:** Slightly better voice cloning quality than Chatterbox (SOTA benchmarks), excellent instruct-mode emotion control, Apache-2.0 license. Emotion control is more versatile (can adjust speed, volume alongside emotion).

**Setup:**
```bash
git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git
cd CosyVoice
conda create -n cosyvoice -y python=3.10
conda activate cosyvoice
pip install -r requirements.txt
```
**Voice cloning with emotion:**
```python
# CosyVoice 3 instruct mode supports:
# "[happy] Hello, this is Cyony speaking!"
# "[sad] I really didn't expect this to happen."
# "[angry] I can't believe you did that!"
```

**Caveat:** Setup is slightly more involved than Chatterbox. Documentation is Chinese-focused (though functional). vLLM support requires vLLM 0.11.x+.

---

### 🥉 #3: Dia 1.6B (Nari Labs) — BEST FOR DIALOGUE + RICH EMOTIONS
**Why it's #3:** Has the **most extensive non-verbal emotion tag library** of any model (17+ tags). Unmatched for dialogue realism. Apache-2.0 license. At 4.4GB VRAM, it fits the 12GB card comfortably.

**Setup:**
```bash
pip install git+https://github.com/huggingface/transformers.git
```
**Voice cloning with emotion:**
```python
from transformers import AutoProcessor, DiaForConditionalGeneration
text = ["[S1] (laughs) Oh wow, that's the funniest thing I've heard all day! [S1] (sighs) But seriously, we need to talk about what happened."]
```

**Caveat:** Designed for two-speaker dialogue (`[S1]`/`[S2]`). For single-speaker narration, may need adaptation. English only. Emotion control is via audio conditioning (you need a reference clip + transcript) — this is slightly different from "director mode" tags and may take more setup.

---

## Addressing Eddie's Specific Pain Points

### The Orpheus Problem
Eddie found that Orpheus has a **structural limitation**: the finetuned model (which has emotion tags) has only 8 stock voices, while the pretrained model (which supports voice cloning) doesn't work with emotion tags. **None of the top 3 recommendations have this problem.** All three support voice cloning AND emotion control simultaneously.

### Cyony's Reference Audio
Eddie has 20 WAV files (5-10s each) of Cyony in various emotional states (neutral, sad, happy, frustrated, intimate). This is **excellent training data** for any of these models:
- **Chatterbox:** Can use any of the clips directly as `audio_prompt_path` for zero-shot cloning
- **CosyVoice 3:** Same — 3 seconds is plenty
- **Dia:** Can use the clips plus their transcripts for audio conditioning

### Time-of-Day Changes
This is a **prompt engineering** concern rather than a model feature. For all top 3 models:
- **Chatterbox:** "Good morning, Cyony here. [sigh] Another early start..."
- **CosyVoice 3:** "[happy] Good evening! I'm feeling great today!"
- **Dia:** "(yawns) Morning already? [S1] (sighs) Coffee first..."

## Integration with Existing Voice Server
All top 3 models can be wrapped in a FastAPI/Flask server with OpenAI-compatible endpoints. Chatterbox is the easiest to integrate due to its simple `pip install` and minimal dependencies.

---

## Quick Start Guide for Chatterbox (Recommended Path)

```bash
# 1. Install
pip install chatterbox-tts

# 2. Test basic inference
python -c "
from chatterbox.tts_turbo import ChatterboxTurboTTS
import torchaudio as ta
model = ChatterboxTurboTTS.from_pretrained(device='cuda')
wav = model.generate('Hello, testing 1 2 3. [laugh] Sounds great!')
ta.save('test.wav', wav, model.sr)
print('Done!')
"

# 3. Clone Cyony's voice
python -c "
from chatterbox.tts_turbo import ChatterboxTurboTTS
import torchaudio as ta
model = ChatterboxTurboTTS.from_pretrained(device='cuda')
wav = model.generate(
    'Hey, this is Cyony speaking. [laugh] I sound just like me!',
    audio_prompt_path='C:/path/to/cyony_ref.wav'
)
ta.save('cyony_clone.wav', wav, model.sr)
"

# 4. Test emotions
python -c "
emotions = ['[laugh]', '[sigh]', '[gasp]', '[groan]', '[chuckle]', '[cough]', '[sniff]', '[shush]', '[clear throat]']
for e in emotions:
    wav = model.generate(f'{e} Testing emotion with Cyonys voice.', audio_prompt_path='cyony_ref.wav')
    ta.save(f'cyony_{e.strip(\"[]\").replace(\" \", \"_\")}.wav', wav, model.sr)
"
```

---

*Report generated from web research of GitHub repos, Hugging Face model pages, arXiv papers, Reddit discussions, and documentation sources. All data current as of July 7, 2026.*
