"""Tests for the ``image_edit`` tool wrapper."""

from __future__ import annotations

import json

from tools import image_edit_tool


class _FakeProvider:
    name = "fake"

    def __init__(self):
        self.calls = []

    def edit(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "success": True,
            "image": "/tmp/edited.png",
            "provider": self.name,
            "prompt": kwargs["prompt"],
            "aspect_ratio": kwargs["aspect_ratio"],
        }


def test_requires_reference_images():
    result = json.loads(image_edit_tool._handle_image_edit({"prompt": "make it cute"}))
    assert result["success"] is False
    assert result["error_type"] == "invalid_argument"


def test_rejects_implicit_last_image_reuse():
    result = json.loads(image_edit_tool._handle_image_edit({
        "prompt": "make it cute",
        "use_last_generated_image": True,
        "reference_images": ["/tmp/a.png"],
    }))
    assert result["success"] is False
    assert result["error_type"] == "unsupported_operation"


def test_dispatches_to_active_provider(monkeypatch):
    provider = _FakeProvider()
    monkeypatch.setattr(image_edit_tool, "_load_provider", lambda: (provider, "fake"))

    result = json.loads(image_edit_tool._handle_image_edit({
        "prompt": "keep the logo, warmer style",
        "reference_images": ["/tmp/ref.png"],
        "aspect_ratio": "square",
        "quality": "high",
        "mode": "reference",
    }))

    assert result["success"] is True
    assert result["image"] == "/tmp/edited.png"
    assert provider.calls[0]["reference_images"] == ["/tmp/ref.png"]
    assert provider.calls[0]["quality"] == "high"
    assert provider.calls[0]["mode"] == "reference"
