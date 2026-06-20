"""Test all possible Modal WebSocket URL patterns to find which one works."""
import asyncio
import websockets

URLS = [
    "wss://msingi-ai--ws.modal.run/ws",
    "wss://msingi-ai--ws.modal.run/web/ws",
    "wss://msingi-ai--msingiai-sauti-gateway-asgi-app.modal.run/ws",
    "wss://msingi-ai--msingiai-sauti-gateway-asgi-app.modal.run/web/ws",
    "wss://msingiai-sauti-gateway--asgi-app.modal.run/ws",
    "wss://msingiai-sauti-gateway--asgi-app.modal.run/web/ws",
]

async def test_url(url):
    try:
        ws = await asyncio.wait_for(
            websockets.connect(url),
            timeout=15,
        )
        await ws.send('{"type":"text_input","text":"hi"}')
        msg = await asyncio.wait_for(ws.recv(), timeout=20)
        await ws.close()
        print(f"  OK   {url}")
        print(f"       Response: {msg[:100]}")
        return True
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"  {e.status_code}   {url}")
        return False
    except asyncio.TimeoutError:
        print(f"  TIMEOUT {url}")
        return False
    except Exception as e:
        print(f"  ERR  {url} -> {type(e).__name__}: {e}")
        return False

async def main():
    print("Testing WebSocket URLs against Modal gateway:\n")
    for url in URLS:
        await test_url(url)

asyncio.run(main())
