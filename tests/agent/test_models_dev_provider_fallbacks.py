from agent.models_dev import get_model_info
from agent.model_metadata import get_model_context_length


def test_zai_coding_glm_5_1_context_falls_back_cleanly():
    ctx = get_model_context_length(
        "glm-5.1",
        provider="zai-coding",
        base_url="https://api.z.ai/api/coding/paas/v4",
    )
    assert ctx == 204800


def test_mimo_falls_back_to_general_xiaomi_catalog_for_flash():
    info = get_model_info("mimo", "mimo-v2-flash")
    assert info is not None
    assert info.context_window == 256000
    assert info.max_output == 64000
