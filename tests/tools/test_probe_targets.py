"""Tests for tools/probe_targets_tool.py — declarative parallel HTTP probe."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest
import yaml

from tools import probe_targets_tool as mod
from tools.probe_targets_tool import (
    DEFAULT_CONCURRENCY,
    ProbeResult,
    _catalogue_path,
    _filter_targets,
    _interpolate,
    _load_catalogue,
    _looks_blocked,
    _probe_one,
    _validate_value,
    probe_targets_tool,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _mock_client(handler):
    """Return an httpx.AsyncClient backed by a MockTransport running *handler*."""
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport, follow_redirects=True)


async def _probe(target: dict, value: str, handler, timeout: float = 2.0) -> ProbeResult:
    async with _mock_client(handler) as client:
        return await _probe_one(target, value, client, timeout, global_regex=None)


# ─── _interpolate ─────────────────────────────────────────────────────────────


class TestInterpolate:
    def test_string(self):
        assert _interpolate("https://x.com/{value}", "nasa") == "https://x.com/nasa"

    def test_dict_recursive(self):
        result = _interpolate({"username": "{value}", "nested": {"name": "{value}"}}, "nasa")
        assert result == {"username": "nasa", "nested": {"name": "nasa"}}

    def test_list_recursive(self):
        assert _interpolate(["{value}", "static"], "nasa") == ["nasa", "static"]

    def test_non_string_passthrough(self):
        assert _interpolate(42, "nasa") == 42
        assert _interpolate(None, "nasa") is None


# ─── _validate_value ──────────────────────────────────────────────────────────


class TestValidateValue:
    def test_passes_when_no_regex(self):
        assert _validate_value("nasa", {}, None) is None

    def test_passes_when_matches_global(self):
        import re
        regex = re.compile(r"^[a-z]+$")
        assert _validate_value("nasa", {}, regex) is None

    def test_rejects_when_global_mismatch(self):
        import re
        regex = re.compile(r"^[a-z]+$")
        reject = _validate_value("NASA42", {}, regex)
        assert reject is not None
        assert "does not match" in reject

    def test_per_target_overrides_global(self):
        import re
        global_regex = re.compile(r"^.*$")  # permissive
        target = {"value_regex": r"^[0-9]+$"}  # strict
        assert _validate_value("abc", target, global_regex) is not None

    def test_invalid_regex_ignored(self):
        target = {"value_regex": "[invalid("}
        assert _validate_value("anything", target, None) is None


# ─── _looks_blocked ───────────────────────────────────────────────────────────


class TestLooksBlocked:
    def test_429_always_blocked(self):
        assert _looks_blocked(429, "") is True

    def test_403_with_cloudflare_blocked(self):
        assert _looks_blocked(403, "attention required | cloudflare") is True

    def test_403_without_markers_not_blocked(self):
        assert _looks_blocked(403, "forbidden") is False

    def test_503_with_just_a_moment_blocked(self):
        assert _looks_blocked(503, "just a moment...") is True

    def test_200_clean_not_blocked(self):
        assert _looks_blocked(200, "profile page content") is False

    def test_200_combined_captcha_blocked(self):
        assert _looks_blocked(200, "just a moment - please solve captcha") is True


# ─── _probe_one detection branches ────────────────────────────────────────────


@pytest.mark.asyncio
class TestProbeOneDetection:
    async def test_status_code_hit_on_200(self):
        def handler(request):
            return httpx.Response(200, text="profile")

        target = {
            "name": "ExampleHit",
            "url": "https://example.com/{value}",
            "detect": "status_code",
            "error_status": 404,
        }
        result = await _probe(target, "nasa", handler)
        assert result.status == "hit"
        assert result.http_status == 200

    async def test_status_code_miss_on_404(self):
        def handler(request):
            return httpx.Response(404, text="not found")

        target = {
            "name": "ExampleMiss",
            "url": "https://example.com/{value}",
            "detect": "status_code",
            "error_status": 404,
        }
        result = await _probe(target, "nasa", handler)
        assert result.status == "miss"
        assert result.http_status == 404

    async def test_body_absent_hit_when_marker_absent(self):
        def handler(request):
            return httpx.Response(200, text="welcome to your profile")

        target = {
            "name": "ExampleBody",
            "url": "https://example.com/{value}",
            "detect": "body_absent",
            "error_strings": ["user not found"],
        }
        result = await _probe(target, "nasa", handler)
        assert result.status == "hit"

    async def test_body_absent_miss_when_marker_present(self):
        def handler(request):
            return httpx.Response(200, text="sorry, user not found here")

        target = {
            "name": "ExampleBody",
            "url": "https://example.com/{value}",
            "detect": "body_absent",
            "error_strings": ["user not found"],
        }
        result = await _probe(target, "nasa", handler)
        assert result.status == "miss"

    async def test_body_absent_404_always_miss(self):
        """A 404 should be a miss even if error_strings aren't in its body."""
        def handler(request):
            return httpx.Response(404, text="generic 404 page")

        target = {
            "name": "ExampleBody",
            "url": "https://example.com/{value}",
            "detect": "body_absent",
            "error_strings": ["no such user"],
        }
        result = await _probe(target, "nasa", handler)
        assert result.status == "miss"

    async def test_body_contains_hit(self):
        def handler(request):
            return httpx.Response(200, text="user claimed")

        target = {
            "name": "Example",
            "url": "https://example.com/{value}",
            "detect": "body_contains",
            "error_strings": ["user claimed"],
        }
        result = await _probe(target, "nasa", handler)
        assert result.status == "hit"

    async def test_redirects_to_hit_when_url_stays(self):
        def handler(request):
            return httpx.Response(200, text="profile", request=request)

        target = {
            "name": "Example",
            "url": "https://example.com/{value}",
            "detect": "redirects_to",
            "redirect_to": "https://example.com/",
        }
        result = await _probe(target, "nasa", handler)
        assert result.status == "hit"

    async def test_redirects_to_miss_when_redirected(self):
        def handler(request):
            if str(request.url) == "https://example.com/nasa":
                return httpx.Response(302, headers={"location": "https://example.com/"})
            return httpx.Response(200, text="home", request=request)

        target = {
            "name": "Example",
            "url": "https://example.com/{value}",
            "detect": "redirects_to",
            "redirect_to": "https://example.com/",
        }
        result = await _probe(target, "nasa", handler)
        assert result.status == "miss"

    async def test_pre_validate_rejects_before_network(self):
        called = []

        def handler(request):
            called.append(request.url)
            return httpx.Response(200)

        target = {
            "name": "Strict",
            "url": "https://example.com/{value}",
            "detect": "status_code",
            "value_regex": r"^[a-z]+$",
        }
        result = await _probe(target, "BAD_42", handler)
        assert result.status == "invalid"
        assert called == []  # no network I/O happened

    async def test_waf_block_detected(self):
        def handler(request):
            return httpx.Response(
                403,
                text="<html>Attention Required! | Cloudflare</html>",
            )

        target = {
            "name": "CFProtected",
            "url": "https://example.com/{value}",
            "detect": "status_code",
            "error_status": 404,
        }
        result = await _probe(target, "nasa", handler)
        assert result.status == "blocked"

    async def test_post_body_placeholder_interpolated(self):
        received = {}

        def handler(request):
            received["url"] = str(request.url)
            received["body"] = request.content
            return httpx.Response(200, text="ok")

        target = {
            "name": "PostSite",
            "url": "https://example.com/profile/{value}",
            "url_probe": "https://api.example.com/check",
            "method": "POST",
            "body": {"username": "{value}"},
            "detect": "status_code",
            "error_status": 404,
        }
        result = await _probe(target, "nasa", handler)
        assert result.status == "hit"
        assert received["url"] == "https://api.example.com/check"
        assert b'"username":"nasa"' in received["body"] or b'"username": "nasa"' in received["body"]


