import asyncio
import websockets
import json
import time

async def test():
    async with websockets.connect('wss://msingi-ai--ws.modal.run/ws') as ws:
        print('Connected')
        t0 = time.time()
        
        # Send long Swahili text
        long_text = "Habari yako leo? Nimekuona ukitembea mjini na nilitaka kukuuliza kuhusu safari yako."
        await ws.send(json.dumps({'type': 'text_input', 'text': long_text}))
        print(f'Sent long text: {long_text[:50]}...')
        
        audio_count = 0
        first_audio_time = None
        
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=65)
                elapsed = (time.time() - t0) * 1000
                
                if isinstance(msg, bytes):
                    audio_count += 1
                    if first_audio_time is None:
                        first_audio_time = elapsed
                        print(f'[{elapsed:.0f}ms] AUDIO #1: {len(msg)} bytes')
                    elif audio_count <= 3:
                        print(f'[{elapsed:.0f}ms] AUDIO #{audio_count}: {len(msg)} bytes')
                else:
                    data = json.loads(msg)
                    mtype = data.get('type')
                    
                    if mtype == 'transcript':
                        print(f'[{elapsed:.0f}ms] transcript: {data["text"][:60]}...')
                    elif mtype == 'llm_response':
                        print(f'[{elapsed:.0f}ms] llm_response: {data["text"][:60]}...')
                    elif mtype == 'turn_complete':
                        print(f'[{elapsed:.0f}ms] turn_complete')
                        print(f'\nResults:')
                        print(f'  First audio: {first_audio_time:.0f}ms' if first_audio_time else '  First audio: NEVER')
                        print(f'  Total audio chunks: {audio_count}')
                        print(f'  Total time: {elapsed:.0f}ms')
                        break
                    elif mtype == 'error':
                        print(f'[{elapsed:.0f}ms] ERROR: {data["detail"]}')
                        break
                        
            except asyncio.TimeoutError:
                print(f'\nTimeout after 65s')
                print(f'  First audio: {first_audio_time:.0f}ms' if first_audio_time else '  First audio: NEVER')
                print(f'  Total audio chunks: {audio_count}')
                break

asyncio.run(test())
