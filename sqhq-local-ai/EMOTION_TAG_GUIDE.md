# 🎭 ORPHEUS TTS EMOTION TAGS - EXACT GUIDE

## THE PROBLEM

**Wrong approach (what Cyony does):**
```python
# ❌ WRONG: Stripping tags or not sending them properly
text = "Hello world"
# Or worse:
text = "Hello <laugh> world"  # But the model sees it wrong
```

**Right approach (what actually works):**
```python
# ✅ CORRECT: Tags must be IN the text, properly formatted
text = "<laugh> Hello world"
```

---

## THE EXACT FORMAT

### 1. API Request Format (POST /v1/tts)

**Wrong:**
```json
{
  "text": "Hello world",
  "voice": "tara",
  "emotion": "laugh"  // ❌ WRONG: This field is ignored for regular TTS
}
```

**Right:**
```json
{
  "text": "<laugh> Hello world",  // ✅ Tag IN the text
  "voice": "tara"
}
```

### 2. Using Mood (Auto-Adds Emotion)

**Wrong:**
```json
{
  "text": "This is funny",  // ❌ Mood needs explicit text with tag
  "mood": "excited"
}
```

**Right:**
```json
{
  "text": "<laugh> This is funny!",  // ✅ Mood + tag
  "voice": "tara",
  "mood": "excited"  // Auto-increases temperature
}
```

### 3. Multiple Emotions in Text

**Wrong:**
```json
{
  "text": "Hello <laugh> how are you <sigh>"  // ❌ Multiple tags break format
}
```

**Right:**
```json
{
  "text": "<laugh> Hey there! <sigh> How's it going?"  // ✅ Tags in text
}
```

### 4. Voice Cloning with Emotions (POST /v1/clone)

**Wrong:**
```json
{
  "text": "Hello world",
  "transcript": "Reference audio transcript",
  "reference_audio_b64": "...",
  "emotion": "laugh"  // ❌ WAS ignored (fixed 2026-07-07)
}
```

**Right:**
```json
{
  "text": "<laugh> Hello world",  // ✅ Tag IN the text
  "transcript": "Reference audio transcript",
  "reference_audio_b64": "..."
}
```

**Note:** As of 2026-07-07, the clone endpoint now processes emotion tags correctly. But for best results, always put the tag IN the text field.

---

## THE EXACT PROMPT FORMAT

The model expects this **exact format**:

```
<|audio|>tara: <laugh> Hello world<|eot_id|><custom_token_4>
```

**Critical parts:**
1. `<|audio|>` - Start marker (must be first)
2. `{voice}:` - Voice name with colon
3. `{text}` - Text with emotion tags
4. `<|eot_id|>` - End of text marker
5. `<custom_token_4>` - Start audio generation

**If any part is missing or wrong, the model reads tags as literal text!**

---

## COMPLETE WORKING EXAMPLES

### Example 1: Simple Laugh
```python
import requests

url = "http://100.72.250.65:5000/v1/tts"

# ✅ CORRECT FORMAT
payload = {
    "text": "<laugh> Hey there! How's it going?",
    "voice": "tara"
}

response = requests.post(url, json=payload)
# Returns: audio/wav with laughing speech
```

### Example 2: Giggle
```python
payload = {
    "text": "<giggle> That's so funny! I love it!",
    "voice": "leah"
}
response = requests.post(url, json=payload)
```

### Example 3: Sigh (Sad)
```python
payload = {
    "text": "<sigh> I guess that's just how it is...",
    "voice": "tara",
    "mood": "sad"  # Auto-adds <sigh> + lowers temperature
}
response = requests.post(url, json=payload)
```

### Example 4: Multiple Emotions
```python
payload = {
    "text": "<giggle> Wait, what? <sigh> Oh no...",
    "voice": "leo"
}
response = requests.post(url, json=payload)
```

---

## AVAILABLE EMOTION TAGS

| Tag | Effect | Best Voices |
|-----|--------|-------------|
| `<laugh>` | Laughing speech | All |
| `<chuckle>` | Light chuckle | All |
| `<giggle>` | Higher pitched giggle | leah, mia, zoe |
| `<sigh>` | Sighing, melancholy | All |
| `<groan>` | Deep groan | leo, dan, zac |
| `<yawn>` | Yawning | All |
| `<gasp>` | Startled gasp | All |
| `<cough>` | Coughing | leo, dan |
| `<sniffle>` | Sniffling | All |

