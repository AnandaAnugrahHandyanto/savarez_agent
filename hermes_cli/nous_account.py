"""Nous account entitlement helpers backed by NAS."""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional


DEFAULT_NOUS_PORTAL_URL = "https://portal.nousresearch.com"
_ACCOUNT_CACHE_TTL_SECONDS = 60
_account_cache: tuple["NousAccountStatus", float] | None = None


@dataclass(frozen=True)
class NousAccountStatus:
    available: bool
    portal_base_url: str
    paid_access: bool = False
    has_active_subscription: Optional[bool] = None
    active_subscription_is_paid: Optional[bool] = None
    subscription_tier: Optional[str] = None
    subscription_plan: Optional[str] = None
    subscription_monthly_charge: Optional[float] = None
    subscription_credits_remaining: Optional[float] = None
    purchased_credits_remaining: Optional[float] = None
    total_usable_credits: Optional[float] = None
    reason: str = ""
    unavailable_reason: str = ""
    account_info: Optional[dict[str, Any]] = None
    source: str = "nas_account"

    @property
    def free_tier(self) -> bool:
        return self.available and not self.paid_access

    @property
    def has_usable_credits(self) -> Optional[bool]:
        if self.total_usable_credits is None:
            return None
        return self.total_usable_credits > 0


def _to_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return None


