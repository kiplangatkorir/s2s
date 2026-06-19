def test_gateway_modal_app_uses_deepseek_secret():
    import gateway.modal_app as modal_app

    assert modal_app.APP_NAME == "msingiai-sauti-gateway"
    assert modal_app.REMOTE_PROJECT_ROOT == "/root/sauti-s2s"
