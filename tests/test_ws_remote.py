import asyncio
import websockets
import sys

async def test():
    print("Starting WS test...", flush=True)
    try:
        ws = await asyncio.wait_for(
            websockets.connect("wss://msingi-ai--ws.modal.run/ws"),
            timeout=20
        )
        print("Connected!", flush=True)
        await ws.send('{"type":"text_input","text":"hi"}')
        msg = await asyncio.wait_for(ws.recv(), timeout=30)
        print(f"Got: {msg}", flush=True)
        await ws.close()
        print("Done", flush=True)
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}", flush=True)

asyncio.run(test())
