"""Regression test: base media fallbacks must not leak host filesystem paths.

The default ``send_voice``/``send_video``/``send_document``/``send_image_file``
fallbacks (used by adapters that don't override them) fabricated a chat message
containing the local cache file path (e.g. ``🔊 Audio: /home/.../x.ogg``), leaking
host paths into user-visible output. They must send a generic notice instead.

Calls the base methods with a duck-typed ``self`` to avoid instantiating the ABC.
"""
import asyncio

import gateway.platforms.base as base

_LEAK = "/home/alice/.hermes/cache/audio/secret-12345.ogg"
_SECRET_DIR = "/home/alice/.hermes/cache"


class _CapturingAdapter:
    def __init__(self):
        self.sent = []

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        self.sent.append(content)
        return None


def _run(coro):
    return asyncio.run(coro)


def test_send_voice_no_path_leak():
    a = _CapturingAdapter()
    _run(base.BasePlatformAdapter.send_voice(a, "chat", _LEAK))
    assert _SECRET_DIR not in a.sent[0]


def test_send_video_no_path_leak():
    a = _CapturingAdapter()
    _run(base.BasePlatformAdapter.send_video(a, "chat", "/home/alice/.hermes/cache/clip.mp4"))
    assert "/home/alice" not in a.sent[0]


def test_send_image_no_path_leak():
    a = _CapturingAdapter()
    _run(base.BasePlatformAdapter.send_image_file(a, "chat", "/home/alice/.hermes/cache/pic.png"))
    assert "/home/alice" not in a.sent[0]


def test_send_document_uses_name_not_path():
    a = _CapturingAdapter()
    _run(base.BasePlatformAdapter.send_document(
        a, "chat", "/home/alice/.hermes/cache/report.pdf", file_name="report.pdf"))
    assert "/home/alice" not in a.sent[0]
    assert "report.pdf" in a.sent[0]
