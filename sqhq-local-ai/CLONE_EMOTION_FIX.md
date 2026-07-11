# 🔧 CLONE ENDPOINT EMOTION TAG FIX - 2026-07-07

## THE BUG

The **clone endpoint (`/v1/clone`)** was **silently ignoring** the `emotion` parameter!

### What Was Happening:
```python
# OrpheusCloneTTS.generate() accepted emotion parameter but NEVER used it
def generate(self, reference_audio, transcript, text, temperature, emotion=None):
    # ❌ No code to add emotion tag to text!
    # Text was passed directly to tokenizer without modification
```

### Why It Failed:
1. **OrpheusFastTTS (regular TTS)** - Properly adds emotion tags (lines 283-285):
   ```python
   if emotion and emotion in EMOTION_TAGS:
       text = f"{EMOTION_TAGS[emotion]} {text}"
   ```

2. **OrpheusCloneTTS (cloned voice)** - Missing the same logic:
   - Accepts `emotion` parameter
   - Never adds it to the text
   - Silently ignores it

---

## THE FIX

Added emotion tag processing to `OrpheusCloneTTS.generate()`:

```python
def generate(self, reference_audio: bytes, transcript: str, text: str,
             temperature: float = 0.5, emotion: str = None) -> tuple[np.ndarray, int]:
    """Clone voice from reference audio and generate speech."""
    import torch
    
    # ✅ NEW: Add emotion tag to text (same as OrpheusFastTTS)
    if emotion and emotion in EMOTION_TAGS:
        text = f"{EMOTION_TAGS[emotion]} {text}"
        print(f"[DEBUG] Clone text with emotion: {repr(text)}")
    
    # 1. Load and resample reference audio
    # ... rest of the method
```

---

## TESTING

### Before Fix:
```python
# Request
payload = {
    "text": "Hello world",
    "transcript": "Reference audio",
    "reference_audio_b64": "...",
    "emotion": "laugh"  # ❌ IGNORED
}

# Result: Normal speech (no laughing pattern)
```

### After Fix:
```python
# Request
payload = {
    "text": "Hello world",
    "transcript": "Reference audio",
    "reference_audio_b64": "...",
    "emotion": "laugh"  # ✅ PROCESSED
}

# Debug output: "[DEBUG] Clone text with emotion: '<laugh> Hello world'"
# Result: Speech with laughing pattern
```

---

## BACKWARD COMPATIBILITY

✅ **Fully backward compatible** - existing code continues to work:
- If `emotion` is not provided → no change (text used as-is)
- If `emotion` is provided but invalid → no change (ignored)
- If `emotion` is valid → tag added to text (new behavior)

---

## RECOMMENDED USAGE

Even though the endpoint now processes the `emotion` parameter, **best practice is still to put the tag IN the text**:

```python
# ✅ BEST: Tag in text (works everywhere)
payload = {
    "text": "<laugh> Hello world",
    "transcript": "...",
    "reference_audio_b64": "..."
}

# ✅ ALSO WORKS: Using emotion parameter (now processed)
payload = {
    "text": "Hello world",
    "transcript": "...",
    "reference_audio_b64": "...",
    "emotion": "laugh"
}
```

**Why?** The `emotion` parameter approach is an alias that prepends the tag to the text anyway. Putting it in the text directly is clearer and more portable.

---

## FILES MODIFIED

- `orpheus_voice_server.py` - Line 377-382: Added emotion tag processing to `OrpheusCloneTTS.generate()`

---

## STATUS

✅ **Fixed and deployed** - 2026-07-07
✅ **Server restarted** with new code
✅ **Guides updated** to reflect the fix
✅ **Fully backward compatible**
