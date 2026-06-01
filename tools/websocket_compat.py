"""Compatibility helpers for the ``websockets`` package.

Hermes runs in environments with several supported ``websockets`` versions.
The modern asyncio client lives under ``websockets.asyncio.client``, while
older releases expose the same connector from top-level or legacy modules.
Keep that import dance in one place so CDP callers don't depend on one layout.
"""

from __future__ import annotations

import importlib
from typing import Any, Callable, Optional

try:  # pragma: no cover - import shape depends on installed websockets version
    from websockets.exceptions import WebSocketException
except Exception:  # pragma: no cover - package may be absent
    WebSocketException = Exception  # type: ignore[assignment,misc]


_CONNECT: Optional[Callable[..., Any]] = None
_CONNECT_ERROR: Optional[ImportError] = None


def _load_websocket_connect() -> Callable[..., Any]:
    """Return a callable compatible with ``websockets.connect``."""
    global _CONNECT, _CONNECT_ERROR

    if _CONNECT is not None:
        return _CONNECT
    if _CONNECT_ERROR is not None:
        raise _CONNECT_ERROR

    errors: list[str] = []
    for module_name in (
        "websockets.asyncio.client",
        "websockets",
        "websockets.client",
        "websockets.legacy.client",
    ):
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            errors.append(f"{module_name}: {type(exc).__name__}: {exc}")
            continue
        connect = getattr(module, "connect", None)
        if callable(connect):
            _CONNECT = connect
            return connect
        errors.append(f"{module_name}: no callable connect")

    _CONNECT_ERROR = ImportError(
        "Could not locate a usable websockets connect() API. Tried: "
        + "; ".join(errors)
    )
    raise _CONNECT_ERROR


def websocket_connect(*args: Any, **kwargs: Any) -> Any:
    """Call the available ``websockets`` connector."""
    return _load_websocket_connect()(*args, **kwargs)


def websockets_available() -> bool:
    """Return True when a usable ``websockets`` connector can be imported."""
    try:
        _load_websocket_connect()
    except ImportError:
        return False
    return True


__all__ = ["WebSocketException", "websocket_connect", "websockets_available"]
