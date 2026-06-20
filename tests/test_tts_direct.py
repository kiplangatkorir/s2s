"""Test TTS directly with longer text to isolate the timeout issue."""
import asyncio
import modal
import time

SautiTTS = modal.Cls.from_name("msingiai-sauti-tts", "SautiTTS")
tts = SautiTTS()

# Short text (works)
short_text = "Habari yako?"
# Long text (times out)
long_text = "Habari yako leo? Nimekuona ukitembea mjini na nilitaka kukuuliza kuhusu safari yako."

async def test_tts(text, label):
    print(f"\n{'='*60}")
    print(f"Testing: {label}")
    print(f"Text: {text[:80]}...")
    print(f"{'='*60}")
    
    t0 = time.perf_counter()
    chunk_count = 0
    total_bytes = 0
    
    try:
        async for chunk in tts.synthesise_stream.remote_gen.aio(text, language="sw"):
            chunk_count += 1
            total_bytes += len(chunk)
            if chunk_count == 1:
                elapsed = (time.perf_counter() - t0) * 1000
                print(f"  First chunk: {elapsed:.0f}ms ({len(chunk)} bytes)")
            elif chunk_count % 50 == 0:
                elapsed = (time.perf_counter() - t0) * 1000
                print(f"  Chunk {chunk_count}: {elapsed:.0f}ms")
        
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"  DONE: {chunk_count} chunks, {total_bytes} bytes in {elapsed:.0f}ms")
        return True
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"  ERROR after {elapsed:.0f}ms: {type(e).__name__}: {e}")
        return False

async def main():
    print("Testing TTS with short and long text...")
    
    short_ok = await test_tts(short_text, "Short text")
    long_ok = await test_tts(long_text, "Long text")
    
    print(f"\n{'='*60}")
    print(f"Results:")
    print(f"  Short: {'PASS' if short_ok else 'FAIL'}")
    print(f"  Long:  {'PASS' if long_ok else 'FAIL'}")
    print(f"{'='*60}")

asyncio.run(main())
