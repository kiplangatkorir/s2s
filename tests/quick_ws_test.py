import asyncio
import websockets
import json
import time

async def test():
    async with websockets.connect('wss://msingi-ai--ws.modal.run/ws') as ws:
        print('Connected')
        t0 = time.time()
        await ws.send(json.dumps({'type': 'text_input', 'text': 'Hi'}))
        print('Sent text_input')
        
        # Wait for first message
        msg = await asyncio.wait_for(ws.recv(), timeout=30)
        elapsed = (time.time() - t0) * 1000
        print(f'First msg in {elapsed:.0f}ms: {str(msg)[:150]}')
        
        # Get a few more messages
        for i in range(5):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=10)
                elapsed = (time.time() - t0) * 1000
                if isinstance(msg, bytes):
                    print(f'  [{elapsed:.0f}ms] audio chunk: {len(msg)} bytes')
                else:
                    print(f'  [{elapsed:.0f}ms] {str(msg)[:100]}')
            except asyncio.TimeoutError:
                print(f'  Timeout after 10s')
                break

asyncio.run(test())
