import json

from fastapi.testclient import TestClient

from gateway.ws_server import create_app


class FakePipeline:
    def __init__(self, session_id: str):
        self.session_id = session_id

    async def run(self, audio_bytes: bytes):
        yield b"fake-audio" + audio_bytes[:2]


def test_gateway_streams_binary_audio_for_end_turn():
    client = TestClient(create_app(lambda sid: FakePipeline(sid)))

    with client.websocket_connect("/ws?session_id=demo") as websocket:
        websocket.send_bytes(b"abc")
        websocket.send_text(json.dumps({"type": "end_turn"}))

        first = websocket.receive_bytes()
        second = websocket.receive_json()

        assert first == b"fake-audio" + b"ab"
        assert second == {"type": "turn_complete", "session_id": "demo"}
