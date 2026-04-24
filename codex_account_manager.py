#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import smtplib
import ssl
import subprocess
import sys
import time
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Iterable, Optional

import httpx

from hermes_cli.env_loader import load_hermes_dotenv

from agent.credential_pool import (
    AUTH_TYPE_OAUTH,
    PooledCredential,
    STATUS_EXHAUSTED,
    STATUS_OK,
    _extract_retry_delay_seconds,
    _parse_absolute_timestamp,
    label_from_token,
    load_pool,
)
from hermes_cli.auth import (
    AuthError,
    clear_provider_auth,
    _codex_device_code_login,
    _read_codex_tokens,
    _save_codex_tokens,
    _write_codex_cli_tokens,
    read_credential_pool,
    refresh_codex_oauth_pure,
    write_credential_pool,
)
from hermes_constants import get_hermes_home

_HERMES_HOME = get_hermes_home()
_PROJECT_ENV = Path(__file__).parent / ".env"
load_hermes_dotenv(hermes_home=_HERMES_HOME, project_env=_PROJECT_ENV)


def _apply_proxy_env_fallbacks() -> None:
    fallback_proxy = (
        os.getenv("HTTP_PROXY")
        or os.getenv("HTTPS_PROXY")
        or os.getenv("http_proxy")
        or os.getenv("https_proxy")
        or os.getenv("CAMOUFOX_PROXY")
        or os.getenv("camoufox_proxy")
    )
    if not fallback_proxy:
        return
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        if not os.getenv(key):
            os.environ[key] = fallback_proxy
    no_proxy = os.getenv("NO_PROXY") or os.getenv("no_proxy")
    if no_proxy:
        os.environ.setdefault("NO_PROXY", no_proxy)
        os.environ.setdefault("no_proxy", no_proxy)


_apply_proxy_env_fallbacks()

APP_NAME = "codex-account-manager"
PROVIDER = "openai-codex"
DEFAULT_BASE_URL = "https://chatgpt.com/backend-api/codex"
DEFAULT_MODEL = "gpt-5.2-codex"
DEFAULT_NOTIFY_EMAIL = os.getenv("CODEX_MANAGER_NOTIFY_EMAIL", "").strip()
WHAM_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
PLAN_EXPIRY_ALERT_WINDOW = timedelta(days=3)

QUOTA_PATTERNS = [
    "quota",
    "insufficient_quota",
    "billing_hard_limit_reached",
    "usage limit",
    "limit reached",
    "credits have been exhausted",
    "credit balance",
    "payment required",
    "out of credits",
    "exceeded your current quota",
]
RATE_LIMIT_PATTERNS = [
    "rate limit",
    "rate_limit",
    "too many requests",
    "try again",
    "please retry after",
    "requests per minute",
    "tokens per minute",
    "requests remaining",
    "resource_exhausted",
]
TRANSIENT_PATTERNS = [
    "reconnecting",
    "connection reset",
    "connection aborted",
    "connection refused",
    "connection error",
    "timed out",
    "timeout",
    "network error",
    "socket hang up",
    "temporarily unavailable",
    "econnreset",
    "econnrefused",
    "etimedout",
    "enotfound",
    "tls handshake timeout",
]
TRANSIENT_RETRY_DELAYS = [3, 8, 15]
AUTH_PATTERNS = [
    "invalid api key",
    "authentication",
    "unauthorized",
    "forbidden",
    "expired",
    "login required",
    "not logged in",
    "invalid_grant",
    "invalid_token",
    "refresh_token_reused",
    "re-authenticate",
]


class ManagerError(Exception):
    pass


