"""Simple benchmark harness for TTFT / TTFA measurement."""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from shared.metrics import LatencyTracker


def simulate_turn(delay_ms: int, llm_ttft_ms: int = 120, first_audio_ms: int = 250) -> dict:
    """Simulate one pipeline turn and return latency metrics."""
    tracker = LatencyTracker(session_id="benchmark")
    tracker.mark("pipeline_start")

    time.sleep(delay_ms / 1000.0)
    tracker.mark("asr_start")
    time.sleep(0.02)
    tracker.mark("asr_end")

    tracker.mark("llm_start")
    time.sleep(llm_ttft_ms / 1000.0)
    tracker.mark("llm_first_token")
    time.sleep(0.03)
    tracker.mark("llm_end")

    time.sleep(first_audio_ms / 1000.0)
    tracker.mark("first_audio_byte")
    tracker.mark("pipeline_end")

    return tracker.to_dict()


def main(iterations: int = 5) -> None:
    samples = [simulate_turn(delay_ms=80) for _ in range(iterations)]
    ttfa = [item["ttfa_ms"] or 0 for item in samples]
    ttft = [item["llm_ttft_ms"] or 0 for item in samples]
    turn_total = [item["turn_total_ms"] or 0 for item in samples]

    print("Latency benchmark (ms)")
    print("-" * 40)
    print(f"TTFA average : {statistics.mean(ttfa):.1f}")
    print(f"TTFA min     : {min(ttfa):.1f}")
    print(f"TTFA max     : {max(ttfa):.1f}")
    print(f"LLM TTFT avg : {statistics.mean(ttft):.1f}")
    print(f"Turn total avg: {statistics.mean(turn_total):.1f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Measure pipeline latency")
    parser.add_argument("--iterations", type=int, default=5)
    args = parser.parse_args()
    main(iterations=args.iterations)
