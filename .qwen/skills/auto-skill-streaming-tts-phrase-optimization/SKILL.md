---
name: streaming-tts-phrase-optimization
description: Optimize streaming TTS pipelines that synthesize text phrase-by-phrase — remove crossfade, increase chunk sizes, stream immediately
source: auto-skill
extracted_at: '2026-06-20T15:00:00.000Z'
---

# Streaming TTS Phrase-Level Optimization

## When to use

When a streaming TTS pipeline (LLM → sentence splitter → per-phrase TTS synthesis) suffers from:
- **Slow response** — audio takes too long to start or finish
- **Voice breaks** — audible gaps or glitches between phrases
- **Too many TTS calls** — each phrase triggers a separate GPU inference

## Root causes

### 1. Crossfade between phrases causes cascading latency and artifacts

The intuitive fix for voice breaks between phrases is crossfading (blending the tail of phrase N with the head of phrase N+1). This creates two problems:

**Latency cascade:** Each phrase's audio must be held back (tail saved for crossfade with the next phrase) until the next phrase starts generating. Audio from phrase N doesn't fully stream until phrase N+1 begins, and N+1 is held for N+2, etc. The result: audio arrives late and in bursts.

**Audio artifacts:** When each phrase is synthesized independently by a neural TTS model, each phrase has its own prosody (pitch contour, rhythm, energy envelope). Crossfading between two independently-generated waveforms with mismatched prosody creates audible glitches — clicks, pops, volume jumps.

### 2. Too many small phrases

A low `flush_chars` threshold (e.g., 25 chars) causes the sentence splitter to emit 8-12 phrases for a typical 2-sentence response. Each phrase = 1 remote TTS call + 1 GPU inference pass. More phrases means:
- More network round-trips (Modal, gRPC, etc.)
- More GPU inference overhead
- More phrase boundaries = more potential voice breaks

## The fix

### A. Remove crossfade, stream audio immediately

Replace the crossfade-hold-back pattern with direct streaming:

**Before (slow, artifacts):**
```python
def synthesise_stream(self, text, ...):
    crossfade_samples = int(sample_rate * CROSSFADE_MS / 1000)
    self._prev_tail = None

    for i, phrase in enumerate(split_phrases(text)):
        audio = synthesize(phrase)

        # Hold back tail for crossfade with next phrase
        if self._prev_tail is not None:
            overlap = min(len(self._prev_tail), len(audio))
            blend = np.linspace(1.0, 0.0, overlap)
            audio[:overlap] = audio[:overlap] * (1 - blend) + self._prev_tail[-overlap:] * blend
            yield encode(self._prev_tail[:-overlap])

        # Save tail — DON'T stream it yet
        self._prev_tail = audio[-crossfade_samples:]
        yield encode(audio[:-crossfade_samples])

    # Flush final tail
    yield encode(fade_out(self._prev_tail))
```

**After (fast, clean):**
```python
def synthesise_stream(self, text, ...):
    phrases = split_phrases(text)

    for i, phrase in enumerate(phrases):
        audio = synthesize(phrase)
        if audio.size == 0:
            continue

        # Light fade only on utterance boundaries
        if i == 0:
            audio = fade_in(audio, fade_ms=15)
        if i == len(phrases) - 1:
            audio = fade_out(audio, fade_ms=15)

        # Stream immediately — no holding back
        yield from encode(audio)
```

### B. Increase phrase chunk sizes

**Sentence splitter:** Increase `flush_chars` from ~25 to ~80 characters. A typical 2-sentence LLM response goes from ~10 phrases to ~2-3 phrases.

**Synthesis chunk size:** Increase the max chars per TTS synthesis pass (e.g., 120 → 200). Longer phrases let the TTS model produce more natural prosody.

**Key tradeoff:** Larger chunks = slightly longer wait before first audio (more tokens must accumulate), but dramatically fewer TTS calls and better voice quality. For conversational AI where responses are 1-3 sentences, 80 chars hits the sweet spot.

### C. Use light fade-in/fade-out only on utterance boundaries

Instead of crossfading between every phrase, apply a very short fade (15ms) only on:
- The first phrase of the entire utterance (fade-in)
- The last phrase of the entire utterance (fade-out)

This prevents hard clicks at the start/end without introducing cross-phrase artifacts.

## Expected results

| Metric | Before | After |
|--------|--------|-------|
| Phrases per response | 8-12 | 2-3 |
| TTS remote calls | 8-12 | 2-3 |
| Voice breaks | Frequent | Rare |
| First audio latency | High (held back by crossfade) | Lower (streams immediately) |

### D. Micro-fades on every phrase (eliminates inter-phrase clicks)

Even without crossfade, there can be amplitude discontinuities between phrase N's end and phrase N+1's start, causing audible clicks. Instead of crossfading (which holds back audio), apply a **3ms fade-in + fade-out** on every phrase — imperceptible to the ear but enough to smooth any DC offset jump:

