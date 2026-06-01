"""Tests for generic proactive gateway notifications."""

from __future__ import annotations

from unittest.mock import MagicMock

from gateway.notifications import (
    NotificationRequest,
    clear_notification_runtime,
    configure_notification_runtime,
    deliver_notification,
)


def test_delivery_uses_existing_router_and_is_idempotent(tmp_path):
    deliverer = MagicMock(return_value=None)
    request = NotificationRequest(
        source="heartbeat",
        content="Review a blocked task.",
        idempotency_key="heartbeat:f-1",
        targets=[{"platform": "telegram", "chat_id": "123", "thread_id": "7"}],
    )
    first = deliver_notification(request, deliverer=deliverer, dedup_path=tmp_path / "dedup.db")
    second = deliver_notification(request, deliverer=deliverer, dedup_path=tmp_path / "dedup.db")

    assert first.delivered is True
    assert second.skipped_reason == "duplicate"
    assert deliverer.call_count == 1
    assert deliverer.call_args.args[0]["deliver"] == "telegram:123:7"
    assert deliverer.call_args.args[0]["_wrap_response"] is False


def test_success_mirrors_transcript_and_publishes_observation(tmp_path):
    store = MagicMock()
    memory = MagicMock()
    request = NotificationRequest(
        source="heartbeat",
        content="Review a blocked task.",
        idempotency_key="heartbeat:f-2",
        targets=["telegram:123"],
        mirror_session_id="session-1",
        observation={"source": "heartbeat", "finding_id": "f-2"},
    )
    result = deliver_notification(
        request,
        deliverer=MagicMock(return_value=None),
        session_store=store,
        memory_manager=memory,
        dedup_path=tmp_path / "dedup.db",
    )

    assert result.delivered is True
    assert result.mirrored_session_id == "session-1"
    store.append_to_transcript.assert_called_once_with(
        "session-1",
        {"role": "assistant", "content": "Review a blocked task."},
    )
    memory.on_observation.assert_called_once_with({"source": "heartbeat", "finding_id": "f-2"})


def test_failed_delivery_does_not_mirror_or_publish(tmp_path):
    store = MagicMock()
    memory = MagicMock()
    request = NotificationRequest(
        source="heartbeat",
        content="Review a blocked task.",
        idempotency_key="heartbeat:f-3",
        targets=["telegram:123"],
        mirror_session_id="session-1",
        observation={"source": "heartbeat", "finding_id": "f-3"},
    )
    result = deliver_notification(
        request,
        deliverer=MagicMock(return_value="send failed"),
        session_store=store,
        memory_manager=memory,
        dedup_path=tmp_path / "dedup.db",
    )

    assert result.delivered is False
    assert result.error == "send failed"
    store.append_to_transcript.assert_not_called()
    memory.on_observation.assert_not_called()


def test_mirror_can_be_disabled(tmp_path):
    store = MagicMock()
    request = NotificationRequest(
        source="heartbeat",
        content="Review a blocked task.",
        idempotency_key="heartbeat:f-no-mirror",
        targets=["telegram:123"],
        mirror=False,
        mirror_session_id="session-1",
    )
    result = deliver_notification(
        request,
        deliverer=MagicMock(return_value=None),
        session_store=store,
        dedup_path=tmp_path / "dedup.db",
    )

    assert result.delivered is True
    assert result.mirrored_session_id is None
    store.append_to_transcript.assert_not_called()


def test_memory_publish_can_resolve_session_when_mirror_disabled(tmp_path, monkeypatch):
    memory = MagicMock()
    resolver = MagicMock(return_value=memory)
    monkeypatch.setattr("gateway.mirror._find_session_id", lambda *_args, **_kwargs: "session-1")
    configure_notification_runtime(memory_manager_resolver=resolver)
    try:
        request = NotificationRequest(
            source="heartbeat",
            content="Review a blocked task.",
            idempotency_key="heartbeat:f-memory-only",
            targets=["telegram:123"],
            mirror=False,
            observation={"source": "heartbeat", "finding_id": "f-memory-only"},
        )
        result = deliver_notification(
            request,
            deliverer=MagicMock(return_value=None),
            dedup_path=tmp_path / "dedup.db",
        )
    finally:
        clear_notification_runtime()

    assert result.delivered is True
    assert result.mirrored_session_id is None
    resolver.assert_called_once_with("session-1")
    memory.on_observation.assert_called_once_with(
        {"source": "heartbeat", "finding_id": "f-memory-only"}
    )


def test_partial_delivery_retries_only_failed_target(tmp_path):
    deliverer = MagicMock(side_effect=[None, "offline", None])
    request = NotificationRequest(
        source="heartbeat",
        content="Review a blocked task.",
        idempotency_key="heartbeat:f-4",
        targets=["telegram:123", "slack:456"],
    )
    first = deliver_notification(request, deliverer=deliverer, dedup_path=tmp_path / "dedup.db")
    second = deliver_notification(request, deliverer=deliverer, dedup_path=tmp_path / "dedup.db")

    assert first.delivered is True
    assert first.delivered_targets == ["telegram:123"]
    assert len(first.failed_targets) == 1
    assert second.delivered is True
    assert second.delivered_targets == ["telegram:123", "slack:456"]
    assert [call.args[0]["deliver"] for call in deliverer.call_args_list] == [
        "telegram:123",
        "slack:456",
        "slack:456",
    ]
