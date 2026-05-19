from types import SimpleNamespace

from gateway.config import Platform
from gateway.platforms.base import _reply_anchor_for_event


def test_base_reply_anchor_uses_root_for_mattermost_threads():
    """Mattermost threaded responses must anchor to the thread root, not the reply post."""
    event = SimpleNamespace(
        message_id="m-user-reply",
        source=SimpleNamespace(
            platform=Platform.MATTERMOST,
            chat_type="group",
            thread_id="root-abc",
        ),
    )

    assert _reply_anchor_for_event(event) == "root-abc"


def test_base_reply_anchor_falls_back_to_message_id_when_no_thread():
    """Non-threaded Mattermost messages should continue using message-id fallback."""
    event = SimpleNamespace(
        message_id="m-top-level",
        source=SimpleNamespace(
            platform=Platform.MATTERMOST,
            chat_type="group",
            thread_id=None,
        ),
    )

    assert _reply_anchor_for_event(event) == "m-top-level"
