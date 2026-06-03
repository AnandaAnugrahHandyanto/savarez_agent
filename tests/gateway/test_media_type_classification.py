from gateway.platforms.base import MessageEvent, MessageType
from gateway.run import _build_media_placeholder


def test_photo_event_with_text_attachment_does_not_call_text_file_an_image():
    event = MessageEvent(
        text="",
        message_type=MessageType.PHOTO,
        media_urls=["/tmp/screenshot.png", "/tmp/message.txt"],
        media_types=["image/png", "text/plain"],
    )

    placeholder = _build_media_placeholder(event)

    assert "[User sent an image: /tmp/screenshot.png]" in placeholder
    assert "[User sent a file: /tmp/message.txt]" in placeholder
    assert "[User sent an image: /tmp/message.txt]" not in placeholder
