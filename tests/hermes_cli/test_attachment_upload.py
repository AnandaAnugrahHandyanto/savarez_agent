"""Tests for POST /api/attachments -- the dashboard attachment-upload endpoint.

This is the backend half of the remote-desktop image fix. The desktop app writes
composer images to its own machine, so when it drives a REMOTE dashboard the
local ``C:\\...`` path is unreadable here. The desktop uploads the bytes as a
base64 data URL; this endpoint caches them on the *backend* filesystem and
returns a backend path the chat can reference. These tests assert the request
contract and that the stored file actually lands on the backend host.
"""

import base64
import os

import pytest

# 1x1 transparent PNG.
_PNG_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _png_data_url() -> str:
    return "data:image/png;base64," + base64.b64encode(_PNG_1x1).decode("ascii")


def _client():
    try:
        from starlette.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")
    from hermes_cli.web_server import app, _SESSION_HEADER_NAME, _SESSION_TOKEN

    client = TestClient(app)
    client.headers[_SESSION_HEADER_NAME] = _SESSION_TOKEN
    return client


class TestAttachmentUpload:
    @pytest.fixture(autouse=True)
    def _setup(self, _isolate_hermes_home):
        self.client = _client()

    def test_image_upload_caches_on_backend(self):
        r = self.client.post(
            "/api/attachments",
            json={"data_url": _png_data_url(), "filename": "composer.png"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["bytes"] == len(_PNG_1x1)

        stored = body["path"]
        # The returned path must be a real file on THIS (backend) host -- never a
        # passed-through client path.
        assert os.path.isfile(stored)
        assert stored.lower().endswith(".png")
        with open(stored, "rb") as fh:
            assert fh.read() == _PNG_1x1

    def test_rejects_windows_client_path(self):
        # A raw C:\ path is exactly what used to leak through to the backend; it
        # is not a data URL, so the endpoint rejects it instead of trying to
        # read a path that doesn't exist here.
        r = self.client.post(
            "/api/attachments",
            json={"data_url": r"C:\Users\justi\AppData\Roaming\Hermes\composer-images\x.png"},
        )
        assert r.status_code == 400

    def test_rejects_non_base64(self):
        r = self.client.post(
            "/api/attachments", json={"data_url": "data:image/png,not-base64"}
        )
        assert r.status_code == 400

    def test_rejects_unsupported_mime(self):
        payload = "data:application/x-msdownload;base64," + base64.b64encode(
            b"MZ\x90\x00"
        ).decode("ascii")
        r = self.client.post("/api/attachments", json={"data_url": payload})
        assert r.status_code == 415

    def test_rejects_non_image_bytes_labeled_image(self):
        # HTML mislabeled as image/png -- the cache_image_from_bytes magic-byte
        # guard must reject it (400), not silently store an HTML "image".
        payload = "data:image/png;base64," + base64.b64encode(
            b"<html>nope</html>"
        ).decode("ascii")
        r = self.client.post("/api/attachments", json={"data_url": payload})
        assert r.status_code == 400

    def test_rejects_oversize(self):
        from hermes_cli import web_server

        big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (web_server._MAX_ATTACHMENT_UPLOAD_BYTES + 1)
        payload = "data:image/png;base64," + base64.b64encode(big).decode("ascii")
        r = self.client.post("/api/attachments", json={"data_url": payload})
        assert r.status_code == 413
