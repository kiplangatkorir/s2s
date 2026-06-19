import time

from shared.metrics import LatencyTracker


def test_latency_tracker_exposes_ttft_and_ttfa_aliases():
    tracker = LatencyTracker("bench-session")
    tracker.mark("pipeline_start")
    time.sleep(0.01)
    tracker.mark("asr_start")
    time.sleep(0.01)
    tracker.mark("asr_end")
    tracker.mark("llm_start")
    tracker.mark("llm_first_token")
    tracker.mark("first_audio_byte")
    tracker.mark("pipeline_end")

    metrics = tracker.to_dict()

    assert metrics["asr_ms"] is not None
    assert metrics["llm_ttft_ms"] is not None
    assert metrics["ttfa_ms"] is not None
    assert metrics["time_to_audio_ms"] == metrics["ttfa_ms"]
