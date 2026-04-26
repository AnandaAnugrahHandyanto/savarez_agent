#!/usr/bin/env python3
"""Bridge between Hermes OAuth token and gws CLI.

Refreshes the token if expired, then executes gws with the valid access token.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure sibling modules (_hermes_home) are importable when run standalone.
_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _hermes_home import get_hermes_home


def get_token_path() -> Path:
    return get_hermes_home() / "google_token.json"


def _load_resource_ownership_policy() -> dict:
    try:
        import yaml
    except Exception:
        return {}
    try:
        cfg_path = get_hermes_home() / "config.yaml"
        if not cfg_path.exists():
            return {}
        data = yaml.safe_load(cfg_path.read_text()) or {}
        policy = data.get("resource_ownership") or {}
        return policy if isinstance(policy, dict) else {}
    except Exception:
        return {}


def _entry_platform_ids(entry: dict, platform: str) -> set[str]:
    if not isinstance(entry, dict):
        return set()
    values: set[str] = set()
    for key in ("platforms", "user_ids"):
        raw_map = entry.get(key)
        raw = raw_map.get(platform) if isinstance(raw_map, dict) else None
        if isinstance(raw, (list, tuple, set)):
            values.update(str(v) for v in raw if str(v).strip())
        elif raw:
            values.add(str(raw))
    return values


def _guard_profile_google_token_for_requester():
    platform = os.getenv("HERMES_SESSION_PLATFORM", "").strip()
    if not platform:
        return
    source_ids = {
        v for v in (
            os.getenv("HERMES_SESSION_USER_ID", "").strip(),
            os.getenv("HERMES_SESSION_CHAT_ID", "").strip(),
        ) if v
    }
    policy = _load_resource_ownership_policy()
    owner = policy.get("owner") if isinstance(policy.get("owner"), dict) else {}
    owner_ids = _entry_platform_ids(owner, platform)
    if owner_ids and source_ids & owner_ids:
        return
    owner_name = owner.get("name") or "the agent owner"
    print(
        "Blocked: requester-owned Google authorization is required; "
        f"not using {owner_name}'s Google token by fallback.",
        file=sys.stderr,
    )
    sys.exit(2)


def _normalize_authorized_user_payload(payload: dict) -> dict:
    normalized = dict(payload)
    if not normalized.get("type"):
        normalized["type"] = "authorized_user"
    return normalized


def refresh_token(token_data: dict) -> dict:
    """Refresh the access token using the refresh token."""
    import urllib.error
    import urllib.parse
    import urllib.request

    required_keys = ["client_id", "client_secret", "refresh_token", "token_uri"]
    missing = [k for k in required_keys if k not in token_data]
    if missing:
        print(f"ERROR: google_token.json is missing required fields: {', '.join(missing)}", file=sys.stderr)
        print("Please re-authenticate by running the Google Workspace setup script.", file=sys.stderr)
        sys.exit(1)

    params = urllib.parse.urlencode({
        "client_id": token_data["client_id"],
        "client_secret": token_data["client_secret"],
        "refresh_token": token_data["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()

    req = urllib.request.Request(token_data["token_uri"], data=params)
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"ERROR: Token refresh failed (HTTP {e.code}): {body}", file=sys.stderr)
        print("Re-run setup.py to re-authenticate.", file=sys.stderr)
        sys.exit(1)

    token_data["token"] = result["access_token"]
    token_data["expiry"] = datetime.fromtimestamp(
        datetime.now(timezone.utc).timestamp() + result["expires_in"],
        tz=timezone.utc,
    ).isoformat()

    get_token_path().write_text(
        json.dumps(_normalize_authorized_user_payload(token_data), indent=2)
    )
    return token_data


def get_valid_token() -> str:
    """Return a valid access token, refreshing if needed."""
    _guard_profile_google_token_for_requester()
    token_path = get_token_path()
    if not token_path.exists():
        print("ERROR: No Google token found. Run setup.py --auth-url first.", file=sys.stderr)
        sys.exit(1)

    token_data = json.loads(token_path.read_text())

    expiry = token_data.get("expiry", "")
    if expiry:
        exp_dt = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if now >= exp_dt:
            token_data = refresh_token(token_data)

    return token_data["token"]


def main():
    """Refresh token if needed, then exec gws with remaining args."""
    if len(sys.argv) < 2:
        print("Usage: gws_bridge.py <gws args...>", file=sys.stderr)
        sys.exit(1)

    access_token = get_valid_token()
    env = os.environ.copy()
    env["GOOGLE_WORKSPACE_CLI_TOKEN"] = access_token

    result = subprocess.run(["gws"] + sys.argv[1:], env=env)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
