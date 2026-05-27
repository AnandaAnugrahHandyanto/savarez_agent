from types import SimpleNamespace

from agent.codex_responses_adapter import (
    _chat_messages_to_responses_input,
    _normalize_codex_response,
    _preflight_codex_input_items,
)


def test_normalize_codex_response_drops_transient_rs_tmp_reasoning_items():
    response = SimpleNamespace(
        status="completed",
        output=[
            SimpleNamespace(
                type="reasoning",
                id="rs_tmp_123",
                encrypted_content="opaque-transient",
                summary=[],
            ),
            SimpleNamespace(
                type="reasoning",
                id="rs_456",
                encrypted_content="opaque-stable",
                summary=[SimpleNamespace(text="stable summary")],
            ),
            SimpleNamespace(
                type="message",
                role="assistant",
                status="completed",
                content=[SimpleNamespace(type="output_text", text="done")],
            ),
        ],
    )

    assistant_message, finish_reason = _normalize_codex_response(response)

    assert finish_reason == "stop"
    assert assistant_message.content == "done"
    assert assistant_message.codex_reasoning_items == [
        {
            "type": "reasoning",
            "encrypted_content": "opaque-stable",
            "id": "rs_456",
            "summary": [{"type": "summary_text", "text": "stable summary"}],
        }
    ]


def test_normalize_codex_response_treats_summary_only_reasoning_as_incomplete():
    response = SimpleNamespace(
        status="completed",
        output=[
            SimpleNamespace(
                type="reasoning",
                id="rs_tmp_789",
                encrypted_content="opaque-transient",
                summary=[SimpleNamespace(text="still thinking")],
            )
        ],
    )

    assistant_message, finish_reason = _normalize_codex_response(response)

    assert finish_reason == "incomplete"
    assert assistant_message.content == ""
    assert assistant_message.reasoning == "still thinking"
    assert assistant_message.codex_reasoning_items is None


# ---------------------------------------------------------------------------
# Regression tests for oversized message/reasoning item IDs (>64 chars)
# See upstream issue #10788 — HTTP 400 string_above_max_length on replay.
# ---------------------------------------------------------------------------

_LONG_ID = "msg_" + "a" * 412  # 416 chars, same length observed in #10788
_SHORT_ID = "msg_" + "b" * 55   # 59 chars, within limit


def test_capture_normalization_drops_oversized_message_item_id():
    """_normalize_codex_response must NOT store message item ids >64 chars."""
    response = SimpleNamespace(
        status="completed",
        output=[
            SimpleNamespace(
                type="message",
                id=_LONG_ID,
                role="assistant",
                status="completed",
                content=[SimpleNamespace(type="output_text", text="hello")],
            ),
        ],
    )

    assistant_message, finish_reason = _normalize_codex_response(response)

    assert finish_reason == "stop"
    assert assistant_message.content == "hello"
    # The captured codex_message_items must NOT contain the oversized id
    items = assistant_message.codex_message_items
    assert items is not None and len(items) == 1
    assert "id" not in items[0]


def test_capture_normalization_preserves_short_message_item_id():
    """Short ids (<=64 chars) should pass through capture normally."""
    response = SimpleNamespace(
        status="completed",
        output=[
            SimpleNamespace(
                type="message",
                id=_SHORT_ID,
                role="assistant",
                status="completed",
                content=[SimpleNamespace(type="output_text", text="ok")],
            ),
        ],
    )

    assistant_message, finish_reason = _normalize_codex_response(response)
    items = assistant_message.codex_message_items
    assert items[0]["id"] == _SHORT_ID


def test_capture_normalization_drops_oversized_reasoning_item_id():
    """_normalize_codex_response must NOT store reasoning item ids >64 chars."""
    response = SimpleNamespace(
        status="completed",
        output=[
            SimpleNamespace(
                type="reasoning",
                id=_LONG_ID,
                encrypted_content="opaque-blob",
                summary=[SimpleNamespace(text="thinking")],
            ),
            SimpleNamespace(
                type="message",
                role="assistant",
                status="completed",
                content=[SimpleNamespace(type="output_text", text="done")],
            ),
        ],
    )

    assistant_message, finish_reason = _normalize_codex_response(response)
    items = assistant_message.codex_reasoning_items
    assert len(items) == 1
    assert "id" not in items[0]


def test_replay_strips_oversized_message_item_id():
    """_chat_messages_to_responses_input must strip message item ids >64 chars
    from the replay payload so the Responses API never sees them."""
    messages = [
        {
            "role": "user",
            "content": "hi",
        },
        {
            "role": "assistant",
            "content": "hello",
            "codex_message_items": [
                {
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": "hello"}],
                    "id": _LONG_ID,
                    "phase": "response.123",
                },
            ],
        },
    ]

    items = _chat_messages_to_responses_input(messages)
    # Find the replayed message item
    replayed = [i for i in items if i.get("type") == "message" and i.get("role") == "assistant"]
    assert len(replayed) == 1
    assert "id" not in replayed[0]
    # Phase must still be present (cache-critical)
    assert replayed[0].get("phase") == "response.123"


def test_replay_preserves_short_message_item_id():
    """Short ids (<=64 chars) should survive replay."""
    messages = [
        {
            "role": "user",
            "content": "hi",
        },
        {
            "role": "assistant",
            "content": "hello",
            "codex_message_items": [
                {
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": "hello"}],
                    "id": _SHORT_ID,
                    "phase": "response.456",
                },
            ],
        },
    ]

    items = _chat_messages_to_responses_input(messages)
    replayed = [i for i in items if i.get("type") == "message" and i.get("role") == "assistant"]
    assert replayed[0]["id"] == _SHORT_ID


def test_preflight_strips_oversized_message_item_id():
    """_preflight_codex_input_items must strip message item ids >64 chars."""
    raw_items = [
        {
            "type": "message",
            "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": "hello"}],
            "id": _LONG_ID,
            "phase": "response.789",
        },
    ]

    normalized = _preflight_codex_input_items(raw_items)
    assistant_items = [i for i in normalized if i.get("role") == "assistant"]
    assert len(assistant_items) == 1
    assert "id" not in assistant_items[0]
    assert assistant_items[0].get("phase") == "response.789"


def test_preflight_preserves_short_message_item_id():
    """Short ids (<=64 chars) should survive preflight."""
    raw_items = [
        {
            "type": "message",
            "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": "hello"}],
            "id": _SHORT_ID,
            "phase": "response.012",
        },
    ]

    normalized = _preflight_codex_input_items(raw_items)
    assistant_items = [i for i in normalized if i.get("role") == "assistant"]
    assert assistant_items[0]["id"] == _SHORT_ID
