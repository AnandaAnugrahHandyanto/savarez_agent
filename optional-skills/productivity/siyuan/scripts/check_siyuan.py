#!/usr/bin/env python3
"""Minimal environment validation helper for the SiYuan optional skill."""

from __future__ import annotations

import json
import os
import sys
from urllib import error, request


def _check(base_url: str, token: str) -> dict:
    req = request.Request(
        f"{base_url.rstrip('/')}/api/notebook/lsNotebooks",
        data=b"{}",
        headers={
            "Authorization": f"Token {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=5) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload


def main() -> int:
    token = os.environ.get("SIYUAN_TOKEN", "").strip()
    base_url = os.environ.get("SIYUAN_URL", "http://127.0.0.1:6806").strip()

    if not token:
        print(json.dumps({
            "ok": False,
            "error": "missing_siyuan_token",
            "message": "Set SIYUAN_TOKEN before running this check.",
            "url": base_url,
        }, ensure_ascii=False))
        return 1

    try:
        payload = _check(base_url, token)
    except error.HTTPError as exc:
        print(json.dumps({
            "ok": False,
            "error": "http_error",
            "status": exc.code,
            "message": exc.reason,
            "url": base_url,
        }, ensure_ascii=False))
        return 2
    except Exception as exc:  # pragma: no cover - exercised via tests with monkeypatch
        print(json.dumps({
            "ok": False,
            "error": "connection_failed",
            "message": str(exc),
            "url": base_url,
        }, ensure_ascii=False))
        return 3

    notebooks = payload.get("data", {}).get("notebooks", []) if isinstance(payload, dict) else []
    print(json.dumps({
        "ok": payload.get("code") == 0,
        "url": base_url,
        "notebook_count": len(notebooks),
        "code": payload.get("code"),
        "msg": payload.get("msg", ""),
    }, ensure_ascii=False))
    return 0 if payload.get("code") == 0 else 4


if __name__ == "__main__":
    raise SystemExit(main())
