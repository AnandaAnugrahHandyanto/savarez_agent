"""Regression tests for LINE inbound MessageType mapping."""

from gateway.platforms.base import MessageEvent, MessageType
from plugins.platforms.line.adapter import _line_msg_type


def test_line_image_messages_map_to_photo_message_type():
    """LINE sends type='image', but Hermes uses MessageType.PHOTO."""
    event = MessageEvent(
        text="[image]",
        message_type=_line_msg_type("image"),
        source=None,  # type: ignore[arg-type]
    )

    assert not hasattr(MessageType, "IMAGE")
    assert event.message_type is MessageType.PHOTO


def test_line_non_text_message_types_map_to_existing_message_types():
    assert _line_msg_type("text") is MessageType.TEXT
    assert _line_msg_type("audio") is MessageType.AUDIO
    assert _line_msg_type("video") is MessageType.VIDEO
    assert _line_msg_type("file") is MessageType.DOCUMENT
    assert _line_msg_type("sticker") is MessageType.STICKER
    assert _line_msg_type("location") is MessageType.LOCATION


def test_line_unknown_message_types_default_to_text():
    assert _line_msg_type("poll") is MessageType.TEXT
    assert _line_msg_type("") is MessageType.TEXT
