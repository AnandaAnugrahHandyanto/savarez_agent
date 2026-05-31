"""Tests for the LINE platform adapter."""

import sys
from pathlib import Path


_repo = str(Path(__file__).resolve().parents[2])
if _repo not in sys.path:
    sys.path.insert(0, _repo)


from gateway.platforms.base import MessageType
from plugins.platforms.line.adapter import _line_message_type


def test_line_message_types_use_gateway_enum_names():
    assert _line_message_type("text") is MessageType.TEXT
    assert _line_message_type("image") is MessageType.PHOTO
    assert _line_message_type("audio") is MessageType.AUDIO
    assert _line_message_type("video") is MessageType.VIDEO
    assert _line_message_type("file") is MessageType.DOCUMENT
    assert _line_message_type("sticker") is MessageType.STICKER
    assert _line_message_type("location") is MessageType.LOCATION
