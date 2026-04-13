"""Tests for Guard-backed Hermes MCP runtime policy checks."""

from __future__ import annotations

import httpx

from tools.guard_runtime_policy import evaluate_guard_tool_call


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "request failed",
                request=httpx.Request("GET", "https://hol.org"),
                response=httpx.Response(self.status_code),
            )


class _FakeClient:
    def __init__(self, routes, recorded_posts):
        self._routes = routes
        self._recorded_posts = recorded_posts

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url, headers=None):
        key = ("GET", url)
        payload = self._routes.get(key)
        if isinstance(payload, Exception):
            raise payload
        if payload is None:
            return _FakeResponse({})
        return _FakeResponse(payload)

    def post(self, url, headers=None, json=None):
        self._recorded_posts.append({"url": url, "headers": headers, "json": json})
        payload = self._routes.get(("POST", url), {})
        if isinstance(payload, Exception):
            raise payload
        return _FakeResponse(payload)


def _patch_guard(monkeypatch, routes, *, token="guard-token", fail_open=True):
    recorded_posts = []

    monkeypatch.setattr(
        "tools.guard_runtime_policy.load_config",
        lambda: {
            "guard": {
                "enabled": True,
                "base_url": "https://guard.example/api/v1/consumer",
                "timeout_seconds": 5,
                "fail_open": fail_open,
                "cache_ttl_seconds": 1,
                "token_env_var": "HERMES_GUARD_TOKEN",
                "enforce_mcp_tools": True,
                "pain_signals_enabled": True,
            }
        },
    )
    monkeypatch.setattr(
        "tools.guard_runtime_policy._load_mcp_config",
        lambda: {
            "github": {
                "url": "https://mcp.github.example/mcp",
            }
        },
    )
    monkeypatch.setattr(
        "tools.guard_runtime_policy.httpx.Client",
        lambda timeout: _FakeClient(routes, recorded_posts),
    )
    monkeypatch.setattr("tools.guard_runtime_policy.time.time", lambda: 1_700_000_000.0)
    monkeypatch.setattr("tools.guard_runtime_policy._CACHE", {})
    if token:
        monkeypatch.setenv("HERMES_GUARD_TOKEN", token)
    else:
        monkeypatch.delenv("HERMES_GUARD_TOKEN", raising=False)
    return recorded_posts


def test_ignores_non_mcp_tool(monkeypatch):
    _patch_guard(monkeypatch, {})
    assert evaluate_guard_tool_call("web_search", {"q": "x"}) is None


def test_blocks_watchlisted_mcp_tool_and_emits_pain_signal(monkeypatch):
    routes = {
        ("GET", "https://guard.example/api/v1/consumer/exceptions"): {"items": []},
        ("GET", "https://guard.example/api/v1/consumer/team/policy-pack"): {
            "blockedArtifacts": [],
            "blockedDomains": [],
            "blockedPublishers": [],
        },
        ("GET", "https://guard.example/api/v1/consumer/watchlist"): {
            "items": [
                {
                    "artifactId": "mcp:hermes:github",
                    "artifactName": "github",
                    "artifactSlug": "github",
                    "reason": "Known data exfiltration behavior.",
                }
            ]
        },
        ("POST", "https://guard.example/api/v1/consumer/signals/pain"): {"items": []},
    }
    recorded_posts = _patch_guard(monkeypatch, routes)

    result = evaluate_guard_tool_call("mcp_github_create_issue", {"title": "x"})

    assert result is not None
    assert result.source == "watchlist"
    assert "Known data exfiltration behavior." in result.reason
    assert len(recorded_posts) == 3
    assert recorded_posts[0]["url"].endswith("/verdict/pre-execution")
    assert recorded_posts[1]["url"].endswith("/receipts/submit")
    assert recorded_posts[2]["json"]["items"][0]["artifactId"] == "mcp:hermes:github"


def test_active_exception_allows_mcp_tool(monkeypatch):
    routes = {
        ("GET", "https://guard.example/api/v1/consumer/exceptions"): {
            "items": [
                {
                    "scope": "artifact",
                    "artifactId": "mcp:hermes:github",
                    "expiresAt": "2099-01-01T00:00:00Z",
                }
            ]
        },
    }
    _patch_guard(monkeypatch, routes)

    result = evaluate_guard_tool_call("mcp_github_create_issue", {"title": "x"})

    assert result is None


