"""Modal deployment wrapper for the Sauti S2S WebSocket gateway.

Deploy:
    modal deploy gateway/modal_app.py
"""

from __future__ import annotations

import sys
import json

import modal


APP_NAME = "msingiai-sauti-gateway"
REMOTE_PROJECT_ROOT = "/root/sauti-s2s"

gateway_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastapi>=0.110",
        "httpx<0.28",
        "modal>=1.4",
        "numpy<2",
        "pydantic>=2",
        "uvicorn>=0.27",
    )
    .add_local_dir(
        ".",
        remote_path=REMOTE_PROJECT_ROOT,
        ignore=[
            ".git",
            ".modal_logs",
            ".pytest_cache",
            "__pycache__",
            "*.pyc",
            "smoke_tts.wav",
            "node_modules",
            ".next",
            "frontend/node_modules",
            "frontend/.next",
        ],
    )
)

app = modal.App(APP_NAME)
deepseek_secret = modal.Secret.from_name("deepseek", required_keys=["DEEPSEEK_API_KEY"])


def _ensure_project_on_path() -> None:
    if REMOTE_PROJECT_ROOT not in sys.path:
        sys.path.insert(0, REMOTE_PROJECT_ROOT)


@app.function(
    image=gateway_image,
    secrets=[deepseek_secret],
    min_containers=1,
    timeout=60 * 60,
)
@modal.asgi_app(label="ws")
def asgi_app():
    _ensure_project_on_path()
    from gateway.ws_server import create_app

    return create_app()


@app.function(
    image=gateway_image,
    secrets=[deepseek_secret],
    timeout=60,
)
def deepseek_healthcheck() -> dict:
    import os

    import httpx

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return {"configured": False, "ok": False, "detail": "DEEPSEEK_API_KEY missing"}

    response = httpx.get(
        "https://api.deepseek.com/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=20.0,
    )
    payload: dict = {
        "configured": True,
        "ok": response.is_success,
        "status_code": response.status_code,
    }
    if response.is_success:
        body = response.json()
        payload["models"] = [
            item.get("id")
            for item in body.get("data", [])[:10]
            if isinstance(item, dict)
        ]
    else:
        payload["detail"] = response.text[:300]
    return payload


@app.local_entrypoint()
def main(check_deepseek: bool = False) -> None:
    if check_deepseek:
        print(json.dumps(deepseek_healthcheck.remote(), indent=2))
        return
    print("Deploy with: modal deploy gateway/modal_app.py")
