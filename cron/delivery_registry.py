"""Persistent registry of cron delivery message_ids → job_name.

Lets the gateway recover skill context when a user replies to a cron
delivery — including replies to *secondary chunks* of a delivery that was
split across multiple platform messages (e.g. Discord's 2000-character
limit, where only chunk 0 carries the ``Cronjob Response: <name>`` header).

Storage is an append-only JSONL file at
``~/.hermes/cron/deliveries.jsonl``. Each line is a single delivery entry::

    {"platform": "discord", "chat_id": "123", "message_id": "456", "job_name": "mail-triage"}

The file is bounded to roughly ``_MAX_ENTRIES`` lines via opportunistic
truncation on register. Lookups are reverse-chronological so the newest
matching entry wins.

This persistence pattern matches the rest of ``cron/`` (json-on-disk in
``~/.hermes/cron/``) — no SQLite required.
"""

import json
import logging
import os
from pathlib import Path
from threading import Lock
from typing import Iterable, Optional

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

_MAX_ENTRIES = 512
_TRUNCATE_TRIGGER = int(_MAX_ENTRIES * 1.5)  # only rewrite the file every ~256 extra entries

_lock = Lock()
_path_cache: Optional[Path] = None


def _registry_path() -> Path:
    global _path_cache
    if _path_cache is None:
        _path_cache = get_hermes_home() / "cron" / "deliveries.jsonl"
        try:
            _path_cache.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning("Could not create cron deliveries dir: %s", exc)
    return _path_cache


def register(
    platform: str,
    chat_id: str,
    message_ids: Iterable[str],
    job_name: str,
) -> None:
    """Record one or more delivery message ids for a cron job.

    Silently no-ops when ``job_name`` or ``chat_id`` is empty, and
    swallows I/O errors so a failed registration never breaks delivery.
    """
    if not job_name or not chat_id:
        return

    plat = str(platform or "")
    chat = str(chat_id)
    job = str(job_name)

    entries = []
    for mid in message_ids or []:
        if mid:
            entries.append(
                {
                    "platform": plat,
                    "chat_id": chat,
                    "message_id": str(mid),
                    "job_name": job,
                }
            )
    if not entries:
        return

    path = _registry_path()
    with _lock:
        try:
            with open(path, "a", encoding="utf-8") as fh:
                for entry in entries:
                    fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning("Could not append to cron deliveries registry: %s", exc)
            return
        _maybe_truncate(path)


def lookup(platform: str, chat_id: str, message_id: str) -> Optional[str]:
    """Return the job name that produced ``message_id``, or None.

    Searches newest entries first so reused message ids (rare across
    chat_id boundaries) prefer the most recent delivery.
    """
    if not message_id or not chat_id:
        return None

    target_plat = str(platform or "")
    target_chat = str(chat_id)
    target_mid = str(message_id)

    path = _registry_path()
    if not path.exists():
        return None

    with _lock:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                lines = fh.readlines()
        except OSError as exc:
            logger.warning("Could not read cron deliveries registry: %s", exc)
            return None

    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (
            entry.get("platform") == target_plat
            and entry.get("chat_id") == target_chat
            and entry.get("message_id") == target_mid
        ):
            return entry.get("job_name")

    return None


def _maybe_truncate(path: Path) -> None:
    """Rewrite the file to keep the most recent ``_MAX_ENTRIES`` lines."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        if len(lines) <= _TRUNCATE_TRIGGER:
            return
        keep = lines[-_MAX_ENTRIES:]
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.writelines(keep)
        os.replace(tmp, path)
    except OSError as exc:
        logger.warning("Could not truncate cron deliveries registry: %s", exc)
