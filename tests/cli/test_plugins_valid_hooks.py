from hermes_cli.plugins import VALID_HOOKS


def test_on_slack_app_init_is_valid():
    assert "on_slack_app_init" in VALID_HOOKS


def test_transform_tts_text_is_valid():
    assert "transform_tts_text" in VALID_HOOKS
