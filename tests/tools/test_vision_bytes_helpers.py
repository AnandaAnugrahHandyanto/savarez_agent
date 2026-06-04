"""Bytes-core variants of the vision encode/resize/sniff helpers."""
import base64

from tools.vision_tools import (
    _detect_image_mime_type_from_bytes,
    _image_bytes_to_base64_data_url,
    _resize_image_bytes_for_vision,
)

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def test_detect_mime_from_bytes_png():
    assert _detect_image_mime_type_from_bytes(PNG) == "image/png"


def test_detect_mime_from_bytes_jpeg():
    assert _detect_image_mime_type_from_bytes(b"\xff\xd8\xff\xe0junk") == "image/jpeg"


def test_detect_mime_from_bytes_rejects_text():
    assert _detect_image_mime_type_from_bytes(b"not an image") is None


def test_detect_mime_from_bytes_rejects_svg():
    # SVG has no magic bytes; the bytes sniff deliberately rejects it.
    assert _detect_image_mime_type_from_bytes(b"<svg xmlns=...></svg>") is None


def test_bytes_to_data_url_roundtrip():
    url = _image_bytes_to_base64_data_url(PNG, "image/png")
    assert url.startswith("data:image/png;base64,")
    assert base64.b64decode(url.split(",", 1)[1]) == PNG


def test_resize_bytes_noop_when_small():
    url = _resize_image_bytes_for_vision(PNG, "image/png")
    assert url == _image_bytes_to_base64_data_url(PNG, "image/png")
