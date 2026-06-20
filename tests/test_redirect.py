import httpx
import sys

client = httpx.Client(timeout=15, follow_redirects=False)

for path in ["/ws", "/ws/", "/health"]:
    try:
        r = client.get(f"https://msingi-ai--ws.modal.run{path}")
        print(f"GET {path}: {r.status_code}", flush=True)
        loc = r.headers.get("location", "none")
        print(f"  Location: {loc}", flush=True)
    except Exception as e:
        print(f"GET {path}: ERROR {e}", flush=True)
