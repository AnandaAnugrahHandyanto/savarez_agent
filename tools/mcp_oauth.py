#!/usr/bin/env python3
"""
MCP OAuth 2.1 Client Support

Implements the browser-based OAuth 2.1 authorization code flow with PKCE
for MCP servers that require OAuth authentication instead of static bearer
tokens.

Uses the MCP Python SDK's ``OAuthClientProvider`` (an ``httpx.Auth`` subclass)
which handles discovery, dynamic client registration, PKCE, token exchange,
refresh, and step-up authorization automatically.

This module provides the glue:
    - ``HermesTokenStorage``: persists tokens/client-info to disk so they
      survive across process restarts.
    - Callback server: ephemeral localhost HTTP server to capture the OAuth
      redirect with the authorization code.
    - ``build_oauth_auth()``: entry point called by ``mcp_tool.py`` that wires
      everything together and returns the ``httpx.Auth`` object.

Configuration in config.yaml::

    mcp_servers:
      my_server:
        url: "https://mcp.example.com/mcp"
        auth: oauth
        oauth:                                  # all fields optional
          client_id: "pre-registered-id"        # skip dynamic registration
          client_secret: "secret"               # confidential clients only
          scope: "read write"                   # default: server-provided
          redirect_port: 0                      # 0 = auto-pick free port
          client_name: "My Custom Client"       # default: "Hermes Agent"
"""

import asyncio
import json
import logging
import os
import re
import secrets
import socket
import stat
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from hermes_constants import secure_parent_dir

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports -- MCP SDK with OAuth support is optional
# ---------------------------------------------------------------------------

_OAUTH_AVAILABLE=False
try:
    from mcp.client.auth import OAuthClientProvider
    from mcp.shared.auth import (
        OAuthClientInformationFull,
        OAuthClientMetadata,
        OAuthMetadata,
        OAuthToken,
    )

    _OAUTH_AVAILABLE=True
except ImportError:
    logger.debug("MCP OAuth types not available -- OAuth MCP auth disabled")

try:
    from pydantic import AnyUrl
except ImportError:
    AnyUrl = None  # type: ignore[assignment, misc]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class OAuthNonInteractiveError(RuntimeError):
    """Raised when OAuth requires browser interaction in a non-interactive env."""


# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

# Port used by the most recent build_oauth_auth() call.  Exposed so that
# tests can verify the callback server and the redirect_uri share a port.
_oauth_port: int | None = None

# Shared callback result for live OAuth flows. ``_wait_for_callback`` may be
# invoked more than once per flow (e.g. SDK retries, or a second concurrent
# waiter sharing the already-bound port). Storing the handler's result dict by
# (callback port, flow identity) lets sibling waiters poll the same buffer
# instead of binding a fresh server, without letting distinct servers/providers
# on the same port consume each other's code/state.
#
# MUST be reset to None on completion, failure, or timeout so a subsequent
# login attempt cannot inherit stale auth_code/state/error from a prior
# flow. ``build_oauth_auth`` also resets inactive slots defensively at flow
# start.
_oauth_result: dict[str, Any] | None = None
_oauth_result_active = False
_oauth_result_port: int | None = None
_oauth_flow_key: tuple[Any, ...] = ("legacy",)
_oauth_results_by_port: dict[tuple[int, tuple[Any, ...]], dict[str, Any]] = {}
# Flows that have reached the user-visible redirect step but may not have
# entered ``_wait_for_callback`` yet. The MCP SDK emits the authorization URL
# before opening the callback listener, so checking for cross-flow port reuse
# only inside ``_wait_for_callback`` is too late: a browser could already hit a
# listener owned by another flow. Claiming here lets the redirect handler fail
# before the URL is shown for a conflicting flow.
_oauth_active_flow_claims: set[tuple[int, tuple[Any, ...]]] = set()
# Ports for which a waiter has decided to bind a listener but has not yet
# finished (the bind may still succeed and publish, or fail). This is an
# explicit "in-progress" marker -- NOT a result buffer. A concurrent waiter
# that sees a pending port must wait for the binding waiter to resolve
# instead of racing its own bind (which would lose and spuriously raise).
_oauth_pending_ports: set[tuple[int, tuple[Any, ...]]] = set()
_oauth_result_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_token_dir() -> Path:
    """Return the directory for MCP OAuth token files.

    Uses HERMES_HOME so each profile gets its own OAuth tokens.
    Layout: ``HERMES_HOME/mcp-tokens/``
    """
    try:
        from hermes_constants import get_hermes_home
        base = Path(get_hermes_home())
    except ImportError:
        base = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
    return base / "mcp-tokens"


