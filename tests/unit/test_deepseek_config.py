from pipeline.orchestrator import PipelineConfig


def test_pipeline_uses_available_deepseek_model():
    assert PipelineConfig().deepseek_model == "deepseek-v4-flash"
