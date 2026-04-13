#!/usr/bin/env python3
"""
Guard-backed runtime policy checks for Hermes MCP tool calls.

This module gives Hermes a lightweight Guard client for MCP tool execution.
It resolves the MCP server behind a tool name, consults Guard verdict,
watchlist, exception, and team-policy surfaces, and can emit pain signals
when Guard blocks a tool call before execution.
"""

from __future__ import annotations

import logging
import os
import hashlib
import time
from dataclasses import dataclass
from typing import Dict, Optional
from urllib.parse import urlencode, urlparse

import httpx

from hermes_cli.config import load_config
from tools.mcp_tool import _load_mcp_config

logger = logging.getLogger(__name__)

_CACHE: Dict[str, tuple[float, object]] = {}


@dataclass(frozen=True)
class GuardRuntimeSettings:
    enabled: bool
    base_url: str
    timeout_seconds: float
    fail_open: bool
    cache_ttl_seconds: int
    token_env_var: str
    enforce_mcp_tools: bool
    pain_signals_enabled: bool


@dataclass(frozen=True)
class GuardArtifactContext:
    artifact_id: str
    artifact_name: str
    artifact_slug: str
    artifact_type: str
    harness: str
    tool_name: str
    server_name: str
    publisher: Optional[str]
    domain: Optional[str]
    launch_summary: str


@dataclass(frozen=True)
class GuardRuntimeBlock:
    reason: str
    recommendation: str
    source: str


def evaluate_guard_tool_call(function_name: str, function_args: dict | None) -> Optional[GuardRuntimeBlock]:
    """Return a Guard block decision for the tool call, or ``None`` to allow."""
    settings = _load_guard_runtime_settings()
    if not settings.enabled or not settings.enforce_mcp_tools:
        return None

    artifact = _resolve_guard_artifact(function_name, function_args)
    if artifact is None:
        return None

    try:
        return _evaluate_mcp_artifact(settings, artifact)
    except Exception as error:
        if settings.fail_open:
            logger.warning("Guard runtime policy check failed open: %s", error)
            return None
        return GuardRuntimeBlock(
            reason=f"Guard policy lookup failed: {error}",
            recommendation="block",
            source="guard-runtime",
        )


def _load_guard_runtime_settings() -> GuardRuntimeSettings:
    config = load_config()
    raw = config.get("guard")
    if not isinstance(raw, dict):
        raw = {}

    base_url = str(raw.get("base_url", "https://hol.org/api/v1/consumer")).rstrip("/")
    timeout_raw = raw.get("timeout_seconds", 5)
    cache_raw = raw.get("cache_ttl_seconds", 60)

    try:
        timeout_seconds = float(timeout_raw)
    except (TypeError, ValueError):
        timeout_seconds = 5.0

    try:
        cache_ttl_seconds = int(cache_raw)
    except (TypeError, ValueError):
        cache_ttl_seconds = 60

    return GuardRuntimeSettings(
        enabled=bool(raw.get("enabled", True)),
        base_url=base_url,
        timeout_seconds=max(timeout_seconds, 1.0),
        fail_open=bool(raw.get("fail_open", True)),
        cache_ttl_seconds=max(cache_ttl_seconds, 1),
        token_env_var=str(raw.get("token_env_var", "HERMES_GUARD_TOKEN")),
        enforce_mcp_tools=bool(raw.get("enforce_mcp_tools", True)),
        pain_signals_enabled=bool(raw.get("pain_signals_enabled", True)),
    )


def _normalize_mcp_name(value: str) -> str:
    return value.replace("-", "_").replace(".", "_")


def _resolve_guard_artifact(
    function_name: str,
    function_args: dict | None,
) -> Optional[GuardArtifactContext]:
    artifact = _resolve_mcp_artifact(function_name)
    if artifact is not None:
        return artifact
    return _resolve_declared_guard_artifact(function_name, function_args)