def fetch_nous_account_info(
    access_token: str,
    portal_base_url: str = "",
    *,
    timeout_seconds: float = 8.0,
) -> dict[str, Any]:
    """Fetch raw Nous account info from NAS ``/api/oauth/account``."""
    token = str(access_token or "").strip()
    if not token:
        return {}
    base = (portal_base_url or DEFAULT_NOUS_PORTAL_URL).rstrip("/")
    req = urllib.request.Request(
        f"{base}/api/oauth/account",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        payload = json.loads(resp.read().decode())
    return payload if isinstance(payload, dict) else {}


def parse_nous_account_status(
    account_info: dict[str, Any] | None,
    *,
    portal_base_url: str = "",
    unavailable_reason: str = "",
) -> NousAccountStatus:
    """Normalize NAS account JSON into entitlement fields Hermes uses."""
    base = (portal_base_url or DEFAULT_NOUS_PORTAL_URL).rstrip("/")
    if not isinstance(account_info, dict) or not account_info:
        return NousAccountStatus(
            available=False,
            portal_base_url=base,
            unavailable_reason=unavailable_reason or "Account information unavailable",
            account_info=account_info if isinstance(account_info, dict) else None,
        )

    paid_service = account_info.get("paid_service_access")
    if not isinstance(paid_service, dict):
        paid_service = {}
    subscription = account_info.get("subscription")
    if not isinstance(subscription, dict):
        subscription = {}

    raw_paid = _to_bool(paid_service.get("paid_access"))
    if raw_paid is None:
        raw_paid = _to_bool(paid_service.get("allowed"))
    total_usable = _to_float(paid_service.get("total_usable_credits"))
    if total_usable is None:
        sub_credits = _to_float(
            paid_service.get("subscription_credits_remaining")
            if "subscription_credits_remaining" in paid_service
            else subscription.get("credits_remaining")
        ) or 0.0
        purchased = _to_float(
            paid_service.get("purchased_credits_remaining")
            if "purchased_credits_remaining" in paid_service
            else account_info.get("purchased_credits_remaining")
        ) or 0.0
        total_usable = sub_credits + purchased

    paid_access = bool(raw_paid) if raw_paid is not None else total_usable > 0

    subscription_tier = paid_service.get("subscription_tier")
    if subscription_tier in (None, ""):
        subscription_tier = subscription.get("tier")

    subscription_plan = subscription.get("plan")
    if subscription_plan in (None, "") and subscription_tier not in (None, ""):
        subscription_plan = str(subscription_tier)

    return NousAccountStatus(
        available=True,
        portal_base_url=base,
        paid_access=paid_access,
        has_active_subscription=_to_bool(paid_service.get("has_active_subscription")),
        active_subscription_is_paid=_to_bool(paid_service.get("active_subscription_is_paid")),
        subscription_tier=str(subscription_tier) if subscription_tier not in (None, "") else None,
        subscription_plan=str(subscription_plan) if subscription_plan not in (None, "") else None,
        subscription_monthly_charge=_to_float(
            paid_service.get("subscription_monthly_charge")
            if "subscription_monthly_charge" in paid_service
            else subscription.get("monthly_charge")
        ),
        subscription_credits_remaining=_to_float(
            paid_service.get("subscription_credits_remaining")
            if "subscription_credits_remaining" in paid_service
            else subscription.get("credits_remaining")
        ),
        purchased_credits_remaining=_to_float(
            paid_service.get("purchased_credits_remaining")
            if "purchased_credits_remaining" in paid_service
            else account_info.get("purchased_credits_remaining")
        ),
        total_usable_credits=total_usable,
        reason=str(paid_service.get("reason") or ""),
        account_info=account_info,
    )


def get_nous_account_status(
    *,
    force_refresh: bool = False,
    timeout_seconds: float = 8.0,
) -> NousAccountStatus:
    """Return the current user's live NAS entitlement status."""
    global _account_cache
    now = time.monotonic()
    if not force_refresh and _account_cache is not None:
        cached, cached_at = _account_cache
        if now - cached_at < _ACCOUNT_CACHE_TTL_SECONDS:
            return cached

    try:
        from hermes_cli.auth import DEFAULT_NOUS_PORTAL_URL as _AUTH_DEFAULT_PORTAL
        from hermes_cli.auth import get_provider_auth_state, resolve_nous_access_token

        state = get_provider_auth_state("nous") or {}
        portal_base_url = str(
            state.get("portal_base_url") or _AUTH_DEFAULT_PORTAL or DEFAULT_NOUS_PORTAL_URL
        ).rstrip("/")
        token = resolve_nous_access_token(timeout_seconds=timeout_seconds)
        info = fetch_nous_account_info(
            token,
            portal_base_url,
            timeout_seconds=timeout_seconds,
        )
        status = parse_nous_account_status(info, portal_base_url=portal_base_url)
        _account_cache = (status, now)
        return status
    except Exception as exc:
        try:
            from hermes_cli.auth import get_provider_auth_state

            state = get_provider_auth_state("nous") or {}
            portal_base_url = str(
                state.get("portal_base_url") or DEFAULT_NOUS_PORTAL_URL
            ).rstrip("/")
        except Exception:
            portal_base_url = DEFAULT_NOUS_PORTAL_URL
        return NousAccountStatus(
            available=False,
            portal_base_url=portal_base_url,
            unavailable_reason=str(exc) or type(exc).__name__,
        )


def format_nous_billing_guidance_lines(
    status: NousAccountStatus | None = None,
    *,
    force_refresh: bool = True,
) -> list[str]:
    """Return user-facing guidance for Nous 402/payment-required errors."""
    if status is None:
        status = get_nous_account_status(force_refresh=force_refresh)
    portal = (status.portal_base_url or DEFAULT_NOUS_PORTAL_URL).rstrip("/")
    billing_url = f"{portal}/billing"
    if not status.available:
        return [
            "Check your Nous billing and credits in Nous Portal.",
            f"Billing: {billing_url}",
        ]
    if not status.has_active_subscription:
        return [
            "Your Nous account does not have an active subscription for paid services.",
            f"Subscribe: {billing_url}",
        ]
    if status.has_usable_credits is False or not status.paid_access:
        return [
            "Your Nous account has an active subscription but no usable credits for paid services.",
            f"Top up credits: {billing_url}",
        ]
    return [
        "Nous reported a payment or entitlement error even though your account shows paid access.",
        f"Check billing details: {billing_url}",
    ]

