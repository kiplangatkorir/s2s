# sauti-s2s

A streaming speech-to-speech pipeline designed to behave more like the top voice AI stacks used in production: low-latency ASR, streamed LLM responses, phrase-level TTS, and interruptible barge-in.

## What "top-lab quality" means here

We are targeting the same core design patterns used by leading voice systems:

- Streaming-first ASR: emit partial transcripts as the user speaks.
- Streaming LLM: use token streaming instead of waiting for the full answer.
- Phrase-level TTS: flush short chunks early so playback starts before the full sentence is complete.
- Barge-in: stop TTS and LLM generation immediately when the user starts talking again.
- Warm GPU workers: keep Modal functions warm to avoid cold-start penalties.
- Metrics-driven tuning: track TTFT, TTFA, and end-to-end turn latency.

## Current architecture

- modal_apps/sauti_asr.py: GPU-backed Track A Whisper/Paza ASR from Modal volume `sauti-asr-checkpoints`, mounted at `/ckpts/track_a_whisper_paza_full`
- modal_apps/sauti_tts.py: GPU-backed VoxCPM2 Swahili LoRA TTS from Modal volume `sauti-tts-v2-data`, mounted at `/vol/checkpoints/voxcpm2_sw_lora_waxal_s300/latest`
- pipeline/orchestrator.py: coordinates ASR → LLM → TTS
- pipeline/sentence_splitter.py: flushes phrase-sized chunks for fast audio start
- pipeline/barge_in.py: interruption handling for user barge-in
- shared/metrics.py: TTFT / TTFA / turn-time measurement

## Latency targets

- TTFA (time to first audio): aim for under 800 ms in a warm environment
- TTFT (time to first token): keep the LLM response path low and stable
- End-to-end turn latency: measure and iterate with the benchmark harness

## Benchmarking

Run the benchmark from the repo root:

python tests/benchmarks/measure_latency.py --iterations 5

This gives a repeatable baseline for TTFA and TTFT while we tune the pipeline.

## Gateway deployment

The gateway path in [gateway/ws_server.py](gateway/ws_server.py) delegates to [pipeline/orchestrator.py](pipeline/orchestrator.py), which reads `DEEPSEEK_API_KEY` from the runtime environment. That means the gateway must be started with the key available locally or run on Modal with the secret attached to the same process.

The Modal deployment wrapper is [gateway/modal_app.py](gateway/modal_app.py). It attaches the Modal secret named `deepseek`, which must contain `DEEPSEEK_API_KEY`.

Deploy the gateway with:

python -m modal deploy gateway/modal_app.py

## Production mindset

The real goal is not a batch pipeline that waits for full sentences. The goal is a voice stack that feels continuous: speech arrives, partial text appears, tokens stream, the first phrase plays quickly, and the user can interrupt naturally.