def _resolve_mcp_artifact(function_name: str) -> Optional[GuardArtifactContext]:
    if not function_name.startswith("mcp_"):
        return None

    servers = _load_mcp_config()
    if not isinstance(servers, dict) or not servers:
        return None

    for server_name, server_config in servers.items():
        normalized = _normalize_mcp_name(server_name)
        prefix = f"mcp_{normalized}_"
        if not function_name.startswith(prefix):
            continue

        artifact_id = f"mcp:hermes:{server_name}"
        artifact_slug = server_name.lower()
        url = str(server_config.get("url", "")).strip()
        domain = urlparse(url).netloc or None
        command = str(server_config.get("command", "")).strip()
        args = server_config.get("args")
        launch_summary = url if url else " ".join(
            [part for part in [command, *args] if isinstance(part, str) and part]
        ).strip()
        if not launch_summary:
            launch_summary = server_name

        publisher = domain or command or None

        return GuardArtifactContext(
            artifact_id=artifact_id,
            artifact_name=server_name,
            artifact_slug=artifact_slug,
            artifact_type="mcp-server",
            harness="hermes",
            tool_name=function_name,
            server_name=server_name,
            publisher=publisher,
            domain=domain,
            launch_summary=launch_summary,
        )

    return None


def _resolve_declared_guard_artifact(
    function_name: str,
    function_args: dict | None,
) -> Optional[GuardArtifactContext]:
    if not isinstance(function_args, dict):
        return None

    raw_artifact = function_args.get("guard_artifact")
    metadata = raw_artifact if isinstance(raw_artifact, dict) else function_args

    artifact_name = str(
        metadata.get("guard_artifact_name")
        or metadata.get("artifact_name")
        or metadata.get("name")
        or ""
    ).strip()
    if not artifact_name:
        return None

    artifact_id = str(
        metadata.get("guard_artifact_id")
        or metadata.get("artifact_id")
        or f"tool:hermes:{function_name}"
    ).strip()
    artifact_slug = str(
        metadata.get("guard_artifact_slug")
        or metadata.get("artifact_slug")
        or artifact_name.lower().replace(" ", "-")
    ).strip()
    artifact_type = str(
        metadata.get("guard_artifact_type")
        or metadata.get("artifact_type")
        or "plugin"
    ).strip() or "plugin"
    harness = str(metadata.get("guard_harness") or "hermes").strip() or "hermes"
    publisher = str(
        metadata.get("guard_publisher")
        or metadata.get("publisher")
        or ""
    ).strip() or None
    domain = str(
        metadata.get("guard_domain")
        or metadata.get("domain")
        or ""
    ).strip() or None
    launch_summary = str(
        metadata.get("guard_launch_summary")
        or metadata.get("launch_summary")
        or function_name
    ).strip() or function_name

    return GuardArtifactContext(
        artifact_id=artifact_id,
        artifact_name=artifact_name,
        artifact_slug=artifact_slug,
        artifact_type=artifact_type,
        harness=harness,
        tool_name=function_name,
        server_name=artifact_name,
        publisher=publisher,
        domain=domain,
        launch_summary=launch_summary,
    )


def _evaluate_mcp_artifact(
    settings: GuardRuntimeSettings,
    artifact: GuardArtifactContext,
) -> Optional[GuardRuntimeBlock]:
    with httpx.Client(timeout=settings.timeout_seconds) as client:
        preexecution_verdict = _match_preexecution_verdict(
            settings,
            client,
            artifact,
        )
        if preexecution_verdict is not _PREEXECUTION_FALLBACK:
            if preexecution_verdict is None:
                return None
            _emit_receipt(settings, client, artifact, preexecution_verdict)
            _emit_pain_signal(settings, client, artifact, preexecution_verdict)
            return preexecution_verdict

        exception_block = _match_exception(settings, client, artifact)
        if exception_block == "allow":
            return None

        team_policy_block = _match_team_policy(settings, client, artifact)
        if team_policy_block is not None:
            _emit_receipt(settings, client, artifact, team_policy_block)
            _emit_pain_signal(settings, client, artifact, team_policy_block)
            return team_policy_block

        watchlist_block = _match_watchlist(settings, client, artifact)
        if watchlist_block is not None:
            _emit_receipt(settings, client, artifact, watchlist_block)
            _emit_pain_signal(settings, client, artifact, watchlist_block)
            return watchlist_block

        verdict_block = _match_verdict(settings, client, artifact)
        if verdict_block is not None:
            _emit_receipt(settings, client, artifact, verdict_block)
            _emit_pain_signal(settings, client, artifact, verdict_block)
            return verdict_block

    return None


