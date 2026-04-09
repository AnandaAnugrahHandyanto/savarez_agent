#!/usr/bin/env python3
"""
Sync the sherlock-project site database into a Hermes probe-targets YAML file.

Fetches https://raw.githubusercontent.com/sherlock-project/sherlock/master/
sherlock_project/resources/data.json and transforms each entry into the
Hermes declarative target schema expected by
``tools/probe_targets_tool.py``.

Output: ``~/.hermes/probe-targets/usernames.yaml``

Idempotent — safe to re-run at any time. Intended to be runnable manually or
on a cron schedule to pick up upstream additions/removals.

Transform rules (see also: plan at ~/.claude/plans/lovely-squishing-fox.md):

* ``errorType=status_code`` → ``detect: status_code``, copy ``errorCode`` to
  ``error_status`` (default 404).
* ``errorType=message``     → ``detect: body_absent``. Sherlock's ``errorMsg``
  is the "not found" marker: user EXISTS iff the marker is absent. Stored as
  a list even when upstream has a single string.
* ``errorType=response_url`` → ``detect: redirects_to``. User EXISTS iff the
  final response URL is NOT equal to ``errorUrl``.
* ``regexCheck``      → per-target ``value_regex`` (pre-validates the probe value
  before any network call).
* ``request_method`` / ``request_payload`` / ``headers`` copied verbatim.
* ``isNSFW`` entries are skipped unless ``--include-nsfw`` is passed.

Usage:
    python scripts/sync_sherlock_data.py
    python scripts/sync_sherlock_data.py --include-nsfw
    python scripts/sync_sherlock_data.py --output /tmp/test.yaml
    python scripts/sync_sherlock_data.py --source /path/to/local/data.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import urllib.request
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


SHERLOCK_DATA_URL = (
    "https://raw.githubusercontent.com/sherlock-project/sherlock/"
    "master/sherlock_project/resources/data.json"
)

DEFAULT_OUTPUT = Path.home() / ".hermes" / "probe-targets" / "usernames.yaml"

# Default concurrency cap for the probe_targets tool. Matches sherlock's
# upstream worker count and keeps us polite to target sites.
DEFAULT_CONCURRENCY = 20

# A permissive but sane default username regex for pre-validation. Per-target
# entries override this when sherlock provides a ``regexCheck``.
DEFAULT_VALUE_REGEX = r"^[A-Za-z0-9_.\-]{1,64}$"

logger = logging.getLogger("sync_sherlock_data")


def fetch_upstream(source: str) -> dict[str, Any]:
    """Load sherlock's data.json from a URL or local file path."""
    if source.startswith(("http://", "https://")):
        logger.info("Fetching %s", source)
        req = urllib.request.Request(
            source,
            headers={"User-Agent": "hermes-probe-targets-sync/1.0"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    else:
        logger.info("Reading %s", source)
        raw = Path(source).read_text(encoding="utf-8")
    return json.loads(raw)


def _as_list(value: Any) -> list[str]:
    """Normalise a string-or-list field to a list of strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _substitute_placeholder(obj: Any) -> Any:
    """Replace sherlock's ``{}`` placeholder with Hermes's ``{value}`` marker.

    Walks strings, dicts, and lists recursively. Non-string leaves pass through.
    """
    if isinstance(obj, str):
        return obj.replace("{}", "{value}")
    if isinstance(obj, dict):
        return {k: _substitute_placeholder(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_substitute_placeholder(v) for v in obj]
    return obj


def _has_placeholder(obj: Any) -> bool:
    """Return True if ``{}`` appears anywhere inside *obj* (string/dict/list)."""
    if isinstance(obj, str):
        return "{}" in obj
    if isinstance(obj, dict):
        return any(_has_placeholder(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_has_placeholder(v) for v in obj)
    return False


def transform_entry(name: str, entry: dict[str, Any]) -> dict[str, Any] | None:
    """Transform one sherlock site entry into a Hermes target dict.

    Returns ``None`` if the entry is unusable (missing URL, unknown errorType,
    or no ``{}`` placeholder anywhere).
    """
    url = entry.get("url")
    if not url:
        logger.debug("Skipping %s: no URL", name)
        return None

    error_type = entry.get("errorType")
    if error_type not in {"status_code", "message", "response_url"}:
        logger.debug("Skipping %s: unknown errorType=%r", name, error_type)
        return None

    url_probe = entry.get("urlProbe")
    payload = entry.get("request_payload")

    # Sherlock's ``{}`` placeholder can live in url, urlProbe, or nested inside
    # request_payload (e.g. Discord's ``{"username": "{}"}`` POST body). Refuse
    # the entry only when no placeholder exists anywhere — that would make the
    # probe value have nowhere to go.
    if not (_has_placeholder(url) or _has_placeholder(url_probe) or _has_placeholder(payload)):
        logger.debug("Skipping %s: no '{}' placeholder anywhere", name)
        return None

    target: dict[str, Any] = {
        "name": name,
        "url": _substitute_placeholder(url),
    }

    if url_probe:
        target["url_probe"] = _substitute_placeholder(url_probe)

    request_method = (entry.get("request_method") or "GET").upper()
    if request_method != "GET":
        target["method"] = request_method

    if payload is not None:
        target["body"] = _substitute_placeholder(payload)

    headers = entry.get("headers")
    if headers:
        target["headers"] = headers

    regex_check = entry.get("regexCheck")
    if regex_check:
        target["value_regex"] = regex_check

    if error_type == "status_code":
        target["detect"] = "status_code"
        target["error_status"] = int(entry.get("errorCode", 404))
    elif error_type == "message":
        # Sherlock's errorMsg marks "user not found"; we flip to body_absent
        # so "hit" means none of the error strings are present in the body.
        target["detect"] = "body_absent"
        target["error_strings"] = _as_list(entry.get("errorMsg"))
        if not target["error_strings"]:
            logger.debug("Skipping %s: errorType=message with empty errorMsg", name)
            return None
    elif error_type == "response_url":
        target["detect"] = "redirects_to"
        error_url = entry.get("errorUrl")
        if not error_url:
            logger.debug("Skipping %s: errorType=response_url with no errorUrl", name)
            return None
        target["redirect_to"] = error_url

    return target


def build_catalogue(raw: dict[str, Any], include_nsfw: bool) -> list[dict[str, Any]]:
    """Transform the upstream dict into a list of Hermes target entries."""
    targets: list[dict[str, Any]] = []
    skipped_nsfw = 0
    skipped_bad = 0

    for name, entry in raw.items():
        if name.startswith("$"):  # e.g. "$schema" metadata key
            continue
        if not isinstance(entry, dict):
            continue
        if entry.get("isNSFW") and not include_nsfw:
            skipped_nsfw += 1
            continue

        transformed = transform_entry(name, entry)
        if transformed is None:
            skipped_bad += 1
            continue
        targets.append(transformed)

    # Sort for stable diffs across runs.
    targets.sort(key=lambda t: t["name"].lower())

    logger.info(
        "Transformed %d targets (skipped %d NSFW, %d unusable)",
        len(targets),
        skipped_nsfw,
        skipped_bad,
    )
    return targets


def write_yaml(path: Path, targets: list[dict[str, Any]]) -> None:
    """Write the final catalogue to disk, creating parent dirs as needed."""
    doc = {
        "version": 1,
        "concurrency": DEFAULT_CONCURRENCY,
        "pre_validate": {"value_regex": DEFAULT_VALUE_REGEX},
        "targets": targets,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(
            "# Auto-generated by hermes-agent/scripts/sync_sherlock_data.py\n"
            "# Source: https://github.com/sherlock-project/sherlock\n"
            "# License: MIT (upstream)\n"
            "# Re-run the sync script to refresh.\n\n"
        )
        yaml.safe_dump(
            doc,
            f,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
            width=120,
        )
    logger.info("Wrote %d targets to %s", len(targets), path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument(
        "--source",
        default=SHERLOCK_DATA_URL,
        help="URL or local path to sherlock data.json (default: upstream master)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"YAML output path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--include-nsfw",
        action="store_true",
        help="Include NSFW sites (off by default)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose logging",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    try:
        raw = fetch_upstream(args.source)
    except Exception as e:  # noqa: BLE001 — script entry point needs a broad catch
        logger.error("Failed to load sherlock data.json: %s", e)
        return 2

    targets = build_catalogue(raw, include_nsfw=args.include_nsfw)
    if not targets:
        logger.error("No targets produced — refusing to overwrite %s", args.output)
        return 3

    write_yaml(args.output, targets)
    print(f"OK — {len(targets)} targets written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
