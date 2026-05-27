from types import SimpleNamespace

from gateway.approval_routing import approval_target_for_adapter, format_approval_prompt
from gateway.platforms.base import Platform
from gateway.run import _gateway_approval_delivery_context


def test_approval_target_for_adapter_routes_telegram_to_configured_topic():
    chat_id, metadata = approval_target_for_adapter(
        adapter_name="telegram",
        default_chat_id="615821439",
        default_metadata={"thread_id": "1", "reply_to_message_id": 99},
        approvals_config={"gateway_target": "telegram:-1003812316571:126"},
    )

    assert chat_id == "-1003812316571"
    assert metadata["thread_id"] == "126"
    assert "reply_to_message_id" not in metadata


def test_approval_target_for_adapter_ignores_other_platforms():
    chat_id, metadata = approval_target_for_adapter(
        adapter_name="discord",
        default_chat_id="orig-channel",
        default_metadata={"thread_id": "source-thread"},
        approvals_config={"gateway_target": "telegram:-1003812316571:126"},
    )

    assert chat_id == "orig-channel"
    assert metadata == {"thread_id": "source-thread"}


def test_gateway_approval_delivery_context_uses_runtime_config_for_routing_and_lv_prompt(monkeypatch):
    monkeypatch.setattr(
        "gateway.run._load_gateway_runtime_config",
        lambda: {
            "approvals": {
                "gateway_target": "telegram:-1003812316571:126",
                "prompt_language": "lv",
            }
        },
    )
    source = SimpleNamespace(
        platform=Platform.TELEGRAM,
        chat_id="-100source",
        thread_id="180",
        chat_name="Life_OS_Hermes",
        description="Life_OS_Hermes / topic 180",
    )

    chat_id, metadata, prompt = _gateway_approval_delivery_context(
        source=source,
        default_chat_id="-100source",
        default_metadata={"thread_id": "180", "reply_to_message_id": 99},
        command="rm -rf /tmp/demo",
        description="recursive delete",
        html_mode=True,
    )

    assert chat_id == "-1003812316571"
    assert metadata is not None
    assert metadata["thread_id"] == "126"
    assert "reply_to_message_id" not in metadata
    assert "Nepieciešams tavs apstiprinājums" in prompt
    assert "Life_OS_Hermes / topic 180" in prompt
    assert "rm -rf /tmp/demo" in prompt


def test_format_approval_prompt_lv_simple_language_has_project_and_action():
    text = format_approval_prompt(
        command="rm -rf /tmp/demo",
        description="recursive delete",
        source_label="Life_OS_Hermes / topic 126",
        language="lv",
    )

    assert "Nepieciešams tavs apstiprinājums" in text
    assert "No kurienes" in text
    assert "Life_OS_Hermes / topic 126" in text
    assert "Ko apstiprini" in text
    assert "rm -rf /tmp/demo" in text
    assert "recursive delete" in text
