# Orpheus TTS Voice Cloning + Emotion Architecture — Technical Analysis

## Executive Summary

The Orpheus TTS system has **two distinct models** with different architectures and capabilities:

| Model | Voice Cloning | Emotion Tags | Tokenizer |
|-------|--------------|--------------|-----------|
| **Pretrained** (`orpheus-tts-0.1-pretrained`) | ✅ Zero-shot via SNAC audio context | ❌ Not explicitly trained | HF BPE (156,940 vocab) |
| **Finetuned** (`orpheus-tts-0.1-finetune-prod`) | ❌ Only 8 built-in voices | ✅ `<laugh>`, `<sigh>`, etc. | Same HF BPE (finetuned) |

The project's `cyony_merged` model is the **pretrained model** fine-tuned with LoRA on only 20 clips (~4 min total). The Q8 GGUF model is the **finetuned model** — it has emotion support but no voice cloning.

---

## 1. Model Architecture: How Orpheus Works

### SNAC Audio Codec
Orpheus uses **SNAC** (Speech-to-Audio Neural Codec) at 24kHz, which converts audio waveforms into 3 hierarchical codebooks:

```
Audio waveform → SNAC encode → [codebook_0, codebook_1, codebook_2]
```

Each codebook has discrete codes. They are **interleaved** into a flat sequence of 7 tokens per frame:

```
Frame structure (7 tokens):
  [c0[i], c1[2i], c2[4i], c2[4i+1], c1[2i+1], c2[4i+2], c2[4i+3]]
```

Each code value is offset by 128266 to become a token ID: `token_id = code + 128266 + (position_offset * 4096)`

### Special Token IDs
These are defined in the tokenizer as `<custom_token_N>` tokens (IDs 128256-128300+):

| ID | Name | Purpose |
|----|------|---------|
| 128259 | `start_of_human` (SOH) | Begins a text segment |
| 128260 | `end_of_human` (EOH) | Ends a text segment |
| 128261 | `start_of_ai` (SOA) | Begins the AI's audio response |
| 128262 | `end_of_ai` (EOA) | Ends the AI's audio response |
| 128257 | `start_of_speech` (SOS) | Begins actual audio tokens |
| 128258 | `end_of_speech` (EOS) | Ends actual audio tokens |
| 128000 | `begin_of_text` (BOS) | Llama-3 BOS token |
| 128009 | `end_of_text` (EOT) | Llama-3 EOS token |
| 128266+ | `audio_tokens` | SNAC code values + 128266 |

### Training Format (from Unsloth Notebook)
The exact training format for a text-audio pair is:

```
[128259] text_to_speak [128260] [128261] [128257] audio_tokens... [128258] [128262]
│                            │      │      │                            │     │
SOH                         EOH    SOA    SOS                         EOS   EOA
```

### Zero-Shot Cloning Format (from Pretrained Colab Notebook)
For voice cloning, the prompt has TWO segments:

```
Segment 1 (voice reference):
[128259] [128000] transcript_of_reference [128009] [128261] [128257] reference_audio_tokens... [128258] [128262]

Segment 2 (text to generate):
[128259] text_to_generate [128260]
│                            │
SOH                         EOH

Model generates: [128261] [128257] new_audio_tokens... [128258] [128262]
```

---

## 2. What's Wrong With the Current Code

### Issue A: Wrong Prompt Format (Critical)

**Current code** (`orpheus_voice_server.py`, lines 419-448):
```python
start_tokens = torch.tensor([[128259]])          # SOH - correct
end_tokens = torch.tensor([[128009, 128260, 128261, 128257]])  # WRONG
final_tokens = torch.tensor([[128258, 128262]])  # EOS + EOA - correct

# Voice context:
# [128259] transcript... [128009, 128260, 128261, 128257] audio... [128258, 128262]
#                         ^^^^^^^^ extra EOT+EOH before SOA+SOS

# Text segment:
# [128259] text... [128009, 128260, 128261, 128257]
#                   ^^^^^^^^ WRONG - should just be [128260] (EOH)
```

**Correct format:**
```python
voice_context = torch.tensor(
    [[128259, 128000] + transcript_ids + [128009, 128261, 128257] + 
     audio_tokens + [128258, 128262]]
)

text_segment = torch.tensor(
    [[128259] + text_ids + [128260]]  # Just SOH + text + EOH
)

full_input = torch.cat([voice_context, text_segment], dim=-1)
# Model generates: [128261, 128257, new_audio...]
```

