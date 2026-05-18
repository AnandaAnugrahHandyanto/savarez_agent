"""Tests for media-routing in ``GatewayRunner._prepare_inbound_message_text``.

Regression coverage for the user-reported bug where uploading images
alongside a non-image attachment (e.g. an .md document) on Discord
caused the whole turn to fail with HTTP 400 "Could not process image"
from Anthropic.

Root cause: the routing loop in ``gateway/run.py`` used
``mtype.startswith("image/") OR event.message_type == PHOTO`` to decide
whether to attach a media URL as a vision image. When Discord set the
message-level type to PHOTO (because at least one attachment was an
image), every other attachment in the same message -- including
documents -- got routed as an image and base64'd into a vision content
part, which Anthropic then rejected with a generic 400.

Fix: trust the per-attachment MIME when it's known; only fall back to
the message-level type when the per-attachment slot is empty/unknown.
"""

from __future__ import annotations

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent, MessageType
from gateway.run import GatewayRunner
from gateway.session import SessionSource, build_session_key


def _make_runner() -> GatewayRunner:
    runner = GatewayRunner.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.DISCORD: PlatformConfig(enabled=True, token="fake")},
    )
    runner.adapters = {}
    runner._model = "anthropic/claude-sonnet-4"
    runner._base_url = None
    runner._decide_image_input_mode = lambda: "native"
    return runner


def _source() -> SessionSource:
    return SessionSource(
        platform=Platform.DISCORD,
        chat_id="chat-mixed",
        chat_type="thread",
        user_name="user-mixed",
    )


@pytest.mark.asyncio
async def test_image_plus_document_only_image_routed_as_image():
    """When a message carries one PNG + one MD document, only the PNG
    should land in the native-image buffer. The MD must NOT be base64'd
    into a vision content part -- that's the bug Anthropic returns 400
    for ("Could not process image").
    """
    runner = _make_runner()
    source = _source()

    event = MessageEvent(
        text="here are some images and the meeting notes",
        # Discord sets PHOTO at the message level whenever ANY attachment
        # is an image; the per-attachment MIME is the authoritative signal.
        message_type=MessageType.PHOTO,
        source=source,
        media_urls=["/tmp/scan.png", "/tmp/transcript.md"],
        media_types=["image/png", "text/markdown"],
    )

    await runner._prepare_inbound_message_text(
        event=event,
        source=source,
        history=[],
    )

    pending = runner._consume_pending_native_image_paths(build_session_key(source))
    assert pending == ["/tmp/scan.png"], (
        f"Only the image should be routed as a native image; got: {pending}"
    )


@pytest.mark.asyncio
async def test_multiple_images_plus_document_only_images_routed():
    """Variant of the user-reported failure: 3 PNGs + 1 MD upload should
    route exactly 3 images, not 4.
    """
    runner = _make_runner()
    source = _source()

    event = MessageEvent(
        text="three pngs and a transcript",
        message_type=MessageType.PHOTO,
        source=source,
        media_urls=[
            "/tmp/raw.png", "/tmp/realsrgan.png", "/tmp/rrn.png",
            "/tmp/Weekly_Video_pipeline_sync.md",
        ],
        media_types=["image/png", "image/png", "image/png", "text/markdown"],
    )

    await runner._prepare_inbound_message_text(
        event=event,
        source=source,
        history=[],
    )

    pending = runner._consume_pending_native_image_paths(build_session_key(source))
    assert pending == ["/tmp/raw.png", "/tmp/realsrgan.png", "/tmp/rrn.png"], (
        f"Document must not be routed as a 4th image; got: {pending}"
    )


@pytest.mark.asyncio
async def test_unknown_mime_falls_back_to_message_type_for_image():
    """Backward compatibility: legacy adapters that set message_type=PHOTO
    but leave media_types empty (or with blank strings) still get their
    media routed as images. This keeps existing platforms working.
    """
    runner = _make_runner()
    source = _source()

    event = MessageEvent(
        text="legacy adapter, no per-attachment MIME",
        message_type=MessageType.PHOTO,
        source=source,
        media_urls=["/tmp/legacy.png"],
        media_types=[""],
    )

    await runner._prepare_inbound_message_text(
        event=event,
        source=source,
        history=[],
    )

    assert runner._consume_pending_native_image_paths(
        build_session_key(source)
    ) == ["/tmp/legacy.png"]


@pytest.mark.asyncio
async def test_document_only_message_routes_nothing_as_image():
    """A message with only a non-image attachment (and no PHOTO type)
    should not route anything as an image.
    """
    runner = _make_runner()
    source = _source()

    event = MessageEvent(
        text="just a doc",
        message_type=MessageType.DOCUMENT,
        source=source,
        media_urls=["/tmp/report.pdf"],
        media_types=["application/pdf"],
    )

    await runner._prepare_inbound_message_text(
        event=event,
        source=source,
        history=[],
    )

    assert runner._consume_pending_native_image_paths(build_session_key(source)) == []


@pytest.mark.asyncio
async def test_audio_alongside_image_not_cross_routed():
    """Audio attachments alongside an image must not get routed as an
    image even if message_type happens to be PHOTO (symmetric to the
    document case).
    """
    runner = _make_runner()
    source = _source()

    event = MessageEvent(
        text="image + voice note",
        message_type=MessageType.PHOTO,
        source=source,
        media_urls=["/tmp/photo.jpg", "/tmp/voice.ogg"],
        media_types=["image/jpeg", "audio/ogg"],
    )

    await runner._prepare_inbound_message_text(
        event=event,
        source=source,
        history=[],
    )

    pending = runner._consume_pending_native_image_paths(build_session_key(source))
    assert pending == ["/tmp/photo.jpg"], (
        f"Audio must not be routed as an image; got: {pending}"
    )
