"""Analyze TTS audio output for clicks and discontinuities."""
import asyncio
import modal
import numpy as np
import wave
import tempfile

async def main():
    SautiTTS = modal.Cls.from_name("msingiai-sauti-tts", "SautiTTS")
    tts = SautiTTS()
    
    # Test with longer text
    text = "Habari yako leo? Nimekuona ukitembea mjini na nilitaka kukuuliza kuhusu safari yako."
    
    print(f"Generating TTS for: {text[:60]}...")
    print("This may take a moment...")
    
    chunks = []
    chunk_count = 0
    async for chunk in tts.synthesise_stream.remote_gen.aio(text, language="sw"):
        chunks.append(chunk)
        chunk_count += 1
        if chunk_count % 10 == 0:
            print(f"  Received chunk {chunk_count}...")
    
    print(f"\nTotal chunks: {chunk_count}")
    print(f"Total bytes: {sum(len(c) for c in chunks)}")
    
    # Combine all chunks
    audio_bytes = b''.join(chunks)
    
    # Convert to numpy array (16-bit PCM)
    audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
    
    # Save to WAV file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        wav_path = f.name
        with wave.open(wav_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(48000)
            wf.writeframes(audio_bytes)
    
    print(f"\nSaved to: {wav_path}")
    print(f"Duration: {len(audio_array) / 48000:.2f} seconds")
    
    # Analyze for discontinuities
    print("\nAnalyzing for discontinuities...")
    
    # Calculate sample-to-sample differences
    diffs = np.abs(np.diff(audio_array.astype(np.int32)))
    
    # Find large jumps (potential clicks)
    threshold = 5000  # Large amplitude jump
    click_locations = np.where(diffs > threshold)[0]
    
    print(f"Found {len(click_locations)} potential click locations (diff > {threshold})")
    
    if len(click_locations) > 0:
        print("\nFirst 10 click locations:")
        for i, loc in enumerate(click_locations[:10]):
            time_ms = loc / 48.0  # Convert to milliseconds
            print(f"  {i+1}. Sample {loc} ({time_ms:.1f}ms): jump of {diffs[loc]}")
    
    # Check for silence gaps
    window_size = 480  # 10ms window
    silence_threshold = 100
    
    silent_windows = []
    for i in range(0, len(audio_array) - window_size, window_size):
        window = audio_array[i:i+window_size]
        if np.max(np.abs(window)) < silence_threshold:
            silent_windows.append(i)
    
    print(f"\nFound {len(silent_windows)} silent windows (10ms each)")
    
    if len(silent_windows) > 0:
        print("First 5 silent windows:")
        for i, loc in enumerate(silent_windows[:5]):
            time_ms = loc / 48.0
            print(f"  {i+1}. Sample {loc} ({time_ms:.1f}ms)")
    
    print("\nOpen the WAV file to listen and inspect the waveform.")

if __name__ == "__main__":
    asyncio.run(main())
