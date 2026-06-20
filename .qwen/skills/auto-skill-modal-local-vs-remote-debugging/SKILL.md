---
name: modal-local-vs-remote-debugging
description: Systematic checklist for diagnosing "works locally but not on remote" issues in Modal-based deployments
source: auto-skill
extracted_at: '2026-06-20T14:15:00.000Z'
---

# Modal Local vs Remote Deployment Debugging

## When to use

When a user reports that their Modal-based application:
- Works perfectly in local development (`modal run` or `uvicorn` locally)
- Fails silently or throws errors when deployed (`modal deploy`)
- Frontend connects locally but not from deployed environments (Vercel, etc.)

## Systematic diagnosis checklist

### 1. Verify Modal apps are actually deployed

```bash
modal app list
```

**Windows users:** Modal CLI uses Unicode checkmarks in output, which fails with `'charmap' codec can't encode character '\u2713'` on Windows. Prefix all `modal` commands with UTF-8 mode:
```bash
set "PYTHONUTF8=1" && modal app list
set "PYTHONUTF8=1" && modal deploy your_app.py
set "PYTHONUTF8=1" && modal run your_app.py::function
```

**Common issue:** Apps appear deployed in your local workspace but you're checking from a different Modal account/workspace. The `modal app list` command shows apps in the currently authenticated workspace only.

**What to check:**
- Are all required Modal apps showing up? (e.g., ASR, TTS, gateway)
- Do app names match what your code references via `modal.Cls.from_name("app-name", "ClassName")`?
- Were apps deployed under a different Modal account?

### 2. Check Modal secrets configuration

```bash
modal secret list
```

**Common issues:**
- Secret names don't match what's referenced in code (`modal.Secret.from_name("secret-name")`)
- Required keys are missing from the secret (check `required_keys=["API_KEY"]` in your code)
- Secret was created but never populated with actual values

**Verification:** Run a health check function that uses the secret:
```bash
modal run your_app.py::healthcheck_function
```

### 3. Frontend environment variables (critical for WebSocket/API URLs)

**The #1 culprit:** Frontend hardcodes `localhost` URLs that work locally but fail when deployed.

**Check these files:**
- `frontend/.env.local` (for local dev)
- `frontend/.env.production` (for deployed builds)
- Root `.env.example` (should document all required vars)

**Common pattern in React/Next.js:**
```typescript
// This FAILS when deployed to Vercel:
const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";

// When deployed, the browser tries to connect to localhost:8000
// which doesn't exist on the user's machine.
```

**Fix:** Set the environment variable in your deployment platform (Vercel, Netlify, etc.):
```
NEXT_PUBLIC_WS_URL=wss://your-modal-app.modal.run/ws
```

Then redeploy the frontend.

### 4. Gateway image dependencies

**Check the Modal image definition in your gateway app:**
```python
gateway_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("fastapi", "httpx", "modal", "numpy", "pydantic", "uvicorn")
    .add_local_dir(".", remote_path="/root/project", ignore=[".git", "__pycache__"])
)
```

**Common issues:**
- `add_local_dir()` pointing to a directory that doesn't exist locally (e.g., sibling repo)
- Missing Python packages that work locally via `pip install -e .` but aren't in the image
- Code references files that are `.gitignore`d and not included in the image

**Verification:** Check the Modal build logs when deploying — look for "No files found" warnings.

### 5. WebSocket URL protocol (ws vs wss)

**Critical for deployed environments:**
- Local: `ws://localhost:8000/ws` (insecure WebSocket)
- Deployed: `wss://your-app.modal.run/ws` (secure WebSocket required)

**Browser security:** Modern browsers block insecure WebSocket connections from HTTPS pages. If your frontend is deployed to HTTPS (Vercel, Netlify), it **must** use `wss://` not `ws://`.

### 6. Modal function references by name

**Check how your code references Modal functions:**
```python
# This requires the app to be deployed in the SAME Modal workspace:
asr = modal.Cls.from_name("msingiai-sauti-asr", "SautiASR")
tts = modal.Cls.from_name("msingiai-sauti-tts", "SautiTTS")
```

**Common issues:**
- Apps deployed under different names (typo in `modal.App("app-name")`)
- Apps deployed to a different Modal workspace (personal vs team account)
- App was deleted or stopped