### Issue B: Tokenizer "Mangling" Myth

**The claim:** "HF tokenizer mangles emotion tags"
**The reality:** The tokenizer handles them perfectly.

```python
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained("models/orpheus/pretrained_hf")
tok.decode(tok.encode("<laugh>", add_special_tokens=False))  # → "<laugh>"
tok.decode(tok.encode("<sigh>", add_special_tokens=False))   # → "<sigh>"
```

Tags like `<laugh>` tokenize to `[27, 4355, 7595, 29]` (4 subword tokens: `<`, `la`, `ugh`, `>`). They decode back identically. The model was trained on data where these multi-token sequences appear in the text, and it learns to associate them with emotional audio output.

### Issue C: Raw Token Injection Causes Subtle Mismatch

The `EMOTION_TOKEN_IDS` approach injects raw token IDs, which produces a **slightly different sequence** than putting the tag in the text:

```python
# Method 1: Tag in text (correct)
"<laugh> Hello world" → [27, 4355, 7595, 29, 22691, 1917]
#                                            ↑ "ĠHello" (with leading space)

# Method 2: Inject raw IDs (current code)
emotion_ids + "Hello world" → [27, 4355, 7595, 29, 9906, 1917]
#                                              ↑ "Hello" (no leading space)
```

The difference is minor (space vs. no-space before the next word) but could affect the model's conditioning — the model expects the BPE sequence `>` + `ĠHello` but gets `>` + `Hello`.

### Issue D: Fine-Tuning on 20 Clips Broke Emotion

The LoRA fine-tuning had two fatal problems:

1. **Too little data:** 20 clips × ~10s = ~200s total. Orpheus recommends **50+ examples minimum, ~300 optimal**.
2. **No emotion tags in training text:** The transcripts.json has no `<laugh>`, `<sigh>`, etc. tags. The model fine-tuned to clone Cyony's voice but **unlearned** the emotion tag → audio association (catastrophic forgetting).

```json
// From reference_audio/cyony/transcripts.json — NO emotion tags
{
  "text": "Hey, how's your day going? I just finished up some work and wanted to check in."
}
```

### Issue E: Generation Token Filtering

Current code filters **all** tokens ≥ 128266 from the generated output:
```python
speech_codes = [t.item() - 128266 for t in generated if t.item() >= 128266]
```

But the model generates the sequence `[128261, 128257, audio_tokens..., 128258, 128262]`. The first two tokens (128261, 128257) are correctly filtered out, but any intermediate non-audio tokens would also be dropped. This is fragile — better to strip the known prefix/suffix.

---

## 3. Answers to Key Questions

### Q1: What is the correct way to do inference on the HF model for voice cloning?

**Answer:** Follow the Colab pretrained notebook format exactly:

