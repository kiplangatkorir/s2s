from gateway.ws_server import create_app


def test_gateway_app_creates_fastapi_app():
    app = create_app()

    assert app is not None
    assert hasattr(app, "routes")