_PREEXECUTION_FALLBACK = object()


def _authorized_headers(settings: GuardRuntimeSettings) -> Dict[str, str]:
    token = os.getenv(settings.token_env_var, "").strip()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _cache_key(settings: GuardRuntimeSettings, suffix: str) -> str:
    return f"{settings.base_url}|{settings.token_env_var}|{suffix}"


def _get_cached(settings: GuardRuntimeSettings, suffix: str) -> object | None:
    cache_key = _cache_key(settings, suffix)
    cached = _CACHE.get(cache_key)
    if cached is None:
        return None
    expires_at, payload = cached
    if expires_at < time.time():
        _CACHE.pop(cache_key, None)
        return None
    return payload


def _set_cached(settings: GuardRuntimeSettings, suffix: str, payload: object) -> object:
    _CACHE[_cache_key(settings, suffix)] = (
        time.time() + settings.cache_ttl_seconds,
        payload,
    )
    return payload


def _fetch_json(
    settings: GuardRuntimeSettings,
    client: httpx.Client,
    path: str,
    *,
    require_auth: bool = False,
) -> object | None:
    cached = _get_cached(settings, path)
    if cached is not None:
        return cached

    headers = _authorized_headers(settings)
    if require_auth and not headers:
        return None

    response = client.get(f"{settings.base_url}{path}", headers=headers or None)
    response.raise_for_status()
    return _set_cached(settings, path, response.json())


def _post_json(
    settings: GuardRuntimeSettings,
    client: httpx.Client,
    path: str,
    payload: dict,
    *,
    require_auth: bool = False,
) -> object | None:
    headers = _authorized_headers(settings)
    if require_auth and not headers:
        return None

    response = client.post(
        f"{settings.base_url}{path}",
        headers=headers or None,
        json=payload,
    )
    response.raise_for_status()
    return response.json()


def _matches_artifact(record: dict, artifact: GuardArtifactContext) -> bool:
    haystacks = [
        str(record.get("artifactId", "")).strip().lower(),
        str(record.get("artifactSlug", "")).strip().lower(),
        str(record.get("artifactName", "")).strip().lower(),
    ]
    needles = [
        artifact.artifact_id.lower(),
        artifact.artifact_slug.lower(),
        artifact.server_name.lower(),
    ]
    for needle in needles:
        if not needle:
            continue
        if any(needle == haystack or needle in haystack for haystack in haystacks if haystack):
            return True
    return False


def _match_exception(
    settings: GuardRuntimeSettings,
    client: httpx.Client,
    artifact: GuardArtifactContext,
) -> Optional[str]:
    payload = _fetch_json(settings, client, "/exceptions", require_auth=True)
    if not isinstance(payload, dict):
        return None

    items = payload.get("items")
    if not isinstance(items, list):
        return None

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for item in items:
        if not isinstance(item, dict):
            continue
        expires_at = str(item.get("expiresAt", ""))
        if expires_at and expires_at <= now:
            continue
        scope = str(item.get("scope", ""))
        if scope == "global":
            return "allow"
        if scope == "harness" and str(item.get("harness", "")) == artifact.harness:
            return "allow"
        if scope == "artifact" and str(item.get("artifactId", "")) == artifact.artifact_id:
            return "allow"
    return None