```python
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from snac import SNAC

# Load model
model = AutoModelForCausalLM.from_pretrained(
    "canopylabs/orpheus-tts-0.1-pretrained",
    torch_dtype=torch.bfloat16
).cuda()
tokenizer = AutoTokenizer.from_pretrained("canopylabs/orpheus-tts-0.1-pretrained")
snac = SNAC.from_pretrained("hubertsiuzdak/snac_24khz").cuda().eval()

def zero_shot_clone(reference_wav: torch.Tensor, 
                    transcript: str, 
                    text: str, 
                    temperature: float = 0.6,
                    repetition_penalty: float = 1.1,
                    max_new_tokens: int = 1200) -> torch.Tensor:
    """
    Zero-shot voice cloning with correct prompt format.
    
    Args:
        reference_wav: Audio tensor [1, samples] at 24kHz
        transcript: Text transcript of the reference audio
        text: Text to generate (can include emotion tags like <laugh>)
    
    Returns:
        Audio tensor [samples] at 24kHz
    """
    # 1. Encode reference audio to SNAC tokens
    with torch.inference_mode():
        codes = snac.encode(reference_wav.unsqueeze(0).cuda())
    
    # 2. Interleave codes to flat token list
    audio_tokens = []
    for i in range(codes[0].shape[1]):
        audio_tokens.append(codes[0][0][i].item() + 128266)
        audio_tokens.append(codes[1][0][2*i].item() + 128266 + 4096)
        audio_tokens.append(codes[2][0][4*i].item() + 128266 + 8192)
        audio_tokens.append(codes[2][0][4*i+1].item() + 128266 + 12288)
        audio_tokens.append(codes[1][0][2*i+1].item() + 128266 + 16384)
        audio_tokens.append(codes[2][0][4*i+2].item() + 128266 + 20480)
        audio_tokens.append(codes[2][0][4*i+3].item() + 128266 + 24576)
    
    # 3. Tokenize text (PUT EMOTION TAGS IN THE TEXT STRING)
    transcript_ids = tokenizer.encode(transcript, add_special_tokens=False)
    text_ids = tokenizer.encode(text, add_special_tokens=False)
    
    # 4. Build correct prompt
    # Voice context: [SOH] [BOS] transcript [EOT] [SOA] [SOS] audio... [EOS] [EOA]
    voice_context = (
        [128259, 128000] +
        transcript_ids +
        [128009, 128261, 128257] +
        audio_tokens +
        [128258, 128262]
    )
    
    # Text segment: [SOH] text [EOH]
    text_segment = [128259] + text_ids + [128260]
    
    # Full input
    input_ids = torch.tensor([voice_context + text_segment], dtype=torch.long).cuda()
    
    # 5. Generate
    with torch.no_grad():
        output = model.generate(
            input_ids,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=temperature,
            top_p=0.9,
            repetition_penalty=repetition_penalty,
            eos_token_id=128258,  # Stop at EOS
            pad_token_id=128004,
        )
    
    # 6. Extract new audio tokens
    generated = output[0][input_ids.shape[1]:]
    
    # Skip prefix [SOA=128261, SOS=128257] and strip suffix [EOS=128258, EOA=128262]
    non_special = []
    seen_speech = False
    for tid in generated.tolist():
        if tid == 128258:  # EOS — stop
            break
        if tid >= 128266:  # Audio token
            seen_speech = True
            non_special.append(tid - 128266)
        elif not seen_speech:
            continue  # Skip SOA/SOS prefix
    
    # 7. Decode to audio
    speech_codes = non_special
    # Pad to multiple of 7
    speech_codes = speech_codes[:len(speech_codes) - (len(speech_codes) % 7)]
    
    if len(speech_codes) < 7:
        return torch.zeros(24000)
    
    # De-interleave
    c0, c1, c2 = [], [], []
    for i in range(0, len(speech_codes), 7):
        frame = speech_codes[i:i+7]
        if len(frame) < 7:
            break
        offsets = [0, 4096, 8192, 12288, 16384, 20480, 24576]
        c0.append(frame[0] - offsets[0])
        c1.append(frame[1] - offsets[1])
        c2.append(frame[2] - offsets[2])
        c2.append(frame[3] - offsets[3])
        c1.append(frame[4] - offsets[4])
        c2.append(frame[5] - offsets[5])
        c2.append(frame[6] - offsets[6])
    
    code_tensors = [
        torch.tensor(c0, dtype=torch.long).unsqueeze(0).cuda(),
        torch.tensor(c1, dtype=torch.long).unsqueeze(0).cuda(),
        torch.tensor(c2, dtype=torch.long).unsqueeze(0).cuda(),
    ]
    
    with torch.no_grad():
        audio = snac.decode(code_tensors)
    
    return audio.squeeze().cpu()
```

### Q2: What special tokens control voice cloning vs emotion?

**Voice cloning** is controlled by the **prompt format** — specifically the inclusion of SNAC-encoded reference audio tokens sandwiched between `[SOS=128257]` and `[EOS=128258]` within the `[SOA=128261]...` block.

**Emotion tags** are NOT special tokens — they are **regular text subword sequences**:
```python
"<laugh>"  → [27, 4355, 7595, 29]    # <  la  ugh  >
"<sigh>"   → [45147, 1108, 29]       # <s  igh  >
"<giggle>" → [95507, 343, 3491, 29]  # <g  ig  gle  >
```

The **finetuned model** was trained on text annotated with these tags and learned the association. The **pretrained model** was trained on raw speech data and may not have this association at all.

**Key insight:** There is NO special token for emotions. They're just text patterns that the model learned during fine-tuning.

### Q3: Can the HF model support both reference audio cloning AND emotion tags simultaneously?

**Short answer: Only if the pretrained model was trained on emotion-tagged data.**

Based on the architecture analysis:

