"""Proton Pass CLI integration.

Hermes pulls API keys from Proton Pass at process startup so they don't
have to live in plaintext in ``~/.hermes/.env``.

Design summary
--------------

* The ``pass-cli`` binary is auto-installed via the official install
  script on first use.
* The access token is stored in ``~/.hermes/.env`` as
  ``PROTON_PASS_ACCESS_TOKEN``.  This is the one bootstrap secret.
* Pulling secrets uses two CLI calls per item:
  1. ``pass-cli item list <vault_name> --output json`` to enumerate.
  2. ``pass-cli item view --vault-name <v> --item-title <t>
     --field password --output json`` for each item.
* Convention: item title = env-var name, password field = value.
* Failures NEVER block startup.

References:
- https://protonpass.github.io/pass-cli/
- https://proton.me/blog/pass-access-tokens
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_PASSCLI_DOWNLOAD_TIMEOUT = 60
_PASSCLI_RUN_TIMEOUT = 30
_PASSCLI_LIST_TIMEOUT = 15
_PASSCLI_VIEW_TIMEOUT = 10

# In-process cache so repeated fetches within one process don't re-run
# the N+1 subprocess calls.
_CacheKey = Tuple[str, str]  # (token_fingerprint, vault_name)
_CACHE: Dict[_CacheKey, "_CachedFetch"] = {}


@dataclass
class _CachedFetch:
    secrets: Dict[str, str]
    fetched_at: float

    def is_fresh(self, ttl: float) -> bool:
        return ttl > 0 and (time.time() - self.fetched_at) < ttl


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass
class FetchResult:
    """Outcome of a single Proton Pass pull."""

    secrets: Dict[str, str] = field(default_factory=dict)
    applied: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None
    binary_path: Optional[Path] = None

    @property
    def ok(self) -> bool:
        return self.error is None


# ---------------------------------------------------------------------------
# Binary discovery + install
# ---------------------------------------------------------------------------


def _hermes_bin_dir() -> Path:
    from hermes_constants import get_hermes_home
    return get_hermes_home() / "bin"


def find_passcli(*, install_if_missing: bool = False) -> Optional[Path]:
    """Return a path to a usable ``pass-cli`` binary, or None."""
    managed = _hermes_bin_dir() / "pass-cli"
    if managed.exists() and os.access(managed, os.X_OK):
        return managed

    system = shutil.which("pass-cli")
    if system:
        return Path(system)

    if install_if_missing:
        try:
            return install_passcli()
        except Exception as exc:  # noqa: BLE001
            logger.warning("pass-cli auto-install failed: %s", exc)
            return None
    return None


def install_passcli(*, force: bool = False) -> Path:
    """Install pass-cli via the official script.  Returns the binary path."""
    bin_dir = _hermes_bin_dir()
    bin_dir.mkdir(parents=True, exist_ok=True)
    target = bin_dir / "pass-cli"

    if target.exists() and not force:
        return target

    with tempfile.TemporaryDirectory(prefix="hermes-pp-") as tmpdir:
        script = Path(tmpdir) / "install.sh"
        _http_download("https://proton.me/download/pass-cli/install.sh", script)

        env = os.environ.copy()
        env["PREFIX"] = str(bin_dir)
        proc = subprocess.run(  # noqa: S603
            ["bash", str(script)],
            env=env, capture_output=True, text=True,
            timeout=_PASSCLI_DOWNLOAD_TIMEOUT,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()[:300]
            raise RuntimeError(f"pass-cli install failed: {err}")

    # The script may put the binary in bin_dir/bin/.
    candidates = list(bin_dir.rglob("pass-cli"))
    if not candidates:
        raise RuntimeError(f"pass-cli install completed but binary not found in {bin_dir}")
    installed = candidates[0]
    if installed != target:
        shutil.move(str(installed), str(target))
        for d in bin_dir.glob("bin"):
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)

    logger.info("Installed pass-cli at %s", target)
    return target


def _http_download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "hermes-agent"})
    try:
        with urllib.request.urlopen(req, timeout=_PASSCLI_DOWNLOAD_TIMEOUT) as resp:  # noqa: S310
            with open(dest, "wb") as f:
                shutil.copyfileobj(resp, f)
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to download {url}: {exc}") from exc


# ---------------------------------------------------------------------------
# Core fetch
# ---------------------------------------------------------------------------


def _run_passcli(
    passcli: Path, args: List[str], *,
    access_token: str, timeout: int = _PASSCLI_RUN_TIMEOUT,
    agent_reason: Optional[str] = None,
) -> subprocess.CompletedProcess:
    """Run a pass-cli command with the PAT set."""
    cmd = [str(passcli)] + args
    env = os.environ.copy()
    env["PROTON_PASS_PERSONAL_ACCESS_TOKEN"] = access_token
    env["PROTON_PASS_DISABLE_TELEMETRY"] = "1"
    env.setdefault("PROTON_PASS_KEY_PROVIDER", "fs")
    env.setdefault("NO_COLOR", "1")
    if agent_reason:
        env["PROTON_PASS_AGENT_REASON"] = agent_reason
    try:
        return subprocess.run(  # noqa: S603
            cmd, env=env, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"pass-cli timed out after {timeout}s") from exc
    except OSError as exc:
        raise RuntimeError(f"Failed to invoke pass-cli: {exc}") from exc


def _view_item_field(
    passcli: Path, access_token: str, vault_name: str,
    item_title: str, field_name: str,
) -> Optional[str]:
    """View a single field of an item.  Returns the value or None."""
    proc = _run_passcli(
        passcli,
        ["item", "view", "--vault-name", vault_name,
         "--item-title", item_title, "--field", field_name, "--output", "json"],
        access_token=access_token, timeout=_PASSCLI_VIEW_TIMEOUT,
        agent_reason=f"Hermes startup: read {item_title}",
    )
    if proc.returncode != 0:
        return None

    raw = proc.stdout.strip()
    if not raw:
        return None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw  # plain string value

    if isinstance(payload, dict):
        return payload.get("value") or payload.get("password") or payload.get(field_name)
    return str(payload) if payload else None


def _is_valid_env_name(name: str) -> bool:
    if not name:
        return False
    if not (name[0].isalpha() or name[0] == "_"):
        return False
    return all(c.isalnum() or c == "_" for c in name)


def fetch_protonpass_secrets(
    *, access_token: str, vault_name: str = "Hermes",
    binary: Optional[Path] = None, cache_ttl_seconds: float = 300,
    use_cache: bool = True, **_kwargs: object,
) -> Tuple[Dict[str, str], List[str]]:
    """Pull secrets from Proton Pass.  Returns ``(secrets, warnings)``."""
    if not access_token:
        raise RuntimeError("Proton Pass access token is empty")
    if not vault_name:
        raise RuntimeError("Proton Pass vault_name is empty")

    cache_key = (hashlib.sha256(access_token.encode()).hexdigest()[:16], vault_name)
    if use_cache:
        cached = _CACHE.get(cache_key)
        if cached and cached.is_fresh(cache_ttl_seconds):
            return cached.secrets, []

    passcli = binary or find_passcli(install_if_missing=True)
    if passcli is None:
        raise RuntimeError(
            "pass-cli not found. Install manually from "
            "https://protonpass.github.io/pass-cli/ or run "
            "`hermes secrets protonpass setup`."
        )

    # List items in the vault.
    proc = _run_passcli(
        passcli, ["item", "list", vault_name, "--output", "json"],
        access_token=access_token, timeout=_PASSCLI_LIST_TIMEOUT,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip().replace("\x1b", "")
        raise RuntimeError(f"pass-cli item list failed: {err[:200]}")

    raw = proc.stdout.strip()
    if not raw:
        return {}, [f"No items found in vault '{vault_name}'"]

    try:
        items = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"pass-cli returned non-JSON: {exc}") from exc

    if not isinstance(items, list):
        raise RuntimeError(f"Unexpected response shape: {type(items).__name__}")

    secrets: Dict[str, str] = {}
    warnings: List[str] = []

    for item in items:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("Title")
        if not title or not isinstance(title, str):
            continue
        if not _is_valid_env_name(title):
            warnings.append(f"Skipping {title!r}: not a valid env-var name")
            continue

        value = _view_item_field(passcli, access_token, vault_name, title, "password")
        if value is None:
            warnings.append(f"Could not read password for {title!r}")
            continue
        secrets[title] = value

    if use_cache:
        _CACHE[cache_key] = _CachedFetch(secrets=secrets, fetched_at=time.time())

    return secrets, warnings


# ---------------------------------------------------------------------------
# Public entry point -- called from hermes_cli.env_loader
# ---------------------------------------------------------------------------


def apply_protonpass_secrets(
    *, enabled: bool,
    access_token_env: str = "PROTON_PASS_ACCESS_TOKEN",
    vault_name: str = "Hermes",
    override_existing: bool = False,
    cache_ttl_seconds: float = 300,
    auto_install: bool = True,
    home_path: Optional[Path] = None,
    **_kwargs: object,
) -> FetchResult:
    """Pull secrets from Proton Pass and set them on ``os.environ``."""
    result = FetchResult()
    if not enabled:
        return result

    access_token = os.environ.get(access_token_env, "").strip()
    if not access_token:
        result.error = (
            f"secrets.protonpass.enabled is true but {access_token_env} is "
            "not set.  Run `hermes secrets protonpass setup`."
        )
        return result

    if not vault_name:
        result.error = "secrets.protonpass.vault_name is empty."
        return result

    binary = find_passcli(install_if_missing=auto_install)
    result.binary_path = binary
    if binary is None:
        result.error = (
            "pass-cli not found. Run `hermes secrets protonpass setup`."
        )
        return result

    try:
        secrets, warnings = fetch_protonpass_secrets(
            access_token=access_token, vault_name=vault_name,
            binary=binary, cache_ttl_seconds=cache_ttl_seconds,
        )
    except RuntimeError as exc:
        result.error = str(exc)
        return result

    result.secrets = secrets
    result.warnings.extend(warnings)

    for key, value in secrets.items():
        if key == access_token_env:
            result.skipped.append(key)
            continue
        if not override_existing and os.environ.get(key):
            result.skipped.append(key)
            continue
        os.environ[key] = value
        result.applied.append(key)

    return result


def _reset_cache_for_tests(**_kw: object) -> None:
    """Test hook: clear in-process cache."""
    _CACHE.clear()
