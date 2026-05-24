"""Tests for Camofox-backed web_extract plugin."""

from __future__ import annotations

import asyncio


class MockResponse:
    def __init__(self, data=None, status_code=200, error: Exception | None = None):
        self._data = data or {}
        self.status_code = status_code
        self._error = error

    def json(self):
        return self._data

    def raise_for_status(self):
        if self._error:
            raise self._error
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


SNAPSHOT = """
- document:
  - heading "Example Domain" [level=1] [ref=e1]
  - paragraph: This domain is for examples.
  - link "Learn more" [ref=e2]:
    - /url: https://iana.org/domains/example
  - button "Accept cookies" [ref=e3]
"""


def test_camofox_provider_available_requires_configured_healthy_server(monkeypatch):
    from plugins.web.camofox.provider import CamofoxWebSearchProvider

    provider = CamofoxWebSearchProvider()

    monkeypatch.delenv("CAMOFOX_URL", raising=False)
    assert provider.is_available() is False

    monkeypatch.setenv("CAMOFOX_URL", "http://localhost:9377")
    monkeypatch.setattr(
        "plugins.web.camofox.provider.requests.get",
        lambda *args, **kwargs: MockResponse({"ok": True}, status_code=200),
    )
    assert provider.is_available() is True

    monkeypatch.setattr(
        "plugins.web.camofox.provider.requests.get",
        lambda *args, **kwargs: MockResponse({"ok": False}, status_code=503),
    )
    assert provider.is_available() is False


def test_camofox_provider_extract_creates_tab_reads_snapshot_and_cleans_up(monkeypatch):
    from plugins.web.camofox.provider import CamofoxWebSearchProvider, _extract_single

    calls = []

    def fake_post(url, json=None, timeout=None):
        calls.append(("post", url, json, timeout))
        if url.endswith("/tabs"):
            return MockResponse({"tabId": "tab-123", "title": "Example Domain"})
        if url.endswith("/tabs/tab-123/wait"):
            return MockResponse({"ok": True})
        raise AssertionError(f"unexpected POST {url}")

    def fake_get(url, params=None, timeout=None):
        calls.append(("get", url, params, timeout))
        assert url == "http://localhost:9377/tabs/tab-123/snapshot"
        return MockResponse({
            "snapshot": SNAPSHOT,
            "title": "Example Domain",
            "url": "https://example.com/",
        })

    def fake_delete(url, json=None, timeout=None):
        calls.append(("delete", url, json, timeout))
        return MockResponse({"ok": True})

    monkeypatch.setenv("CAMOFOX_URL", "http://localhost:9377/")
    monkeypatch.setattr("plugins.web.camofox.provider.requests.post", fake_post)
    monkeypatch.setattr("plugins.web.camofox.provider.requests.get", fake_get)
    monkeypatch.setattr("plugins.web.camofox.provider.requests.delete", fake_delete)

    result = _extract_single("https://example.com/")

    assert result["url"] == "https://example.com/"
    assert result["title"] == "Example Domain"
    assert "# Example Domain" in result["content"]
    assert "[Learn more](https://iana.org/domains/example)" in result["content"]
    assert "Accept cookies" not in result["content"]
    assert "ref=e" not in result["content"]
    assert result["raw_content"] == result["content"]
    assert result["metadata"]["extractor"] == "camofox"
    assert any(call[0] == "delete" and call[1] == "http://localhost:9377/sessions/" + call[2]["userId"] for call in calls)


def test_camofox_provider_extract_single_returns_per_url_error_and_still_cleans_up(monkeypatch):
    from plugins.web.camofox.provider import _extract_single

    deletes = []

    def fake_post(url, json=None, timeout=None):
        return MockResponse(status_code=500)

    def fake_delete(url, json=None, timeout=None):
        deletes.append((url, json))
        return MockResponse({"ok": True})

    monkeypatch.setenv("CAMOFOX_URL", "http://localhost:9377")
    monkeypatch.setattr("plugins.web.camofox.provider.requests.post", fake_post)
    monkeypatch.setattr("plugins.web.camofox.provider.requests.delete", fake_delete)

    result = _extract_single("https://bad.example/")

    assert result["url"] == "https://bad.example/"
    assert result["title"] == ""
    assert result["content"] == ""
    assert "error" in result
    assert deletes, "ephemeral Camofox session should be cleaned up even after failure"


def test_camofox_provider_extract_batches_without_cross_url_failure(monkeypatch):
    from plugins.web.camofox.provider import CamofoxWebSearchProvider

    def fake_single(url):
        if "bad" in url:
            return {"url": url, "title": "", "content": "", "error": "boom"}
        return {"url": url, "title": "OK", "content": "# OK", "raw_content": "# OK"}

    def fake_check_website_access(url):
        return None

    def fake_is_safe_url(url):
        return True

    monkeypatch.setattr("plugins.web.camofox.provider._extract_single", fake_single)
    monkeypatch.setattr("tools.website_policy.check_website_access", fake_check_website_access)
    monkeypatch.setattr("tools.url_safety.is_safe_url", fake_is_safe_url)

    provider = CamofoxWebSearchProvider()
    results = asyncio.run(provider.extract(["https://ok.example/", "https://bad.example/"]))

    assert results[0]["content"] == "# OK"
    assert results[1]["error"] == "boom"


def test_camofox_provider_requires_llm_processing_returns_false():
    from plugins.web.camofox.provider import CamofoxWebSearchProvider

    provider = CamofoxWebSearchProvider()
    assert provider.requires_llm_processing() is False


def test_camofox_provider_supports_extract_but_not_search():
    from plugins.web.camofox.provider import CamofoxWebSearchProvider

    provider = CamofoxWebSearchProvider()
    assert provider.supports_search() is False
    assert provider.supports_extract() is True
    assert provider.supports_crawl() is False