**Verification:** Check the Modal dashboard to see if apps are running and accessible.

### 7. CORS and origin restrictions

**If your gateway has CORS configured:**
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # <-- This blocks deployed frontend
    allow_credentials=True,
)
```

**Fix:** Add your deployed frontend URL to `allow_origins`:
```python
allow_origins=[
    "http://localhost:3000",
    "https://your-app.vercel.app",
]
```

## Quick diagnostic script

Create a simple script to verify Modal deployment status:

```python
import modal
import json

def check_deployment():
    print("=== Modal Deployment Check ===\n")
    
    # Check apps
    try:
        apps = modal.App.list()
        print(f"✓ Found {len(apps)} deployed apps")
        for app in apps:
            print(f"  - {app}")
    except Exception as e:
        print(f"✗ Error listing apps: {e}")
    
    # Check secrets
    try:
        secrets = modal.Secret.list()
        print(f"\n✓ Found {len(secrets)} secrets")
        for secret in secrets:
            print(f"  - {secret['name']}")
    except Exception as e:
        print(f"✗ Error listing secrets: {e}")
    
    # Test a Modal function
    try:
        TestFn = modal.Cls.from_name("your-app-name", "YourClass")
        instance = TestFn()
        result = instance.your_method.remote()
        print(f"\n✓ Modal function test passed: {result}")
    except Exception as e:
        print(f"\n✗ Modal function test failed: {e}")

if __name__ == "__main__":
    check_deployment()
```

## Common error messages and fixes

### "App 'app-name' not found"
- App isn't deployed → run `modal deploy your_app.py`
- Wrong workspace → check `modal token` or Modal dashboard account

### "Secret 'secret-name' not found"
- Secret doesn't exist → create it in Modal dashboard or via CLI
- Secret exists but missing required keys → update the secret with all required keys

### WebSocket connection fails from deployed frontend
- Missing `NEXT_PUBLIC_WS_URL` env var → set it in Vercel/Netlify
- Using `ws://` instead of `wss://` → Modal requires secure WebSocket
- CORS blocking the origin → add your frontend URL to gateway CORS config

### "Module not found" in Modal function
- Missing package in image → add it to `pip_install()` in your image definition
- Local code not included → check `add_local_dir()` paths and ignore patterns
- Sibling repo not found → ensure the directory exists locally before deploying

## Prevention

1. **Document all environment variables** in `.env.example` (including frontend vars like `NEXT_PUBLIC_WS_URL`)
2. **Add a deployment health check** endpoint that verifies secrets and dependencies
3. **Test the full deployment flow** in a staging environment before production
4. **Use Modal's `modal shell`** to debug deployed functions interactively
5. **Check Modal logs** after deployment for warnings about missing files or dependencies

## Deployment order

When your architecture has multiple Modal apps where one references others by name (e.g., a gateway calling `modal.Cls.from_name("asr-app", "ASRClass")`), **deploy the leaf apps first, then the gateway**:

```bash
# 1. Deploy worker apps first (they must exist before gateway references them)
modal deploy modal_apps/sauti_asr.py
modal deploy modal_apps/sauti_tts.py

# 2. Deploy gateway last (it resolves ASR/TTS by name at runtime)
modal deploy gateway/modal_app.py
```

**Why:** The gateway doesn't resolve references at deploy time — `modal.Cls.from_name()` is called lazily at runtime. But the apps still need to exist in the workspace for the gateway to function. If they don't exist, calls fail with "App not found" at runtime.

## Post-deploy verification

After deploying the gateway, hit its health endpoint to confirm it's live:

```bash
# Check gateway health
python -c "import httpx; r = httpx.get('https://your-app--label.modal.run/health', timeout=15); print(r.status_code, r.json())"

# Verify secrets are wired (call a function that uses the secret)
python -c "import modal; r = modal.Function.from_name('gateway-app', 'healthcheck').remote(); print(r)"
```

Expected: `200 {'status': 'ok'}`

If the health endpoint hangs or errors, the issue is in the image build or secret configuration — check Modal dashboard logs.

## Modal WebSocket cold-start 404 (browser-only)

**Symptom:** Python WebSocket clients connect fine (`websockets.connect()` returns 101), but browsers connecting to the same `wss://` URL get a transient **404** on the WebSocket upgrade — typically right after a fresh `modal deploy`.

