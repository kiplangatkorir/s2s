import sys
import types


def test_modal_asr_and_tts_apps_import():
    import modal_apps.sauti_asr as sauti_asr
    import modal_apps.sauti_tts as sauti_tts

    assert sauti_asr.CHECKPOINT_DIR == "/ckpts/track_a_whisper_paza_full"
    assert sauti_asr.REMOTE_ASR_PACKAGE_PARENT == "/root/sauti_asr_pkg"
    assert (
        sauti_asr._resolve_local_asr_package("/root/sauti_asr.py").as_posix()
        == "/root/sauti_asr_pkg/sauti_asr"
    )
    assert sauti_tts.CHECKPOINT_DIR == "/vol/checkpoints/voxcpm2_sw_lora_waxal_s300/latest"


def test_asr_package_import_preparation_removes_app_module_alias():
    import modal_apps.sauti_asr as sauti_asr

    original = sys.modules.get("sauti_asr")
    sys.modules["sauti_asr"] = types.ModuleType("sauti_asr")
    try:
        sauti_asr._prepare_asr_package_import()
        assert "sauti_asr" not in sys.modules
        assert sys.path[0] == sauti_asr.REMOTE_ASR_PACKAGE_PARENT
    finally:
        if original is not None:
            sys.modules["sauti_asr"] = original
        else:
            sys.modules.pop("sauti_asr", None)