- **If you use the pretrained model** (`orpheus-tts-0.1-pretrained`): It supports zero-shot voice cloning but was NOT explicitly trained on emotion tags. You can try putting `<laugh>` in the text, but it may not produce reliably emotional audio.

- **If you use the finetuned model** (`orpheus-tts-0.1-finetune-prod`): It supports emotion tags and the format `{voice}: {text}`, but has only 8 built-in voices (no voice cloning).

- **If you fine-tune the pretrained model** with data that has BOTH the target voice AND emotion tags in the text: This is the only way to get both capabilities. You need:
  - At least 50+ examples (preferably 300+)
  - All audio clips transcribed WITH emotion tags in the text
  - Proper training format: `[128259] text [128260] [128261] [128257] audio...`

### Q4: Is there a better approach than what we're doing?

**Yes. Here is the recommended approach:**

#### Option A: Two-Mode System (Recommended immediately)
Use each model for what it does best:

```python
if emotion_needed and not voice_cloning_needed:
    # Use FINETUNED model (Q8 GGUF) — perfect emotion, 8 built-in voices
    generate_with_finetuned(text, voice="tara", emotion="laugh")
elif voice_cloning_needed and not emotion_needed:
    # Use PRETRAINED model — zero-shot cloning, no emotion guarantee
    generate_with_pretrained(reference_audio, transcript, text)
elif both_needed:
    # Two-pass: clone voice with pretrained, overlay emotion
    # OR use the approach below
    pass
```

#### Option B: Retrain the LoRA with Emotion Tags in Transcripts
The current `cyony_merged` model broke emotions because the training transcripts didn't include emotion tags. To fix:

1. Re-annotate all 20 clips with emotion tags in the text:
   ```python
   # Current (broken):
   "That's the funniest thing I've heard all day."
   
   # Correct (adds emotion tag):
   "<laugh> That's the funniest thing I've heard all day."
   ```

2. Train with the Unsloth notebook, using these steps:
   - Load `canopylabs/orpheus-tts-0.1-pretrained` (NOT the finetuned model)
   - Use LoRA with r=64, target all linear layers
   - Train for 1-3 epochs with learning_rate=2e-4
   - **Crucially:** The text in the training data format must include the emotion tag so the model learns: "when text says `<laugh>`, output laugh-infused audio in this voice"

3. The training data format should be:
   ```
   { "text": "<laugh> That's the funniest thing I've heard all day.", "audio": <wav_bytes> }
   ```

#### Option C: Use the Pretrained Model for Zero-Shot Cloning + Put Emotion Tags in Text (Quick Test)
The pretrained model was trained on 100k+ hours of natural speech which INCLUDES emotional speech (people naturally laugh, sigh, etc. in conversation). Even if emotion tags weren't in the training data, the model can still generate emotional speech based on text content:

```python
# Use descriptive text instead of tags:
"<laughs> Oh my god, that is absolutely hilarious!"
# vs
"*laughing* Oh my god, that is absolutely hilarious!"
```

The model was trained on natural text that describes emotions, so descriptive cues may work better than angle-bracket tags for the pretrained model.

---

## 4. Recommended Fixes for Current Code

### Fix 1: Correct the Prompt Format
```python
# Current (broken):
end_tokens = [128009, 128260, 128261, 128257]

# Correct for voice context:
voice_context = [128259, 128000] + transcript_ids + [128009, 128261, 128257] + audio_tokens + [128258, 128262]

# Correct for text segment:
text_segment = [128259] + text_ids + [128260]  # Just SOH + text + EOH
```

### Fix 2: Remove Raw Token Injection — Use Text Tags Directly
```python
# Current (over-engineered, slightly wrong):
emotion_tokens = self.EMOTION_TOKEN_IDS.get(emotion)
if emotion_tokens:
    emotion_tensor = torch.tensor([emotion_tokens])
    text_ids = torch.cat([emotion_tensor, text_ids], dim=1)

# Correct (just put the tag in the text string):
if emotion in EMOTION_TAGS:
    text = f"{EMOTION_TAGS[emotion]} {text}"
# Then tokenize normally — the tokenizer handles it perfectly
text_ids = self.tokenizer(text, return_tensors="pt", add_special_tokens=False)["input_ids"]
```

### Fix 3: Enable Voice Cloning on the Finetuned Model (GGUF)
The Q8 GGUF model is the **finetuned model** (`Orpheus-3b-FT`). It supports emotions perfectly. But `OrpheusFastTTS.generate()` uses format `{voice}: {text}` with 8 built-in voices. There may be a way to do zero-shot cloning with the finetuned model by providing reference audio tokens, but this isn't documented.