# ─── _filter_targets ──────────────────────────────────────────────────────────


class TestFilterTargets:
    TARGETS = [
        {"name": "GitHub", "category": "dev"},
        {"name": "Twitter", "category": "social"},
        {"name": "Reddit", "category": "social"},
    ]

    def test_no_filters(self):
        assert len(_filter_targets(self.TARGETS, None, None)) == 3

    def test_category_filter(self):
        result = _filter_targets(self.TARGETS, ["social"], None)
        assert [t["name"] for t in result] == ["Twitter", "Reddit"]

    def test_category_case_insensitive(self):
        result = _filter_targets(self.TARGETS, ["SOCIAL"], None)
        assert len(result) == 2

    def test_target_names_filter(self):
        result = _filter_targets(self.TARGETS, None, ["GitHub", "Reddit"])
        assert [t["name"] for t in result] == ["GitHub", "Reddit"]

    def test_combined_filters(self):
        result = _filter_targets(self.TARGETS, ["social"], ["Reddit"])
        assert [t["name"] for t in result] == ["Reddit"]


# ─── Catalogue loading ────────────────────────────────────────────────────────


class TestCatalogueLoading:
    def test_catalogue_path_sanitises_name(self):
        assert _catalogue_path("usernames").name == "usernames.yaml"
        assert _catalogue_path("../etc/passwd").name == "etcpasswd.yaml"

    def test_catalogue_path_rejects_empty(self):
        with pytest.raises(ValueError):
            _catalogue_path("/")

    def test_load_catalogue_from_tmp(self, tmp_path, monkeypatch):
        custom_dir = tmp_path / "probe-targets"
        custom_dir.mkdir()
        (custom_dir / "test.yaml").write_text(
            yaml.safe_dump(
                {
                    "version": 1,
                    "concurrency": 5,
                    "targets": [
                        {
                            "name": "Demo",
                            "url": "https://demo.example/{value}",
                            "detect": "status_code",
                            "error_status": 404,
                        }
                    ],
                }
            )
        )
        monkeypatch.setattr(mod, "PROBE_TARGETS_DIR", custom_dir)
        # Clear cache so the monkeypatched dir is used.
        mod._CATALOGUE_CACHE.clear()

        doc = _load_catalogue("test")
        assert doc["concurrency"] == 5
        assert len(doc["targets"]) == 1

    def test_load_catalogue_missing_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "PROBE_TARGETS_DIR", tmp_path)
        mod._CATALOGUE_CACHE.clear()
        with pytest.raises(FileNotFoundError):
            _load_catalogue("nope")