```python
# First phrase of utterance: gentle 15ms fade
# Middle phrases: 3ms micro-fade in/out
# Last phrase: gentle 15ms fade
fade_in_ms = 15 if is_first else 3
fade_out_ms = 15 if is_last else 3
phrase_audio = fade_in(phrase_audio, fade_ms=fade_in_ms, sample_rate=sample_rate)
phrase_audio = fade_out(phrase_audio, fade_ms=fade_out_ms, sample_rate=sample_rate)
```

At 48kHz, 3ms = 144 samples — completely inaudible but eliminates clicks.

### E. TTS inference speed tuning

For real-time conversational AI, prioritize speed over quality. These settings typically save 1-3s per phrase:

| Setting | Batch quality | Real-time (fast) | Why |
|---------|--------------|------------------|-----|
| `denoise` | `True` | `False` | Denoiser is a full post-processing pass — skip it |
| `retry_badcase` | `True` | `False` | Re-generates on bad outputs — adds 1-3s per retry |
| `inference_timesteps` | 20 | 12 | ~40% faster inference with minor quality loss |
| `load_denoiser` (model init) | `True` | `False` | Skips loading denoiser weights — faster cold start |

### F. First-phrase fast flush in sentence splitter

The sentence splitter's `flush_chars` threshold determines when the first phrase goes to TTS. Lowering it for the first phrase only gives earlier audio without increasing TTS call count:

```python
class SentenceSplitter:
    def __init__(self, flush_chars=55, first_flush_chars=None):
        self.flush_chars = flush_chars
        self.first_flush_chars = first_flush_chars or max(20, flush_chars // 2)
        self._first_phrase_emitted = False

    def _try_flush(self):
        # Use lower threshold for first phrase only
        threshold = self.first_flush_chars if not self._first_phrase_emitted else self.flush_chars
        # ... rest of flush logic uses `threshold` ...
        if phrase:
            self._first_phrase_emitted = True
            return phrase
```

This means: first TTS call starts at ~27 chars instead of 55 → earlier first audio. Subsequent phrases still use the normal threshold.

### G. Silence-based VAD auto end-of-turn (browser-side)

Instead of requiring the user to press a stop button, monitor audio RMS during recording and auto-send `end_turn` after ~1.4s of silence following speech:

```typescript
const SILENCE_RMS_THRESHOLD = 0.012;
const SILENCE_DURATION_S = 1.4;
const FRAME_DURATION_S = 4096 / 48000;
const SILENCE_FRAMES = Math.ceil(SILENCE_DURATION_S / FRAME_DURATION_S);

// In ScriptProcessorNode.onaudioprocess:
const rms = Math.sqrt(copy.reduce((s, v) => s + v * v, 0) / copy.length);
if (rms > SILENCE_RMS_THRESHOLD) {
  silenceState.hasSpoken = true;
  silenceState.count = 0;
} else if (silenceState.hasSpoken) {
  silenceState.count++;
  if (silenceState.count >= SILENCE_FRAMES) {
    // Auto end-of-turn
    stopRecording();
  }
}
```

Key details:
- Only trigger after `hasSpoken` is true (don't auto-stop during initial silence)
- Use a ref for the stop function to avoid stale closures in the callback
- 1.4s silence feels natural — shorter feels rushed, longer feels unresponsive
- RMS threshold ~0.012 works with browser noise suppression enabled

### H. Reduce LLM max_tokens for conversational AI

For voice assistants where responses are 1-3 sentences, lower `max_tokens` from 256 to 128. The LLM finishes sooner, so the full pipeline completes faster. Combined with a system prompt that says "keep responses short (1-3 sentences)", this is safe.

## Latency optimization summary

| Technique | Saves | Complexity |
|-----------|-------|------------|
| Remove crossfade | 1-3s cascading delay | Low |
| Increase chunk sizes | Fewer TTS calls | Low |
| Micro-fades (3ms) | Eliminates clicks | Trivial |
| Disable denoise/retry | 1-3s per phrase | Trivial |
| Lower inference_timesteps | ~40% faster inference | Trivial |
| First-phrase fast flush | 0.5-1s to first audio | Low |
| Silence-based VAD | 1-2s (no manual stop) | Medium |
| Lower LLM max_tokens | Pipeline finishes sooner | Trivial |

## Anti-patterns to avoid

- **Don't crossfade independently-synthesized phrases** — the prosody mismatch creates worse artifacts than the gap it tries to hide
- **Don't use very small flush_chars for production** — the latency savings are marginal vs. the cost of extra TTS calls
- **Don't add silence between phrases to mask gaps** — this adds dead time and sounds unnatural
- **Don't disable all fades** — the 3ms micro-fade on every phrase costs nothing and prevents clicks
- **Don't set silence threshold too low** — below 0.005 RMS picks up background noise as "speech"
- **Don't keep `retry_badcase=True` for real-time** — each retry adds 1-3s of GPU inference
