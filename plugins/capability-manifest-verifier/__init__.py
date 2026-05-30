"""evaOS capability manifest verifier for Hermes.

This plugin is intentionally narrow: when explicitly enabled, it verifies a
broker-issued HS256 JWT and enforces its tool grants through Hermes'
``pre_tool_call`` hook. It does not add tools, shell access, or a generic
policy bypass surface.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

from hermes_cli.config import cfg_get, load_config_readonly


PLUGIN_NAME = "capability-manifest-verifier"
_MAX_TOKEN_FILE_BYTES = 64 * 1024
_MAX_REASON_CHARS = 160


class ManifestError(Exception):
    """Raised for manifest verification failures with a safe user message."""


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _safe_text(value: Any, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    cleaned = " ".join(value.replace("\n", " ").replace("\r", " ").split())
    if not cleaned:
        return fallback
    return cleaned[:_MAX_REASON_CHARS]


def _block(tool_name: str, reason: str) -> dict[str, str]:
    return {
        "action": "block",
        "message": f"{PLUGIN_NAME} blocked tool '{tool_name}': {reason}",
    }


def _entry_config() -> dict[str, Any]:
    try:
        cfg = load_config_readonly()
    except Exception:
        return {}
    entry = cfg_get(cfg, "plugins", "entries", PLUGIN_NAME, default={})
    return entry if isinstance(entry, dict) else {}


def _read_manifest_token(entry: dict[str, Any]) -> str:
    token = os.environ.get("EVAOS_CAPABILITY_MANIFEST_JWT", "").strip()
    if token:
        return token

    manifest_path = entry.get("manifest_path") or entry.get("path")
    if not isinstance(manifest_path, str) or not manifest_path.strip():
        raise ManifestError("manifest unavailable")

    path = Path(manifest_path).expanduser()
    try:
        if path.stat().st_size > _MAX_TOKEN_FILE_BYTES:
            raise ManifestError("manifest unavailable")
        raw = path.read_text(encoding="utf-8").strip()
    except ManifestError:
        raise
    except Exception as exc:
        raise ManifestError("manifest unavailable") from exc

    if not raw:
        raise ManifestError("manifest unavailable")

    if raw.startswith("{"):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ManifestError("manifest invalid") from exc
        for key in ("jwt", "signed_jwt", "token", "manifest_jwt"):
            candidate = data.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        raise ManifestError("manifest unavailable")

    return raw


def _read_secret(entry: dict[str, Any]) -> str:
    secret = os.environ.get("EVAOS_CAPABILITY_MANIFEST_SECRET", "").strip()
    if secret:
        return secret

    secret_env = entry.get("secret_env")
    if isinstance(secret_env, str) and secret_env.strip():
        secret = os.environ.get(secret_env.strip(), "").strip()
        if secret:
            return secret

    raise ManifestError("manifest unavailable")


def _decode_and_verify(token: str, secret: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3 or not all(parts):
        raise ManifestError("manifest invalid")
    header_b64, payload_b64, sig_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii", errors="strict")

    try:
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
        provided_sig = _b64url_decode(sig_b64)
    except Exception as exc:
        raise ManifestError("manifest invalid") from exc

    if not isinstance(header, dict) or header.get("alg") != "HS256":
        raise ManifestError("manifest invalid")
    if not isinstance(payload, dict):
        raise ManifestError("manifest invalid")

    expected_sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(provided_sig, expected_sig):
        raise ManifestError("manifest invalid")

    if payload.get("iss") != "evaos-broker" or payload.get("aud") != "evaos-runtime":
        raise ManifestError("manifest invalid")

    now = int(time.time())
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)):
        raise ManifestError("manifest invalid")
    if int(exp) < now:
        raise ManifestError("manifest expired")

    nbf = payload.get("nbf")
    if isinstance(nbf, (int, float)) and int(nbf) > now:
        raise ManifestError("manifest invalid")

    return payload


def _expected_agent_id(entry: dict[str, Any]) -> str:
    for key in ("agent_id", "runtime_id", "subject"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return os.environ.get("EVAOS_CAPABILITY_AGENT_ID", "").strip()


def _validate_target(payload: dict[str, Any], entry: dict[str, Any]) -> None:
    expected = _expected_agent_id(entry)
    if not expected:
        return
    candidates = [
        payload.get("agent_id"),
        payload.get("runtime_id"),
        payload.get("sub"),
    ]
    if expected not in {c for c in candidates if isinstance(c, str)}:
        raise ManifestError("manifest target mismatch")


def _grant_for_tool(payload: dict[str, Any], tool_name: str) -> Any:
    grants = payload.get("tool_grants")
    if not isinstance(grants, dict):
        grants = payload.get("grants")
    if not isinstance(grants, dict):
        return None
    if tool_name in grants:
        return grants.get(tool_name)
    return grants.get("*")


def _decision_and_reason(grant: Any) -> tuple[str, str]:
    if isinstance(grant, str):
        return grant.strip().lower(), ""
    if not isinstance(grant, dict):
        return "deny", "not granted by capability manifest"
    raw = grant.get("decision", grant.get("mode", grant.get("effect", "deny")))
    decision = raw.strip().lower() if isinstance(raw, str) else "deny"
    reason = _safe_text(grant.get("reason"), "not granted by capability manifest")
    return decision, reason


def _load_payload(entry: dict[str, Any]) -> dict[str, Any]:
    token = _read_manifest_token(entry)
    secret = _read_secret(entry)
    payload = _decode_and_verify(token, secret)
    _validate_target(payload, entry)
    return payload


def _on_pre_tool_call(tool_name: str = "", args: Any = None, **_: Any) -> Optional[dict[str, str]]:
    del args
    safe_tool_name = _safe_text(tool_name, "unknown")
    entry = _entry_config()
    try:
        payload = _load_payload(entry)
    except ManifestError as exc:
        return _block(safe_tool_name, str(exc))

    grant = _grant_for_tool(payload, safe_tool_name)
    decision, reason = _decision_and_reason(grant)

    if decision in {"allow", "allowed"}:
        return None
    if decision in {"requires_approval", "approval", "needs_approval"}:
        return _block(safe_tool_name, "approval required by capability manifest")
    if decision in {"deny", "denied", "block", "blocked"}:
        return _block(safe_tool_name, reason)
    return _block(safe_tool_name, "not granted by capability manifest")


def register(ctx) -> None:
    ctx.register_hook("pre_tool_call", _on_pre_tool_call)
