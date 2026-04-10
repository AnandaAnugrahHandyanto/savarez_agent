"""GitHub Copilot authentication utilities.

Implements the OAuth device code flow used by the Copilot CLI and handles
token validation/exchange for the Copilot API.

Token type support (per GitHub docs):
  gho_          OAuth token           ✓  (default via copilot login)
  github_pat_   Fine-grained PAT      ✓  (needs Copilot Requests permission)
  ghu_          GitHub App token      ✓  (via environment variable)
  ghp_          Classic PAT           ✗  NOT SUPPORTED

Credential search order (matching Copilot CLI behaviour):
  1. COPILOT_GITHUB_TOKEN env var
  2. GH_TOKEN env var
  3. GITHUB_TOKEN env var
  4. gh auth token  CLI fallback
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# OAuth device code flow constants (VS Code Copilot OAuth App client ID —
# grants access to the full model catalog including internal-only models)
COPILOT_OAUTH_CLIENT_ID = "Iv1.b507a08c87ecfe98"
COPILOT_DEVICE_CODE_URL = "https://github.com/login/device/code"
COPILOT_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"

# Copilot API constants
COPILOT_TOKEN_EXCHANGE_URL = "https://api.github.com/copilot_internal/v2/token"
COPILOT_API_BASE_URL = "https://api.githubcopilot.com"
DEFAULT_COPILOT_API_BASE_URL = "https://api.individual.githubcopilot.com"

# Header constants — keep in sync with VS Code / Copilot CLI versions.
# Used by both token exchange and API request headers.
_EDITOR_VERSION = "vscode/1.104.1"
_EXCHANGE_USER_AGENT = "GitHubCopilotChat/0.26.7"

# Token type prefixes
_CLASSIC_PAT_PREFIX = "ghp_"
_SUPPORTED_PREFIXES = ("gho_", "github_pat_", "ghu_")

# Env var search order (matches Copilot CLI)
COPILOT_ENV_VARS = ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")

# Polling constants
_DEVICE_CODE_POLL_INTERVAL = 5  # seconds
_DEVICE_CODE_POLL_SAFETY_MARGIN = 3  # seconds


def validate_copilot_token(token: str) -> tuple[bool, str]:
    """Validate that a token is usable with the Copilot API.

    Returns (valid, message).
    """
    token = token.strip()
    if not token:
        return False, "Empty token"

    if token.startswith(_CLASSIC_PAT_PREFIX):
        return False, (
            "Classic Personal Access Tokens (ghp_*) are not supported by the "
            "Copilot API. Use one of:\n"
            "  → `copilot login` or `hermes model` to authenticate via OAuth\n"
            "  → A fine-grained PAT (github_pat_*) with Copilot Requests permission\n"
            "  → `gh auth login` with the default device code flow (produces gho_* tokens)"
        )

    return True, "OK"


def resolve_copilot_token(*, exchange: bool = True) -> tuple[str, str, Optional[str]]:
    """Resolve a GitHub token suitable for Copilot API use.

    When *exchange* is True (the default), the raw GitHub token is exchanged
    for a short-lived Copilot API JWT via ``/copilot_internal/v2/token``.
    This is required to access internal-access models (e.g. ``claude-opus-4.6-1m``).
    If the exchange fails, the raw token is returned as a fallback.

    Returns (token, source, base_url) where source describes where the token came from,
    and base_url is the derived Copilot API base URL (or None if not available).
    Raises ValueError if only a classic PAT is available.
    """
    raw_token = ""
    source = ""

    # 1. Check env vars in priority order
    for env_var in COPILOT_ENV_VARS:
        val = os.getenv(env_var, "").strip()
        if val:
            valid, msg = validate_copilot_token(val)
            if not valid:
                logger.warning(
                    "Token from %s is not supported: %s", env_var, msg
                )
                continue
            raw_token, source = val, env_var
            break

    # 2. Fall back to gh auth token
    if not raw_token:
        token = _try_gh_cli_token()
        if token:
            valid, msg = validate_copilot_token(token)
            if not valid:
                raise ValueError(
                    f"Token from `gh auth token` is a classic PAT (ghp_*). {msg}"
                )
            raw_token, source = token, "gh auth token"

    if not raw_token:
        return "", "", None

    # 3. Exchange raw token for Copilot API JWT
    if exchange:
        jwt, base_url = resolve_copilot_api_token(raw_token)
        return jwt, source, base_url

    return raw_token, source, None


def _gh_cli_candidates() -> list[str]:
    """Return candidate ``gh`` binary paths, including common Homebrew installs."""
    candidates: list[str] = []

    resolved = shutil.which("gh")
    if resolved:
        candidates.append(resolved)

    for candidate in (
        "/opt/homebrew/bin/gh",
        "/usr/local/bin/gh",
        str(Path.home() / ".local" / "bin" / "gh"),
    ):
        if candidate in candidates:
            continue
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            candidates.append(candidate)

    return candidates


def _try_gh_cli_token() -> Optional[str]:
    """Return a token from ``gh auth token`` when the GitHub CLI is available."""
    for gh_path in _gh_cli_candidates():
        try:
            result = subprocess.run(
                [gh_path, "auth", "token"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            logger.debug("gh CLI token lookup failed (%s): %s", gh_path, exc)
            continue
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return None


# ─── OAuth Device Code Flow ────────────────────────────────────────────────

def copilot_device_code_login(
    *,
    host: str = "github.com",
    timeout_seconds: float = 300,
) -> Optional[str]:
    """Run the GitHub OAuth device code flow for Copilot.

    Prints instructions for the user, polls for completion, and returns
    the OAuth access token on success, or None on failure/cancellation.

    This replicates the flow used by opencode and the Copilot CLI.
    """
    import urllib.request
    import urllib.parse

    domain = host.rstrip("/")
    device_code_url = f"https://{domain}/login/device/code"
    access_token_url = f"https://{domain}/login/oauth/access_token"

    # Step 1: Request device code
    data = urllib.parse.urlencode({
        "client_id": COPILOT_OAUTH_CLIENT_ID,
        "scope": "read:user",
    }).encode()

    req = urllib.request.Request(
        device_code_url,
        data=data,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "HermesAgent/1.0",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            device_data = json.loads(resp.read().decode())
    except Exception as exc:
        logger.error("Failed to initiate device authorization: %s", exc)
        print(f"  ✗ Failed to start device authorization: {exc}")
        return None

    verification_uri = device_data.get("verification_uri", "https://github.com/login/device")
    user_code = device_data.get("user_code", "")
    device_code = device_data.get("device_code", "")
    interval = max(device_data.get("interval", _DEVICE_CODE_POLL_INTERVAL), 1)

    if not device_code or not user_code:
        print("  ✗ GitHub did not return a device code.")
        return None

    # Step 2: Show instructions
    print()
    print(f"  Open this URL in your browser: {verification_uri}")
    print(f"  Enter this code: {user_code}")
    print()
    print("  Waiting for authorization...", end="", flush=True)

    # Step 3: Poll for completion
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        time.sleep(interval + _DEVICE_CODE_POLL_SAFETY_MARGIN)

        poll_data = urllib.parse.urlencode({
            "client_id": COPILOT_OAUTH_CLIENT_ID,
            "device_code": device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        }).encode()

        poll_req = urllib.request.Request(
            access_token_url,
            data=poll_data,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "HermesAgent/1.0",
            },
        )

        try:
            with urllib.request.urlopen(poll_req, timeout=10) as resp:
                result = json.loads(resp.read().decode())
        except Exception:
            print(".", end="", flush=True)
            continue

        if result.get("access_token"):
            print(" ✓")
            return result["access_token"]

        error = result.get("error", "")
        if error == "authorization_pending":
            print(".", end="", flush=True)
            continue
        elif error == "slow_down":
            # RFC 8628: add 5 seconds to polling interval
            server_interval = result.get("interval")
            if isinstance(server_interval, (int, float)) and server_interval > 0:
                interval = int(server_interval)
            else:
                interval += 5
            print(".", end="", flush=True)
            continue
        elif error == "expired_token":
            print()
            print("  ✗ Device code expired. Please try again.")
            return None
        elif error == "access_denied":
            print()
            print("  ✗ Authorization was denied.")
            return None
        elif error:
            print()
            print(f"  ✗ Authorization failed: {error}")
            return None

    print()
    print("  ✗ Timed out waiting for authorization.")
    return None


# ─── Copilot Token Exchange ────────────────────────────────────────────────

# Module-level cache for exchanged Copilot JWT tokens.
# Maps raw_token_fingerprint -> (jwt, expires_at_epoch, base_url).
_jwt_cache: dict[str, tuple[str, float, Optional[str]]] = {}
_JWT_REFRESH_MARGIN_SECONDS = 120  # refresh 2 min before expiry


def _token_fp(raw_token: str) -> str:
    """Short fingerprint of a raw token for cache keying (avoid storing full token)."""
    import hashlib
    return hashlib.sha256(raw_token.encode()).hexdigest()[:16]


def derive_copilot_base_url_from_token(token: str) -> Optional[str]:
    """Derive the Copilot API base URL from a proxy-ep field in the token.

    The exchanged Copilot token is a semicolon-separated string like
    ``tid=xxx;exp=xxx;proxy-ep=proxy.enterprise.githubcopilot.com;...``.
    This function extracts the ``proxy-ep`` value and converts it to an
    API base URL by replacing the leading ``proxy.`` with ``api.``.

    Returns ``https://{api_hostname}`` or ``None`` if proxy-ep is absent.
    """
    m = re.search(r'(?:^|;)\s*proxy-ep=([^;\s]+)', token)
    if not m:
        return None

    proxy_ep = m.group(1)

    # Strip https:// prefix if present
    if proxy_ep.startswith("https://"):
        hostname = proxy_ep[len("https://"):]
    elif proxy_ep.startswith("http://"):
        hostname = proxy_ep[len("http://"):]
    else:
        hostname = proxy_ep

    # Strip trailing slashes
    hostname = hostname.rstrip("/")

    # Replace leading "proxy." with "api."
    if hostname.startswith("proxy."):
        api_hostname = "api." + hostname[len("proxy."):]
    else:
        api_hostname = hostname

    return f"https://{api_hostname}"


def exchange_copilot_token(raw_token: str, *, timeout: float = 10.0) -> tuple[str, float, Optional[str]]:
    """Exchange a raw GitHub token for a short-lived Copilot API token.

    Calls ``GET https://api.github.com/copilot_internal/v2/token`` with
    ``Authorization: Bearer <raw_token>`` and returns ``(token, expires_at, base_url)``.

    The returned token is a semicolon-separated string (not a JWT) that may
    contain a ``proxy-ep`` field pointing to an enterprise endpoint.

    Results are cached in-process and reused until close to expiry.

    Raises ``ValueError`` on failure.
    """
    fp = _token_fp(raw_token)

    # Check cache first
    cached = _jwt_cache.get(fp)
    if cached:
        jwt, expires_at, base_url = cached
        if time.time() < expires_at - _JWT_REFRESH_MARGIN_SECONDS:
            return jwt, expires_at, base_url

    import urllib.request

    req = urllib.request.Request(
        COPILOT_TOKEN_EXCHANGE_URL,
        method="GET",
        headers={
            "Authorization": f"Bearer {raw_token}",
            "User-Agent": _EXCHANGE_USER_AGENT,
            "Accept": "application/json",
            "X-Github-Api-Version": "2025-04-01",
            "Editor-Version": _EDITOR_VERSION,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except Exception as exc:
        logger.debug("Copilot token exchange failed: %s", exc)
        raise ValueError(f"Copilot token exchange failed: {exc}") from exc

    jwt = data.get("token", "")
    expires_at = data.get("expires_at", 0)
    if not jwt:
        raise ValueError("Copilot token exchange returned empty token")

    # Convert expires_at to float if needed
    expires_at = float(expires_at) if expires_at else time.time() + 1800

    # Derive enterprise base URL from proxy-ep in the token
    base_url = derive_copilot_base_url_from_token(jwt)

    _jwt_cache[fp] = (jwt, expires_at, base_url)
    logger.debug(
        "Copilot token exchanged successfully, expires_at=%s, base_url=%s",
        expires_at,
        base_url,
    )
    return jwt, expires_at, base_url


def resolve_copilot_api_token(raw_token: str, *, timeout: float = 10.0) -> tuple[str, Optional[str]]:
    """Resolve a raw GitHub token to a Copilot API-ready token.

    Convenience wrapper around :func:`exchange_copilot_token` that returns
    ``(token, base_url)``. Falls back to ``(raw_token, None)`` on exchange failure
    (preserves existing behaviour for accounts that don't need exchange).
    """
    if not raw_token:
        return raw_token, None
    try:
        jwt, _, base_url = exchange_copilot_token(raw_token, timeout=timeout)
        return jwt, base_url
    except Exception as exc:
        logger.debug(
            "Copilot token exchange failed, falling back to raw token: %s", exc
        )
        return raw_token, None


# ─── Copilot API Headers ───────────────────────────────────────────────────

def copilot_request_headers(
    *,
    is_agent_turn: bool = True,
    is_vision: bool = False,
) -> dict[str, str]:
    """Build the standard headers for Copilot API requests.

    Replicates the header set used by opencode and the Copilot CLI.
    """
    headers: dict[str, str] = {
        "Editor-Version": _EDITOR_VERSION,
        "User-Agent": "HermesAgent/1.0",
        "Copilot-Integration-Id": "vscode-chat",
        "Openai-Intent": "conversation-edits",
        "x-initiator": "agent" if is_agent_turn else "user",
    }
    if is_vision:
        headers["Copilot-Vision-Request"] = "true"

    return headers