---

## MOOD PRESETS (Auto-Adds Emotions)

| Mood | Temperature | Emotion Added | Description |
|------|-------------|---------------|-------------|
| `warm_calm` | 0.5 | None | Gentle, soothing |
| `excited` | 0.9 | `<laugh>` | High energy, joyful |
| `sad` | 0.4 | `<sigh>` | Melancholy, slow |
| `whisper_intimate` | 0.3 | None | Very soft, close |
| `angry` | 0.85 | `<groan>` | Sharp, forceful |
| `playful` | 0.8 | `<chuckle>` | Light, teasing |
| `serious` | 0.4 | None | Professional, measured |
| `vulnerable` | 0.5 | `<sigh>` | Open, emotional |
| `annoyed` | 0.6 | `<groan>` | Irritated, clipped |
| `storytelling` | 0.7 | None | Narrative, varied |
| `surprised` | 0.85 | `<gasp>` | Startled, sudden |
| `tired` | 0.3 | `<yawn>` | Low energy, slow |

---

## COMMON MISTAKES

### ❌ Mistake 1: Tag Not in Text
```python
# WRONG
payload = {
    "text": "Hello world",  # No tag
    "emotion": "laugh"  # Ignored!
}

# RIGHT
payload = {
    "text": "<laugh> Hello world"  # Tag IN text
}
```

### ❌ Mistake 2: Wrong Prompt Format
```python
# WRONG
prompt = f"User: {text}"  # Missing <|audio|> and voice format

# RIGHT
prompt = f"<|audio|>{voice}: {text}<|eot_id|><custom_token_4>"
```

### ❌ Mistake 3: Stripping Tags Before Sending
```python
# WRONG
text = "Hello <laugh> world"
text = text.replace("<laugh>", "")  # Strips the tag!

# RIGHT
text = "Hello <laugh> world"  # Keep the tag!
```

### ❌ Mistake 4: Using Wrong Model
```python
# WRONG
model = "Q4_K_M"  # Tags don't work well

# RIGHT
model = "Q8_0"  # Tags work perfectly
```

### ❌ Mistake 5: Not Using Voice Format
```python
# WRONG
prompt = f"{text}<|eot_id|><custom_token_4>"  # Missing <|audio|> and voice

# RIGHT
prompt = f"<|audio|>{voice}: {text}<|eot_id|><custom_token_4>"
```

---

## DEBUGGING

### Check if tags are in text:
```python
print(f"Text: {repr(text)}")
print(f"Tags found: {[t for t in ['<laugh>', '<giggle>', '<sigh>'] if t in text]}")
```

### Check what the model sees:
```python
prompt = f"<|audio|>{voice}: {text}<|eot_id|><custom_token_4>"
print(f"Prompt: {repr(prompt)}")
```

### Expected output:
```
Prompt: '<|audio|>tara: <laugh> Hey there!<|eot_id|><custom_token_4>'
```

### If tags are missing:
```python
# Add the tag
text = f"<laugh> {text}"
```

---

## QUICK REFERENCE

**To make TTS with laugh:**
1. Add `<laugh>` to the **start** of your text
2. Send as `POST /v1/tts` with `{"text": "<laugh> Your text", "voice": "tara"}`
3. The model will generate laughing speech

**To make TTS with giggle:**
1. Add `<giggle>` to the start of your text
2. Send with `{"text": "<giggle> Your text", "voice": "leah"}`

**To make TTS with sigh:**
1. Add `<sigh>` to the start
2. Send with `{"text": "<sigh> Your text", "voice": "tara"}`

---

## THE GOLDEN RULE

**Tags go IN the text, not in separate fields!**

```python
# ✅ CORRECT
payload = {
    "text": "<laugh> Hello world",  # Tag here
    "voice": "tara"
}

# ❌ WRONG
payload = {
    "text": "Hello world",
    "emotion": "laugh"  # NOT HERE
}
```

**That's it!** If the tag is in the text, the model will perform it. 🎭