def _safe_filename(name: str) -> str:
    """Sanitize a server name for use as a filename (no path separators)."""
    return re.sub(r"[^\w\-]", "_", name).strip("_")[:128] or "default"


def _find_free_port() -> int:
    """Find an available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _is_interactive() -> bool:
    """Return True if we can reasonably expect to interact with a user."""
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def _can_open_browser() -> bool:
    """Return True if opening a browser is likely to work."""
    # Explicit SSH session → no local display
    if os.environ.get("SSH_CLIENT") or os.environ.get("SSH_TTY"):
        return False
    # macOS and Windows usually have a display
    if os.name == "nt":
        return True
    try:
        if os.uname().sysname == "Darwin":
            return True
    except AttributeError:
        pass
    # Linux/other posix: need DISPLAY or WAYLAND_DISPLAY
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return True
    return False


def _read_json(path: Path) -> dict | None:
    """Read a JSON file, returning None if it doesn't exist or is invalid."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read %s: %s", path, exc)
        return None


def _write_json(path: Path, data: dict) -> None:
    """Write a dict as JSON with restricted permissions (0o600).

    Uses ``os.open`` with ``O_EXCL`` and an explicit mode so the file is
    created atomically at 0o600. The previous ``write_text`` + post-write
    ``chmod`` opened a TOCTOU window where the temp file briefly inherited
    the process umask (commonly 0o644 = world-readable), exposing OAuth
    tokens to other local users between create and chmod. Mirrors the fix
    in ``agent/google_oauth.py`` (#19673).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Tighten parent dir to 0o700 so siblings can't traverse to the creds.
    # No-op on Windows (POSIX mode bits aren't enforced); ignore failures.
    # secure_parent_dir refuses to chmod / or top-level dirs (#25821).
    secure_parent_dir(path)
    # Per-process random suffix avoids collisions between concurrent
    # writers and stale leftovers from a prior crashed write.
    tmp = path.with_suffix(f".tmp.{os.getpid()}.{secrets.token_hex(4)}")
    try:
        fd = os.open(
            str(tmp),
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            stat.S_IRUSR | stat.S_IWUSR,
        )
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, default=str)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# HermesTokenStorage -- persistent token/client-info on disk
# ---------------------------------------------------------------------------


class HermesTokenStorage:
    """Persist OAuth tokens and client registration to JSON files.

    File layout::

        HERMES_HOME/mcp-tokens/<server_name>.json         -- tokens
        HERMES_HOME/mcp-tokens/<server_name>.client.json   -- client info
        HERMES_HOME/mcp-tokens/<server_name>.meta.json     -- oauth server metadata
    """

    def __init__(self, server_name: str):
        self._server_name = _safe_filename(server_name)

    def _tokens_path(self) -> Path:
        return _get_token_dir() / f"{self._server_name}.json"

    def _client_info_path(self) -> Path:
        return _get_token_dir() / f"{self._server_name}.client.json"

    def _meta_path(self) -> Path:
        return _get_token_dir() / f"{self._server_name}.meta.json"

    # -- tokens ------------------------------------------------------------

    async def get_tokens(self) -> "OAuthToken | None":
        data = _read_json(self._tokens_path())
        if data is None:
            return None
        # Hermes records an absolute wall-clock ``expires_at`` alongside the
        # SDK's serialized token (see ``set_tokens``). On read we rewrite
        # ``expires_in`` to the remaining seconds so the SDK's downstream
        # ``update_token_expiry`` computes the correct absolute time and
        # ``is_token_valid()`` correctly reports False for tokens that
        # expired while the process was down.
        #
        # Legacy token files (pre-Fix-A) have ``expires_in`` but no
        # ``expires_at``. We fall back to the file's mtime as a best-effort
        # wall-clock proxy for when the token was written: if (mtime +
        # expires_in) is in the past, clamp ``expires_in`` to zero so the
        # SDK refreshes before the first request. This self-heals one-time
        # on the next successful ``set_tokens``, which writes the new
        # ``expires_at`` field. The stored ``expires_at`` is stripped before
        # model_validate because it's not part of the SDK's OAuthToken schema.
        absolute_expiry = data.pop("expires_at", None)
        if absolute_expiry is not None:
            data["expires_in"] = int(max(absolute_expiry - time.time(), 0))
        elif data.get("expires_in") is not None:
            try:
                file_mtime = self._tokens_path().stat().st_mtime
            except OSError:
                file_mtime = None
            if file_mtime is not None:
                try:
                    implied_expiry = file_mtime + int(data["expires_in"])
                    data["expires_in"] = int(max(implied_expiry - time.time(), 0))
                except (TypeError, ValueError):
                    pass
        try:
            return OAuthToken.model_validate(data)
        except (ValueError, TypeError, KeyError) as exc:
            logger.warning("Corrupt tokens at %s -- ignoring: %s", self._tokens_path(), exc)
            return None

    async def set_tokens(self, tokens: "OAuthToken") -> None:
        payload = tokens.model_dump(mode="json", exclude_none=True)
        # Persist an absolute ``expires_at`` so a process restart can
        # reconstruct the correct remaining TTL. Without this the MCP SDK's
        # ``_initialize`` reloads a relative ``expires_in`` which has no
        # wall-clock reference, leaving ``context.token_expiry_time=None``
        # and ``is_token_valid()`` falsely reporting True. See Fix A in
        # ``mcp-oauth-token-diagnosis`` skill + Claude Code's
        # ``OAuthTokens.expiresAt`` persistence (auth.ts ~180).
        expires_in = payload.get("expires_in")
        if expires_in is not None:
            try:
                payload["expires_at"] = time.time() + int(expires_in)
            except (TypeError, ValueError):
                # Mock tokens or unusual shapes: skip the expires_at write
                # rather than fail persistence.
                pass
        _write_json(self._tokens_path(), payload)
        logger.debug("OAuth tokens saved for %s", self._server_name)

    # -- client info -------------------------------------------------------

    async def get_client_info(self) -> "OAuthClientInformationFull | None":
        data = _read_json(self._client_info_path())
        if data is None:
            return None
        try:
            return OAuthClientInformationFull.model_validate(data)
        except (ValueError, TypeError, KeyError) as exc:
            logger.warning("Corrupt client info at %s -- ignoring: %s", self._client_info_path(), exc)
            return None

    async def set_client_info(self, client_info: "OAuthClientInformationFull") -> None:
        _write_json(self._client_info_path(), client_info.model_dump(mode="json", exclude_none=True))
        logger.debug("OAuth client info saved for %s", self._server_name)

    # -- oauth server metadata --------------------------------------------
    # The MCP SDK keeps discovered ``OAuthMetadata`` (token endpoint URL,
    # etc.) in memory only. Persisting it here lets a restarted process
    # refresh tokens without re-running metadata discovery. Without this,
    # cold-start refresh requests fall back to the SDK's guessed
    # ``{server_url}/token`` which returns 404 on most real providers and
    # forces a full browser re-authorization.

    def save_oauth_metadata(self, metadata: "OAuthMetadata") -> None:
        _write_json(self._meta_path(), metadata.model_dump(exclude_none=True, mode="json"))
        logger.debug("OAuth metadata saved for %s", self._server_name)

    def load_oauth_metadata(self) -> "OAuthMetadata | None":
        data = _read_json(self._meta_path())
        if data is None:
            return None
        try:
            return OAuthMetadata.model_validate(data)
        except (ValueError, TypeError, KeyError) as exc:
            logger.warning("Corrupt OAuth metadata at %s -- ignoring: %s", self._meta_path(), exc)
            return None

    # -- cleanup -----------------------------------------------------------

    def remove(self) -> None:
        """Delete all stored OAuth state for this server."""
        for p in (self._tokens_path(), self._client_info_path(), self._meta_path()):
            p.unlink(missing_ok=True)

    def has_cached_tokens(self) -> bool:
        """Return True if we have tokens on disk (may be expired)."""
        return self._tokens_path().exists()


# ---------------------------------------------------------------------------
# Callback handler factory -- each invocation gets its own result dict
# ---------------------------------------------------------------------------


# Query parameters that carry OAuth secrets and must never reach the logs.
# ``code``/``state`` are the authorization code and CSRF token; ``error``
# can echo provider-side detail. ``BaseHTTPRequestHandler`` log lines embed
# the raw request line (e.g. ``"GET /callback?code=...&state=..."``), so the
# formatted message is scrubbed before it is handed to the logger.
_SENSITIVE_CALLBACK_QUERY_RE = re.compile(
    r"\b(code|state|error)=[^&\s\"']*",
    re.IGNORECASE,
)


def _redact_callback_log(message: str) -> str:
    """Redact OAuth secrets from a callback HTTP-server log line.

    Replaces the value of any ``code``/``state``/``error`` query parameter
    with ``REDACTED`` so the authorization code and CSRF state never land in
    debug logs (which may be shipped off-box or shared in bug reports).
    """
    return _SENSITIVE_CALLBACK_QUERY_RE.sub(
        lambda m: f"{m.group(1)}=REDACTED", message
    )


def _make_callback_handler() -> tuple[type, dict]:
    """Create a per-flow callback HTTP handler class with its own result dict.

    Returns ``(HandlerClass, result_dict)`` where *result_dict* is a mutable
    dict that the handler writes ``auth_code`` and ``state`` into when the
    OAuth redirect arrives.  Each call returns a fresh pair so concurrent
    flows don't stomp on each other.
    """
    result: dict[str, Any] = {"auth_code": None, "state": None, "error": None}

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            params = parse_qs(urlparse(self.path).query)
            code = params.get("code", [None])[0]
            state = params.get("state", [None])[0]
            error = params.get("error", [None])[0]

            result["auth_code"] = code
            result["state"] = state
            result["error"] = error

            body = (
                "<html><body><h2>Authorization Successful</h2>"
                "<p>You can close this tab and return to Hermes.</p></body></html>"
            ) if code else (
                "<html><body><h2>Authorization Failed</h2>"
                f"<p>Error: {error or 'unknown'}</p></body></html>"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, fmt: str, *args: Any) -> None:
            # The request line embedded here contains the callback query
            # string (?code=...&state=...); redact secrets before logging.
            logger.debug("OAuth callback: %s", _redact_callback_log(fmt % args))

    return _Handler, result


# ---------------------------------------------------------------------------
# Async redirect + callback handlers for OAuthClientProvider
# ---------------------------------------------------------------------------


async def _redirect_handler(authorization_url: str, callback_port: int | None = None) -> None:
    """Show the authorization URL to the user.

    Opens the browser automatically when possible; always prints the URL
    as a fallback for headless/SSH/gateway environments.
    """
    msg = (
        f"\n  MCP OAuth: authorization required.\n"
        f"  Open this URL in your browser:\n\n"
        f"    {authorization_url}\n"
    )
    print(msg, file=sys.stderr)

    # On a remote SSH session the OAuth provider redirects to
    # http://127.0.0.1:<port>/callback, which reaches the callback server on
    # the *remote* machine — not the user's local machine where the browser
    # opened.  Print a port-forward hint so the user knows to tunnel first.
    callback_port = callback_port or _oauth_port
    if callback_port and (os.getenv("SSH_CLIENT") or os.getenv("SSH_TTY")):
        print(
            f"  Remote session detected. The OAuth provider will redirect your browser to\n"
            f"    http://127.0.0.1:{callback_port}/callback\n"
            f"  which the callback listener on THIS machine is waiting on. If your browser\n"
            f"  is on a different machine, forward the port first in a separate terminal:\n"
            f"\n"
            f"    ssh -N -L {callback_port}:127.0.0.1:{callback_port} <user>@<this-host>\n"
            f"\n"
            f"  Then open the URL above. See: https://hermes-agent.nousresearch.com/docs/guides/oauth-over-ssh\n",
            file=sys.stderr,
        )

    if _can_open_browser():
        try:
            opened = webbrowser.open(authorization_url)
            if opened:
                print("  (Browser opened automatically.)\n", file=sys.stderr)
            else:
                print("  (Could not open browser — please open the URL manually.)\n", file=sys.stderr)
        except Exception:
            print("  (Could not open browser — please open the URL manually.)\n", file=sys.stderr)
    else:
        print("  (Headless environment detected — open the URL manually.)\n", file=sys.stderr)


def _claim_callback_flow(
    port: int,
    flow_key: tuple[Any, ...] | None = None,
) -> tuple[int, tuple[Any, ...]]:
    """Reserve a callback port for one OAuth flow before URL emission.

    ``OAuthClientProvider`` calls ``redirect_handler`` before it calls the
    callback waiter. If two distinct flows share a configured callback port,
    allowing the second URL to be shown risks the user's browser redirecting to
    the first flow's listener and writing the second code/state into the first
    result buffer. This guard is therefore shared by the redirect handler and
    callback waiter and runs before any conflicting authorization URL is shown.
    """
    slot_key = _callback_result_key(port, flow_key)
    with _oauth_result_lock:
        same_port_other_flow_active = any(
            key[0] == port and key != slot_key
            for key in (
                *_oauth_active_flow_claims,
                *_oauth_results_by_port.keys(),
                *_oauth_pending_ports,
            )
        )
        if same_port_other_flow_active:
            raise OAuthNonInteractiveError(
                f"OAuth callback port 127.0.0.1:{port} is already in use by "
                "another active OAuth flow. Set 'oauth.redirect_port: 0' or "
                "configure unique callback ports for concurrent MCP logins."
            )
        _oauth_active_flow_claims.add(slot_key)
    return slot_key


def _make_redirect_handler(port: int, flow_key: tuple[Any, ...]):
    """Return a redirect handler that claims this flow before showing its URL."""

    async def _bound_redirect_handler(authorization_url: str) -> None:
        _claim_callback_flow(port, flow_key)
        await _redirect_handler(authorization_url, callback_port=port)

    return _bound_redirect_handler


def _callback_result_key(
    port: int,
    flow_key: tuple[Any, ...] | None = None,
) -> tuple[int, tuple[Any, ...]]:
    """Return the isolation key for an OAuth callback result buffer."""
    return (port, flow_key or _oauth_flow_key)


def _flow_key_for_config(
    server_name: str,
    server_url: str,
    cfg: dict[str, Any],
) -> tuple[Any, ...]:
    """Build a stable in-process identity for one OAuth login flow.

    The callback server is keyed by port *and* this flow identity. That lets
    sibling waiters for the same provider reuse the listener/result, while
    distinct MCP servers/providers that intentionally share a redirect_port do
    not consume each other's authorization code/state.
    """
    cfg_items: list[tuple[str, str]] = []
    for key, value in sorted(cfg.items()):
        if key.startswith("_") or key == "timeout":
            continue
        try:
            encoded = json.dumps(value, sort_keys=True, default=str)
        except TypeError:
            encoded = repr(value)
        cfg_items.append((key, encoded))
    return (server_name, server_url, tuple(cfg_items))


def _make_wait_for_callback(
    port: int,
    flow_key: tuple[Any, ...],
):
    """Return a provider callback handler bound to one flow identity."""
    async def _bound_wait_for_callback() -> tuple[str, str | None]:
        return await _wait_for_callback(port=port, flow_key=flow_key)

    return _bound_wait_for_callback


async def _wait_for_callback(
    port: int | None = None,
    flow_key: tuple[Any, ...] | None = None,
) -> tuple[str, str | None]:
    """Wait for the OAuth callback to arrive on the local callback server.

    Uses the module-level ``_oauth_port`` which is set by ``build_oauth_auth``
    before this is ever called.  Polls for the result without blocking the
    event loop.

    Raises:
        OAuthNonInteractiveError: If the callback times out (no user present
            to complete the browser auth).
        RuntimeError: If ``_oauth_port`` has not been set, which would indicate
            that ``build_oauth_auth`` was skipped — the asserting form below
            was a silent bug when running Python with ``-O``/``-OO``.
    """
    if port is None:
        port = _oauth_port
    if port is None:
        raise RuntimeError(
            "OAuth callback port not set — build_oauth_auth must be called "
            "before _wait_for_oauth_callback"
        )

    # Reuse the shared result buffer only after a sibling waiter has
    # successfully bound and published a listener for this exact port. Do not
    # publish a fresh result before HTTPServer succeeds: a concurrent waiter
    # could otherwise poll an unbacked buffer if the bind fails.
    global _oauth_result, _oauth_result_active, _oauth_result_port
    slot_key = _claim_callback_flow(port, flow_key)
    waiting_for_pending = False
    with _oauth_result_lock:
        existing_result = _oauth_results_by_port.get(slot_key)
        same_port_other_flow_active = any(
            key[0] == port and key != slot_key
            for key in (*_oauth_results_by_port.keys(), *_oauth_pending_ports)
        )
        if existing_result is not None:
            # A sibling already bound and published a live listener for this
            # exact flow. Reuse that listener/result so SDK retries do not
            # race a second bind.
            handler_cls = None
            result = existing_result
            owns_shared_slot = False
        elif slot_key in _oauth_pending_ports:
            # A sibling has committed to binding this exact port/flow but has
            # not yet finished. Binding ourselves would lose the race and
            # raise spuriously even though that sibling is about to publish a
            # listener. Wait below for its bind to resolve instead.
            handler_cls = None
            result = None
            owns_shared_slot = False
            waiting_for_pending = True
        elif same_port_other_flow_active:
            # One HTTPServer can only hand its callback to the result buffer it
            # was created with. Without a state-aware demux layer, a different
            # flow on the same callback port would either fail a second bind or
            # risk consuming the wrong code/state. Fail early and tell the user
            # to let Hermes choose unique callback ports for concurrent flows.
            raise OAuthNonInteractiveError(
                f"OAuth callback port 127.0.0.1:{port} is already in use by "
                "another active OAuth flow. Set 'oauth.redirect_port: 0' or "
                "configure unique callback ports for concurrent MCP logins."
            )
        else:
            handler_cls, result = _make_callback_handler()
            owns_shared_slot = True
            # Reserve the in-progress marker while still holding the lock so
            # concurrent waiters observe it atomically with our decision to
            # bind. This is not a result buffer -- nothing polls it.
            _oauth_pending_ports.add(slot_key)

    server: HTTPServer | None = None
    if handler_cls is not None:
        try:
            server = HTTPServer(("127.0.0.1", port), handler_cls)
        except OSError as exc:
            with _oauth_result_lock:
                # Bind failed: drop the in-progress marker so a waiting
                # sibling stops waiting, and fall back to any listener a
                # sibling may already have published for this port.
                _oauth_pending_ports.discard(slot_key)
                existing_result = _oauth_results_by_port.get(slot_key)
            if existing_result is not None:
                result = existing_result
                owns_shared_slot = False
            else:
                # We could not bind and no sibling has published a live
                # listener for this port, so nothing will populate a result
                # buffer. Surface the failure immediately rather than polling
                # until timeout.
                with _oauth_result_lock:
                    _oauth_active_flow_claims.discard(slot_key)
                raise OAuthNonInteractiveError(
                    f"OAuth callback server failed to bind on 127.0.0.1:{port}. "
                    "The configured callback port may already be in use; set "
                    "'oauth.redirect_port: 0' in config.yaml to auto-pick a free port."
                ) from exc
        else:
            with _oauth_result_lock:
                # The in-progress marker guarantees we are the sole binder
                # for this port, so the published slot below cannot collide
                # with a sibling. Publish the live buffer and drop the
                # marker atomically so siblings switch from waiting to
                # reusing the listener.
                _oauth_results_by_port[slot_key] = result
                _oauth_result = result
                _oauth_result_active = True
                _oauth_result_port = port
                _oauth_pending_ports.discard(slot_key)
            threading.Thread(target=server.handle_request, daemon=True).start()

    if waiting_for_pending:
        # Poll for the binding sibling to either publish a listener or
        # abandon its bind. Binding a local socket is fast, so this resolves
        # quickly; the bound below is a safety net, not the expected path.
        pending_timeout = 10.0
        pending_poll = 0.05
        pending_elapsed = 0.0
        while True:
            with _oauth_result_lock:
                result = _oauth_results_by_port.get(slot_key)
                still_pending = slot_key in _oauth_pending_ports
            if result is not None:
                break
            if not still_pending:
                # The binding sibling failed to bind and published nothing.
                with _oauth_result_lock:
                    _oauth_active_flow_claims.discard(slot_key)
                raise OAuthNonInteractiveError(
                    f"OAuth callback server failed to bind on 127.0.0.1:{port}. "
                    "The configured callback port may already be in use; set "
                    "'oauth.redirect_port: 0' in config.yaml to auto-pick a free port."
                )
            if pending_elapsed >= pending_timeout:
                with _oauth_result_lock:
                    _oauth_active_flow_claims.discard(slot_key)
                raise OAuthNonInteractiveError(
                    f"OAuth callback listener did not come up on 127.0.0.1:{port}."
                )
            await asyncio.sleep(pending_poll)
            pending_elapsed += pending_poll

    try:
        timeout = 300.0
        poll_interval = 0.5
        elapsed = 0.0
        while elapsed < timeout:
            if result["auth_code"] is not None or result["error"] is not None:
                break
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        if result["error"]:
            raise RuntimeError(f"OAuth authorization failed: {result['error']}")
        if result["auth_code"] is None:
            raise OAuthNonInteractiveError(
                "OAuth callback timed out — no authorization code received. "
                "Ensure you completed the browser authorization flow."
            )

        return result["auth_code"], result["state"]
    finally:
        if server is not None:
            server.server_close()
        # Clear the shared slot on any exit (success, error, timeout) so a
        # subsequent login attempt cannot inherit stale auth_code/state/error.
        # Only the waiter that installed the slot clears it, to avoid a
        # concurrent sibling waiter wiping out a result it still needs.
        if owns_shared_slot:
            with _oauth_result_lock:
                if _oauth_results_by_port.get(slot_key) is result:
                    _oauth_results_by_port.pop(slot_key, None)
                _oauth_active_flow_claims.discard(slot_key)
                if _oauth_result is result:
                    _oauth_result = None
                    _oauth_result_active = bool(_oauth_results_by_port)
                    next_key = next(iter(_oauth_results_by_port), None)
                    _oauth_result_port = next_key[0] if next_key is not None else None
                    if next_key is not None:
                        _oauth_result = _oauth_results_by_port[next_key]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def remove_oauth_tokens(server_name: str) -> None:
    """Delete stored OAuth tokens and client info for a server."""
    storage = HermesTokenStorage(server_name)
    storage.remove()
    logger.info("OAuth tokens removed for '%s'", server_name)


# ---------------------------------------------------------------------------
# Extracted helpers (Task 3 of MCP OAuth consolidation)
#
# These compose into ``build_oauth_auth`` below, and are also used by
# ``tools.mcp_oauth_manager.MCPOAuthManager._build_provider`` so the two
# construction paths share one implementation.
# ---------------------------------------------------------------------------


def _reset_shared_callback_result() -> None:
    """Drop stale ``_oauth_result`` before a new provider is constructed.

    Active callback listeners own the shared slot until their waiter exits.
    Provider construction must not clear that live buffer, because sibling
    waiters may still need to reuse it instead of racing a second bind on the
    same port. Stale, inactive slots left by tests or unexpected paths are safe
    to discard.
    """
    global _oauth_result, _oauth_result_active, _oauth_result_port
    with _oauth_result_lock:
        if not _oauth_result_active:
            _oauth_result = None
            _oauth_result_port = None
            _oauth_results_by_port.clear()
            # Do not clear _oauth_active_flow_claims here. A redirect handler
            # claims its (port, flow) before the provider publishes its
            # callback listener, so _oauth_result_active can still be false in
            # that handoff window. Clearing claims during unrelated provider
            # construction would let a different flow on the same port emit a
            # competing auth URL instead of failing closed. The waiter that owns
            # a claim releases it in _wait_for_callback() cleanup/error paths.


def _configure_callback_port(cfg: dict) -> int:
    """Pick or validate the OAuth callback port.

    Stores the resolved port into ``cfg['_resolved_port']`` so sibling
    helpers (and the manager) can read it from the same dict. Returns the
    resolved port.

    NOTE: also sets the legacy module-level ``_oauth_port`` so existing
    direct calls to ``_wait_for_callback`` keep working. Provider callbacks
    are bound to their resolved port/flow identity via ``_make_wait_for_callback``.
    """
    global _oauth_port
    requested = int(cfg.get("redirect_port", 0))
    port = _find_free_port() if requested == 0 else requested
    cfg["_resolved_port"] = port
    _oauth_port = port  # legacy consumer: _wait_for_callback reads this
    return port


def _configure_callback_flow(
    server_name: str,
    server_url: str,
    cfg: dict[str, Any],
) -> tuple[int, tuple[Any, ...]]:
    """Resolve callback port and flow identity for provider construction."""
    global _oauth_flow_key
    port = _configure_callback_port(cfg)
    flow_key = _flow_key_for_config(server_name, server_url, cfg)
    _oauth_flow_key = flow_key  # legacy consumer: direct _wait_for_callback()
    cfg["_flow_key"] = flow_key
    return port, flow_key


def _build_client_metadata(cfg: dict) -> "OAuthClientMetadata":
    """Build OAuthClientMetadata from the oauth config dict.

    Requires ``cfg['_resolved_port']`` to have been populated by
    :func:`_configure_callback_port` first.
    """
    port = cfg.get("_resolved_port")
    if port is None:
        raise ValueError(
            "_configure_callback_port() must be called before _build_client_metadata()"
        )
    client_name = cfg.get("client_name", "Hermes Agent")
    scope = cfg.get("scope")
    redirect_uri = f"http://127.0.0.1:{port}/callback"

    metadata_kwargs: dict[str, Any] = {
        "client_name": client_name,
        "redirect_uris": [AnyUrl(redirect_uri)],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }
    if scope:
        metadata_kwargs["scope"] = scope
    if cfg.get("client_secret"):
        metadata_kwargs["token_endpoint_auth_method"] = "client_secret_post"

    return OAuthClientMetadata.model_validate(metadata_kwargs)


def _maybe_preregister_client(
    storage: "HermesTokenStorage",
    cfg: dict,
    client_metadata: "OAuthClientMetadata",
) -> None:
    """If cfg has a pre-registered client_id, persist it to storage."""
    client_id = cfg.get("client_id")
    if not client_id:
        return
    port = cfg["_resolved_port"]
    redirect_uri = f"http://127.0.0.1:{port}/callback"

    info_dict: dict[str, Any] = {
        "client_id": client_id,
        "redirect_uris": [redirect_uri],
        "grant_types": client_metadata.grant_types,
        "response_types": client_metadata.response_types,
        "token_endpoint_auth_method": client_metadata.token_endpoint_auth_method,
    }
    if cfg.get("client_secret"):
        info_dict["client_secret"] = cfg["client_secret"]
    if cfg.get("client_name"):
        info_dict["client_name"] = cfg["client_name"]
    if cfg.get("scope"):
        info_dict["scope"] = cfg["scope"]

    client_info = OAuthClientInformationFull.model_validate(info_dict)
    _write_json(storage._client_info_path(), client_info.model_dump(mode="json", exclude_none=True))
    logger.debug("Pre-registered client_id=%s for '%s'", client_id, storage._server_name)


def build_oauth_auth(
    server_name: str,
    server_url: str,
    oauth_config: dict | None = None,
) -> "OAuthClientProvider | None":
    """Build an ``httpx.Auth``-compatible OAuth handler for an MCP server.

    Public API preserved for backwards compatibility. New code should use
    :func:`tools.mcp_oauth_manager.get_manager` so OAuth state is shared
    across config-time, runtime, and reconnect paths.

    Args:
        server_name: Server key in mcp_servers config (used for storage).
        server_url: MCP server endpoint URL.
        oauth_config: Optional dict from the ``oauth:`` block in config.yaml.

    Returns:
        An ``OAuthClientProvider`` instance, or None if the MCP SDK lacks
        OAuth support.
    """
    if not _OAUTH_AVAILABLE:
        logger.warning(
            "MCP OAuth requested for '%s' but SDK auth types are not available. "
            "Install with: pip install 'mcp>=1.26.0'",
            server_name,
        )
        return None

    cfg = dict(oauth_config or {})  # copy — we mutate _resolved_port
    storage = HermesTokenStorage(server_name)

    # Defensive reset: if a previous flow exited via an unexpected path
    # (e.g. test harness) and left stale callback state behind, drop it
    # before the new flow's _wait_for_callback can latch onto it.
    _reset_shared_callback_result()

    if not _is_interactive() and not storage.has_cached_tokens():
        logger.warning(
            "MCP OAuth for '%s': non-interactive environment and no cached tokens "
            "found. The OAuth flow requires browser authorization. Run "
            "interactively first to complete the initial authorization, then "
            "cached tokens will be reused.",
            server_name,
        )

    port, flow_key = _configure_callback_flow(server_name, server_url, cfg)
    client_metadata = _build_client_metadata(cfg)
    _maybe_preregister_client(storage, cfg, client_metadata)

    return OAuthClientProvider(
        server_url=server_url,
        client_metadata=client_metadata,
        storage=storage,
        redirect_handler=_make_redirect_handler(port, flow_key),
        callback_handler=_make_wait_for_callback(port, flow_key),
        timeout=float(cfg.get("timeout", 300)),
    )