def _match_preexecution_verdict(
    settings: GuardRuntimeSettings,
    client: httpx.Client,
    artifact: GuardArtifactContext,
) -> object:
    headers = _authorized_headers(settings)
    if not headers:
        return _PREEXECUTION_FALLBACK

    payload = {
        "harness": artifact.harness,
        "artifactName": artifact.artifact_name,
        "artifactType": artifact.artifact_type,
        "artifactId": artifact.artifact_id,
        "artifactSlug": artifact.artifact_slug,
        "publisher": artifact.publisher,
        "domain": artifact.domain,
        "launchSummary": artifact.launch_summary,
    }

    cache_suffix = f"/verdict/pre-execution:{artifact.artifact_id}"
    cached = _get_cached(settings, cache_suffix)
    if isinstance(cached, dict):
        return _block_from_preexecution_payload(cached)

    try:
        response = _post_json(
            settings,
            client,
            "/verdict/pre-execution",
            payload,
            require_auth=True,
        )
    except Exception as error:
        logger.warning("Guard pre-execution verdict lookup failed: %s", error)
        return _PREEXECUTION_FALLBACK

    if not isinstance(response, dict):
        return _PREEXECUTION_FALLBACK

    if str(response.get("decision", "")).strip().lower() == "allow":
        _emit_receipt(
            settings,
            client,
            artifact,
            GuardRuntimeBlock(
                reason=str(response.get("rationale", "")).strip()
                or "Guard allowed tool execution.",
                recommendation="monitor",
                source=f"preexecution-{str(response.get('scope', 'guard')).strip() or 'guard'}",
            ),
        )

    _set_cached(settings, cache_suffix, response)
    return _block_from_preexecution_payload(response)


def _block_from_preexecution_payload(
    payload: dict,
) -> object:
    decision = str(payload.get("decision", "")).strip().lower()
    rationale = str(payload.get("rationale", "")).strip()
    scope = str(payload.get("scope", "guard")).strip() or "guard"

    if decision == "allow":
        return None

    if decision in {"block", "review"}:
        recommendation = "block" if decision == "block" else "review"
        return GuardRuntimeBlock(
            reason=rationale or f"Guard requires {decision} before tool execution.",
            recommendation=recommendation,
            source=f"preexecution-{scope}",
        )

    return _PREEXECUTION_FALLBACK


def _match_team_policy(
    settings: GuardRuntimeSettings,
    client: httpx.Client,
    artifact: GuardArtifactContext,
) -> Optional[GuardRuntimeBlock]:
    payload = _fetch_json(settings, client, "/team/policy-pack", require_auth=True)
    if not isinstance(payload, dict):
        return None

    blocked_artifacts = payload.get("blockedArtifacts")
    if isinstance(blocked_artifacts, list):
        if artifact.artifact_id in {str(item) for item in blocked_artifacts}:
            return GuardRuntimeBlock(
                reason=f"Guard team policy blocks the MCP server '{artifact.server_name}'.",
                recommendation="block",
                source="team-policy",
            )

    blocked_domains = payload.get("blockedDomains")
    if artifact.domain and isinstance(blocked_domains, list):
        normalized_domain = artifact.domain.lower()
        if normalized_domain in {str(item).lower() for item in blocked_domains}:
            return GuardRuntimeBlock(
                reason=f"Guard team policy blocks the domain '{artifact.domain}' used by '{artifact.server_name}'.",
                recommendation="block",
                source="team-policy",
            )

    blocked_publishers = payload.get("blockedPublishers")
    if artifact.publisher and isinstance(blocked_publishers, list):
        normalized_publisher = artifact.publisher.lower()
        if normalized_publisher in {str(item).lower() for item in blocked_publishers}:
            return GuardRuntimeBlock(
                reason=f"Guard team policy blocks the publisher '{artifact.publisher}'.",
                recommendation="block",
                source="team-policy",
            )

    return None


def _match_watchlist(
    settings: GuardRuntimeSettings,
    client: httpx.Client,
    artifact: GuardArtifactContext,
) -> Optional[GuardRuntimeBlock]:
    payload = _fetch_json(settings, client, "/watchlist", require_auth=True)
    if not isinstance(payload, dict):
        return None

    items = payload.get("items")
    if not isinstance(items, list):
        return None

    for item in items:
        if isinstance(item, dict) and _matches_artifact(item, artifact):
            reason = str(item.get("reason", "")).strip()
            detail = reason or f"Guard watchlist matched '{artifact.server_name}'."
            return GuardRuntimeBlock(
                reason=detail,
                recommendation="block",
                source="watchlist",
            )
    return None


