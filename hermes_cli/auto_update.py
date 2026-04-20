"""
Auto-update functionality for Hermes Gateway.

Supports two modes:
- notify: Check for updates, notify user when available
- apply: Auto-apply after grace period when silent
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

_UPDATE_MANIFEST_FILE = ".update_manifest.json"
_HOME_CHANNEL_FILE = ".home_channel.json"

_HOURS_SECONDS = {
    "1h": 3600,
    "6h": 6 * 3600,
    "12h": 12 * 3600,
    "24h": 24 * 3600,
    "48h": 48 * 3600,
    "72h": 72 * 3600,
}


def _get_repo_dir() -> Optional[Path]:
    """Return the active Hermes git checkout, or None if not a git install."""
    hermes_home = get_hermes_home()
    repo_dir = hermes_home / "hermes-agent"
    if (repo_dir / ".git").exists():
        return repo_dir
    return None


def parse_check_interval(interval: str) -> Optional[int]:
    """Parse check_interval string to seconds.

    Supports:
    - Shorthand: "1h", "24h", etc. → seconds
    - Cron expression (5-part UTC): "0 * * * *" → check every hour

    Returns None if invalid.
    """
    interval = interval.strip()
    if interval in _HOURS_SECONDS:
        return _HOURS_SECONDS[interval]
    parts = interval.split()
    if len(parts) == 5:
        return None
    return None


class AutoUpdater:
    def __init__(self, config: Dict[str, Any]):
        self.enabled = config.get("enabled", False)
        self.mode = config.get("mode", "notify")
        self.check_interval_str = config.get("check_interval", "24h")
        self.grace_period_seconds = config.get("grace_period_seconds", 300)

        self.check_interval = parse_check_interval(self.check_interval_str)
        self._last_check_ts: Optional[float] = None
        self._last_update_available: bool = False

    def check_for_updates(self) -> Dict[str, Any]:
        """Check for available updates.

        Returns dict with:
        - available: bool
        - version: str (current version)
        - commits: int (commits behind)
        """
        from hermes_cli.banner import check_for_updates_uncached

        hermes_home = get_hermes_home()
        version = self._get_current_version()
        behind = check_for_updates_uncached()

        result = {
            "available": behind is not None and behind > 0,
            "version": version,
            "commits": behind or 0,
        }
        self._last_update_available = result["available"]
        self._last_check_ts = time.time()
        return result

    def _get_current_version(self) -> str:
        """Get current Hermes version."""
        try:
            result = subprocess.run(
                ["git", "describe", "--tags", "--always"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return "unknown"

    def _is_fork(self) -> bool:
        """Check if this is a fork (not the official repo)."""
        from hermes_cli.main import _is_fork

        repo_dir = _get_repo_dir()
        if not repo_dir:
            return False

        git_cmd = ["git"]
        try:
            result = subprocess.run(
                git_cmd + ["remote", "get-url", "origin"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                origin_url = result.stdout.strip()
                return _is_fork(origin_url) is not False
        except Exception:
            pass
        return False

    def should_apply(self) -> bool:
        """Check if update should be auto-applied.

        Returns False if:
        - Not enabled
        - Mode is "notify" (not "apply")
        - This is a fork
        - No updates available
        - Grace period hasn't passed
        """
        if not self.enabled:
            return False
        if self.mode != "apply":
            return False
        if self._is_fork():
            logger.warning("Auto-update skipped: running from a fork")
            return False
        if not self._last_update_available:
            return False

        if self._last_check_ts:
            elapsed = time.time() - self._last_check_ts
            if elapsed < self.grace_period_seconds:
                return False
        return True

    def apply_update(self) -> bool:
        """Apply the update via git pull and execv.

        Returns True if update started (does not return on success).
        """
        repo_dir = _get_repo_dir()
        if not repo_dir:
            logger.error("Cannot apply update: not a git install")
            return False

        try:
            subprocess.run(
                ["git", "fetch", "origin", "--quiet"],
                cwd=repo_dir,
                capture_output=True,
                timeout=30,
            )
            result = subprocess.run(
                ["git", "pull", "--ff-only", "origin", "main"],
                cwd=repo_dir,
                capture_output=True,
                timeout=60,
            )
            if result.returncode != 0:
                logger.error(f"git pull failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Update failed: {e}")
            return False

        manifest = {
            "version": self._get_current_version(),
            "timestamp": int(time.time()),
        }
        manifest_path = get_hermes_home() / _UPDATE_MANIFEST_FILE
        try:
            manifest_path.write_text(json.dumps(manifest))
        except Exception as e:
            logger.error(f"Failed to write manifest: {e}")
            return False

        os.execv(sys.executable, [sys.executable] + sys.argv)

    def _load_home_channel(self) -> Optional[Dict[str, Any]]:
        """Load persisted home channel from file."""
        path = get_hermes_home() / _HOME_CHANNEL_FILE
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except Exception:
            return None

    def _save_home_channel(self, channel: Dict[str, Any]) -> None:
        """Persist home channel to file."""
        path = get_hermes_home() / _HOME_CHANNEL_FILE
        try:
            path.write_text(json.dumps(channel))
        except Exception as e:
            logger.error(f"Failed to save home channel: {e}")

    def update_home_channel(self, platform: str, chat_id: str) -> None:
        """Update the persisted home channel for notifications."""
        self._save_home_channel({"platform": platform, "chat_id": chat_id})

    async def check_post_update_notification(self) -> bool:
        """Poll for update manifest after gateway restart.

        Non-blocking: checks for up to 10 iterations with 1s sleep.
        Returns True if manifest was found and notification sent.
        """
        hermes_home = get_hermes_home()
        manifest_path = hermes_home / _UPDATE_MANIFEST_FILE
        channel = self._load_home_channel()

        if not channel:
            return False

        for _ in range(10):
            if manifest_path.exists():
                break
            await asyncio.sleep(1)
        else:
            return False

        try:
            manifest = json.loads(manifest_path.read_text())
        except Exception:
            return False

        manifest_ts = manifest.get("timestamp", 0)
        if time.time() - manifest_ts > 5 * 60:
            return False

        await self._notify_user(
            f"Hermes updated to {manifest.get('version', 'unknown')} and restarted successfully.",
            channel,
        )

        try:
            manifest_path.unlink()
        except Exception:
            pass

        return True

    async def _notify_user(self, message: str, channel: Dict[str, Any]) -> None:
        """Send notification to user's home channel."""
        from gateway.run import gateway_runner

        if not gateway_runner:
            return

        try:
            await gateway_runner.send_message(
                channel.get("platform", ""),
                channel.get("chat_id", ""),
                message,
            )
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")