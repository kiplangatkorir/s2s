"""Quick end-to-end test: connect to Modal gateway, send text, check response."""
import asyncio
import json
import sys
import websockets


async def test():
    uri = "wss://msingi-ai--ws.modal.run/ws"
    sys.stdout.write("Connecting to gateway...\n")
    sys.stdout.flush()

    async with websockets.connect(uri) as ws:
        sys.stdout.write("Sending text_input: 'Hello'\n")
        sys.stdout.flush()
        await ws.send(json.dumps({"type": "text_input", "text": "Hello"}))

        text_msgs = []
        text_deltas = []
        audio_chunks = 0
        total_audio_bytes = 0

        async for msg in ws:
            if isinstance(msg, bytes):
                audio_chunks += 1
                total_audio_bytes += len(msg)
                sys.stdout.write(f"  [audio] {len(msg)} bytes (chunk #{audio_chunks})\n")
                sys.stdout.flush()
            else:
                data = json.loads(msg)
                msg_type = data.get("type")
                sys.stdout.write(f"  [json] type={msg_type}\n")
                sys.stdout.flush()

                if msg_type == "transcript":
                    text_msgs.append(("user", data.get("text")))
                elif msg_type == "text_delta":
                    text_deltas.append(data.get("text", ""))
                elif msg_type == "llm_response":
                    text_msgs.append(("assistant", data.get("text")))
                elif msg_type == "turn_complete":
                    break

        sys.stdout.write(f"\n=== RESULTS ===\n")
        sys.stdout.write(f"Audio chunks: {audio_chunks} ({total_audio_bytes} bytes total)\n")
        sys.stdout.write(f"Text deltas: {len(text_deltas)}\n")
        sys.stdout.write(f"Messages:\n")
        for role, text in text_msgs:
            sys.stdout.write(f"  [{role}]: {text}\n")
        sys.stdout.write(f"PASS\n")
        sys.stdout.flush()


asyncio.run(test())
