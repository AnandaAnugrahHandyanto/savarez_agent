"""Tiny stdlib HTTP helper used by fetch_*.py scripts.

Provides polite retry + JSON convenience + User-Agent enforcement.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_UA = "hermes-agent osint-investigation skill (https://github.com/NousResearch/hermes-agent)"


def get(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    user_agent: str | None = None,
    max_retries: int = 3,
    backoff: float = 1.5,
    timeout: float = 30.0,
) -> bytes:
    """GET with retry on 429/5xx and Retry-After honoring."""
    if params:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{urllib.parse.urlencode(params)}"
    h = {"User-Agent": user_agent or os.environ.get("HERMES_OSINT_UA", DEFAULT_UA)}
    if headers:
        h.update(headers)

    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(url, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < max_retries:
                retry_after = e.headers.get("Retry-After") if e.headers else None
                wait = float(retry_after) if (retry_after and retry_after.isdigit()) else backoff ** (attempt + 1)
                time.sleep(wait)
                last_err = e
                continue
            raise
        except urllib.error.URLError as e:
            if attempt < max_retries:
                time.sleep(backoff ** (attempt + 1))
                last_err = e
                continue
            raise
    if last_err:
        raise last_err
    raise RuntimeError("unreachable")


def get_json(url: str, **kwargs) -> dict | list:
    return json.loads(get(url, **kwargs).decode("utf-8"))
