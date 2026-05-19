"""Tests for proactive vision image capping in conversation history."""

from __future__ import annotations

from agent.message_sanitization import cap_vision_images_in_messages


def _tool_image_msg(call_id: str, b64: str = "abc") -> dict:
    return {
        "role": "tool",
        "tool_call_id": call_id,
        "content": [
            {"type": "text", "text": "loaded"},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            },
        ],
    }


def test_cap_disabled_when_limit_zero():
    messages = [_tool_image_msg("c1"), _tool_image_msg("c2")]
    assert cap_vision_images_in_messages(messages, 0) == 0
    assert messages[0]["content"][1]["type"] == "image_url"


def test_keeps_n_most_recent_strips_oldest():
    messages = [
        _tool_image_msg("c1", "one"),
        _tool_image_msg("c2", "two"),
        _tool_image_msg("c3", "three"),
    ]
    stripped = cap_vision_images_in_messages(messages, 2)
    assert stripped == 1
    assert messages[0]["content"][1]["type"] == "text"
    assert "kept 2 most recent" in messages[0]["content"][1]["text"]
    assert messages[1]["content"][1]["type"] == "image_url"
    assert messages[2]["content"][1]["type"] == "image_url"


def test_prunes_multimodal_envelope_images():
    messages = [
        {
            "role": "tool",
            "tool_call_id": "c1",
            "content": {
                "_multimodal": True,
                "content": [
                    {"type": "text", "text": "summary"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,old"}},
                ],
                "text_summary": "summary",
            },
        },
        _tool_image_msg("c2", "new"),
    ]
    assert cap_vision_images_in_messages(messages, 1) == 1
    inner = messages[0]["content"]["content"]
    assert inner[1]["type"] == "text"
    assert messages[1]["content"][1]["type"] == "image_url"


def test_agent_cap_method_uses_config():
    from run_agent import AIAgent

    agent = AIAgent.__new__(AIAgent)
    agent.max_vision_images_in_context = 1
    messages = [_tool_image_msg("c1"), _tool_image_msg("c2")]
    assert agent._cap_vision_images_in_context(messages) == 1
    assert messages[0]["content"][1]["type"] == "text"
    assert messages[1]["content"][1]["type"] == "image_url"