def test_preexecution_verdict_blocks_before_fallback_lookups(monkeypatch):
    routes = {
        ("POST", "https://guard.example/api/v1/consumer/verdict/pre-execution"): {
            "decision": "block",
            "rationale": "Team policy blocks github before execution.",
            "scope": "artifact",
        },
        ("POST", "https://guard.example/api/v1/consumer/signals/pain"): {"items": []},
    }
    recorded_posts = _patch_guard(monkeypatch, routes)

    result = evaluate_guard_tool_call("mcp_github_create_issue", {"title": "x"})

    assert result is not None
    assert result.source == "preexecution-artifact"
    assert result.recommendation == "block"
    assert len(recorded_posts) == 3
    assert recorded_posts[0]["url"].endswith("/verdict/pre-execution")
    assert recorded_posts[0]["json"]["artifactId"] == "mcp:hermes:github"
    assert recorded_posts[1]["url"].endswith("/receipts/submit")


def test_verdict_investigate_blocks_when_no_exception(monkeypatch):
    routes = {
        ("POST", "https://guard.example/api/v1/consumer/verdict/pre-execution"): httpx.ConnectError(
            "offline"
        ),
        ("GET", "https://guard.example/api/v1/consumer/exceptions"): {"items": []},
        ("GET", "https://guard.example/api/v1/consumer/team/policy-pack"): {
            "blockedArtifacts": [],
            "blockedDomains": [],
            "blockedPublishers": [],
        },
        ("GET", "https://guard.example/api/v1/consumer/watchlist"): {"items": []},
        (
            "GET",
            "https://guard.example/api/v1/consumer/verdict/resolve?ecosystem=hermes&name=github",
        ): {
            "items": [
                {
                    "artifactName": "GitHub Remote MCP",
                    "recommendation": "investigate",
                }
            ]
        },
        ("POST", "https://guard.example/api/v1/consumer/signals/pain"): {"items": []},
    }
    recorded_posts = _patch_guard(monkeypatch, routes)

    result = evaluate_guard_tool_call("mcp_github_create_issue", {"title": "x"})

    assert result is not None
    assert result.source == "verdict"
    assert result.recommendation == "investigate"
    assert "GitHub Remote MCP" in result.reason
    assert len(recorded_posts) == 3
    assert recorded_posts[0]["url"].endswith("/verdict/pre-execution")
    assert recorded_posts[1]["url"].endswith("/receipts/submit")


def test_fail_open_allows_on_lookup_error(monkeypatch):
    routes = {
        ("GET", "https://guard.example/api/v1/consumer/exceptions"): httpx.ConnectError(
            "offline"
        ),
    }
    _patch_guard(monkeypatch, routes, fail_open=True)

    result = evaluate_guard_tool_call("mcp_github_create_issue", {"title": "x"})

    assert result is None


def test_declared_guard_artifact_supports_non_mcp_tools(monkeypatch):
    routes = {
        ("POST", "https://guard.example/api/v1/consumer/verdict/pre-execution"): {
            "decision": "block",
            "rationale": "Guard blocks the outbound skill before execution.",
            "scope": "artifact",
        },
        ("POST", "https://guard.example/api/v1/consumer/signals/pain"): {"items": []},
    }
    recorded_posts = _patch_guard(monkeypatch, routes)

    result = evaluate_guard_tool_call(
        "run_skill",
        {
            "guard_artifact": {
                "guard_artifact_id": "skill:hermes:secret-probe",
                "guard_artifact_name": "Secret Probe",
                "guard_artifact_slug": "secret-probe",
                "guard_artifact_type": "skill",
                "guard_publisher": "odd-labs",
                "guard_domain": "evil.example",
                "guard_launch_summary": "python secret_probe.py --upload",
            }
        },
    )

    assert result is not None
    assert result.source == "preexecution-artifact"
    assert recorded_posts[0]["json"]["artifactId"] == "skill:hermes:secret-probe"
    assert recorded_posts[0]["json"]["artifactType"] == "skill"
    assert recorded_posts[1]["url"].endswith("/receipts/submit")
