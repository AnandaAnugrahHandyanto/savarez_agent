"""Shared HTTP client for the Hypura harness daemon (openclaw-mirror)."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

from hermes_cli.config import load_config

logger = logging.getLogger(__name__)


def get_harness_url() -> str:
    """Local harness base URL from env, then Hermes config."""
    config = load_config()
    harness_cfg = config.get("harness", {}) if isinstance(config.get("harness"), dict) else {}
    host = os.getenv("HYPURA_HARNESS_HOST") or harness_cfg.get("host", "127.0.0.1")
    port = os.getenv("HYPURA_HARNESS_PORT") or harness_cfg.get("port", 18794)
    return f"http://{host}:{port}"


def is_harness_running() -> bool:
    try:
        with httpx.Client(timeout=1.0) as client:
            resp = client.get(f"{get_harness_url().rstrip('/')}/status")
            return resp.status_code == 200
    except Exception:
        return False


def call_harness(
    endpoint: str,
    payload: dict[str, Any] | None = None,
    *,
    method: str = "POST",
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Call harness HTTP API; returns a dict (never raises to tool handlers)."""
    url = f"{get_harness_url().rstrip('/')}/{endpoint.lstrip('/')}"
    try:
        with httpx.Client(timeout=timeout) as client:
            if method.upper() == "GET":
                resp = client.get(url)
            else:
                resp = client.post(url, json=payload or {})
            if resp.status_code != 200:
                return {
                    "success": False,
                    "error": f"harness_status_{resp.status_code}",
                    "detail": resp.text[:500],
                }
            data = resp.json()
            if isinstance(data, dict):
                return data
            return {"success": True, "data": data}
    except Exception as exc:
        logger.debug("Harness call failed: %s", exc)
        return {
            "success": False,
            "error": "harness_connection_failed",
            "detail": str(exc),
            "recommendation": "Run: hermes harness start",
        }


def call_harness_json(
    endpoint: str,
    payload: dict[str, Any] | None = None,
    *,
    method: str = "POST",
    timeout: float = 30.0,
) -> str:
    """JSON string wrapper for registry handlers."""
    return json.dumps(
        call_harness(endpoint, payload, method=method, timeout=timeout),
        ensure_ascii=False,
    )
