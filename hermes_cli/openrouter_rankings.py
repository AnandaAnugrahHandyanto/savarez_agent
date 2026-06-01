"""OpenRouter daily usage rankings — drives picker ordering.

OpenRouter publishes a documented dataset endpoint,
``GET /api/v1/datasets/rankings-daily``, returning the top-50 public models
per day by total token usage (``prompt_tokens + completion_tokens``) — the
same data behind the public chart at https://openrouter.ai/rankings.

We use it to **order** the curated OpenRouter picker list by real-world demand
instead of a hand-maintained sequence, while keeping the manifest's curation
(which models *appear*, tool/free filtering, and any pinned headline models)
untouched.

Design
------
* ``fetch_openrouter_rankings()`` returns ``{canonical_model_id: rank_int}``
  for the most recent day, where rank 0 is the most-used model. The endpoint
  IDs are *dated permaslugs* (e.g. ``anthropic/claude-4.7-opus-20260416``);
  we normalize them to OpenRouter routing IDs (``anthropic/claude-opus-4.7``)
  so they line up with the picker's model IDs.
* Authentication: any valid OpenRouter API key (the same key used for
  inference). When no key is available the fetch is skipped and callers fall
  back to manifest order.
* Cached on disk for ``_RANKINGS_TTL_HOURS`` so the picker never blocks on the
  network more than once a day. The dataset itself only updates ~daily.
* Every failure path is silent and degrades to "no ranking data" so the picker
  keeps working offline / without a key / on a rate-limit.

The reorder itself (pinned-first, ranked tail, manifest tiebreak) lives in
``reorder_by_usage()`` and is pure/testable — it takes the ranking map as an
argument and never touches the network.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from hermes_cli import __version__ as _HERMES_VERSION

logger = logging.getLogger(__name__)

RANKINGS_URL = "https://openrouter.ai/api/v1/datasets/rankings-daily"
_RANKINGS_TTL_HOURS = 24.0
_FETCH_TIMEOUT = 8.0
_HERMES_USER_AGENT = f"hermes-cli/{_HERMES_VERSION}"

# In-process cache: {canonical_id: rank}. None = not yet loaded this session.
_rankings_cache: dict[str, int] | None = None
_rankings_cache_at: float = 0.0


# ---------------------------------------------------------------------------
# Permaslug → canonical routing ID normalization
# ---------------------------------------------------------------------------

# The rankings dataset uses dated permaslugs that don't always map to the
# routing ID by a simple date-suffix strip. Most differ only by a trailing
# ``-YYYYMMDD`` date; a few reorder name components (OpenRouter lists Anthropic
# as ``claude-<gen>-opus`` in rankings but routes it as ``claude-opus-<gen>``).
#
# ``normalize_permaslug`` handles the mechanical cases (date suffix, ``:free``
# variant tag). ``_PERMASLUG_ALIASES`` covers the handful of family reorderings
# that can't be derived mechanically. Keep this table tiny — it only needs
# entries for *curated* models whose permaslug shape differs structurally from
# their routing ID.
_DATE_SUFFIX_RE = re.compile(r"-\d{8}$")

# Maps a *normalized-but-still-wrong* permaslug stem to the routing ID.
# Built for the Anthropic opus/sonnet component reorder seen in the live data
# (e.g. "claude-4.7-opus" → "claude-opus-4.7"). Generated lazily/structurally
# below rather than enumerated per-version so new Claude releases self-map.
_ANTHROPIC_REORDER_RE = re.compile(
    r"^anthropic/claude-(?P<gen>\d+(?:\.\d+)?)-(?P<tier>opus|sonnet|haiku)$"
)


def _strip_date_and_tags(permaslug: str) -> tuple[str, bool]:
    """Return ``(stem, is_free)`` with the date suffix and ``:free`` tag removed."""
    is_free = permaslug.endswith(":free")
    stem = permaslug[: -len(":free")] if is_free else permaslug
    stem = _DATE_SUFFIX_RE.sub("", stem)
    return stem, is_free


def normalize_permaslug(permaslug: str) -> str | None:
    """Map a rankings ``model_permaslug`` to an OpenRouter routing ID.

    Returns ``None`` for the reserved ``other`` aggregate row or anything that
    doesn't look like a ``vendor/model`` slug.

    Mechanical transforms:
      * drop trailing ``-YYYYMMDD`` date
      * preserve a ``:free`` variant tag
      * reorder Anthropic ``claude-<gen>-<tier>`` → ``claude-<tier>-<gen>``
    """
    if not isinstance(permaslug, str):
        return None
    permaslug = permaslug.strip()
    if not permaslug or permaslug == "other" or "/" not in permaslug:
        return None

    stem, is_free = _strip_date_and_tags(permaslug)

    m = _ANTHROPIC_REORDER_RE.match(stem)
    if m:
        stem = f"anthropic/claude-{m.group('tier')}-{m.group('gen')}"

    return f"{stem}:free" if is_free else stem


# ---------------------------------------------------------------------------
# Disk cache
# ---------------------------------------------------------------------------


def _cache_path() -> Path:
    from hermes_constants import get_hermes_home

    return get_hermes_home() / "cache" / "openrouter_rankings.json"


def _read_disk_cache() -> tuple[dict[str, int] | None, float]:
    path = _cache_path()
    try:
        mtime = path.stat().st_mtime
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, FileNotFoundError, json.JSONDecodeError):
        return (None, 0.0)
    if not isinstance(data, dict):
        return (None, 0.0)
    ranks = data.get("ranks")
    if not isinstance(ranks, dict):
        return (None, 0.0)
    out: dict[str, int] = {}
    for k, v in ranks.items():
        if isinstance(k, str) and isinstance(v, int):
            out[k] = v
    return (out, mtime)


def _write_disk_cache(ranks: dict[str, int]) -> None:
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"ranks": ranks, "saved_at": time.time()}, fh, indent=2)
        from utils import atomic_replace

        atomic_replace(tmp, path)
    except OSError as exc:
        logger.info("openrouter rankings cache write failed: %s", exc)


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------


def _resolve_openrouter_api_key() -> str:
    """Best-effort OpenRouter API key for the rankings call (auth required)."""
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if key:
        return key
    try:
        from hermes_cli.auth import resolve_api_key_provider_credentials

        creds = resolve_api_key_provider_credentials("openrouter")
        return str(creds.get("api_key") or "").strip()
    except Exception:
        return ""


def _parse_latest_day_ranks(payload: Any) -> dict[str, int]:
    """Build ``{canonical_id: rank}`` from the rankings payload's latest day.

    Rank 0 = most-used. The ``other`` aggregate row is dropped. When two
    permaslugs normalize to the same routing ID (a dated + ``:free`` variant of
    the same model), the higher-usage (lower-rank) one wins.
    """
    if not isinstance(payload, dict):
        return {}
    rows = payload.get("data")
    if not isinstance(rows, list) or not rows:
        return {}

    latest = ""
    for r in rows:
        if isinstance(r, dict):
            d = str(r.get("date") or "")
            if d > latest:
                latest = d
    if not latest:
        return {}

    day: list[tuple[str, int]] = []
    for r in rows:
        if not isinstance(r, dict) or str(r.get("date") or "") != latest:
            continue
        slug = r.get("model_permaslug")
        try:
            tokens = int(str(r.get("total_tokens") or "0"))
        except (TypeError, ValueError):
            tokens = 0
        canonical = normalize_permaslug(slug) if slug is not None else None
        if canonical is None:
            continue
        day.append((canonical, tokens))

    day.sort(key=lambda t: t[1], reverse=True)
    ranks: dict[str, int] = {}
    for idx, (canonical, _tokens) in enumerate(day):
        ranks.setdefault(canonical, idx)  # first (highest usage) wins
    return ranks


def fetch_openrouter_rankings(
    *,
    force_refresh: bool = False,
    timeout: float = _FETCH_TIMEOUT,
) -> dict[str, int]:
    """Return ``{canonical_model_id: rank}`` for the latest day, or ``{}``.

    Rank 0 is the most-used model. Cached in-process and on disk for
    ``_RANKINGS_TTL_HOURS``. Returns ``{}`` on any failure (no key, network,
    rate limit, parse) so callers fall back to manifest order.
    """
    global _rankings_cache, _rankings_cache_at

    now = time.time()
    ttl = _RANKINGS_TTL_HOURS * 3600.0

    if not force_refresh and _rankings_cache is not None and (now - _rankings_cache_at) < ttl:
        return dict(_rankings_cache)

    disk, disk_mtime = _read_disk_cache()
    if not force_refresh and disk is not None and (now - disk_mtime) < ttl:
        _rankings_cache = disk
        _rankings_cache_at = disk_mtime
        return dict(disk)

    api_key = _resolve_openrouter_api_key()
    if not api_key:
        # No key — can't call the authed endpoint. Use stale disk if present.
        if disk is not None:
            _rankings_cache = disk
            _rankings_cache_at = disk_mtime
            return dict(disk)
        return {}

    try:
        req = urllib.request.Request(
            RANKINGS_URL,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": _HERMES_USER_AGENT,
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        logger.info("openrouter rankings fetch failed: %s", exc)
        if disk is not None:
            _rankings_cache = disk
            _rankings_cache_at = disk_mtime
            return dict(disk)
        return {}
    except Exception as exc:  # pragma: no cover — defensive
        logger.info("openrouter rankings fetch errored: %s", exc)
        return dict(disk) if disk is not None else {}

    ranks = _parse_latest_day_ranks(payload)
    if not ranks:
        if disk is not None:
            _rankings_cache = disk
            _rankings_cache_at = disk_mtime
            return dict(disk)
        return {}

    _write_disk_cache(ranks)
    _rankings_cache = ranks
    _rankings_cache_at = now
    return dict(ranks)


# ---------------------------------------------------------------------------
# Reorder (pure — no network)
# ---------------------------------------------------------------------------


def reorder_by_usage(
    curated: list[tuple[str, str]],
    ranks: dict[str, int],
    pinned_ids: list[str],
) -> list[tuple[str, str]]:
    """Reorder ``curated`` ``[(id, desc), ...]`` by OpenRouter usage rank.

    Ordering rules:
      1. **Pinned** models (in ``pinned_ids`` order) come first, always,
         regardless of usage — these are the editorial headline picks.
      2. The remaining models are sorted by ``ranks[id]`` ascending (rank 0 =
         most used first).
      3. Models with no ranking data keep their original manifest order and
         are appended after all ranked models (stable: a model OpenRouter has
         never seen shouldn't leapfrog one with real usage).

    The function is stable and never drops or adds entries — it only permutes
    ``curated``. Descriptions/badges are preserved verbatim.
    """
    if not curated:
        return []

    by_id = {mid: (mid, desc) for mid, desc in curated}
    original_index = {mid: i for i, (mid, _desc) in enumerate(curated)}
    consumed: set[str] = set()

    result: list[tuple[str, str]] = []

    # 1. Pinned first, in the given order, skipping any not present in curated.
    for pid in pinned_ids:
        if pid in by_id and pid not in consumed:
            result.append(by_id[pid])
            consumed.add(pid)

    remaining = [mid for mid, _ in curated if mid not in consumed]

    # 2 + 3. Ranked models by usage, then unranked in manifest order.
    def sort_key(mid: str) -> tuple[int, int, int]:
        if mid in ranks:
            return (0, ranks[mid], original_index[mid])
        return (1, 0, original_index[mid])

    for mid in sorted(remaining, key=sort_key):
        result.append(by_id[mid])

    return result
