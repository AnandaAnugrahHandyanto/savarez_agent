#!/usr/bin/env python3
"""
Google OAuth 2.1 flow for Gemini API.

Implements the Authorization Code + PKCE (S256) flow with a localhost
callback server, matching the pattern used by OpenClaw's google-gemini-cli.

File layout:
    HERMES_HOME/gemini_oauth.json   -- stored credentials
"""

from __future__ import annotations

import base64
import json
import logging
import os
import secrets
import stat
import threading
import time
import webbrowser
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# OAuth Constants
# -----------------------------------------------------------------------------

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo?alt=json"

# Client ID — Nous Research "Desktop app" OAuth client
# (Google considers installed-app secrets non-confidential)
CLIENT_ID = "621167296065-a5t1j78e61ljeu3kr3nqmi80khki983f.apps.googleusercontent.com"
CLIENT_SECRET = ""  # Not used for public/client OAuth
REDIRECT_URI = "http://localhost:8085/oauth2callback"

SCOPES = []

# Token refresh buffer: 5 minutes before expiry
REFRESH_SKEW_SECONDS = 5 * 60

# Timeout for OAuth callback
OAUTH_TIMEOUT_SECONDS = 300


# -----------------------------------------------------------------------------
# PKCE Helpers
# -----------------------------------------------------------------------------

def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate_pkce() -> tuple[str, str]:
    """Generate a PKCE code verifier and S256 challenge.

    Returns (verifier, challenge) — verifier is 32 random bytes (43 chars base64url),
    challenge is the SHA-256 hash of the verifier, base64url-encoded.
    """
    verifier_bytes = secrets.token_bytes(32)
    verifier = _base64url_encode(verifier_bytes)
    digest = sha256(verifier.encode("ascii")).digest()
    challenge = _base64url_encode(digest)
    return verifier, challenge


# -----------------------------------------------------------------------------
# Token Storage
# -----------------------------------------------------------------------------

def _get_token_path() -> Path:
    from hermes_cli.config import get_hermes_home
    return Path(get_hermes_home()) / "gemini_oauth.json"


def load_credentials() -> Optional[Dict[str, Any]]:
    """Load stored OAuth credentials from disk.

    Returns None if no credentials are stored.
    """
    path = _get_token_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read Gemini OAuth credentials: %s", exc)
        return None


def save_credentials(creds: Dict[str, Any]) -> None:
    """Persist OAuth credentials to disk with 0o600 permissions."""
    path = _get_token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(creds, indent=2, default=str), encoding="utf-8")
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        tmp.rename(path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


# -----------------------------------------------------------------------------
# Callback Server
# -----------------------------------------------------------------------------

class _CallbackHandler(BaseHTTPRequestHandler):
    """Per-flow callback handler — writes code/state into a shared result dict."""

    # Class-level result dict shared across all instances within one flow
    _result: Dict[str, Any] = {"auth_code": None, "state": None, "error": None}

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.debug("OAuth callback: %s", fmt % args)

    def do_GET(self) -> None:  # noqa: N802
        params = parse_qs(urlparse(self.path).query)
        code = params.get("code", [None])[0]
        state = params.get("state", [None])[0]
        error = params.get("error", [None])[0]

        self._result["auth_code"] = code
        self._result["state"] = state
        self._result["error"] = error

        if code:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>Authorization Successful</h2>"
                b"<p>You can close this tab and return to Hermes.</p></body></html>"
            )
        else:
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                f"<html><body><h2>Authorization Failed</h2>"
                f"<p>Error: {error or 'unknown'}</p></body></html>".encode()
            )


