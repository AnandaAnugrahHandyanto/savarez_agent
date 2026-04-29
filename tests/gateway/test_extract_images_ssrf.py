"""Tests for SSRF protection in outbound image URL extraction.

extract_images() parses model responses for image URLs. Platform adapters
then fetch these URLs server-side via send_image(). Without SSRF
protection, a model response containing <img src="http://169.254.169.254/...">
causes the gateway to fetch cloud metadata endpoints.

This is a different code path from cache_image_from_url() (inbound
attachment caching, covered by PR #4687). This covers the outbound
LLM-response → send_image() path.
"""

from gateway.platforms.base import BasePlatformAdapter


class TestExtractImagesSSRF:

    def test_metadata_endpoint_extracted(self):
        """Verify extract_images picks up the URL (the raw bug)."""
        images, _ = BasePlatformAdapter.extract_images(
            '<img src="http://169.254.169.254/latest/meta-data/">'
        )
        # extract_images itself doesn't filter — it just parses
        assert len(images) == 1
        assert "169.254.169.254" in images[0][0]

    def test_private_ip_extracted(self):
        images, _ = BasePlatformAdapter.extract_images(
            '![logo](http://192.168.1.1/admin/logo.png)'
        )
        assert len(images) == 1

    def test_public_url_extracted(self):
        images, _ = BasePlatformAdapter.extract_images(
            '![chart](https://example.com/chart.png)'
        )
        assert len(images) == 1
        assert "example.com" in images[0][0]

    def test_safe_url_check_blocks_private(self):
        """The is_safe_url guard in _process_message_background blocks SSRF."""
        from gateway.platforms.base import _is_safe_url
        assert _is_safe_url("http://169.254.169.254/meta-data/") is False
        assert _is_safe_url("http://127.0.0.1:8080/secret") is False
        assert _is_safe_url("http://192.168.1.1/admin") is False

    def test_safe_url_allows_public(self, monkeypatch):
        from gateway.platforms.base import _is_safe_url
        from tools import url_safety

        monkeypatch.setattr(
            url_safety.socket,
            "getaddrinfo",
            lambda *args, **kwargs: [
                (url_safety.socket.AF_INET, url_safety.socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))
            ],
        )
        assert _is_safe_url("https://example.com/image.png") is True
