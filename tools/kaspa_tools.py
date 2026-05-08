"""Read-only Kaspa/Kasia HTTP status tools."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request
from urllib.parse import urlparse

from tools.registry import registry, tool_error, tool_result


USER_AGENT = "HermesAgent/KaspaTools"
DEFAULT_KASPA_API_URL = "https://api.kaspa.org"
DEFAULT_KASIA_INDEXER_URL = "https://indexer.kasia.fyi"


def _normalize_base_url(url: str) -> str:
    """Validate and normalize an HTTP(S) base URL."""
    value = str(url or "").strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("url must be an http:// or https:// URL")
    return value


def _coerce_timeout_seconds(value: Any = None) -> int:
    """Coerce timeout to an int in the allowed 1-30 second range."""
    if value is None or value == "":
        return 10
    try:
        timeout = int(float(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("timeout_seconds must be a number") from exc
    if timeout < 1:
        return 1
    if timeout > 30:
        return 30
    return timeout


def _decode_json_body(body: bytes) -> Any:
    if not body:
        return None
    text = body.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _get_json(base_url: str, path: str, timeout_seconds: Any = None) -> dict[str, Any]:
    """GET a read-only JSON-ish endpoint and return status plus parsed payload."""
    url = _normalize_base_url(base_url)
    timeout = _coerce_timeout_seconds(timeout_seconds)
    endpoint = f"{url}{path}"
    req = request.Request(endpoint, headers={"User-Agent": USER_AGENT}, method="GET")

    try:
        with request.urlopen(req, timeout=timeout) as response:
            status_code = int(response.getcode())
            body = response.read()
    except error.HTTPError as exc:
        payload = _decode_json_body(exc.read())
        raise RuntimeError(
            json.dumps({
                "message": f"HTTP {exc.code} from {endpoint}",
                "url": url,
                "endpoint": endpoint,
                "status_code": int(exc.code),
                "payload": payload,
            })
        ) from exc
    except error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise RuntimeError(
            json.dumps({
                "message": f"Network error fetching {endpoint}: {reason}",
                "url": url,
                "endpoint": endpoint,
                "status_code": None,
            })
        ) from exc

    return {
        "url": url,
        "endpoint": endpoint,
        "status_code": status_code,
        "payload": _decode_json_body(body),
    }


def _error_from_exception(exc: Exception) -> str:
    try:
        details = json.loads(str(exc))
    except json.JSONDecodeError:
        return tool_error(str(exc))
    message = details.pop("message", "Kaspa/Kasia HTTP request failed")
    return tool_error(message, ok=False, **details)


def _health_tool(args: dict, *, env_name: str, default_url: str, path: str, payload_key: str) -> str:
    base_url = args.get("url") or os.getenv(env_name) or default_url
    try:
        result = _get_json(base_url, path, args.get("timeout_seconds"))
    except Exception as exc:
        return _error_from_exception(exc)

    status_code = result["status_code"]
    if not 200 <= status_code < 300:
        return tool_error(
            f"HTTP {status_code} from {result['endpoint']}",
            ok=False,
            url=result["url"],
            endpoint=result["endpoint"],
            status_code=status_code,
            payload=result["payload"],
        )

    return tool_result(
        ok=True,
        url=result["url"],
        endpoint=result["endpoint"],
        status_code=status_code,
        **{payload_key: result["payload"]},
    )


def kaspa_api_health(args: dict, **kwargs) -> str:
    """Check the public/read-only Kaspa API health endpoint."""
    return _health_tool(
        args,
        env_name="KASPA_API_URL",
        default_url=DEFAULT_KASPA_API_URL,
        path="/info/health",
        payload_key="health",
    )


def kasia_indexer_health(args: dict, **kwargs) -> str:
    """Check the public/read-only Kasia indexer metrics endpoint."""
    return _health_tool(
        args,
        env_name="KASIA_INDEXER_URL",
        default_url=DEFAULT_KASIA_INDEXER_URL,
        path="/metrics",
        payload_key="metrics",
    )


_URL_SCHEMA = {
    "type": "string",
    "description": "Optional http:// or https:// base URL. Defaults to the corresponding environment variable, then the public default.",
}

_TIMEOUT_SCHEMA = {
    "type": "number",
    "description": "Optional timeout in seconds. Defaults to 10 and is clamped to the 1-30 second range.",
}


registry.register(
    name="kaspa_api_health",
    toolset="kaspa",
    schema={
        "name": "kaspa_api_health",
        "description": "Read-only check of the Kaspa API /info/health endpoint.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": _URL_SCHEMA,
                "timeout_seconds": _TIMEOUT_SCHEMA,
            },
            "additionalProperties": False,
        },
    },
    handler=kaspa_api_health,
    description="Read-only Kaspa API health check",
)

registry.register(
    name="kasia_indexer_health",
    toolset="kaspa",
    schema={
        "name": "kasia_indexer_health",
        "description": "Read-only check of the Kasia indexer /metrics endpoint.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": _URL_SCHEMA,
                "timeout_seconds": _TIMEOUT_SCHEMA,
            },
            "additionalProperties": False,
        },
    },
    handler=kasia_indexer_health,
    description="Read-only Kasia indexer metrics check",
)
