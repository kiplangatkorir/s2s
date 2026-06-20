import asyncio
import websockets
import json
import time

URL = "wss://msingi-ai--ws.modal.run/ws"

async def test():
    async with websockets.connect(URL) as ws:
        t0 = time.perf_counter()
        await ws.send(json.dumps({"type": "text_input", "text": "Habari yako leo? Nimekuona ukitembea mjini na nilitaka kukuuliza kuhusu safari yako."}))

        chunks = []
        first_audio = None
        msg_count = 0

        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=60)
            except asyncio.TimeoutError:
                print("TIMEOUT waiting for message")
                break

            msg_count += 1
            elapsed = (time.perf_counter() - t0) * 1000

            if isinstance(msg, bytes):
                if first_audio is None:
                    first_audio = elapsed
                chunks.append((elapsed, len(msg)))
            elif isinstance(msg, str):
                data = json.loads(msg)
                mtype = data.get("type", "?")
                if mtype == "transcript":
                    print(f"  [{elapsed:7.0f}ms] transcript: {data.get('text','')[:60]}")
                elif mtype == "text_delta":
                    pass
                elif mtype == "llm_response":
                    print(f"  [{elapsed:7.0f}ms] llm_response: {data.get('text','')[:80]}")
                elif mtype == "turn_complete":
                    print(f"  [{elapsed:7.0f}ms] turn_complete")
                    break
                elif mtype == "error":
                    print(f"  [{elapsed:7.0f}ms] ERROR: {data.get('detail','')}")
                    break
                elif mtype == "ping":
                    await ws.send(json.dumps({"type": "pong"}))
                else:
                    print(f"  [{elapsed:7.0f}ms] {mtype}")

        print(f"\nResults:")
        print(f"  First audio:  {first_audio:.0f}ms" if first_audio else "  First audio:  NEVER")
        print(f"  Total chunks: {len(chunks)}")

        if len(chunks) >= 2:
            gaps = [chunks[i][0] - chunks[i-1][0] for i in range(1, len(chunks))]
            max_gap = max(gaps)
            avg_gap = sum(gaps) / len(gaps)
            print(f"  Avg gap:      {avg_gap:.0f}ms")
            print(f"  Max gap:      {max_gap:.0f}ms")
            print(f"  Total audio:  {(chunks[-1][0] - chunks[0][0]):.0f}ms")

            big_gaps = [(i, g) for i, g in enumerate(gaps) if g > 500]
            if big_gaps:
                print(f"  Gaps > 500ms: {len(big_gaps)}")
                for i, g in big_gaps[:5]:
                    print(f"    chunk {i} to {i+1}: {g:.0f}ms (at {chunks[i][0]:.0f}ms)")
            else:
                print(f"  Gaps > 500ms: none (smooth!)")

asyncio.run(test())
