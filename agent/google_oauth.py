"""Google OAuth 2.0 for Gemini API — Authorization Code + PKCE (S256).

Provides browser-based OAuth login against Google's authorization server,
with a localhost callback server to capture the authorization code.
Follows the same pattern as the Anthropic adapter in this codebase.

Auth flow:
  1. Generate PKCE code_verifier + code_challenge
  2. Open browser to Google authorization URL
  3. Localhost server on port 8085 captures the callback
  4. Exchange authorization code for access + refresh tokens
  5. Persist tokens to ~/.hermes/gemini_oauth.json
  6. Before API calls: check expiry, refresh if within 5 minutes

Token storage:
  - File: ~/.hermes/gemini_oauth.json
  - Permissions: 0o600
  - Fields: client_id, client_secret, access_token, refresh_token,
            expires_at, email
"""

import base64
import hashlib
import json
import logging
import os
import secrets
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

# ── Google OAuth endpoints ──────────────────────────────────────────────
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

# ── Scopes ──────────────────────────────────────────────────────────────
GOOGLE_OAUTH_SCOPES = (
    "https://www.googleapis.com/auth/cloud-platform "
    "https://www.googleapis.com/auth/userinfo.email"
)

# ── Default OAuth client (Desktop app — secrets are non-confidential) ──
# These should be registered by the project maintainer on a GCP project
# with the Generative Language API enabled.  Desktop-type OAuth client IDs
# are public by design (security relies on PKCE, not client_secret).
# Override for local development via HERMES_GEMINI_CLIENT_ID / HERMES_GEMINI_CLIENT_SECRET.
#
# TODO(maintainer): Register a GCP OAuth Desktop client and fill these in,
#   similar to how Anthropic, Copilot, Codex, and Qwen all ship a built-in
#   public client_id.
_DEFAULT_CLIENT_ID = ""   # e.g. "123456789-abcdef.apps.googleusercontent.com"
_DEFAULT_CLIENT_SECRET = ""   # GOCSPX-... (non-confidential for Desktop apps)

# ── Localhost callback ──────────────────────────────────────────────────
_REDIRECT_PORT = 8085
_REDIRECT_URI = f"http://localhost:{_REDIRECT_PORT}/oauth2callback"

# ── Token file ──────────────────────────────────────────────────────────
_OAUTH_FILE = get_hermes_home() / "gemini_oauth.json"

# ── Refresh margin (seconds) ────────────────────────────────────────────
_REFRESH_MARGIN = 5 * 60  # refresh if within 5 minutes of expiry


# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------

def _generate_pkce() -> Tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge (S256).

    Returns (verifier, challenge) both as URL-safe base64 strings.
    """
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


# ---------------------------------------------------------------------------
# Credential file I/O
# ---------------------------------------------------------------------------

def _get_client_id() -> str:
    return os.getenv("HERMES_GEMINI_CLIENT_ID", "") or _DEFAULT_CLIENT_ID


def _get_client_secret() -> str:
    return os.getenv("HERMES_GEMINI_CLIENT_SECRET", "") or _DEFAULT_CLIENT_SECRET


def save_credentials(data: Dict[str, Any]) -> None:
    """Persist OAuth credentials to ~/.hermes/gemini_oauth.json (mode 0600)."""
    _OAUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _OAUTH_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.chmod(str(tmp), 0o600)
    tmp.replace(_OAUTH_FILE)
    logger.debug("Saved Gemini OAuth credentials to %s", _OAUTH_FILE)


def load_credentials() -> Optional[Dict[str, Any]]:
    """Load stored Gemini OAuth credentials. Returns None if absent/corrupt."""
    if not _OAUTH_FILE.exists():
        return None
    try:
        data = json.loads(_OAUTH_FILE.read_text(encoding="utf-8"))
        if data.get("access_token"):
            return data
    except (json.JSONDecodeError, OSError, IOError) as exc:
        logger.debug("Failed to read Gemini OAuth credentials: %s", exc)
    return None


def clear_credentials() -> bool:
    """Remove stored Gemini OAuth credentials. Returns True if file existed."""
    if _OAUTH_FILE.exists():
        _OAUTH_FILE.unlink(missing_ok=True)
        return True
    return False


# ---------------------------------------------------------------------------
# Localhost callback server
# ---------------------------------------------------------------------------

class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler to capture the OAuth callback from Google."""

    auth_code: Optional[str] = None
    error: Optional[str] = None

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "error" in params:
            _OAuthCallbackHandler.error = params["error"][0]
            self._respond("Authorization failed. You can close this tab.")
            return

        code = params.get("code", [None])[0]
        if code:
            _OAuthCallbackHandler.auth_code = code
            self._respond(
                "Authorization successful! You can close this tab and return to Hermes."
            )
        else:
            _OAuthCallbackHandler.error = "no_code"
            self._respond("No authorization code received. Please try again.")

    def _respond(self, message: str):
        html = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<title>Hermes — Google Authorization</title>"
            "<style>body{font-family:system-ui,sans-serif;display:flex;"
            "justify-content:center;align-items:center;min-height:80vh;"
            "background:#f8f9fa;margin:0}div{text-align:center;padding:2rem;"
            "background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.1)}"
            "h2{margin:0 0 .5rem}</style></head><body><div>"
            f"<h2>Hermes Agent</h2><p>{message}</p></div></body></html>"
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def log_message(self, format, *args):  # noqa: A002
        """Silence default stderr logging."""
        pass