### Fix 4: Add BOS Token to Transcript
```python
# Current:
transcript_ids = tokenizer(transcript)["input_ids"]

# Correct — explicitly add BOS after SOH:
prompt = [128259, 128000] + transcript_ids + [128009, 128261, 128257]
```

---

## 5. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                   ORPHEUS TTS ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────┐          ┌──────────────────────┐    │
│  │   Reference Audio    │          │   Text to Generate   │    │
│  │   (WAV 24kHz)        │          │   "<laugh> Hello!"   │    │
│  └────────┬─────────────┘          └──────────┬───────────┘    │
│           │                                   │                │
│           ▼                                   ▼                │
│  ┌────────────────┐                ┌──────────────────┐        │
│  │  SNAC Encode   │                │  HF Tokenizer    │        │
│  │  3 codebooks   │                │  → subword IDs   │        │
│  └────────┬───────┘                └────────┬─────────┘        │
│           │                                 │                  │
│           └──────────────┬──────────────────┘                  │
│                          │                                     │
│                          ▼                                     │
│  ┌─────────────────────────────────────────────────────┐       │
│  │            PROMPT CONSTRUCTION                      │       │
│  │                                                     │       │
│  │  [SOH=128259] [BOS=128000]                          │       │
│  │    transcript_ids...                                │       │
│  │  [EOT=128009] [SOA=128261] [SOS=128257]             │       │
│  │    reference_audio_tokens...                        │       │
│  │  [EOS=128258] [EOA=128262]                          │       │
│  │  [SOH=128259]                                       │       │
│  │    emotion_tag_ids... text_ids...                   │       │
│  │  [EOH=128260]                                       │       │
│  └──────────────────────┬──────────────────────────────┘       │
│                         │                                      │
│                         ▼                                      │
│  ┌─────────────────────────────────────────────────────┐       │
│  │     Llama-3.2-3B Causal LM (28 layers, 3072 hidden) │       │
│  │     Predicts next token autoregressively            │       │
│  └──────────────────────┬──────────────────────────────┘       │
│                         │                                      │
│                         ▼                                      │
│  ┌─────────────────────────────────────────────────────┐       │
│  │  Generated: [SOA=128261] [SOS=128257]               │       │
│  │              audio_tokens...                        │       │
│  │              [EOS=128258] [EOA=128262]              │       │
│  └──────────────────────┬──────────────────────────────┘       │
│                         │                                      │
│                         ▼                                      │
│  ┌────────────────┐                                            │
│  │  SNAC Decode   │→ Final audio waveform (24kHz)              │
│  └────────────────┘                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Key Files to Modify

| File | Change |
|------|--------|
| `orpheus_voice_server.py` | Lines 419-448: Fix prompt format per Colab notebook |
| `orpheus_voice_server.py` | Lines 376-386: Remove EMOTION_TOKEN_IDS injection — put tags in text string instead |
| `orpheus_voice_server.py` | Lines 423-424: Add BOS=128000 after SOH=128259 in voice context |
| `orpheus_voice_server.py` | Lines 468-469: Fix generation token extraction (strip SOA/SOS prefix properly) |
| Training pipeline | Re-annotate transcripts with emotion tags (e.g., `<laugh>` before laugh clips) |

---

## 7. Summary of Findings

1. **The prompt format is wrong** — the biggest issue. The current `end_tokens=[128009, 128260, 128261, 128257]` doesn't match the training format.

2. **Emotion tags are NOT special tokens** — they're regular BPE subword sequences. The HF tokenizer handles them correctly. Raw token injection is unnecessary.

3. **The finetuned model (Q8 GGUF) and pretrained model have different capabilities** — you can't get full emotion support + voice cloning from either one without further fine-tuning.

4. **The LoRA fine-tuning on 20 clips broke emotion understanding** because (a) too little data, and (b) transcripts lacked emotion tags.

5. **Best fix for immediate use:** Fix the prompt format, put emotion tags directly in the text string, and accept that the pretrained model's emotion support is limited (it generates emotional audio based on text semantics, not explicit tags).

6. **Best fix for full capability:** Re-fine-tune with properly annotated data (50-300 clips with emotion tags in every transcript), using the pretrained model as the base.