class ProbeError(Exception):
    def __init__(self, status_code: Optional[int], message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class CommandFailed(ManagerError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def manager_state_file() -> Path:
    return get_hermes_home() / "codex_account_manager" / "state.json"


def ensure_state_file(path: Optional[Path] = None) -> Path:
    state_path = (path or manager_state_file()).expanduser().resolve()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    if not state_path.exists():
        initial_state = {
            "active_credential_id": None,
            "active_credential_changed_at": None,
            "last_auto_switch_at": None,
            "last_auto_switch_from_credential_id": None,
            "last_auto_switch_to_credential_id": None,
            "last_probe": {},
            "alerts": {},
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        state_path.write_text(json.dumps(initial_state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state_path


def _within_recent_seconds(value: Any, limit_seconds: float) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return (datetime.now(timezone.utc) - dt).total_seconds() <= max(limit_seconds, 0.0)


def _auto_switch_cooldown_active(state: dict[str, Any], current_id: str | None, *, cooldown_seconds: float = 90.0) -> bool:
    current = str(current_id or "").strip()
    if not current:
        return False
    if not _within_recent_seconds(state.get("last_auto_switch_at"), cooldown_seconds):
        return False
    recent_ids = {
        str(state.get("last_auto_switch_from_credential_id") or "").strip(),
        str(state.get("last_auto_switch_to_credential_id") or "").strip(),
    }
    recent_ids.discard("")
    return current in recent_ids


def _record_auto_switch(state: dict[str, Any], from_id: str, to_id: str) -> dict[str, Any]:
    state["last_auto_switch_at"] = now_iso()
    state["last_auto_switch_from_credential_id"] = from_id
    state["last_auto_switch_to_credential_id"] = to_id
    return state


def _should_confirm_before_switch(status: str) -> bool:
    return status == "quota_exhausted"


def _default_manager_state() -> dict[str, Any]:
    return {
        "active_credential_id": None,
        "active_credential_changed_at": None,
        "last_auto_switch_at": None,
        "last_auto_switch_from_credential_id": None,
        "last_auto_switch_to_credential_id": None,
        "last_probe": {},
        "alerts": {},
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def _backup_corrupt_json(path: Path) -> Optional[Path]:
    try:
        backup_path = path.with_name(f"{path.name}.corrupt-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
        backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        return backup_path
    except Exception:
        return None


def load_manager_state(path: Optional[Path] = None) -> dict[str, Any]:
    state_path = ensure_state_file(path)
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as exc:
        backup_path = _backup_corrupt_json(state_path)
        initial_state = _default_manager_state()
        state_path.write_text(json.dumps(initial_state, ensure_ascii=False, indent=2), encoding="utf-8")
        backup_note = f"；已备份到 {backup_path}" if backup_path else ""
        raise ManagerError(f"账号管理状态文件损坏，已重建默认 state.json（{exc}）{backup_note}") from exc
    if not isinstance(payload, dict):
        raise ManagerError("账号管理状态文件格式不正确：顶层必须是 JSON 对象。")
    payload.setdefault("active_credential_id", None)
    payload.setdefault("active_credential_changed_at", None)
    payload.setdefault("last_auto_switch_at", None)
    payload.setdefault("last_auto_switch_from_credential_id", None)
    payload.setdefault("last_auto_switch_to_credential_id", None)
    payload.setdefault("last_probe", {})
    payload.setdefault("alerts", {})
    payload.setdefault("created_at", payload.get("updated_at") or now_iso())
    payload.setdefault("updated_at", now_iso())
    return payload


def save_manager_state(state: dict[str, Any], path: Optional[Path] = None) -> Path:
    state_path = ensure_state_file(path)
    state["updated_at"] = now_iso()
    tmp = state_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(state_path)
    return state_path


def load_codex_pool():
    return load_pool(PROVIDER)


def require_pool_entries() -> list[PooledCredential]:
    entries = load_codex_pool().entries()
    if not entries:
        raise ManagerError("当前还没有任何 Codex 账号，请先执行 add 登录账号。")
    return entries


def resolve_entry(pool, target: str | None) -> PooledCredential:
    index, entry, error = pool.resolve_target(target)
    if entry is None or index is None:
        raise ManagerError(error or f"找不到账号: {target}")
    return entry


def _write_pool_entries(entries: Iterable[PooledCredential]) -> list[PooledCredential]:
    normalized = list(entries)
    payload = [entry.to_dict() for entry in normalized]
    write_credential_pool(PROVIDER, payload)
    return normalized


def _replace_pool_entry(entry_id: str, transform) -> PooledCredential:
    pool = load_codex_pool()
    new_entries: list[PooledCredential] = []
    updated: Optional[PooledCredential] = None
    for entry in pool.entries():
        if entry.id == entry_id:
            updated = transform(entry)
            new_entries.append(updated)
        else:
            new_entries.append(entry)
    if updated is None:
        raise ManagerError(f"账号不存在: {entry_id}")
    _write_pool_entries(new_entries)
    refreshed_pool = load_codex_pool()
    refreshed = next((item for item in refreshed_pool.entries() if item.id == entry_id), None)
    if refreshed is None:
        raise ManagerError(f"账号更新后丢失: {entry_id}")
    return refreshed


def _move_entry_to_front(entry_id: str) -> list[PooledCredential]:
    pool = load_codex_pool()
    chosen = None
    others: list[PooledCredential] = []
    for entry in pool.entries():
        if entry.id == entry_id:
            chosen = entry
        else:
            others.append(entry)
    if chosen is None:
        raise ManagerError(f"账号不存在: {entry_id}")
    ordered = [chosen, *others]
    normalized = [replace(entry, priority=index) for index, entry in enumerate(ordered)]
    return _write_pool_entries(normalized)


def _promote_active_entry_source(entry_id: str) -> list[PooledCredential]:
    pool = load_codex_pool()
    target = next((entry for entry in pool.entries() if entry.id == entry_id), None)
    if target is None:
        raise ManagerError(f"账号不存在: {entry_id}")
    target_email = _normalized_email(_entry_email(target))
    target_key = _token_key(target.access_token, target.refresh_token)

    rewritten: list[PooledCredential] = []
    found = False
    for entry in pool.entries():
        if entry.id == entry_id:
            rewritten.append(replace(entry, source="device_code"))
            found = True
        elif entry.source == "device_code":
            same_email = target_email and _normalized_email(_entry_email(entry)) == target_email
            same_tokens = _token_key(entry.access_token, entry.refresh_token) == target_key
            if same_email or same_tokens:
                continue
            rewritten.append(replace(entry, source="manual:device_code"))
        else:
            rewritten.append(entry)
    if not found:
        raise ManagerError(f"账号不存在: {entry_id}")
    return _write_pool_entries(rewritten)


def _token_key(access_token: str | None, refresh_token: str | None) -> str:
    return f"{access_token or ''}::{refresh_token or ''}"


def _resolve_entry_from_auth_tokens(entries: list[PooledCredential], tokens: Optional[dict[str, Any]]) -> Optional[PooledCredential]:
    if not isinstance(tokens, dict):
        return None
    account_id = str(tokens.get("account_id") or "").strip()
    access_token = str(tokens.get("access_token") or "")
    refresh_token = str(tokens.get("refresh_token") or "")
    token_key = _token_key(access_token, refresh_token)
    email = _normalized_email(label_from_token(access_token, "") if access_token else "")

    if account_id:
        matched = next((entry for entry in entries if str(entry.account_id or "").strip() == account_id), None)
        if matched is not None:
            return matched
    if token_key != "::":
        matched = next((entry for entry in entries if _token_key(entry.access_token, entry.refresh_token) == token_key), None)
        if matched is not None:
            return matched
    if email:
        matched = [entry for entry in entries if _normalized_email(_entry_email(entry)) == email]
        if len(matched) == 1:
            return matched[0]
    return None


def active_entry_with_source(pool=None, state: Optional[dict[str, Any]] = None) -> tuple[Optional[PooledCredential], str | None]:
    pool = pool or load_codex_pool()
    entries = pool.entries()
    if not entries:
        return None, None

    try:
        cli_tokens = _read_codex_cli_tokens_raw()
    except Exception:
        cli_tokens = None
    matched = _resolve_entry_from_auth_tokens(entries, cli_tokens)
    if matched is not None:
        return matched, "codex_cli_auth"

    try:
        current_tokens = _read_codex_tokens()
    except Exception:
        current_tokens = None
    if isinstance(current_tokens, dict):
        matched = _resolve_entry_from_auth_tokens(entries, current_tokens.get("tokens"))
        if matched is not None:
            return matched, "hermes_auth"

    state = state or load_manager_state()
    active_id = state.get("active_credential_id")
    if active_id:
        matched = next((entry for entry in entries if entry.id == active_id), None)
        if matched is not None:
            return matched, "state"
    return entries[0], "pool_first"


def active_entry(pool=None, state: Optional[dict[str, Any]] = None) -> Optional[PooledCredential]:
    entry, _source = active_entry_with_source(pool, state)
    return entry


def _entries_for_activation(entries: list[PooledCredential], entry_id: str) -> list[PooledCredential]:
    target = next((entry for entry in entries if entry.id == entry_id), None)
    if target is None:
        raise ManagerError(f"账号不存在: {entry_id}")

    target_email = _normalized_email(_entry_email(target))
    target_key = _token_key(target.access_token, target.refresh_token)
    rewritten: list[PooledCredential] = []
    for entry in entries:
        if entry.id == entry_id:
            rewritten.append(replace(entry, source="device_code"))
        elif entry.source == "device_code":
            same_email = target_email and _normalized_email(_entry_email(entry)) == target_email
            same_tokens = _token_key(entry.access_token, entry.refresh_token) == target_key
            if same_email or same_tokens:
                continue
            rewritten.append(replace(entry, source="manual:device_code"))
        else:
            rewritten.append(entry)

    chosen = next((item for item in rewritten if item.id == entry_id), None)
    if chosen is None:
        raise ManagerError(f"切换后找不到账号: {entry_id}")
    ordered = [chosen, *(item for item in rewritten if item.id != entry_id)]
    return [replace(item, priority=index) for index, item in enumerate(ordered)]



def activate_entry(entry: PooledCredential, *, path: Optional[Path] = None) -> PooledCredential:
    current_entries = load_codex_pool().entries()
    normalized = _entries_for_activation(current_entries, entry.id)
    _write_pool_entries(normalized)
    refreshed = next((item for item in normalized if item.id == entry.id), None)
    if refreshed is None:
        raise ManagerError(f"切换后找不到账号: {entry.id}")

    _save_codex_tokens(
        {
            "access_token": refreshed.access_token,
            "refresh_token": refreshed.refresh_token or "",
            **({"account_id": refreshed.account_id} if refreshed.account_id else {}),
            **({"id_token": refreshed.id_token} if refreshed.id_token else {}),
        },
        last_refresh=refreshed.last_refresh,
    )
    if refreshed.refresh_token:
        _write_codex_cli_tokens(
            refreshed.access_token,
            refreshed.refresh_token,
            last_refresh=refreshed.last_refresh,
            account_id=refreshed.account_id,
            id_token=refreshed.id_token,
        )
    state = load_manager_state(path)
    state["active_credential_id"] = refreshed.id
    state["active_credential_changed_at"] = now_iso()
    save_manager_state(state, path)
    return refreshed


def _entry_email(entry: PooledCredential, snapshot: Optional[dict[str, Any]] = None) -> str:
    extra = entry.extra or {}
    snapshot = snapshot or {}
    for candidate in (
        extra.get("email"),
        snapshot.get("email"),
        entry.label if "@" in (entry.label or "") else "",
    ):
        value = str(candidate or "").strip()
        if value:
            return value
    return ""


def _normalized_email(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if "@" in text else ""


def _entry_account_label(entry: PooledCredential) -> str:
    email = _entry_email(entry)
    if email:
        return email
    return entry.label


def _entry_metadata_patch(entry: PooledCredential, **updates: Any) -> PooledCredential:
    merged = dict(entry.extra or {})
    for key, value in updates.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    return replace(entry, extra=merged)


def _parse_plan_expiry_value(value: Any) -> Optional[str]:
    parsed = _parse_absolute_timestamp(value)
    if parsed is None:
        return None
    return datetime.fromtimestamp(parsed, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _extract_usage_plan_expiry(payload: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    candidates: list[tuple[str, Any]] = [
        ("plan_expires_at", payload.get("plan_expires_at")),
        ("subscription_expires_at", payload.get("subscription_expires_at")),
        ("expires_at", payload.get("expires_at")),
    ]
    subscription = payload.get("subscription")
    if isinstance(subscription, dict):
        for key in ("plan_expires_at", "expires_at", "current_period_end", "ends_at"):
            candidates.append((f"subscription.{key}", subscription.get(key)))
    for source, raw in candidates:
        parsed = _parse_plan_expiry_value(raw)
        if parsed:
            return parsed, source
    return None, None


def _usage_headers(entry: PooledCredential) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {entry.access_token}",
        "Accept": "application/json",
        "User-Agent": "CodexBar",
    }
    if entry.account_id:
        headers["ChatGPT-Account-Id"] = str(entry.account_id)
    return headers


def _format_transport_error_message(exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    return message


def _fetch_usage_snapshot(entry: PooledCredential, *, timeout: float = 20.0) -> dict[str, Any]:
    try:
        response = httpx.get(
            WHAM_USAGE_URL,
            headers=_usage_headers(entry),
            timeout=httpx.Timeout(timeout),
            trust_env=True,
        )
    except (httpx.TimeoutException, httpx.NetworkError, httpx.ProtocolError, httpx.TransportError) as exc:
        raise ProbeError(None, _format_transport_error_message(exc)) from exc
    try:
        payload = response.json()
    except Exception:
        payload = response.text
    if response.status_code != 200:
        raise ProbeError(response.status_code, _coerce_error_message(payload))
    if not isinstance(payload, dict):
        raise ProbeError(response.status_code, _coerce_error_message(payload))
    return payload


def _apply_usage_snapshot(entry: PooledCredential, payload: dict[str, Any]) -> PooledCredential:
    plan_expires_at, plan_expires_source = _extract_usage_plan_expiry(payload)
    rate_limit = payload.get("rate_limit") if isinstance(payload.get("rate_limit"), dict) else {}
    primary_window = rate_limit.get("primary_window") if isinstance(rate_limit.get("primary_window"), dict) else {}
    secondary_window = rate_limit.get("secondary_window") if isinstance(rate_limit.get("secondary_window"), dict) else {}
    updates = {
        "email": payload.get("email") or (entry.extra or {}).get("email") or label_from_token(entry.access_token, entry.label),
        "account_id": payload.get("account_id") or (entry.extra or {}).get("account_id"),
        "plan_type": payload.get("plan_type") or (entry.extra or {}).get("plan_type"),
        "plan_expires_at": plan_expires_at or (entry.extra or {}).get("plan_expires_at"),
        "plan_expires_source": plan_expires_source or (entry.extra or {}).get("plan_expires_source"),
        "rate_limit_allowed": rate_limit.get("allowed") if isinstance(rate_limit.get("allowed"), bool) else None,
        "primary_reset_at": _parse_plan_expiry_value(primary_window.get("reset_at")),
        "secondary_reset_at": _parse_plan_expiry_value(secondary_window.get("reset_at")),
        "primary_used_percent": primary_window.get("used_percent"),
        "secondary_used_percent": secondary_window.get("used_percent"),
        "usage_checked_at": now_iso(),
    }
    return _entry_metadata_patch(entry, **updates)


def _entry_quota_bits(entry: PooledCredential) -> list[str]:
    bits: list[str] = []
    if entry.primary_used_percent is not None:
        bits.append(f"主窗口已用 {entry.primary_used_percent}%")
    if entry.secondary_used_percent is not None:
        bits.append(f"次窗口已用 {entry.secondary_used_percent}%")
    if isinstance(entry.rate_limit_allowed, bool):
        bits.append("允许请求" if entry.rate_limit_allowed else "当前不可请求")
    if entry.primary_reset_at:
        bits.append(f"主窗口重置={entry.primary_reset_at}")
    elif entry.secondary_reset_at:
        bits.append(f"次窗口重置={entry.secondary_reset_at}")
    return bits


def _refresh_current_entry_for_list(current: Optional[PooledCredential]) -> tuple[Optional[PooledCredential], Optional[dict[str, Any]]]:
    if current is None:
        return None, None
    try:
        result = probe_account(current)
        refreshed = next((item for item in load_codex_pool().entries() if item.id == current.id), current)
        return refreshed, result
    except Exception:
        return current, None


def _refresh_all_entries_for_list(entries: list[PooledCredential]) -> tuple[list[PooledCredential], dict[str, dict[str, Any]]]:
    live_results: dict[str, dict[str, Any]] = {}
    for entry in entries:
        try:
            result = probe_account(entry)
        except Exception:
            continue
        live_results[entry.id] = result
    refreshed_pool = load_codex_pool()
    refreshed_entries = list(refreshed_pool.entries())
    return refreshed_entries, live_results


def _best_effort_enrich_entry(entry: PooledCredential) -> PooledCredential:
    try:
        payload = _fetch_usage_snapshot(entry)
    except Exception:
        return entry
    updated = _replace_pool_entry(entry.id, lambda current: _apply_usage_snapshot(current, payload))
    refreshed_label = (payload.get("email") or "").strip() if isinstance(payload, dict) else ""
    if refreshed_label and updated.label.startswith("codex-oauth-"):
        updated = _replace_pool_entry(updated.id, lambda current: replace(current, label=refreshed_label))
    return updated


def _merge_same_email_entry(entry: PooledCredential) -> PooledCredential:
    normalized_email = _normalized_email(_entry_email(entry))
    if not normalized_email:
        return entry

    pool = load_codex_pool()
    existing = next(
        (
            candidate
            for candidate in pool.entries()
            if candidate.id != entry.id and _normalized_email(_entry_email(candidate)) == normalized_email
        ),
        None,
    )
    if existing is None:
        return entry

    merged_extra = dict(existing.extra or {})
    merged_extra.update({key: value for key, value in (entry.extra or {}).items() if value is not None})
    replacement = replace(
        existing,
        label=entry.label or existing.label,
        auth_type=entry.auth_type,
        source=entry.source,
        access_token=entry.access_token,
        refresh_token=entry.refresh_token,
        base_url=entry.base_url,
        expires_at=entry.expires_at,
        expires_at_ms=entry.expires_at_ms,
        last_refresh=entry.last_refresh,
        inference_base_url=entry.inference_base_url,
        agent_key=entry.agent_key,
        agent_key_expires_at=entry.agent_key_expires_at,
        request_count=entry.request_count,
        last_status=entry.last_status,
        last_status_at=entry.last_status_at,
        last_error_code=entry.last_error_code,
        last_error_reason=entry.last_error_reason,
        last_error_message=entry.last_error_message,
        last_error_reset_at=entry.last_error_reset_at,
        extra=merged_extra,
    )
    updated_entries: list[PooledCredential] = []
    for candidate in pool.entries():
        if candidate.id == existing.id:
            updated_entries.append(replacement)
        elif candidate.id == entry.id:
            continue
        else:
            updated_entries.append(candidate)
    _write_pool_entries(updated_entries)
    refreshed_pool = load_codex_pool()
    refreshed = next((candidate for candidate in refreshed_pool.entries() if candidate.id == existing.id), None)
    if refreshed is None:
        raise ManagerError(f"覆盖同邮箱账号后找不到账号: {existing.id}")
    return refreshed


def add_account(label: Optional[str] = None, *, activate: bool = False, plan_expires_at: Optional[str] = None, auth_file: Optional[Path] = None) -> PooledCredential:
    pool = load_codex_pool()
    state = load_manager_state()
    creds = _creds_from_auth_file(auth_file) if auth_file else _codex_device_code_login()
    token_bundle = creds["tokens"]
    fallback = f"codex-oauth-{len(pool.entries()) + 1}"
    token_email = label_from_token(token_bundle["access_token"], fallback)
    parsed_plan_expires_at = _parse_plan_expiry_value(plan_expires_at)
    final_label = (label or "").strip() or token_email
    entry = PooledCredential(
        provider=PROVIDER,
        id=uuid.uuid4().hex[:6],
        label=final_label,
        auth_type=AUTH_TYPE_OAUTH,
        priority=len(pool.entries()),
        source="manual:device_code",
        access_token=token_bundle["access_token"],
        refresh_token=token_bundle.get("refresh_token"),
        base_url=creds.get("base_url") or DEFAULT_BASE_URL,
        last_refresh=creds.get("last_refresh"),
        request_count=0,
        extra={
            "email": token_email if token_email != fallback else None,
            "id_token": token_bundle.get("id_token"),
            "plan_expires_at": parsed_plan_expires_at,
            "plan_expires_source": "manual" if parsed_plan_expires_at else None,
        },
    )
    pool.add_entry(entry)
    saved = next((item for item in load_codex_pool().entries() if item.id == entry.id), entry)
    saved = _best_effort_enrich_entry(saved)
    merged = _merge_same_email_entry(saved)
    merged_existing = merged.id != entry.id
    should_activate = activate or merged_existing or state.get("active_credential_id") == merged.id
    if should_activate:
        return activate_entry(merged)
    return merged


def _entries_matching_email(target: str, entries: Optional[list[PooledCredential]] = None) -> list[PooledCredential]:
    normalized_target = _normalized_email(target)
    if not normalized_target:
        return []
    entries = entries if entries is not None else load_codex_pool().entries()
    return [entry for entry in entries if _normalized_email(_entry_email(entry)) == normalized_target]


def _remove_entries_by_ids(entry_ids: set[str], entries: Optional[list[PooledCredential]] = None) -> list[PooledCredential]:
    entries = list(entries if entries is not None else load_codex_pool().entries())
    removed: list[PooledCredential] = []
    kept: list[PooledCredential] = []
    for entry in entries:
        if entry.id in entry_ids:
            removed.append(entry)
        else:
            kept.append(entry)
    if not removed:
        return []
    normalized = [replace(entry, priority=index) for index, entry in enumerate(kept)]
    _write_pool_entries(normalized)
    return removed


def _entries_matching_identity(target_entry: PooledCredential, entries: Optional[list[PooledCredential]] = None) -> list[PooledCredential]:
    entries = entries if entries is not None else load_codex_pool().entries()
    normalized_email = _normalized_email(_entry_email(target_entry))
    token_key = _token_key(target_entry.access_token, target_entry.refresh_token)
    account_id = str(target_entry.account_id or "").strip()

    matched: list[PooledCredential] = []
    for entry in entries:
        if entry.id == target_entry.id:
            matched.append(entry)
            continue
        if normalized_email and _normalized_email(_entry_email(entry)) == normalized_email:
            matched.append(entry)
            continue
        if account_id and str(entry.account_id or "").strip() == account_id:
            matched.append(entry)
            continue
        if token_key and _token_key(entry.access_token, entry.refresh_token) == token_key:
            matched.append(entry)
    return matched


def _codex_cli_auth_path() -> Path:
    codex_home = os.getenv("CODEX_HOME", "").strip()
    if not codex_home:
        codex_home = str(Path.home() / ".codex")
    return Path(codex_home).expanduser() / "auth.json"



def _clear_codex_cli_auth_file() -> None:
    auth_path = _codex_cli_auth_path()
    try:
        auth_path.unlink(missing_ok=True)
    except OSError as exc:
        raise ManagerError(f"清理 Codex CLI 登录态失败: {exc}") from exc



def _read_auth_file_payload(path: Path, *, missing_label: str = "Codex auth.json") -> dict[str, Any]:
    auth_path = Path(path).expanduser()
    if not auth_path.is_file():
        raise ManagerError(f"没找到 {missing_label}: {auth_path}")
    try:
        payload = json.loads(auth_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ManagerError(f"{missing_label} 已损坏，无法解析: {auth_path} ({exc})") from exc
    if not isinstance(payload, dict):
        raise ManagerError(f"{missing_label} 格式不正确: {auth_path}")
    tokens = payload.get("tokens")
    if not isinstance(tokens, dict):
        raise ManagerError(f"{missing_label} 缺少 tokens 对象: {auth_path}")
    access_token = str(tokens.get("access_token") or "").strip()
    refresh_token = str(tokens.get("refresh_token") or "").strip()
    if not access_token or not refresh_token:
        raise ManagerError(f"{missing_label} 缺少 access_token / refresh_token: {auth_path}")
    return payload



def _read_codex_cli_tokens_raw() -> Optional[dict[str, Any]]:
    auth_path = _codex_cli_auth_path()
    if not auth_path.is_file():
        return None
    payload = _read_auth_file_payload(auth_path, missing_label="Codex CLI auth.json")
    return dict(payload.get("tokens") or {})



def _creds_from_auth_file(path: Path) -> dict[str, Any]:
    payload = _read_auth_file_payload(path, missing_label="导入 auth.json")
    tokens = dict(payload.get("tokens") or {})
    return {
        "tokens": tokens,
        "base_url": str(payload.get("base_url") or DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL,
        "last_refresh": payload.get("last_refresh"),
    }



def remove_account(target: str) -> PooledCredential:
    pool = load_codex_pool()
    email_matches = _entries_matching_email(target, pool.entries())
    removed_entries: list[PooledCredential] = []
    if len(email_matches) > 1:
        removed_entries = _remove_entries_by_ids({entry.id for entry in email_matches}, pool.entries())
        if not removed_entries:
            raise ManagerError(f"删除失败: {target}")
        removed = next((entry for entry in removed_entries if entry.source == "device_code"), removed_entries[0])
    elif len(email_matches) == 1:
        matched_entries = _entries_matching_identity(email_matches[0], pool.entries())
        removed_entries = _remove_entries_by_ids({entry.id for entry in matched_entries}, pool.entries())
        if not removed_entries:
            raise ManagerError(f"删除失败: {target}")
        removed = next((entry for entry in removed_entries if entry.id == email_matches[0].id), removed_entries[0])
    else:
        index, entry, error = pool.resolve_target(target)
        if entry is None or index is None:
            raise ManagerError(error or f"找不到账号: {target}")
        matched_entries = _entries_matching_identity(entry, pool.entries())
        removed_entries = _remove_entries_by_ids({item.id for item in matched_entries}, pool.entries())
        if not removed_entries:
            raise ManagerError(f"删除失败: {target}")
        removed = next((item for item in removed_entries if item.id == entry.id), removed_entries[0])
    state = load_manager_state()
    active_removed = state.get("active_credential_id") in {entry.id for entry in removed_entries}
    raw_remaining = [PooledCredential.from_dict(PROVIDER, payload) for payload in read_credential_pool(PROVIDER)]
    if active_removed:
        state["active_credential_id"] = raw_remaining[0].id if raw_remaining else None
        save_manager_state(state)
        if raw_remaining:
            activate_entry(raw_remaining[0])
        else:
            clear_provider_auth(PROVIDER)
            _clear_codex_cli_auth_file()
    return removed


def switch_account(target: str) -> PooledCredential:
    pool = load_codex_pool()
    entry = resolve_entry(pool, target)
    return activate_entry(entry)


def _probe_payload(model: str) -> dict[str, Any]:
    return {
        "model": model,
        "instructions": "Reply with OK only.",
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "ping",
                    }
                ],
            }
        ],
        "store": False,
    }


def _coerce_error_message(payload: Any) -> str:
    if isinstance(payload, dict):
        if isinstance(payload.get("error"), dict):
            nested = payload["error"]
            for key in ("message", "error_description", "code", "type"):
                value = nested.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        for key in ("message", "error_description", "error", "detail", "code"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        try:
            return json.dumps(payload, ensure_ascii=False)
        except Exception:
            return str(payload)
    if isinstance(payload, str):
        return payload.strip()
    return str(payload)


def classify_probe_failure(status_code: Optional[int], message: str) -> dict[str, Any]:
    lowered = (message or "").lower()
    reset_at = None
    retry_delay = _extract_retry_delay_seconds(message or "")
    if retry_delay:
        reset_at = (datetime.now(timezone.utc) + timedelta(seconds=retry_delay)).isoformat().replace("+00:00", "Z")
    parsed_reset_at = _parse_absolute_timestamp(message or "")
    if parsed_reset_at is not None:
        reset_at = datetime.fromtimestamp(parsed_reset_at, tz=timezone.utc).isoformat().replace("+00:00", "Z")

    if status_code in {401, 403} or any(pattern in lowered for pattern in AUTH_PATTERNS):
        return {
            "status": "auth_invalid",
            "status_code": status_code or 401,
            "message": message or "认证失效",
            "reset_at": None,
        }
    if status_code == 429 or any(pattern in lowered for pattern in RATE_LIMIT_PATTERNS):
        return {
            "status": "rate_limited",
            "status_code": status_code or 429,
            "message": message or "触发频率限制",
            "reset_at": reset_at,
        }
    if status_code == 402 or any(pattern in lowered for pattern in QUOTA_PATTERNS):
        return {
            "status": "quota_exhausted",
            "status_code": status_code or 402,
            "message": message or "额度已耗尽",
            "reset_at": reset_at,
        }
    if any(pattern in lowered for pattern in TRANSIENT_PATTERNS):
        return {
            "status": "transient_error",
            "status_code": status_code,
            "message": message or "网络抖动/代理握手异常",
            "reset_at": reset_at,
        }
    return {
        "status": "error",
        "status_code": status_code,
        "message": message or "未知错误",
        "reset_at": reset_at,
    }


def _probe_request(*, entry: PooledCredential, model: str, timeout: float = 20.0) -> dict[str, Any]:
    del model  # Probe now uses the Codex usage endpoint instead of a responses call.
    return _fetch_usage_snapshot(entry, timeout=timeout)


def _usage_reset_at(payload: dict[str, Any]) -> Optional[str]:
    rate_limit = payload.get("rate_limit")
    if not isinstance(rate_limit, dict):
        return None
    for window_name in ("primary_window", "secondary_window"):
        window = rate_limit.get(window_name)
        if not isinstance(window, dict):
            continue
        parsed = _parse_plan_expiry_value(window.get("reset_at"))
        if parsed:
            return parsed
    return None


def _build_probe_ok_result(entry: PooledCredential, payload: dict[str, Any], checked_at: str) -> dict[str, Any]:
    rate_limit = payload.get("rate_limit") if isinstance(payload.get("rate_limit"), dict) else {}
    primary = rate_limit.get("primary_window") if isinstance(rate_limit.get("primary_window"), dict) else {}
    secondary = rate_limit.get("secondary_window") if isinstance(rate_limit.get("secondary_window"), dict) else {}
    plan_type = payload.get("plan_type") or entry.plan_type or "unknown"
    message_bits = [f"套餐={plan_type}"]
    if payload.get("email"):
        message_bits.append(f"邮箱={payload['email']}")
    if primary.get("used_percent") is not None:
        message_bits.append(f"主窗口已用 {primary['used_percent']}%")
    if secondary.get("used_percent") is not None:
        message_bits.append(f"次窗口已用 {secondary['used_percent']}%")

    allowed = rate_limit.get("allowed") if isinstance(rate_limit.get("allowed"), bool) else None
    if allowed is not None:
        message_bits.append("当前允许请求" if allowed else "当前不允许请求")

    status = "ok"
    status_code = 200
    if allowed is False:
        status = "rate_limited"
        status_code = 429

    return {
        "id": entry.id,
        "label": entry.label,
        "email": _entry_email(entry),
        "plan_type": entry.plan_type,
        "plan_expires_at": entry.plan_expires_at,
        "status": status,
        "status_code": status_code,
        "message": "；".join(message_bits),
        "reset_at": _usage_reset_at(payload),
        "checked_at": checked_at,
        "active": False,
    }


def _status_to_pool_fields(status: str, status_code: Optional[int], message: str, reset_at: Optional[str]) -> dict[str, Any]:
    if status == "ok":
        return {
            "last_status": STATUS_OK,
            "last_status_at": None,
            "last_error_code": None,
            "last_error_reason": None,
            "last_error_message": None,
            "last_error_reset_at": None,
        }
    reason = {
        "quota_exhausted": "quota",
        "rate_limited": "rate_limit",
        "auth_invalid": "auth_invalid",
        "transient_error": "transient_error",
    }.get(status, "error")
    return {
        "last_status": STATUS_EXHAUSTED,
        "last_status_at": time.time(),
        "last_error_code": status_code,
        "last_error_reason": reason,
        "last_error_message": message or None,
        "last_error_reset_at": reset_at,
    }


def _update_probe_snapshot(result: dict[str, Any], *, path: Optional[Path] = None) -> None:
    state = load_manager_state(path)
    snapshots = state.setdefault("last_probe", {})
    snapshots[result["id"]] = {
        "label": result["label"],
        "email": result.get("email"),
        "plan_type": result.get("plan_type"),
        "plan_expires_at": result.get("plan_expires_at"),
        "status": result["status"],
        "status_code": result.get("status_code"),
        "message": result.get("message"),
        "reset_at": result.get("reset_at"),
        "checked_at": result.get("checked_at"),
    }
    save_manager_state(state, path)


def _refresh_entry_tokens(entry: PooledCredential) -> tuple[PooledCredential, Optional[dict[str, Any]]]:
    if not entry.refresh_token:
        result = {
            "status": "auth_invalid",
            "status_code": 401,
            "message": "缺少 refresh_token，需要重新登录。",
            "reset_at": None,
        }
        return entry, result
    try:
        refreshed = refresh_codex_oauth_pure(entry.access_token, entry.refresh_token)
    except AuthError as exc:
        failure = classify_probe_failure(None, str(exc))
        if failure["status"] == "error" and getattr(exc, "relogin_required", False):
            failure["status"] = "auth_invalid"
            failure["status_code"] = 401
        return entry, failure
    updated = _replace_pool_entry(
        entry.id,
        lambda current: replace(
            _entry_metadata_patch(
                current,
                account_id=refreshed.get("account_id") or current.account_id,
                id_token=refreshed.get("id_token") or current.id_token,
            ),
            access_token=refreshed["access_token"],
            refresh_token=refreshed["refresh_token"],
            last_refresh=refreshed.get("last_refresh"),
            **_status_to_pool_fields("ok", None, "", None),
        ),
    )
    return updated, None


def _probe_with_existing_access_token(
    entry: PooledCredential,
    *,
    model: str,
    checked_at: str,
    refresh_failure: dict[str, Any],
) -> Optional[dict[str, Any]]:
    refresh_status = str(refresh_failure.get("status") or "")
    refresh_code = refresh_failure.get("status_code")
    refresh_message = str(refresh_failure.get("message") or "")
    refresh_message_lower = refresh_message.lower()
    looks_like_auth_refresh_failure = (
        refresh_status == "auth_invalid"
        or refresh_code in {401, 403}
        or "status 401" in refresh_message_lower
        or "status 403" in refresh_message_lower
        or any(pattern in refresh_message_lower for pattern in AUTH_PATTERNS)
    )
    if not looks_like_auth_refresh_failure:
        return None
    try:
        payload = _probe_request(entry=entry, model=model)
    except ProbeError as exc:
        failure = classify_probe_failure(exc.status_code, exc.message)
        if failure["status"] == "auth_invalid":
            return None
        updated = _replace_pool_entry(
            entry.id,
            lambda current: replace(current, **_status_to_pool_fields(
                failure["status"],
                failure.get("status_code"),
                failure.get("message", ""),
                failure.get("reset_at"),
            )),
        )
        return {
            "id": updated.id,
            "label": updated.label,
            "email": _entry_email(updated),
            "plan_type": updated.plan_type,
            "plan_expires_at": updated.plan_expires_at,
            "status": failure["status"],
            "status_code": failure.get("status_code"),
            "message": f"刷新令牌失败，已回退为现有 access_token 探测；{failure.get('message')}",
            "reset_at": failure.get("reset_at"),
            "checked_at": checked_at,
            "active": False,
        }
    except Exception:
        return None

    result = _build_probe_ok_result(entry, payload, checked_at)
    prefix = "刷新令牌失败，但当前 access_token 仍可用；"
    if result.get("message"):
        result["message"] = prefix + str(result["message"])
    else:
        result["message"] = prefix.rstrip("；")
    updated = _replace_pool_entry(
        entry.id,
        lambda current: replace(
            _apply_usage_snapshot(current, payload),
            **_status_to_pool_fields(
                result["status"],
                result.get("status_code"),
                result.get("message", ""),
                result.get("reset_at"),
            ),
        ),
    )
    return {**result, "email": _entry_email(updated), "plan_type": updated.plan_type, "plan_expires_at": updated.plan_expires_at}



def probe_account(entry: PooledCredential, *, model: str = DEFAULT_MODEL, skip_request: bool = False) -> dict[str, Any]:
    checked_at = now_iso()
    refreshed_entry, refresh_failure = _refresh_entry_tokens(entry)
    if refresh_failure is not None:
        fallback_result = _probe_with_existing_access_token(
            entry,
            model=model,
            checked_at=checked_at,
            refresh_failure=refresh_failure,
        )
        if fallback_result is not None:
            _update_probe_snapshot(fallback_result)
            return fallback_result
        updated = _replace_pool_entry(
            entry.id,
            lambda current: replace(current, **_status_to_pool_fields(
                refresh_failure["status"],
                refresh_failure.get("status_code"),
                refresh_failure.get("message", ""),
                refresh_failure.get("reset_at"),
            )),
        )
        return {
            "id": updated.id,
            "label": updated.label,
            "email": _entry_email(updated),
            "plan_type": updated.plan_type,
            "plan_expires_at": updated.plan_expires_at,
            "status": refresh_failure["status"],
            "status_code": refresh_failure.get("status_code"),
            "message": refresh_failure.get("message"),
            "reset_at": refresh_failure.get("reset_at"),
            "checked_at": checked_at,
            "active": False,
        }

    if skip_request:
        result = {
            "id": refreshed_entry.id,
            "label": refreshed_entry.label,
            "email": _entry_email(refreshed_entry),
            "plan_type": refreshed_entry.plan_type,
            "plan_expires_at": refreshed_entry.plan_expires_at,
            "status": "ok",
            "status_code": 200,
            "message": "刷新令牌成功；已跳过实际额度探测请求。",
            "reset_at": None,
            "checked_at": checked_at,
            "active": False,
        }
        _update_probe_snapshot(result)
        return result

    try:
        payload = _probe_request(entry=refreshed_entry, model=model)
        result = _build_probe_ok_result(refreshed_entry, payload, checked_at)
        updated = _replace_pool_entry(
            refreshed_entry.id,
            lambda current: replace(
                _apply_usage_snapshot(current, payload),
                **_status_to_pool_fields(
                    result["status"],
                    result.get("status_code"),
                    result.get("message", ""),
                    result.get("reset_at"),
                ),
            ),
        )
        result = {**result, "email": _entry_email(updated), "plan_type": updated.plan_type, "plan_expires_at": updated.plan_expires_at}
    except ProbeError as exc:
        failure = classify_probe_failure(exc.status_code, exc.message)
        updated = _replace_pool_entry(
            refreshed_entry.id,
            lambda current: replace(current, **_status_to_pool_fields(
                failure["status"],
                failure.get("status_code"),
                failure.get("message", ""),
                failure.get("reset_at"),
            )),
        )
        result = {
            "id": updated.id,
            "label": updated.label,
            "email": _entry_email(updated),
            "plan_type": updated.plan_type,
            "plan_expires_at": updated.plan_expires_at,
            "status": failure["status"],
            "status_code": failure.get("status_code"),
            "message": failure.get("message"),
            "reset_at": failure.get("reset_at"),
            "checked_at": checked_at,
            "active": False,
        }
    _update_probe_snapshot(result)
    return result


def send_email(subject: str, body: str, to_email: str) -> None:
    if not to_email:
        raise ManagerError("未配置提醒邮箱。")

    qq_script = Path("/root/.hermes/bin/send_qq.py")
    qq_cfg = Path.home() / ".config" / "openclaw-mail" / "qq_smtp.json"
    qq_pass = Path.home() / ".config" / "openclaw-mail" / "qq_smtp.pass"
    if qq_script.exists() and qq_cfg.exists() and qq_pass.exists():
        proc = subprocess.run(
            [
                sys.executable,
                str(qq_script),
                "--to",
                to_email,
                "--subject",
                subject,
                "--body",
                body,
            ],
            text=True,
            capture_output=True,
        )
        if proc.returncode != 0:
            raise ManagerError((proc.stderr or proc.stdout).strip() or "QQ 邮件发送失败")
        return

    address = os.getenv("EMAIL_ADDRESS", "")
    password = os.getenv("EMAIL_PASSWORD", "")
    smtp_host = os.getenv("EMAIL_SMTP_HOST", "")
    smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587"))
    if not all([address, password, smtp_host, to_email]):
        raise ManagerError("邮件环境未配置完整，且未找到可用 QQ 邮件脚本。")

    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = address
    msg["To"] = to_email
    smtp = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
    try:
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(address, password)
        smtp.send_message(msg)
    finally:
        try:
            smtp.quit()
        except Exception:
            smtp.close()


def _expiry_alert_key(result: dict[str, Any]) -> str:
    return f"plan_expiry:{result['id']}:{result.get('plan_expires_at') or ''}:{result.get('plan_type') or ''}"


def _should_send_plan_expiry_alert(result: dict[str, Any]) -> bool:
    plan_type = str(result.get("plan_type") or "").strip().lower()
    if plan_type not in {"plus", "team"}:
        return False
    plan_expires_at = result.get("plan_expires_at")
    parsed = _parse_absolute_timestamp(plan_expires_at)
    if parsed is None:
        return False
    remaining = datetime.fromtimestamp(parsed, tz=timezone.utc) - datetime.now(timezone.utc)
    return remaining <= PLAN_EXPIRY_ALERT_WINDOW


def maybe_send_invalid_alert(result: dict[str, Any], notify_email: str | None) -> bool:
    if result.get("status") != "auth_invalid":
        return False
    to_email = (notify_email or DEFAULT_NOTIFY_EMAIL or "").strip()
    if not to_email:
        return False

    state = load_manager_state()
    alerts = state.setdefault("alerts", {})
    alert_key = f"auth_invalid:{result['id']}:{result.get('message') or ''}"
    if alerts.get(alert_key):
        return False

    account_name = result.get("email") or result["label"]
    body = (
        f"时间: {now_iso()}\n"
        f"账号邮箱: {account_name}\n"
        f"账号标识: {result['label']} ({result['id']})\n"
        f"状态: 认证失效\n"
        f"HTTP: {result.get('status_code')}\n"
        f"套餐: {result.get('plan_type') or '未知'}\n"
        f"详情: {result.get('message') or '无'}\n"
        f"建议: 重新登录这个账号，然后再执行 codex-account-manager switch <账号> 或 probe。\n"
    )
    subject = f"[Codex账号失效提醒] {account_name}"
    send_email(subject, body, to_email)
    alerts[alert_key] = now_iso()
    save_manager_state(state)
    return True


def maybe_send_plan_expiry_alert(result: dict[str, Any], notify_email: str | None) -> bool:
    if not _should_send_plan_expiry_alert(result):
        return False
    to_email = (notify_email or DEFAULT_NOTIFY_EMAIL or "").strip()
    if not to_email:
        return False

    state = load_manager_state()
    alerts = state.setdefault("alerts", {})
    alert_key = _expiry_alert_key(result)
    if alerts.get(alert_key):
        return False

    parsed = _parse_absolute_timestamp(result.get("plan_expires_at"))
    if parsed is None:
        return False
    expires_at = datetime.fromtimestamp(parsed, tz=timezone.utc)
    remaining = expires_at - datetime.now(timezone.utc)
    account_name = result.get("email") or result["label"]
    remaining_days = max(0, remaining.total_seconds() / 86400)
    body = (
        f"时间: {now_iso()}\n"
        f"账号邮箱: {account_name}\n"
        f"账号标识: {result['label']} ({result['id']})\n"
        f"套餐: {result.get('plan_type') or '未知'}\n"
        f"到期时间: {result.get('plan_expires_at')}\n"
        f"剩余时间: 约 {remaining_days:.2f} 天\n"
        f"说明: 该账号的 Plus/Team 资格小于 3 天，请及时续费或准备切换。\n"
    )
    subject = f"[Codex账号到期提醒] {account_name}"
    send_email(subject, body, to_email)
    alerts[alert_key] = now_iso()
    save_manager_state(state)
    return True


def choose_next_entry(results: list[dict[str, Any]], current_id: str, attempted_ids: Optional[set[str]] = None) -> Optional[PooledCredential]:
    attempted_ids = attempted_ids or set()
    allowed_statuses = {"ok"}
    pool = load_codex_pool()
    pool_by_id = {entry.id: entry for entry in pool.entries()}

    candidates: list[tuple[tuple[Any, ...], PooledCredential]] = []
    for result in results:
        if result["id"] == current_id or result["id"] in attempted_ids:
            continue
        if result["status"] not in allowed_statuses:
            continue

        matched = pool_by_id.get(result["id"])
        if matched is None:
            continue

        primary_used = result.get("primary_used_percent")
        if primary_used is None:
            primary_used = matched.primary_used_percent
        secondary_used = result.get("secondary_used_percent")
        if secondary_used is None:
            secondary_used = matched.secondary_used_percent
        rate_limit_allowed = result.get("rate_limit_allowed")
        if rate_limit_allowed is None:
            rate_limit_allowed = matched.rate_limit_allowed

        sort_key = (
            0 if rate_limit_allowed is True else 1,
            primary_used if isinstance(primary_used, (int, float)) else 10**9,
            secondary_used if isinstance(secondary_used, (int, float)) else 10**9,
            matched.priority,
        )
        candidates.append((sort_key, matched))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def probe_all(*, model: str = DEFAULT_MODEL, auto_switch: bool = False, notify_email: str | None = None, skip_request: bool = False) -> dict[str, Any]:
    pool = load_codex_pool()
    state = load_manager_state()
    current_active, active_source = active_entry_with_source(pool, state)
    if current_active is None:
        raise ManagerError("当前还没有可用账号。")

    results: list[dict[str, Any]] = []
    for entry in pool.entries():
        result = probe_account(entry, model=model, skip_request=skip_request)
        result["active"] = entry.id == current_active.id
        results.append(result)
        if result["status"] == "auth_invalid":
            maybe_send_invalid_alert(result, notify_email)
        maybe_send_plan_expiry_alert(result, notify_email)

    switched_to = None
    confirmation_probe = None
    confirmation_error = None
    confirmed_status = None
    auto_switch_skipped = None
    active_result = next((item for item in results if item["id"] == current_active.id), None)
    if auto_switch:
        if active_result is None:
            auto_switch_skipped = "missing_active_probe"
        else:
            active_status = str(active_result.get("status") or "").strip().lower()
            if active_status in {"", "ok", "transient_error"}:
                auto_switch_skipped = f"status:{active_status or 'unknown'}"
            elif _auto_switch_cooldown_active(state, current_active.id):
                auto_switch_skipped = "cooldown"
            else:
                target_status = active_status
                if _should_confirm_before_switch(active_status):
                    try:
                        confirmation_probe = probe_account(current_active, model=model, skip_request=skip_request)
                        confirmed_status = str(confirmation_probe.get("status") or "").strip().lower() or None
                    except Exception as exc:
                        confirmation_error = str(exc)
                        auto_switch_skipped = "confirmation_error"
                    else:
                        target_status = confirmed_status or active_status
                        if target_status != active_status:
                            auto_switch_skipped = f"confirmation:{target_status or 'unknown'}"
                if auto_switch_skipped is None and target_status not in {"quota_exhausted", "rate_limited", "auth_invalid", "error", "command_failed"}:
                    auto_switch_skipped = f"status:{target_status or 'unknown'}"
                if auto_switch_skipped is None:
                    next_entry = choose_next_entry(results, current_active.id)
                    if next_entry is not None:
                        activated = activate_entry(next_entry)
                        state = load_manager_state()
                        _record_auto_switch(state, current_active.id, activated.id)
                        save_manager_state(state)
                        switched_to = {"id": activated.id, "label": activated.label}
                    else:
                        auto_switch_skipped = "no_candidate"

    summary = {
        "checked_at": now_iso(),
        "active": {"id": current_active.id, "label": current_active.label},
        "active_source": active_source,
        "switched_to": switched_to,
        "confirmation_probe": confirmation_probe,
        "confirmation_error": confirmation_error,
        "confirmed_status": confirmed_status,
        "auto_switch_skipped": auto_switch_skipped,
        "results": results,
        "notes": [
            "probe 现在直接查询 ChatGPT/Codex 的 usage 接口（wham/usage），不会再误发 /responses 导致 HTTP 400。",
            "httpx 默认会读取系统代理环境变量（如 HTTP_PROXY / HTTPS_PROXY / ALL_PROXY）。"
        ],
    }
    return summary


def detect_command_failure(output: str, returncode: int) -> tuple[str | None, str | None]:
    lowered = (output or "").lower()
    if any(pattern in lowered for pattern in QUOTA_PATTERNS):
        return "quota_exhausted", "检测到额度耗尽/额度限制"
    if any(pattern in lowered for pattern in RATE_LIMIT_PATTERNS):
        return "rate_limited", "检测到频率限制"
    if any(pattern in lowered for pattern in AUTH_PATTERNS):
        return "auth_invalid", "检测到账号失效/认证失败"
    if returncode != 0 and any(pattern in lowered for pattern in TRANSIENT_PATTERNS):
        return "transient_reconnect", "检测到网络抖动/重连中断"
    if returncode != 0:
        return "command_failed", "命令执行失败"
    return None, None


def execute_command_with_auto_switch(
    command: str,
    *,
    notify_email: str | None = None,
    max_switches: Optional[int] = None,
    cwd: str | None = None,
    env: Optional[dict[str, str]] = None,
    stream_output: bool = True,
    event_callback: Optional[callable] = None,
) -> tuple[int, str]:
    pool = load_codex_pool()
    entries = pool.entries()
    if not entries:
        raise ManagerError("没有任何 Codex 账号可用。")

    attempted: set[str] = set()
    switches = 0
    transient_retries = 0
    merged_env = os.environ.copy()
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
    ):
        value = os.environ.get(key)
        if value:
            merged_env[key] = value
    if env:
        merged_env.update(env)
    collected_outputs: list[str] = []
    proxy_snapshot = {
        key: merged_env.get(key)
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")
        if merged_env.get(key)
    }
    if proxy_snapshot:
        print(f"[codex-account-manager] proxy env injected: {json.dumps(proxy_snapshot, ensure_ascii=False)}", file=sys.stderr)

    def emit_event(event_type: str, **payload: Any) -> None:
        if event_callback is None:
            return
        try:
            event_callback({"type": event_type, **payload})
        except Exception:
            pass

    while True:
        current = active_entry(load_codex_pool(), load_manager_state())
        if current is None:
            raise ManagerError("没有可用的当前账号。")
        activate_entry(current)
        proc = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            env=merged_env,
            cwd=cwd,
        )
        output = (proc.stdout or "") + ("\n" if proc.stdout and proc.stderr else "") + (proc.stderr or "")
        if output:
            collected_outputs.append(output)
        if stream_output:
            sys.stdout.write(proc.stdout or "")
            sys.stderr.write(proc.stderr or "")
        failure_kind, failure_reason = detect_command_failure(output, proc.returncode)
        if failure_kind is None:
            return 0, "\n".join(chunk.rstrip("\n") for chunk in collected_outputs if chunk)
        if failure_kind == "transient_reconnect":
            if transient_retries < len(TRANSIENT_RETRY_DELAYS):
                delay = TRANSIENT_RETRY_DELAYS[transient_retries]
                transient_retries += 1
                print(
                    f"[codex-account-manager] transient failure detected, retrying current account in {delay}s ({transient_retries}/{len(TRANSIENT_RETRY_DELAYS)}): {failure_reason}",
                    file=sys.stderr,
                )
                emit_event(
                    "transient_retry",
                    account_id=current.id,
                    account_label=current.label,
                    retry_index=transient_retries,
                    retry_delay_seconds=delay,
                    retry_limit=len(TRANSIENT_RETRY_DELAYS),
                    reason=failure_reason,
                )
                time.sleep(delay)
                continue

            attempted.add(current.id)
            transient_retries = 0
            if max_switches is not None and switches >= max_switches:
                return proc.returncode or 1, "\n".join(chunk.rstrip("\n") for chunk in collected_outputs if chunk)

            probe_summary = probe_all(auto_switch=False, notify_email=notify_email, skip_request=True)
            next_entry = choose_next_entry(probe_summary["results"], current.id, attempted)
            if next_entry is None:
                emit_event(
                    "transient_exhausted_no_switch",
                    account_id=current.id,
                    account_label=current.label,
                    retry_limit=len(TRANSIENT_RETRY_DELAYS),
                    reason=failure_reason,
                )
                return proc.returncode or 1, "\n".join(chunk.rstrip("\n") for chunk in collected_outputs if chunk)
            print(
                f"[codex-account-manager] transient retries exhausted on {current.label}, switching to next account: {next_entry.label}",
                file=sys.stderr,
            )
            emit_event(
                "transient_switch",
                from_account_id=current.id,
                from_account_label=current.label,
                to_account_id=next_entry.id,
                to_account_label=next_entry.label,
                retry_limit=len(TRANSIENT_RETRY_DELAYS),
                reason=failure_reason,
            )
            activate_entry(next_entry)
            switches += 1
            continue
        transient_retries = 0
        if failure_kind not in {"quota_exhausted", "rate_limited", "auth_invalid"}:
            return proc.returncode or 1, "\n".join(chunk.rstrip("\n") for chunk in collected_outputs if chunk)

        failure_message = failure_reason or "命令失败"
        reset_at = None
        if failure_kind == "auth_invalid":
            reset_at = None
        result_like = {
            "id": current.id,
            "label": current.label,
            "status": failure_kind,
            "status_code": 401 if failure_kind == "auth_invalid" else 429 if failure_kind == "rate_limited" else 402,
            "message": failure_message,
            "reset_at": reset_at,
        }
        _replace_pool_entry(
            current.id,
            lambda entry: replace(entry, **_status_to_pool_fields(
                failure_kind,
                result_like["status_code"],
                result_like["message"],
                result_like["reset_at"],
            )),
        )
        if failure_kind == "auth_invalid":
            maybe_send_invalid_alert(result_like, notify_email)

        attempted.add(current.id)
        if max_switches is not None and switches >= max_switches:
            return proc.returncode or 1, "\n".join(chunk.rstrip("\n") for chunk in collected_outputs if chunk)

        probe_summary = probe_all(auto_switch=False, notify_email=notify_email, skip_request=True)
        next_entry = choose_next_entry(probe_summary["results"], current.id, attempted)
        if next_entry is None:
            return proc.returncode or 1, "\n".join(chunk.rstrip("\n") for chunk in collected_outputs if chunk)
        activate_entry(next_entry)
        switches += 1


def run_with_auto_switch(command: str, *, notify_email: str | None = None, max_switches: Optional[int] = None) -> int:
    returncode, _output = execute_command_with_auto_switch(
        command,
        notify_email=notify_email,
        max_switches=max_switches,
        stream_output=True,
    )
    return returncode


def _format_result_row(result: dict[str, Any]) -> str:
    active = "*" if result.get("active") else " "
    account_name = result.get("email") or result["label"]
    base = f"{active} {account_name} [{result['id']}] -> {result['status']}"
    if result.get("plan_type"):
        base += f" | plan={result['plan_type']}"
    if result.get("plan_expires_at"):
        base += f" | plan_expires={result['plan_expires_at']}"
    if result.get("status_code"):
        base += f" (HTTP {result['status_code']})"
    if result.get("reset_at"):
        base += f"，重置时间: {result['reset_at']}"
    if result.get("message"):
        base += f"，说明: {result['message']}"
    return base



def _entry_snapshot(entry: Optional[PooledCredential]) -> Optional[dict[str, Any]]:
    if entry is None:
        return None
    return {
        "id": entry.id,
        "label": entry.label,
        "email": _entry_email(entry) or None,
        "account_id": entry.account_id,
        "source": entry.source,
        "priority": entry.priority,
        "token_key": _token_key(entry.access_token, entry.refresh_token),
    }



def _token_snapshot(tokens: Optional[dict[str, Any]], *, source: str) -> Optional[dict[str, Any]]:
    if not isinstance(tokens, dict):
        return None
    access_token = str(tokens.get("access_token") or "")
    refresh_token = str(tokens.get("refresh_token") or "")
    account_id = str(tokens.get("account_id") or "").strip() or None
    if not access_token and not refresh_token and not account_id:
        return None
    email = label_from_token(access_token, "") if access_token else ""
    return {
        "source": source,
        "email": email or None,
        "account_id": account_id,
        "token_key": _token_key(access_token, refresh_token),
        "has_access_token": bool(access_token),
        "has_refresh_token": bool(refresh_token),
    }



def doctor_report() -> dict[str, Any]:
    pool = load_codex_pool()
    entries = pool.entries()
    state = load_manager_state()
    resolved_active, resolved_active_source = active_entry_with_source(pool, state)
    active = None
    active_id = state.get("active_credential_id") if isinstance(state, dict) else None
    if active_id:
        active = next((entry for entry in entries if entry.id == active_id), None)
    if active is None:
        active = resolved_active
    pool_first = entries[0] if entries else None

    try:
        hermes_payload = _read_codex_tokens()
    except Exception:
        hermes_payload = None
    hermes_tokens = hermes_payload.get("tokens") if isinstance(hermes_payload, dict) else None
    cli_tokens = _read_codex_cli_tokens_raw()

    active_info = _entry_snapshot(active)
    pool_first_info = _entry_snapshot(pool_first)
    hermes_info = _token_snapshot(hermes_tokens, source="hermes_auth")
    cli_info = _token_snapshot(cli_tokens, source="codex_cli")

    active_key = active_info.get("token_key") if active_info else None
    checks = {
        "pool_has_entries": bool(entries),
        "active_present": active_info is not None,
        "pool_first_matches_active": bool(active_key and pool_first_info and pool_first_info.get("token_key") == active_key),
        "hermes_matches_active": bool(active_key and hermes_info and hermes_info.get("token_key") == active_key),
        "cli_matches_active": bool(active_key and cli_info and cli_info.get("token_key") == active_key),
        "hermes_matches_cli": bool(hermes_info and cli_info and hermes_info.get("token_key") == cli_info.get("token_key")),
    }

    issues: list[str] = []
    if not checks["pool_has_entries"]:
        issues.append("账号池为空。")
    if checks["pool_has_entries"] and not checks["active_present"]:
        issues.append("状态文件里的活动账号在当前账号池中不存在。")
    if active_info and not checks["pool_first_matches_active"]:
        issues.append("账号池首项与活动账号不一致，优先级可能错乱。")
    if active_info and not checks["hermes_matches_active"]:
        issues.append("Hermes auth.json 当前登录态与活动账号不一致。")
    if active_info and not checks["cli_matches_active"]:
        issues.append("Codex CLI auth.json 当前登录态与活动账号不一致。")
    if hermes_info and cli_info and not checks["hermes_matches_cli"]:
        issues.append("Hermes auth.json 与 Codex CLI auth.json 彼此不一致。")

    return {
        "checked_at": now_iso(),
        "overall_status": "ok" if not issues else "warn",
        "active": active_info,
        "resolved_active": _entry_snapshot(resolved_active),
        "resolved_active_source": resolved_active_source,
        "pool_first": pool_first_info,
        "hermes_auth": hermes_info,
        "codex_cli": cli_info,
        "checks": checks,
        "issues": issues,
        "pool_size": len(entries),
    }



def doctor_fix() -> dict[str, Any]:
    before = doctor_report()
    pool = load_codex_pool()
    state = load_manager_state()
    target = active_entry(pool, state)
    if target is None and pool.entries():
        target = pool.entries()[0]
    if target is None:
        return {
            "fixed": False,
            "reason": "no_accounts",
            "before": before,
            "after": before,
            "actions": [],
        }

    needs_fix = before["overall_status"] != "ok"
    actions: list[str] = []
    if needs_fix:
        activate_entry(target)
        actions.append(f"reactivated:{target.id}")

    after = doctor_report()
    return {
        "fixed": needs_fix,
        "reason": "reconciled" if needs_fix else "already_ok",
        "before": before,
        "after": after,
        "actions": actions,
    }


def cmd_add(args) -> int:
    entry = add_account(
        label=args.label,
        activate=args.activate,
        plan_expires_at=args.plan_expires_at,
        auth_file=Path(args.auth_file).expanduser() if getattr(args, "auth_file", None) else None,
    )
    account_name = _entry_account_label(entry)
    print(f"已添加账号: {account_name} [{entry.id}]")
    if entry.plan_type:
        expiry_text = f"，到期={entry.plan_expires_at}" if entry.plan_expires_at else ""
        print(f"套餐信息: {entry.plan_type}{expiry_text}")
    maybe_send_plan_expiry_alert(
        {
            "id": entry.id,
            "label": entry.label,
            "email": _entry_email(entry),
            "plan_type": entry.plan_type,
            "plan_expires_at": entry.plan_expires_at,
        },
        args.notify_email,
    )
    if args.activate:
        print("已同时切换为当前活动账号。")
    return 0


def cmd_list(args) -> int:
    pool = load_codex_pool()
    state = load_manager_state()
    last_probe = state.get("last_probe") if isinstance(state.get("last_probe"), dict) else {}
    current = active_entry(pool, state)
    live_results: dict[str, dict[str, Any]] = {}

    if getattr(args, "refresh_all", False):
        refreshed_entries, live_results = _refresh_all_entries_for_list(list(pool.entries()))
        pool = load_codex_pool()
        current = active_entry(pool, load_manager_state())
        pool_entries = refreshed_entries
    else:
        current, current_probe = _refresh_current_entry_for_list(current)
        if current_probe and current:
            live_results[current.id] = current_probe
        pool = load_codex_pool()
        pool_entries = list(pool.entries())
    rows = []
    for entry in pool_entries:
        snapshot = last_probe.get(entry.id) if isinstance(last_probe.get(entry.id), dict) else {}
        quota_bits = _entry_quota_bits(entry)
        live_probe = live_results.get(entry.id)
        if live_probe and live_probe.get("message"):
            quota_bits = [live_probe["message"]]
        rows.append(
            {
                "id": entry.id,
                "label": entry.label,
                "email": (live_probe or {}).get("email") or _entry_email(entry, snapshot),
                "plan_type": (live_probe or {}).get("plan_type") or entry.plan_type,
                "plan_expires_at": (live_probe or {}).get("plan_expires_at") or entry.plan_expires_at,
                "active": bool(current and current.id == entry.id),
                "source": entry.source,
                "status": entry.last_status or "unknown",
                "last_error_code": entry.last_error_code,
                "last_error_reason": entry.last_error_reason,
                "last_error_message": entry.last_error_message,
                "last_error_reset_at": entry.last_error_reset_at,
                "last_refresh": entry.last_refresh,
                "quota": "；".join(quota_bits) if quota_bits else "暂无额度快照",
                "usage_checked_at": entry.usage_checked_at,
            }
        )
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("当前没有任何 Codex 账号。")
        return 0
    for row in rows:
        marker = "*" if row["active"] else " "
        tail = []
        if row["plan_type"]:
            tail.append(f"plan={row['plan_type']}")
        if row["plan_expires_at"]:
            tail.append(f"plan_expires={row['plan_expires_at']}")
        if row["quota"]:
            tail.append(f"quota={row['quota']}")
        if row["usage_checked_at"]:
            tail.append(f"usage_checked={row['usage_checked_at']}")
        if row["last_error_reason"]:
            tail.append(f"reason={row['last_error_reason']}")
        if row["last_error_code"]:
            tail.append(f"http={row['last_error_code']}")
        if row["last_error_reset_at"]:
            tail.append(f"reset={row['last_error_reset_at']}")
        extra = f" | {' | '.join(tail)}" if tail else ""
        account_name = row["email"] or row["label"]
        print(f"{marker} {account_name} [{row['id']}] | label={row['label']} | source={row['source']} | pool_status={row['status']}{extra}")
    return 0


def cmd_switch(args) -> int:
    entry = switch_account(args.target)
    print(f"已切换到账号: {entry.label} [{entry.id}]")
    return 0


def cmd_remove(args) -> int:
    removed = remove_account(args.target)
    print(f"已删除账号: {removed.label} [{removed.id}]")
    return 0


def cmd_probe(args) -> int:
    summary = probe_all(
        model=args.model,
        auto_switch=args.auto_switch,
        notify_email=args.notify_email,
        skip_request=args.skip_request,
    )
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    print(f"检查时间: {summary['checked_at']}")
    print(f"当前活动账号: {summary['active']['label']} [{summary['active']['id']}]")
    if summary.get("switched_to"):
        print(f"已自动切换到: {summary['switched_to']['label']} [{summary['switched_to']['id']}]")
    for result in summary["results"]:
        print(_format_result_row(result))
    for note in summary.get("notes", []):
        print(f"提示: {note}")
    return 0


def cmd_watch(args) -> int:
    while True:
        cmd_probe(args)
        if args.once:
            return 0
        time.sleep(max(5, int(args.interval)))


def cmd_run(args) -> int:
    command = args.command or ""
    if not command.strip():
        raise ManagerError("run 子命令需要 --command '...'。")
    return run_with_auto_switch(command, notify_email=args.notify_email, max_switches=args.max_switches)



def cmd_doctor(args) -> int:
    payload = doctor_fix() if args.fix else {"before": doctor_report(), "after": None, "fixed": False, "reason": "inspect_only", "actions": []}
    report = payload["before"] if not args.fix else payload["after"]
    if args.json:
        print(json.dumps(payload if args.fix else report, ensure_ascii=False, indent=2))
        return 0

    print(f"检查时间: {report['checked_at']}")
    print(f"整体状态: {report['overall_status']}")
    if args.fix:
        status_text = "已修复" if payload.get("fixed") else "无需修复"
        print(f"修复结果: {status_text} ({payload.get('reason')})")
        for action in payload.get("actions", []):
            print(f"修复动作: {action}")

    active = report.get("active") or {}
    pool_first = report.get("pool_first") or {}
    hermes_auth = report.get("hermes_auth") or {}
    codex_cli = report.get("codex_cli") or {}

    def _line(name: str, item: dict[str, Any]) -> str:
        if not item:
            return f"- {name}: 缺失"
        bits = []
        if item.get("email"):
            bits.append(f"email={item['email']}")
        if item.get("id"):
            bits.append(f"id={item['id']}")
        if item.get("account_id"):
            bits.append(f"account_id={item['account_id']}")
        if item.get("source"):
            bits.append(f"source={item['source']}")
        return f"- {name}: " + (" | ".join(bits) if bits else "存在")

    print(_line("活动账号", active))
    print(_line("账号池首项", pool_first))
    print(_line("Hermes auth", hermes_auth))
    print(_line("Codex CLI auth", codex_cli))

    for key, value in report.get("checks", {}).items():
        print(f"检查项 {key}: {'ok' if value else 'warn'}")
    for issue in report.get("issues", []):
        print(f"问题: {issue}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="Codex 多账号管理工具：支持多账号登录、批量探测可用性、手动切换、额度/认证失败时自动切换，以及失效邮件提醒。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="新增账号：通过设备码登录一个 Codex 账号，或导入 auth.json", description="新增账号：可拉起 OpenAI/Codex 设备码登录，也可直接导入已有 auth.json，保存 refresh token，并尽量识别账号邮箱。")
    add_parser.add_argument("--label", help="账号备注名")
    add_parser.add_argument("--auth-file", help="指定要导入的 auth.json 路径；不传则走设备码登录")
    add_parser.add_argument("--activate", action="store_true", help="新增后立即切换为当前账号")
    add_parser.add_argument("--notify-email", default=DEFAULT_NOTIFY_EMAIL, help="账号即将到期时提醒邮箱")
    add_parser.add_argument("--plan-expires-at", help="手动记录套餐到期时间（支持 ISO 时间 / epoch 秒 / epoch 毫秒）")
    add_parser.set_defaults(func=cmd_add)

    list_parser = subparsers.add_parser("list", help="查看账号列表：展示邮箱、套餐、当前账号额度快照", description="查看账号列表：列出所有已保存账号，优先显示账号邮箱；默认仅对当前活动账号做一次实时额度探测，可选刷新全部账号快照。")
    list_parser.add_argument("--json", action="store_true", help="JSON 输出")
    list_parser.add_argument("--refresh-all", action="store_true", help="顺手刷新全部账号的实时额度快照，而不只是当前活动账号")
    list_parser.set_defaults(func=cmd_list)

    switch_parser = subparsers.add_parser("switch", help="切换账号：按序号 / id / 邮箱 / label 切到目标账号", description="切换账号：把目标账号写回 Hermes 与 Codex CLI 的认证文件，并设为当前活动账号。")
    switch_parser.add_argument("target", help="账号序号 / id / label")
    switch_parser.set_defaults(func=cmd_switch)

    remove_parser = subparsers.add_parser("remove", help="删除账号：从账号池移除指定账号", description="删除账号：从 Codex 多账号池里移除指定账号；若删的是当前账号，会自动切到下一个可用账号。")
    remove_parser.add_argument("target", help="账号序号 / id / label")
    remove_parser.set_defaults(func=cmd_remove)

    probe_parser = subparsers.add_parser("probe", help="巡检账号：探测全部账号的认证与额度状态", description="巡检账号：刷新 token 后查询 usage 状态，判断账号是否可用、是否限流、是否额度耗尽，并可自动切换。")
    probe_parser.add_argument("--model", default=DEFAULT_MODEL, help=f"探测模型，默认 {DEFAULT_MODEL}")
    probe_parser.add_argument("--notify-email", default=DEFAULT_NOTIFY_EMAIL, help="账号失效时提醒邮箱")
    probe_parser.add_argument("--auto-switch", action="store_true", help="当前活动账号失效/限额时自动切换到下一个健康账号")
    probe_parser.add_argument("--skip-request", action="store_true", help="只刷新令牌，不发送实际探测请求")
    probe_parser.add_argument("--json", action="store_true", help="JSON 输出")
    probe_parser.set_defaults(func=cmd_probe)

    watch_parser = subparsers.add_parser("watch", help="持续巡检：按固定间隔轮询账号状态", description="持续巡检：周期性执行 probe，可用于 cron / 常驻巡检，支持自动切换与邮件提醒。")
    watch_parser.add_argument("--interval", type=int, default=1800, help="轮询间隔秒数，默认 1800")
    watch_parser.add_argument("--model", default=DEFAULT_MODEL, help=f"探测模型，默认 {DEFAULT_MODEL}")
    watch_parser.add_argument("--notify-email", default=DEFAULT_NOTIFY_EMAIL, help="账号失效时提醒邮箱")
    watch_parser.add_argument("--auto-switch", action="store_true", help="当前活动账号失效/限额时自动切换到下一个健康账号")
    watch_parser.add_argument("--skip-request", action="store_true", help="只刷新令牌，不发送实际探测请求")
    watch_parser.add_argument("--json", action="store_true", help="JSON 输出")
    watch_parser.add_argument("--once", action="store_true", help="只执行一轮，方便复用 watch 参数")
    watch_parser.set_defaults(func=cmd_watch)

    run_parser = subparsers.add_parser("run", help="带自动切号执行命令：当前号异常时自动换号重试", description="带自动切号执行命令：先用当前账号跑命令，若检测到额度/认证失败，则自动切换到下一个健康账号重试。")
    run_parser.add_argument("--command", required=True, help="要执行的命令，例如: codex exec 'fix bug'")
    run_parser.add_argument("--notify-email", default=DEFAULT_NOTIFY_EMAIL, help="账号失效时提醒邮箱")
    run_parser.add_argument("--max-switches", type=int, default=None, help="最多自动切换次数，默认不限制直到账号用完")
    run_parser.set_defaults(func=cmd_run)

    doctor_parser = subparsers.add_parser("doctor", help="诊断状态：检查活动账号与 Hermes/Codex CLI 登录态是否一致", description="诊断状态：对比活动账号、账号池首项、Hermes auth.json、Codex CLI auth.json，快速找出切号后不一致的问题。")
    doctor_parser.add_argument("--json", action="store_true", help="JSON 输出")
    doctor_parser.add_argument("--fix", action="store_true", help="发现不一致时，按当前活动账号重写 Hermes/Codex CLI 登录态")
    doctor_parser.set_defaults(func=cmd_doctor)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        ensure_state_file()
        return int(args.func(args) or 0)
    except (ManagerError, AuthError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n已取消。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
