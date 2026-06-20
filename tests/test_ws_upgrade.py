"""Test raw WebSocket upgrade request like a browser would send (HTTP/1.1)."""
import http.client
import ssl
import base64
import os

host = "msingi-ai--ws.modal.run"
path = "/ws"

ctx = ssl.create_default_context()
conn = http.client.HTTPSConnection(host, timeout=30, context=ctx)

key = base64.b64encode(os.urandom(16)).decode()

headers = {
    "Upgrade": "websocket",
    "Connection": "Upgrade",
    "Sec-WebSocket-Version": "13",
    "Sec-WebSocket-Key": key,
    "Origin": "https://s2s-henna.vercel.app",
}

print(f"Sending WebSocket upgrade to {host}{path}...", flush=True)
conn.request("GET", path, headers=headers)
resp = conn.getresponse()

print(f"Status: {resp.status} {resp.reason}", flush=True)
print(f"Headers:", flush=True)
for name, value in resp.getheaders():
    print(f"  {name}: {value}", flush=True)

if resp.status == 101:
    print("\nWebSocket upgrade SUCCESS!", flush=True)
    conn.close()
else:
    body = resp.read(500)
    print(f"\nBody: {body[:300]}", flush=True)
    conn.close()
