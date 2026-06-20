"""Quick test to verify new TTS buffering code is running."""
import asyncio
import modal
import time

async def main():
    SautiTTS = modal.Cls.from_name("msingiai-sauti-tts", "SautiTTS")
    tts = SautiTTS()
    
    text = "Habari yako?"
    
    print(f"Generating TTS for: {text}")
    print("Waiting for first chunk...")
    
    t0 = time.time()
    chunk_count = 0
    total_bytes = 0
    
    async for chunk in tts.synthesise_stream.remote_gen.aio(text, language="sw"):
        chunk_count += 1
        total_bytes += len(chunk)
        elapsed = time.time() - t0
        
        if chunk_count == 1:
            print(f"  First chunk: {elapsed:.2f}s, {len(chunk)} bytes")
        elif chunk_count % 10 == 0:
            print(f"  Chunk {chunk_count}: {elapsed:.2f}s, {len(chunk)} bytes")
    
    print(f"\nComplete: {chunk_count} chunks, {total_bytes} bytes in {time.time() - t0:.2f}s")

if __name__ == "__main__":
    asyncio.run(main())
