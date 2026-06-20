"""Test end-to-end audio reception through WebSocket."""
import asyncio
import websockets
import json
import time

async def test_audio():
    uri = "wss://msingi-ai--ws.modal.run/ws"
    async with websockets.connect(uri) as ws:
        print(f"Connected to {uri}")
        
        # Send text input
        await ws.send(json.dumps({
            "type": "text_input",
            "text": "Hello"
        }))
        print("Sent text input")
        
        audio_chunks = []
        text_deltas = []
        start_time = time.time()
        
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=30)
                elapsed = time.time() - start_time
                
                if isinstance(msg, bytes):
                    audio_chunks.append(msg)
                    if len(audio_chunks) == 1:
                        print(f"[OK] First audio chunk at {elapsed:.3f}s ({len(msg)} bytes)")
                    elif len(audio_chunks) <= 5:
                        print(f"     Audio chunk {len(audio_chunks)} at {elapsed:.3f}s ({len(msg)} bytes)")
                else:
                    data = json.loads(msg)
                    msg_type = data.get("type")
                    
                    if msg_type == "text_delta":
                        text_deltas.append(data.get("text", ""))
                    elif msg_type == "llm_response":
                        print(f"[OK] LLM response: {data.get('text', '')[:50]}...")
                    elif msg_type == "turn_complete":
                        print(f"[OK] Turn complete at {elapsed:.3f}s")
                        break
                    elif msg_type == "error":
                        print(f"[ERR] Error: {data.get('detail')}")
                        break
        
        except asyncio.TimeoutError:
            print(f"[ERR] Timeout after {time.time() - start_time:.1f}s")
        
        print(f"\nSummary:")
        print(f"  Text deltas: {len(text_deltas)}")
        print(f"  Audio chunks: {len(audio_chunks)}")
        print(f"  Total audio bytes: {sum(len(c) for c in audio_chunks)}")
        
        if audio_chunks:
            print(f"  [SUCCESS] Audio is streaming!")
        else:
            print(f"  [FAILURE] No audio received")

if __name__ == "__main__":
    asyncio.run(test_audio())