**Root cause:** Modal's `@modal.asgi_app` proxy handles HTTP/1.1 Upgrade fine (Python `websockets` library uses this path). Browsers may send HTTP/2 CONNECT (RFC 8441) or hit the container during cold-start before the ASGI app is fully ready to accept upgrades. The 404 resolves after retry.

**What NOT to do:**
- Don't switch to `@modal.web_server` with `subprocess.Popen(["uvicorn", ...])` — the subprocess exits before Modal routes traffic, causing permanent timeouts.
- Don't assume the issue is the URL — if Python clients work, the URL is correct.

**Fix pattern — two complementary changes:**

### 1. Server-side heartbeat ping (prevents idle timeout + confirms liveness)

```python
# gateway/ws_server.py
import asyncio

HEARTBEAT_INTERVAL_S = 20

async def _heartbeat(ws: WebSocket) -> None:
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_S)
            await ws.send_json({"type": "ping"})
    except (WebSocketDisconnect, RuntimeError):
        pass

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    heartbeat_task = asyncio.create_task(_heartbeat(websocket))
    try:
        while True:
            message = await websocket.receive()
            # ... handle pong responses, normal messages ...
    except WebSocketDisconnect:
        heartbeat_task.cancel()
```

Client must respond to `ping` with `{"type": "pong"}`.

### 2. Client-side exponential backoff reconnection

```typescript
let retryCount = 0;
let disposed = false;

const connectWs = () => {
  if (disposed) return;
  const ws = new WebSocket(url);

  ws.onopen = () => {
    setIsConnected(true);
    setConnectionError(null);
    retryCount = 0;
  };

  ws.onclose = () => {
    setIsConnected(false);
    const delay = Math.min(1000 * 2 ** retryCount, 30000);
    retryCount++;
    if (retryCount <= 3) {
      setConnectionError("Connecting to voice server\u2026");
    } else {
      setConnectionError("Voice server disconnected");
    }
    reconnectTimer = setTimeout(connectWs, delay);
  };

  ws.onmessage = (event) => {
    // Handle ping/pong for heartbeat
    const data = JSON.parse(event.data);
    if (data.type === "ping") {
      ws.send(JSON.stringify({ type: "pong" }));
      return;
    }
    // ... normal message handling ...
  };

  wsRef.current = ws;
};
```

**Key details:**
- Exponential backoff: 1s → 2s → 4s → 8s → 16s → 30s (capped)
- Show "Connecting…" for the first 3 retries, not an error
- Use a `disposed` flag to prevent reconnection after component unmount
- Reset `retryCount` to 0 on successful connection

### Verifying the WebSocket path is valid (debug)

Before assuming the URL is wrong, test the raw upgrade:

```python
import http.client, ssl, base64, os

ctx = ssl.create_default_context()
conn = http.client.HTTPSConnection("your-app.modal.run", timeout=30, context=ctx)
key = base64.b64encode(os.urandom(16)).decode()
conn.request("GET", "/ws", headers={
    "Upgrade": "websocket", "Connection": "Upgrade",
    "Sec-WebSocket-Version": "13", "Sec-WebSocket-Key": key,
    "Origin": "https://your-frontend.vercel.app",
})
resp = conn.getresponse()
print(f"Status: {resp.status}")  # 101 = path is valid
```

If this returns 101, the path works — the issue is browser-specific (HTTP/2, cold-start timing). Add heartbeat + backoff.

## Gotchas

- **`modal app list` only shows the current workspace** — if you have multiple Modal accounts (personal/team), apps in one won't appear in the other
- **Frontend env vars must be set at build time** for Next.js — setting them after deployment won't work, you must redeploy
- **Modal images are rebuilt on every deploy** — if you change dependencies, you must redeploy
- **Local `.env` files are never deployed to Modal** — use Modal secrets for sensitive values
- **WebSocket URLs must match the protocol** — `ws://` for local, `wss://` for deployed HTTPS sites
- **Windows Modal CLI encoding** — Modal uses Unicode symbols (✓ ✗) in terminal output that fail with `charmap` codec on Windows. Always prefix with `set "PYTHONUTF8=1" &&` or set `PYTHONUTF8=1` in your system environment variables
