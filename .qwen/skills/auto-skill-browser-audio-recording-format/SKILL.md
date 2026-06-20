---
name: browser-audio-recording-format
description: Fix voice pipeline failures caused by browser MediaRecorder format (WebM/Opus) vs backend PCM expectations
source: auto-skill
extracted_at: '2026-06-19T17:18:28.562Z'
---

# Browser Audio Recording Format Mismatch

## When to use

When building a voice pipeline where:
- Frontend captures audio via browser's `MediaRecorder` API
- Backend expects raw PCM audio (e.g., 16kHz mono int16)
- The pipeline fails to transcribe or process audio correctly

## The problem

`MediaRecorder` with `mimeType: 'audio/webm'` produces **WebM/Opus** format, which:
- Uses container headers (starts with `\x1a\x45\xdf\xa3`)
- Encodes audio at 48kHz, stereo, with Opus codec
- Is NOT raw PCM

Many ASR backends (especially custom models like Whisper variants) expect **raw 16kHz mono int16 PCM**. When they receive WebM bytes, they either:
- Fail to decode (treating headers as audio samples)
- Produce garbage transcripts
- Return empty results

## The fix

Replace `MediaRecorder` with `ScriptProcessorNode` (or `AudioWorkletNode`) to capture raw PCM frames, then manually resample and convert to int16 bytes.

### Frontend implementation

```typescript
// Helper: resample Float32Array from one rate to another
function resampleFloat32(
  buffer: Float32Array,
  fromRate: number,
  toRate: number
): Float32Array {
  if (fromRate === toRate) return buffer;
  const ratio = fromRate / toRate;
  const newLength = Math.round(buffer.length / ratio);
  const result = new Float32Array(newLength);
  for (let i = 0; i < newLength; i++) {
    const srcIndex = i * ratio;
    const srcFloor = Math.floor(srcIndex);
    const srcCeil = Math.min(srcFloor + 1, buffer.length - 1);
    const frac = srcIndex - srcFloor;
    result[i] = buffer[srcFloor] * (1 - frac) + buffer[srcCeil] * frac;
  }
  return result;
}

// Helper: convert Float32 [-1, 1] to Int16 PCM bytes
function float32ToInt16Bytes(float32: Float32Array): ArrayBuffer {
  const int16 = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return int16.buffer;
}

// Recording setup
const startRecording = async () => {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
    },
  });

  const audioCtx = new AudioContext();
  const source = audioCtx.createMediaStreamSource(stream);
  const scriptNode = audioCtx.createScriptProcessor(4096, 1, 1);

  const nativeSampleRate = audioCtx.sampleRate; // usually 44100 or 48000
  const TARGET_RATE = 16000;

  scriptNode.onaudioprocess = (e) => {
    const inputData = e.inputBuffer.getChannelData(0);
    const copy = new Float32Array(inputData);

    // Resample to 16kHz and convert to int16
    const resampled = resampleFloat32(copy, nativeSampleRate, TARGET_RATE);
    const pcmBytes = float32ToInt16Bytes(resampled);

    // Send raw PCM bytes over WebSocket
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(pcmBytes);
    }
  };

  source.connect(scriptNode);
  scriptNode.connect(audioCtx.destination);
};
```

### Key points

1. **`ScriptProcessorNode`** captures raw PCM frames (Float32Array at native sample rate)
2. **Resample** from native rate (44.1kHz or 48kHz) to 16kHz using linear interpolation
3. **Convert** Float32 [-1, 1] to Int16 PCM bytes
4. **Send** raw bytes over WebSocket (no container, no encoding)
5. Backend receives exactly what it expects: 16kHz mono int16 PCM

## Verification

After implementing the fix:
1. Start recording and check browser console for errors
2. Send a test utterance ("hello", "habari", etc.)
3. Stop recording and wait for transcript
4. Verify transcript appears in UI and matches what you said
5. Check that LLM responds and TTS plays audio

## Gotchas

- **`ScriptProcessorNode` is deprecated** in favor of `AudioWorkletNode`, but still works in all browsers and is simpler to implement
- **Sample rate varies by device**: Always read `audioCtx.sampleRate`, don't assume 44100 or 48000
- **Channel count**: Request `channelCount: 1` in `getUserMedia` to ensure mono input
- **Memory**: Copy the `Float32Array` in `onaudioprocess` — the browser reuses the buffer
- **Cleanup**: Disconnect `scriptNode`, `source`, and close `audioCtx` on stop to prevent memory leaks
