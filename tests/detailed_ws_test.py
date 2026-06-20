import asyncio
import websockets
import json
import time

async def test():
    async with websockets.connect('wss://msingi-ai--ws.modal.run/ws') as ws:
        print('Connected')
        t0 = time.time()
        await ws.send(json.dumps({'type': 'text_input', 'text': 'Hello there'}))
        print('Sent text_input\n')
        
        audio_count = 0
        msg_count = 0
        
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=60)
                elapsed = (time.time() - t0) * 1000
                msg_count += 1
                
                if isinstance(msg, bytes):
                    audio_count += 1
                    if audio_count <= 3:
                        print(f'[{elapsed:7.0f}ms] AUDIO #{audio_count}: {len(msg)} bytes')
                else:
                    data = json.loads(msg)
                    mtype = data.get('type', '?')
                    
                    if mtype == 'transcript':
                        print(f'[{elapsed:7.0f}ms] {mtype}: {data.get("text","")[:50]}')
                    elif mtype == 'text_delta':
                        pass  # too noisy
                    elif mtype == 'llm_response':
                        print(f'[{elapsed:7.0f}ms] {mtype}: {data.get("text","")[:80]}')
                    elif mtype == 'turn_complete':
                        print(f'[{elapsed:7.0f}ms] {mtype}')
                        break
                    elif mtype == 'error':
                        print(f'[{elapsed:7.0f}ms] ERROR: {data.get("detail","")}')
                        break
                    elif mtype == 'ping':
                        await ws.send(json.dumps({'type': 'pong'}))
                    else:
                        print(f'[{elapsed:7.0f}ms] {mtype}: {str(data)[:100]}')
                        
            except asyncio.TimeoutError:
                print(f'\nTimeout after 60s')
                break
        
        print(f'\nTotal messages: {msg_count}')
        print(f'Total audio chunks: {audio_count}')

asyncio.run(test())
