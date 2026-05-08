"""Read-only Kaspa/Kasia HTTP status tools."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request
from urllib.parse import urlencode, urlparse

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


def _get_json(
    base_url: str,
    path: str,
    timeout_seconds: Any = None,
    query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """GET a read-only JSON-ish endpoint and return status plus parsed payload."""
    url = _normalize_base_url(base_url)
    timeout = _coerce_timeout_seconds(timeout_seconds)
    endpoint = f"{url}{path}"
    if query:
        endpoint = f"{endpoint}?{urlencode(query)}"
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
        return tool_error(str(exc), ok=False)
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


def _required_string(args: dict, name: str) -> str:
    value = str(args.get(name) or "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _optional_non_negative_int(args: dict, name: str, *, max_value: int | None = None) -> int | None:
    value = args.get(name)
    if value is None or value == "":
        return None
    try:
        number = int(float(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc
    if number < 0:
        number = 0
    if max_value is not None and number > max_value:
        number = max_value
    return number


def _kasia_indexer_query_tool(
    args: dict,
    *,
    path: str,
    required_params: tuple[str, ...],
) -> str:
    base_url = args.get("url") or os.getenv("KASIA_INDEXER_URL") or DEFAULT_KASIA_INDEXER_URL
    try:
        query: dict[str, Any] = {name: _required_string(args, name) for name in required_params}
        limit = _optional_non_negative_int(args, "limit", max_value=1000)
        block_time = _optional_non_negative_int(args, "block_time")
        if limit is not None:
            query["limit"] = limit
        if block_time is not None:
            query["block_time"] = block_time
        result = _get_json(base_url, path, args.get("timeout_seconds"), query=query)
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
        items=result["payload"],
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


def kasia_indexer_handshakes_by_sender(args: dict, **kwargs) -> str:
    """Fetch read-only Kasia handshake records by sender address."""
    return _kasia_indexer_query_tool(
        args,
        path="/handshakes/by-sender",
        required_params=("address",),
    )


def kasia_indexer_handshakes_by_receiver(args: dict, **kwargs) -> str:
    """Fetch read-only Kasia handshake records by receiver address."""
    return _kasia_indexer_query_tool(
        args,
        path="/handshakes/by-receiver",
        required_params=("address",),
    )


def kasia_indexer_payments_by_sender(args: dict, **kwargs) -> str:
    """Fetch read-only Kasia payment records by sender address."""
    return _kasia_indexer_query_tool(
        args,
        path="/payments/by-sender",
        required_params=("address",),
    )


def kasia_indexer_payments_by_receiver(args: dict, **kwargs) -> str:
    """Fetch read-only Kasia payment records by receiver address."""
    return _kasia_indexer_query_tool(
        args,
        path="/payments/by-receiver",
        required_params=("address",),
    )


def kasia_indexer_contextual_messages_by_sender(args: dict, **kwargs) -> str:
    """Fetch read-only Kasia contextual messages by sender address and alias."""
    return _kasia_indexer_query_tool(
        args,
        path="/contextual-messages/by-sender",
        required_params=("address", "alias"),
    )


def kasia_indexer_self_stash_by_owner(args: dict, **kwargs) -> str:
    """Fetch read-only Kasia self-stash records by scope and owner."""
    return _kasia_indexer_query_tool(
        args,
        path="/self-stash/by-owner",
        required_params=("scope", "owner"),
    )


_URL_SCHEMA = {
    "type": "string",
    "description": "Optional http:// or https:// base URL. Defaults to the corresponding environment variable, then the public default.",
}

_TIMEOUT_SCHEMA = {
    "type": "number",
    "description": "Optional timeout in seconds. Defaults to 10 and is clamped to the 1-30 second range.",
}

_LIMIT_SCHEMA = {
    "type": "integer",
    "description": "Optional max records to return. Clamped to the 0-1000 range.",
    "minimum": 0,
}

_BLOCK_TIME_SCHEMA = {
    "type": "integer",
    "description": "Optional minimum block_time cursor/filter value.",
    "minimum": 0,
}

_KASPA_ADDRESS_SCHEMA = {
    "type": "string",
    "description": "Kaspa address to query in the Kasia indexer.",
}

_ALIAS_SCHEMA = {
    "type": "string",
    "description": "Kasia alias hex string paired with the sender address.",
}

_SCOPE_SCHEMA = {
    "type": "string",
    "description": "Kasia self-stash scope hex string to query.",
}

_OWNER_SCHEMA = {
    "type": "string",
    "description": "Kasia self-stash owner identifier to query.",
}


def _register_kasia_query_tool(
    *,
    name: str,
    handler,
    description: str,
    required_properties: dict[str, dict[str, Any]],
) -> None:
    properties = {
        "url": _URL_SCHEMA,
        **required_properties,
        "limit": _LIMIT_SCHEMA,
        "block_time": _BLOCK_TIME_SCHEMA,
        "timeout_seconds": _TIMEOUT_SCHEMA,
    }
    registry.register(
        name=name,
        toolset="kaspa",
        schema={
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": list(required_properties.keys()),
                "additionalProperties": False,
            },
        },
        handler=handler,
        description=description,
    )


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

_register_kasia_query_tool(
    name="kasia_indexer_handshakes_by_sender",
    handler=kasia_indexer_handshakes_by_sender,
    description="Read-only query of Kasia handshakes by sender address.",
    required_properties={"address": _KASPA_ADDRESS_SCHEMA},
)

_register_kasia_query_tool(
    name="kasia_indexer_handshakes_by_receiver",
    handler=kasia_indexer_handshakes_by_receiver,
    description="Read-only query of Kasia handshakes by receiver address.",
    required_properties={"address": _KASPA_ADDRESS_SCHEMA},
)

_register_kasia_query_tool(
    name="kasia_indexer_payments_by_sender",
    handler=kasia_indexer_payments_by_sender,
    description="Read-only query of Kasia payments by sender address.",
    required_properties={"address": _KASPA_ADDRESS_SCHEMA},
)

_register_kasia_query_tool(
    name="kasia_indexer_payments_by_receiver",
    handler=kasia_indexer_payments_by_receiver,
    description="Read-only query of Kasia payments by receiver address.",
    required_properties={"address": _KASPA_ADDRESS_SCHEMA},
)

_register_kasia_query_tool(
    name="kasia_indexer_contextual_messages_by_sender",
    handler=kasia_indexer_contextual_messages_by_sender,
    description="Read-only query of Kasia contextual messages by sender address and alias.",
    required_properties={"address": _KASPA_ADDRESS_SCHEMA, "alias": _ALIAS_SCHEMA},
)

_register_kasia_query_tool(
    name="kasia_indexer_self_stash_by_owner",
    handler=kasia_indexer_self_stash_by_owner,
    description="Read-only query of Kasia self-stash records by scope and owner.",
    required_properties={"scope": _SCOPE_SCHEMA, "owner": _OWNER_SCHEMA},
)