def _find_free_port() -> int:
    with __import__("socket").socket(__import__("socket").AF_INET, __import__("socket").SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# -----------------------------------------------------------------------------
# OAuth Flow
# -----------------------------------------------------------------------------

def _can_open_browser() -> bool:
    """Return True if opening a browser is likely to work."""
    if os.environ.get("SSH_CLIENT") or os.environ.get("SSH_TTY"):
        return False
    if os.name == "nt":
        return True
    try:
        if __import__("os").uname().sysname == "Darwin":
            return True
    except AttributeError:
        pass
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


async def start_gemini_oauth_flow(
    on_progress: Optional[callable] = None,
) -> Dict[str, Any]:
    """Run the full OAuth flow and return credentials.

    Args:
        on_progress: Optional callback(msg: str) for progress updates.

    Returns:
        Dict with keys: refresh, access, expires (timestamp), email (optional)
    """
    import asyncio

    verifier, challenge = generate_pkce()
    port = _find_free_port()
    redirect_uri = f"http://localhost:{port}/oauth2callback"

    # Start callback server
    on_progress and on_progress("Starting local server for OAuth callback...")

    result: Dict[str, Any] = {"auth_code": None, "state": None, "error": None}
    _CallbackHandler._result = result

    server = HTTPServer(("127.0.0.1", port), _CallbackHandler)
    server_thread = threading.Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    try:
        # Build authorization URL
        import urllib.parse

        auth_params = urllib.parse.urlencode({
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": " ".join(SCOPES),
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": verifier,
            "access_type": "offline",
            "prompt": "consent",
        })
        auth_url = f"{AUTH_URL}?{auth_params}"

        on_progress and on_progress(
            "Open this URL in your browser:\n\n  " + auth_url + "\n"
        )
        print(f"\n  Gemini OAuth: authorization required.", file=__import__("sys").stderr)
        print(f"  Open this URL in your browser:\n\n    {auth_url}\n", file=__import__("sys").stderr)

        if _can_open_browser():
            try:
                opened = webbrowser.open(auth_url)
                print(
                    f"  (Browser opened automatically.)\n",
                    file=__import__("sys").stderr,
                )
            except Exception:
                print(
                    f"  (Could not open browser — please open the URL manually.)\n",
                    file=__import__("sys").stderr,
                )
        else:
            print(
                f"  (Headless environment — open the URL manually.)\n",
                file=__import__("sys").stderr,
            )

        # Wait for callback
        on_progress and on_progress("Waiting for OAuth callback...")
        deadline = time.time() + OAUTH_TIMEOUT_SECONDS
        poll_interval = 0.5

        while time.time() < deadline:
            if result["auth_code"] is not None or result["error"] is not None:
                break
            await asyncio.sleep(poll_interval)

        if result["error"]:
            raise RuntimeError(f"OAuth authorization failed: {result['error']}")
        if result["auth_code"] is None:
            raise TimeoutError("OAuth callback timed out")

        # Verify state
        if result["state"] != verifier:
            raise RuntimeError("OAuth state mismatch — possible CSRF attack")

        code = result["auth_code"]

        # Exchange code for tokens
        on_progress and on_progress("Exchanging authorization code for tokens...")

        import urllib.parse as _urllib_parse

        token_response = __import__("httpx").Client().post(
            TOKEN_URL,
            data=_urllib_parse.urlencode({
                "client_id": CLIENT_ID,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                "code_verifier": verifier,
            }),
        )
        if not token_response.ok:
            raise RuntimeError(f"Token exchange failed: {token_response.text}")

        token_data = token_response.json()
        if not token_data.get("refresh_token"):
            raise RuntimeError("No refresh token received. Please try again.")

        # Get user email
        on_progress and on_progress("Getting user info...")
        email: Optional[str] = None
        try:
            user_resp = __import__("httpx").Client().get(
                USERINFO_URL,
                headers={"Authorization": f"Bearer {token_data['access_token']}"},
            )
            if user_resp.ok:
                email = user_resp.json().get("email")
        except Exception:
            pass

        # Calculate expiry timestamp (with 5-min buffer)
        expires_in = token_data.get("expires_in", 3600)
        expires_at = time.time() + expires_in - REFRESH_SKEW_SECONDS

        return {
            "refresh": token_data["refresh_token"],
            "access": token_data["access_token"],
            "expires": expires_at,
            "email": email,
        }

    finally:
        server.server_close()


def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    """Refresh an expired access token.

    Returns a dict with keys: refresh, access, expires (timestamp)
    """
    import urllib.parse as _urllib_parse

    response = __import__("httpx").Client().post(
        TOKEN_URL,
        data=_urllib_parse.urlencode({
            "client_id": CLIENT_ID,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }),
    )
    if not response.ok:
        raise RuntimeError(f"Token refresh failed: {response.text}")

    data = response.json()
    expires_in = data.get("expires_in", 3600)
    expires_at = time.time() + expires_in - REFRESH_SKEW_SECONDS

    return {
        "refresh": data.get("refresh_token") or refresh_token,
        "access": data["access_token"],
        "expires": expires_at,
    }


def get_valid_access_token() -> tuple[str, float]:
    """Fetch a valid Gemini access token from the local GhostBridge proxy.

    GhostBridge (gemini_bridge.js) runs on 127.0.0.1:18792 and manages the
    OAuth refresh cycle independently. This function simply asks it for a
    fresh token — no OAuth logic lives here any more.
    """
    import json, urllib.request

    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:18792/token", timeout=10
        ) as resp:
            data = json.loads(resp.read())
            token = data["access_token"]
            return token, 0.0
    except Exception as exc:
        raise RuntimeError(
            f"GhostBridge token fetch failed ({exc}). "
            "Is gemini_bridge.js running on port 18792?"
        ) from exc


def has_stored_credentials() -> bool:
    """Return True if stored OAuth credentials exist on disk."""
    return _get_token_path().exists()


def clear_credentials() -> None:
    """Delete stored OAuth credentials."""
    path = _get_token_path()
    path.unlink(missing_ok=True)
    logger.info("Gemini OAuth credentials cleared")
