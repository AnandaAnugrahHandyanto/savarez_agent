"""Claude Code credential discovery + write-back (macOS Keychain + file).

Reads ``Claude Code-credentials`` entries from the macOS login Keychain (the
primary storage for Claude Code on Darwin) and falls back to the JSON file
at ``~/.claude/.credentials.json`` on every platform.

Multi-account support: on Darwin, Claude Code stores additional accounts
under service names like ``Claude Code-credentials-<hex>``.  We detect every
such entry using ``security dump-keychain`` and return them as separate
``ClaudeAccount`` records for the account switcher UI.

Write-back: Anthropic rotates refresh tokens on use, so whenever we refresh
we must persist the new token to the SAME source it came from (Keychain or
file).  ``write_credentials`` routes the write based on ``source``.

Mirrors ``griffinmartin/opencode-claude-auth/src/keychain.ts``.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Service-name constants (must match Claude Code exactly) ────────────
_PRIMARY_SERVICE = "Claude Code-credentials"
# Additional-account entries:  Claude Code-credentials-<hex>
_EXTRA_SERVICE_RE = re.compile(
    r'"Claude Code-credentials(?:-[0-9a-f]+)?"'
)
# When dump-keychain encodes a service name longer than ~56 chars it can be
# split as ``"service"<blob>`` — grab both forms.
_SERVICE_ATTR_RE = re.compile(
    r'0x00000007 <blob>="(Claude Code-credentials(?:-[0-9a-f]+)?)"'
)
_ACCT_ATTR_RE = re.compile(r'"acct"<blob>="([^"]*)"')

_FILE_PATH = Path.home() / ".claude" / ".credentials.json"

# Source tag used in PooledCredential to identify where a Keychain/file entry came from
SOURCE_FILE = "file"
SOURCE_KEYCHAIN_PREFIX = "keychain:"  # e.g. "keychain:Claude Code-credentials"


@dataclass
class ClaudeCredentials:
    """Normalized Claude Code OAuth creds (wrapped or unwrapped JSON parsed)."""
    access_token: str
    refresh_token: str
    expires_at: int  # epoch milliseconds
    subscription_type: Optional[str] = None
    scopes: Optional[List[str]] = None


@dataclass
class ClaudeAccount:
    """A single Claude Code account discovered via Keychain or file fallback."""
    label: str                     # user-facing label ("Claude Pro", "Claude Max 2", …)
    source: str                    # "file" or "keychain:<service>"
    credentials: ClaudeCredentials
    account_name: Optional[str] = None  # Keychain "acct" attribute (macOS username)
    raw_blob: Dict = field(default_factory=dict)  # full parsed JSON for write-back


def _is_darwin() -> bool:
    return platform.system() == "Darwin"


def _parse_credentials_blob(raw: str) -> Optional[ClaudeCredentials]:
    """Parse Claude Code credential JSON, accepting both wrapped and flat shapes.

    Keychain entries are wrapped as ``{"claudeAiOauth": {...}}``; file
    fallback is typically the same wrapper but may be flat.  Entries that
    contain only ``mcpOAuth`` (MCP-server creds, not user creds) return None.
    """
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None

    data = parsed.get("claudeAiOauth") if isinstance(parsed.get("claudeAiOauth"), dict) else parsed
    if not isinstance(data, dict):
        return None

    # Skip MCP-only entries
    if parsed.get("mcpOAuth") and not data.get("accessToken"):
        return None

    access = data.get("accessToken")
    refresh = data.get("refreshToken")
    expires = data.get("expiresAt")
    if not isinstance(access, str) or not isinstance(refresh, str):
        return None
    if not isinstance(expires, int):
        try:
            expires = int(expires or 0)
        except (TypeError, ValueError):
            return None

    scopes_val = data.get("scopes")
    scopes = [s for s in scopes_val if isinstance(s, str)] if isinstance(scopes_val, list) else None
    sub_type = data.get("subscriptionType") if isinstance(data.get("subscriptionType"), str) else None

    return ClaudeCredentials(
        access_token=access,
        refresh_token=refresh,
        expires_at=expires,
        subscription_type=sub_type,
        scopes=scopes,
    )


# ── macOS Keychain low-level helpers ───────────────────────────────────

def _security(*args: str, input_data: Optional[str] = None, timeout: float = 5.0) -> subprocess.CompletedProcess:
    """Run /usr/bin/security with the given args, capturing output."""
    return subprocess.run(
        ["/usr/bin/security", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        input=input_data,
    )


def _find_keychain_services() -> List[str]:
    """Return every ``Claude Code-credentials[-<hex>]`` service name in the login keychain."""
    if not _is_darwin():
        return []
    try:
        result = _security("dump-keychain", timeout=10.0)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("security dump-keychain failed: %s", exc)
        return []
    if result.returncode != 0:
        return []
    services = set()
    for match in _SERVICE_ATTR_RE.finditer(result.stdout):
        services.add(match.group(1))
    # Also match the older form without explicit attr key, in case the
    # layout varies by macOS version.
    for match in _EXTRA_SERVICE_RE.finditer(result.stdout):
        quoted = match.group(0)
        services.add(quoted.strip('"'))
    return sorted(services)


def _find_account_name(service: str) -> Optional[str]:
    """Find the ``acct`` attribute for a given Keychain service.

    Claude Code writes entries with ``-a <macOS_username>``.  We need this
    value to update-in-place (``security add-generic-password -U``) rather
    than create a duplicate entry.
    """
    if not _is_darwin():
        return None
    try:
        # Without -w, the command prints the entry's attributes but not the password
        result = _security("find-generic-password", "-s", service, timeout=3.0)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    m = _ACCT_ATTR_RE.search(result.stdout)
    if m:
        return m.group(1)
    return None


def _read_keychain_entry(service: str) -> Optional[str]:
    """Read the password (JSON blob) for a given Keychain service."""
    if not _is_darwin():
        return None
    try:
        result = _security("find-generic-password", "-s", service, "-w", timeout=3.0)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _write_keychain_entry(service: str, account: str, blob: str) -> bool:
    """Update (or create) a Keychain entry.  Uses ``-U`` for idempotent update."""
    if not _is_darwin():
        return False
    try:
        result = _security(
            "add-generic-password",
            "-s", service,
            "-a", account,
            "-w", blob,
            "-U",  # update if exists — critical, no duplicate entries
            timeout=5.0,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("Keychain write failed: %s", exc)
        return False
    return result.returncode == 0


# ── File fallback ──────────────────────────────────────────────────────

def _read_file_entry() -> Optional[str]:
    """Read ``~/.claude/.credentials.json`` as text, or None if missing."""
    if _FILE_PATH.exists():
        try:
            return _FILE_PATH.read_text(encoding="utf-8")
        except OSError as exc:
            logger.debug("File read failed: %s", exc)
    return None


def _write_file_entry(blob: str) -> bool:
    """Write ``~/.claude/.credentials.json`` with 0600 perms."""
    try:
        _FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _FILE_PATH.write_text(blob, encoding="utf-8")
        try:
            _FILE_PATH.chmod(0o600)
        except OSError:
            pass
    except OSError as exc:
        logger.debug("File write failed: %s", exc)
        return False
    return True


# ── Label formatting ───────────────────────────────────────────────────

def _label_for_subscription(sub_type: Optional[str]) -> str:
    if not sub_type:
        return "Claude"
    sub = sub_type.strip().lower()
    if sub in ("pro",):
        return "Claude Pro"
    if sub in ("max", "max5x", "max20x"):
        return "Claude Max"
    return f"Claude {sub_type}"


def _build_labels(accounts: List[ClaudeAccount]) -> None:
    """Disambiguate duplicate subscription labels with numeric suffixes."""
    seen: Dict[str, int] = {}
    for acct in accounts:
        base = acct.label
        seen[base] = seen.get(base, 0) + 1
    counters: Dict[str, int] = {}
    for acct in accounts:
        base = acct.label
        if seen[base] > 1:
            counters[base] = counters.get(base, 0) + 1
            acct.label = f"{base} {counters[base]}"


# ── Public API ─────────────────────────────────────────────────────────

def read_all_accounts() -> List[ClaudeAccount]:
    """Discover every Claude Code account on the system.

    Order:
      1. macOS Keychain entries (``Claude Code-credentials[-<hex>]``).
      2. File fallback at ``~/.claude/.credentials.json`` (same file is
         used by Claude Code on Linux/Windows).

    An account discovered in both Keychain and file is deduplicated by
    access-token prefix.  Returns accounts in the order: primary Keychain
    first, then extras, then file-only.
    """
    accounts: List[ClaudeAccount] = []
    seen_tokens = set()

    if _is_darwin():
        services = _find_keychain_services()
        for service in services:
            raw = _read_keychain_entry(service)
            if not raw:
                continue
            creds = _parse_credentials_blob(raw)
            if not creds:
                continue
            token_prefix = creds.access_token[:32]
            if token_prefix in seen_tokens:
                continue
            seen_tokens.add(token_prefix)
            try:
                raw_blob = json.loads(raw)
            except json.JSONDecodeError:
                raw_blob = {"claudeAiOauth": creds.__dict__}
            accounts.append(
                ClaudeAccount(
                    label=_label_for_subscription(creds.subscription_type),
                    source=f"{SOURCE_KEYCHAIN_PREFIX}{service}",
                    credentials=creds,
                    account_name=_find_account_name(service),
                    raw_blob=raw_blob,
                )
            )

    raw_file = _read_file_entry()
    if raw_file:
        creds_f = _parse_credentials_blob(raw_file)
        if creds_f and creds_f.access_token[:32] not in seen_tokens:
            seen_tokens.add(creds_f.access_token[:32])
            try:
                raw_blob = json.loads(raw_file)
            except json.JSONDecodeError:
                raw_blob = {"claudeAiOauth": creds_f.__dict__}
            accounts.append(
                ClaudeAccount(
                    label=_label_for_subscription(creds_f.subscription_type),
                    source=SOURCE_FILE,
                    credentials=creds_f,
                    account_name=None,
                    raw_blob=raw_blob,
                )
            )

    _build_labels(accounts)
    return accounts


def read_primary_account() -> Optional[ClaudeAccount]:
    """Return the first discovered account (Keychain wins over file)."""
    accounts = read_all_accounts()
    return accounts[0] if accounts else None


def read_selected_account(source_path: Optional[Path] = None) -> Optional[ClaudeAccount]:
    """Return the account matching the user's persisted selection, if any.

    Reads the selected account ``source`` string from ``source_path`` (defaults
    to ``<HERMES_HOME>/claude_account_source.txt``).  If the file is missing,
    unreadable, or points to a no-longer-present account, falls back to the
    first discovered account.  Returns None if no accounts exist.
    """
    accounts = read_all_accounts()
    if not accounts:
        return None

    if source_path is None:
        try:
            from hermes_constants import get_hermes_home
            source_path = get_hermes_home() / "claude_account_source.txt"
        except Exception:
            source_path = None

    persisted: Optional[str] = None
    if source_path is not None:
        try:
            if source_path.exists():
                persisted = source_path.read_text(encoding="utf-8").strip() or None
        except OSError as exc:
            logger.debug("Failed to read selected-account file %s: %s", source_path, exc)

    if persisted:
        for acct in accounts:
            if acct.source == persisted:
                return acct

    return accounts[0]


def write_credentials(
    source: str,
    creds: ClaudeCredentials,
    *,
    raw_blob: Optional[Dict] = None,
    account_name: Optional[str] = None,
) -> bool:
    """Persist refreshed credentials back to their original source.

    ``source`` follows the format returned by :func:`read_all_accounts`:
    ``"file"`` or ``"keychain:<service>"``.
    """
    # Rebuild the wrapped JSON blob, preserving any extra fields from the
    # original entry (scopes, subscriptionType, etc.).
    blob_dict: Dict = dict(raw_blob or {})
    oauth: Dict = blob_dict.get("claudeAiOauth", {}) if isinstance(blob_dict.get("claudeAiOauth"), dict) else {}
    oauth["accessToken"] = creds.access_token
    oauth["refreshToken"] = creds.refresh_token
    oauth["expiresAt"] = creds.expires_at
    if creds.scopes is not None:
        oauth["scopes"] = list(creds.scopes)
    elif "scopes" not in oauth:
        # Claude Code ≥2.1.81 requires ``user:inference`` in scopes; preserve
        # whatever was there before refresh.
        pass
    if creds.subscription_type is not None:
        oauth["subscriptionType"] = creds.subscription_type
    blob_dict["claudeAiOauth"] = oauth
    blob = json.dumps(blob_dict, indent=2)

    if source == SOURCE_FILE:
        return _write_file_entry(blob)
    if source.startswith(SOURCE_KEYCHAIN_PREFIX):
        service = source[len(SOURCE_KEYCHAIN_PREFIX):]
        acct = account_name or _find_account_name(service) or os.getenv("USER", "hermes")
        return _write_keychain_entry(service, acct, blob)
    logger.debug("write_credentials: unknown source %s", source)
    return False


def find_account_by_access_token_prefix(prefix: str) -> Optional[ClaudeAccount]:
    """Locate the stored account that owns a given access-token prefix."""
    for acct in read_all_accounts():
        if acct.credentials.access_token.startswith(prefix):
            return acct
    return None