def _match_verdict(
    settings: GuardRuntimeSettings,
    client: httpx.Client,
    artifact: GuardArtifactContext,
) -> Optional[GuardRuntimeBlock]:
    query = urlencode({"ecosystem": "hermes", "name": artifact.server_name})
    payload = _fetch_json(settings, client, f"/verdict/resolve?{query}")
    if not isinstance(payload, dict):
        return None

    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return None

    first = items[0]
    if not isinstance(first, dict):
        return None

    recommendation = str(first.get("recommendation", "")).strip().lower()
    artifact_name = str(first.get("artifactName", artifact.server_name)).strip()
    if recommendation == "block":
        return GuardRuntimeBlock(
            reason=f"Guard marked '{artifact_name}' as blocked before tool execution.",
            recommendation="block",
            source="verdict",
        )
    if recommendation == "investigate":
        return GuardRuntimeBlock(
            reason=f"Guard requires review for '{artifact_name}' before tool execution.",
            recommendation="investigate",
            source="verdict",
        )
    return None


def _emit_pain_signal(
    settings: GuardRuntimeSettings,
    client: httpx.Client,
    artifact: GuardArtifactContext,
    block: GuardRuntimeBlock,
) -> None:
    if not settings.pain_signals_enabled:
        return

    headers = _authorized_headers(settings)
    if not headers:
        return

    payload = {
        "items": [
            {
                "signalId": f"{artifact.artifact_id}:blocked-tool-call",
                "signalName": "blocked-tool-call",
                "artifactId": artifact.artifact_id,
                "artifactName": artifact.artifact_name,
                "artifactType": artifact.artifact_type,
                "harness": artifact.harness,
                "latestSummary": f"{block.reason} Tool: {artifact.tool_name}. Launch: {artifact.launch_summary}.",
                "occurredAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "count": 1,
                "source": "scanner",
                "publisher": artifact.publisher,
            }
        ]
    }

    try:
        client.post(
            f"{settings.base_url}/signals/pain",
            headers=headers,
            json=payload,
        ).raise_for_status()
    except Exception as error:
        if settings.fail_open:
            logger.warning("Failed to emit Guard pain signal: %s", error)
            return
        raise


def _emit_receipt(
    settings: GuardRuntimeSettings,
    client: httpx.Client,
    artifact: GuardArtifactContext,
    block: GuardRuntimeBlock,
) -> None:
    headers = _authorized_headers(settings)
    if not headers:
        return

    captured_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    artifact_hash = hashlib.sha256(
        f"{artifact.artifact_id}|{artifact.launch_summary}".encode("utf-8")
    ).hexdigest()
    policy_decision = "allow"
    if block.recommendation == "block":
        policy_decision = "block"
    elif block.recommendation == "review":
        policy_decision = "review"

    payload = {
        "receipts": [
            {
                "receiptId": f"{artifact.artifact_id}:{policy_decision}:{captured_at}",
                "capturedAt": captured_at,
                "harness": artifact.harness,
                "deviceId": "hermes-runtime",
                "deviceName": "Hermes Runtime",
                "artifactId": artifact.artifact_id,
                "artifactName": artifact.artifact_name,
                "artifactType": artifact.artifact_type,
                "artifactSlug": artifact.artifact_slug,
                "artifactHash": artifact_hash,
                "policyDecision": policy_decision,
                "recommendation": block.recommendation,
                "changedSinceLastApproval": policy_decision != "allow",
                "publisher": artifact.publisher,
                "capabilities": [artifact.tool_name],
                "summary": block.reason,
            }
        ]
    }

    try:
        client.post(
            f"{settings.base_url}/receipts/submit",
            headers=headers,
            json=payload,
        ).raise_for_status()
    except Exception as error:
        if settings.fail_open:
            logger.warning("Failed to submit Guard receipt: %s", error)
            return
        raise