# ─── End-to-end handler ───────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestTopLevelHandler:
    async def test_missing_value_errors(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "PROBE_TARGETS_DIR", tmp_path)
        mod._CATALOGUE_CACHE.clear()
        result = json.loads(await probe_targets_tool(value=""))
        assert "error" in result

    async def test_missing_catalogue_errors(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "PROBE_TARGETS_DIR", tmp_path)
        mod._CATALOGUE_CACHE.clear()
        result = json.loads(await probe_targets_tool(value="nasa", target_set="nonexistent"))
        assert "error" in result
        assert "not found" in result["error"].lower()

    async def test_full_run_with_mock_transport(self, tmp_path, monkeypatch):
        """Full pipeline: load YAML → filter → probe → aggregate summary."""
        custom_dir = tmp_path / "probe-targets"
        custom_dir.mkdir()
        (custom_dir / "demo.yaml").write_text(
            yaml.safe_dump(
                {
                    "version": 1,
                    "concurrency": 4,
                    "pre_validate": {"value_regex": r"^[a-z]+$"},
                    "targets": [
                        {
                            "name": "AlphaHit",
                            "url": "https://alpha.example/{value}",
                            "detect": "status_code",
                            "error_status": 404,
                        },
                        {
                            "name": "BetaMiss",
                            "url": "https://beta.example/{value}",
                            "detect": "status_code",
                            "error_status": 404,
                        },
                        {
                            "name": "GammaBlocked",
                            "url": "https://gamma.example/{value}",
                            "detect": "status_code",
                            "error_status": 404,
                        },
                    ],
                }
            )
        )
        monkeypatch.setattr(mod, "PROBE_TARGETS_DIR", custom_dir)
        mod._CATALOGUE_CACHE.clear()

        def handler(request):
            url = str(request.url)
            if url.startswith("https://alpha."):
                return httpx.Response(200, text="profile")
            if url.startswith("https://beta."):
                return httpx.Response(404, text="not found")
            if url.startswith("https://gamma."):
                return httpx.Response(429, text="rate limited")
            return httpx.Response(500)

        # Replace httpx.AsyncClient with a factory that uses our MockTransport.
        real_async_client = httpx.AsyncClient
        transport = httpx.MockTransport(handler)

        def mock_async_client(*args, **kwargs):
            kwargs.pop("limits", None)
            kwargs.pop("http2", None)
            return real_async_client(transport=transport, **kwargs)

        monkeypatch.setattr(mod.httpx, "AsyncClient", mock_async_client)

        raw = await probe_targets_tool(value="nasa", target_set="demo")
        result = json.loads(raw)

        assert result["summary"]["total"] == 3
        assert result["summary"]["hits"] == 1
        assert result["summary"]["misses"] == 1
        assert result["summary"]["blocked"] == 1
        assert result["summary"]["errors"] == 0
        hit_names = [h["name"] for h in result["hits"]]
        assert hit_names == ["AlphaHit"]
        blocked_names = [b["name"] for b in result["blocked"]]
        assert blocked_names == ["GammaBlocked"]

    async def test_concurrency_cap_respected(self, tmp_path, monkeypatch):
        """In-flight count must never exceed the configured concurrency."""
        custom_dir = tmp_path / "probe-targets"
        custom_dir.mkdir()
        cap = 3
        num_targets = 12
        targets = [
            {
                "name": f"Target{i}",
                "url": f"https://t{i}.example/{{value}}",
                "detect": "status_code",
                "error_status": 404,
            }
            for i in range(num_targets)
        ]
        (custom_dir / "cap.yaml").write_text(
            yaml.safe_dump({"version": 1, "concurrency": cap, "targets": targets})
        )
        monkeypatch.setattr(mod, "PROBE_TARGETS_DIR", custom_dir)
        mod._CATALOGUE_CACHE.clear()

        in_flight = 0
        max_in_flight = 0
        lock = asyncio.Lock()

        async def slow_handler(request):
            nonlocal in_flight, max_in_flight
            async with lock:
                in_flight += 1
                max_in_flight = max(max_in_flight, in_flight)
            await asyncio.sleep(0.05)
            async with lock:
                in_flight -= 1
            return httpx.Response(200, text="ok")

        real_async_client = httpx.AsyncClient
        transport = httpx.MockTransport(slow_handler)

        def mock_async_client(*args, **kwargs):
            kwargs.pop("limits", None)
            kwargs.pop("http2", None)
            return real_async_client(transport=transport, **kwargs)

        monkeypatch.setattr(mod.httpx, "AsyncClient", mock_async_client)

        await probe_targets_tool(value="nasa", target_set="cap")
        assert max_in_flight <= cap, f"max in-flight {max_in_flight} exceeded cap {cap}"
