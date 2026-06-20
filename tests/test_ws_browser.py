"""Test WebSocket with browser-like headers to reproduce the 404 issue."""
import asyncio
import websockets

URL = "wss://msingi-ai--ws.modal.run/ws"

async def test_with_headers(origin, label):
    try:
        ws = await asyncio.wait_for(
            websockets.connect(
                URL,
                additional_headers={
                    "Origin": origin,
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                },
            ),
            timeout=15,
        )
        await ws.send('{"type":"text_input","text":"hi"}')
        msg = await asyncio.wait_for(ws.recv(), timeout=20)
        await ws.close()
        print(f"  {label}: OK -> {msg[:80]}")
    except Exception as e:
        print(f"  {label}: FAIL -> {type(e).__name__}: {e}")

async def main():
    print("Testing with browser-like headers:\n")
    await test_with_headers("https://s2s-henna.vercel.app", "Vercel origin")
    await test_with_headers("http://localhost:3000", "Localhost origin")
    await test_with_headers("", "Empty origin")
    print("\nTesting without Origin (bare connect):\n")
    try:
        ws = await asyncio.wait_for(websockets.connect(URL), timeout=15)
        print(f"  Bare connect: OK")
        await ws.close()
    except Exception as e:
        print(f"  Bare connect: FAIL -> {e}")

asyncio.run(main())