def _wait_for_callback(timeout: float = 120.0) -> Optional[str]:
    """Start a localhost server and wait for the OAuth callback.

    Returns the authorization code, or None on timeout/error.
    """
    _OAuthCallbackHandler.auth_code = None
    _OAuthCallbackHandler.error = None

    server = HTTPServer(("127.0.0.1", _REDIRECT_PORT), _OAuthCallbackHandler)
    server.timeout = timeout

    def _serve():
        while _OAuthCallbackHandler.auth_code is None and _OAuthCallbackHandler.error is None:
            server.handle_request()

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    try:
        server.server_close()
    except Exception:
        pass

    if _OAuthCallbackHandler.error:
        logger.error("Google OAuth error: %s", _OAuthCallbackHandler.error)
        return None
    return _OAuthCallbackHandler.auth_code


# ---------------------------------------------------------------------------
# Token exchange
# ---------------------------------------------------------------------------

def exchange_code(
    code: str,
    verifier: str,
    *,
    client_id: str = "",
    client_secret: str = "",
) -> Optional[Dict[str, Any]]:
    """Exchange authorization code for tokens via Google's token endpoint.

    Returns dict with access_token, refresh_token, expires_in, etc.
    or None on failure.
    """
    import urllib.request

    client_id = client_id or _get_client_id()
    client_secret = client_secret or _get_client_secret()

    payload = urlencode({
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": _REDIRECT_URI,
        "code_verifier": verifier,
    }).encode()

    req = urllib.request.Request(
        GOOGLE_TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        logger.error("Gemini token exchange failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------

def refresh_access_token(
    refresh_token: str,
    *,
    client_id: str = "",
    client_secret: str = "",
) -> Optional[Dict[str, Any]]:
    """Refresh the access token using a stored refresh_token.

    Returns dict with new access_token, expires_in, etc. or None.
    """
    import urllib.request

    client_id = client_id or _get_client_id()
    client_secret = client_secret or _get_client_secret()

    payload = urlencode({
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }).encode()

    req = urllib.request.Request(
        GOOGLE_TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        logger.error("Gemini token refresh failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# get_valid_access_token — the main entry point for callers
# ---------------------------------------------------------------------------

def get_valid_access_token() -> Optional[str]:
    """Return a valid access token, refreshing if needed.

    Reads stored credentials, checks expiry, refreshes if within 5 minutes
    of expiration, persists updated tokens, and returns the access_token.
    Returns None if no credentials exist or refresh fails.
    """
    creds = load_credentials()
    if not creds:
        return None

    access_token = creds.get("access_token", "")
    refresh_token = creds.get("refresh_token", "")
    expires_at = creds.get("expires_at", 0)

    now = time.time()
    if access_token and expires_at > now + _REFRESH_MARGIN:
        return access_token

    # Need refresh
    if not refresh_token:
        logger.warning("Gemini OAuth access token expired and no refresh token available.")
        return None

    result = refresh_access_token(
        refresh_token,
        client_id=creds.get("client_id", ""),
        client_secret=creds.get("client_secret", ""),
    )
    if not result or "access_token" not in result:
        logger.error("Gemini token refresh returned no access_token")
        return None

    # Update stored credentials
    creds["access_token"] = result["access_token"]
    creds["expires_at"] = now + result.get("expires_in", 3600)
    # Google may issue a new refresh_token (rotation)
    if result.get("refresh_token"):
        creds["refresh_token"] = result["refresh_token"]
    save_credentials(creds)

    return result["access_token"]


# ---------------------------------------------------------------------------
# Full OAuth login flow
# ---------------------------------------------------------------------------

def run_google_oauth_login(
    *,
    client_id: str = "",
    client_secret: str = "",
    open_browser: bool = True,
) -> Optional[Dict[str, Any]]:
    """Run the full Google OAuth PKCE flow.

    Opens a browser for authorization, captures the callback on localhost,
    exchanges the code for tokens, and returns credential dict suitable for
    ``save_credentials()``.

    Returns dict with: access_token, refresh_token, expires_at, client_id,
    client_secret, email (if available). Returns None on failure/cancel.
    """
    import webbrowser

    client_id = client_id or _get_client_id()
    client_secret = client_secret or _get_client_secret()

    if not client_id:
        print("  ✗ Gemini OAuth is not yet configured (missing client_id).")
        print("    This feature requires a GCP OAuth client to be registered by the project.")
        print("    In the meantime, use an API key from https://aistudio.google.com/apikey")
        return None

    verifier, challenge = _generate_pkce()

    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": _REDIRECT_URI,
        "scope": GOOGLE_OAUTH_SCOPES,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",  # request refresh_token
        "prompt": "consent",  # force consent to always get refresh_token
    }

    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    print()
    print("  Authorize Hermes with your Google account.")
    print()
    print("  ╭─ Google Authorization ──────────────────────────────╮")
    print("  │                                                     │")
    print("  │  A browser window will open for you to sign in.     │")
    print("  │  If it doesn't, copy the URL below into a browser.  │")
    print("  ╰─────────────────────────────────────────────────────╯")
    print()
    print(f"  {auth_url}")
    print()

    if open_browser:
        try:
            webbrowser.open(auth_url)
            print("  (Browser opened automatically)")
        except Exception:
            pass

    print()
    print("  Waiting for authorization...")

    code = _wait_for_callback(timeout=120.0)

    if not code:
        # Fallback: manual paste for headless environments
        print()
        print("  Localhost callback not received. Paste the full callback URL")
        print("  or authorization code below (or press Enter to cancel):")
        print()
        try:
            raw = input("  Code/URL: ").strip()
        except (KeyboardInterrupt, EOFError):
            return None

        if not raw:
            return None

        # Handle pasted full URL
        if raw.startswith("http"):
            parsed = parse_qs(urlparse(raw).query)
            code = parsed.get("code", [None])[0]
        else:
            code = raw

        if not code:
            print("  No authorization code found.")
            return None

    # Exchange code for tokens
    result = exchange_code(code, verifier, client_id=client_id, client_secret=client_secret)
    if not result or "access_token" not in result:
        print("  ✗ Token exchange failed.")
        return None

    now = time.time()
    expires_in = result.get("expires_in", 3600)

    # Try to fetch user email for labeling
    email = _fetch_user_email(result["access_token"])

    creds = {
        "client_id": client_id,
        "client_secret": client_secret,
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token", ""),
        "expires_at": now + expires_in,
        "email": email or "",
    }

    print(f"  ✓ Authorized{f' as {email}' if email else ''}.")
    return creds


def _fetch_user_email(access_token: str) -> Optional[str]:
    """Fetch the authenticated user's email from Google userinfo endpoint."""
    import urllib.request

    req = urllib.request.Request(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data.get("email")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# High-level login-and-save (convenience for CLI)
# ---------------------------------------------------------------------------

def run_gemini_oauth_login_and_save(**kwargs) -> Optional[Dict[str, Any]]:
    """Run OAuth flow and persist credentials. Returns creds dict or None."""
    creds = run_google_oauth_login(**kwargs)
    if creds:
        save_credentials(creds)
    return creds


# ---------------------------------------------------------------------------
# Pure login for credential pool (returns dict compatible with PooledCredential)
# ---------------------------------------------------------------------------

def run_gemini_oauth_login_pure(**kwargs) -> Optional[Dict[str, Any]]:
    """Run OAuth flow and return credentials without persisting.

    Returns dict with: access_token, refresh_token, expires_at_ms.
    Compatible with the credential pool system in auth_commands.py.
    """
    creds = run_google_oauth_login(**kwargs)
    if not creds:
        return None

    return {
        "access_token": creds["access_token"],
        "refresh_token": creds.get("refresh_token", ""),
        "expires_at_ms": int(creds.get("expires_at", time.time() + 3600) * 1000),
    }
