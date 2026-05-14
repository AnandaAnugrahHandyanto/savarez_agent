#!/usr/bin/env python3
"""Compare two redacted public detector capture manifests.

This is a benchmark evidence helper, not a success guarantee. It compares capture
counts and per-detector availability while redacting sensitive detector text.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "hbr.p4.public_detector_compare.v1"
IP_LITERAL_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
DETECTOR_HASH_RE = re.compile(r"\b[a-fA-F0-9]{32,128}\b")
CDP_WS_RE = re.compile(r"wss?://[^\s\"'<>]+/devtools/browser/[^\s\"'<>]+", re.IGNORECASE)
TAKEOVER_TOKEN_RE = re.compile(r"https?://[^\s\"'<>]+/takeover/[^\s\"'<>]+", re.IGNORECASE)
TOKEN_RE = re.compile(r"(?i)\btoken=[^\s&\"'<>]+")
COOKIE_RE = re.compile(r"(?i)\bcookie=[^\s&\"'<>]+")
AUTH_RE = re.compile(r"(?i)\bAuthorization\s*:\s*[^\n\r]+")
HOME_PATH_RE = re.compile(r"/(?:home|Users)/[^\s\"'<>]+")
WINDOWS_USER_PATH_RE = re.compile(r"(?i)\b[A-Z]:\\Users\\[^\s\"'<>]+")
PRIVATE_RUNTIME_PATH_RE = re.compile(r"[^\s\"'<>]*runtime-data/(?:profiles|tmp)[^\s\"'<>]*")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True, help="before run directory or manifest JSON")
    parser.add_argument("--after", type=Path, required=True, help="after run directory or manifest JSON")
    parser.add_argument("--out", type=Path, required=True, help="write markdown comparison here")
    parser.add_argument("--json-out", type=Path, help="optional machine-readable comparison JSON")
    parser.add_argument("--redact", action="store_true", help="compatible explicit option; public comparisons are always redacted")
    return parser.parse_args()


def valid_ip_literal(value: str) -> bool:
    octets = value.split(".")
    return len(octets) == 4 and all(octet.isdigit() and 0 <= int(octet) <= 255 for octet in octets)


def redact_text(text: str) -> str:
    text = CDP_WS_RE.sub("[REDACTED_CDP_URL]", text)
    text = TAKEOVER_TOKEN_RE.sub("[REDACTED_TAKEOVER_URL]", text)
    text = TOKEN_RE.sub("[REDACTED_TOKEN]", text)
    text = COOKIE_RE.sub("[REDACTED_COOKIE]", text)
    text = AUTH_RE.sub("[REDACTED_AUTH]", text)
    text = PRIVATE_RUNTIME_PATH_RE.sub("[REDACTED_PRIVATE_PATH]", text)
    text = HOME_PATH_RE.sub("[REDACTED_PRIVATE_PATH]", text)
    text = WINDOWS_USER_PATH_RE.sub("[REDACTED_PRIVATE_PATH]", text)
    text = DETECTOR_HASH_RE.sub("[REDACTED_HASH]", text)

    def redact_ip(match: re.Match[str]) -> str:
        value = match.group(0)
        return "[REDACTED_IP]" if valid_ip_literal(value) else value

    return IP_LITERAL_RE.sub(redact_ip, text)


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): redact_value(item) for key, item in value.items()}
    return value


def manifest_path(path: Path) -> Path:
    return path / "manifest.json" if path.is_dir() else path


def image_nonblank(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        from PIL import Image  # type: ignore[import-not-found]

        with Image.open(path) as image:
            extrema = image.convert("L").getextrema()
            return bool(extrema and extrema[0] != extrema[1])
    except Exception:  # pragma: no cover - image probing is best-effort metadata
        return False


def detector_nonblank(detector: dict[str, Any]) -> bool:
    screenshot = detector.get("screenshot")
    if isinstance(screenshot, dict):
        return bool(screenshot.get("nonblank"))
    if isinstance(screenshot, str) and screenshot:
        return image_nonblank(Path(screenshot))
    return False


def load_manifest(path: Path, *, redact: bool) -> dict[str, Any]:
    source = manifest_path(path)
    data = json.loads(source.read_text(encoding="utf-8"))
    if isinstance(data, list):
        detectors = data
        counts = {
            "attempted": len(detectors),
            "captured": sum(1 for item in detectors if isinstance(item, dict) and bool(item.get("ok"))),
            "nonblank": sum(1 for item in detectors if isinstance(item, dict) and detector_nonblank(item)),
        }
        manifest: dict[str, Any] = {"counts": counts, "detectors": detectors}
    elif isinstance(data, dict):
        manifest = data
    else:
        raise SystemExit(f"{source} must contain a manifest object or detector list")
    return redact_value(manifest) if redact else manifest


def manifest_counts(manifest: dict[str, Any]) -> dict[str, int]:
    counts = manifest.get("counts") if isinstance(manifest.get("counts"), dict) else {}
    detectors = manifest.get("detectors") if isinstance(manifest.get("detectors"), list) else []
    screenshots = manifest.get("screenshots") if isinstance(manifest.get("screenshots"), list) else []
    captured = counts.get("captured", sum(1 for item in detectors if isinstance(item, dict) and bool(item.get("ok"))))
    if "nonblank" in counts:
        nonblank = counts.get("nonblank")
    elif screenshots:
        nonblank = sum(1 for item in screenshots if isinstance(item, dict) and bool(item.get("nonblank")))
    else:
        nonblank = sum(1 for item in detectors if isinstance(item, dict) and detector_nonblank(item))
    return {
        "attempted": int(counts.get("attempted", len(detectors)) or 0),
        "captured": int(captured or 0),
        "nonblank": int(nonblank or 0),
    }


def detector_slug(detector: dict[str, Any]) -> str:
    return str(detector.get("slug") or detector.get("title") or "unknown")


def detector_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    detectors = manifest.get("detectors") if isinstance(manifest.get("detectors"), list) else []
    mapped: dict[str, dict[str, Any]] = {}
    for detector in detectors:
        if isinstance(detector, dict):
            mapped[detector_slug(detector)] = detector
    return mapped


def detector_ok(detector: dict[str, Any] | None) -> bool | None:
    if detector is None:
        return None
    return bool(detector.get("ok"))


def detector_verdict(before: dict[str, Any] | None, after: dict[str, Any] | None) -> str:
    before_ok = detector_ok(before)
    after_ok = detector_ok(after)
    if before_ok is False and after_ok is True:
        return "improved"
    if before_ok is True and after_ok is False:
        return "regressed"
    if before_ok is None and after_ok is not None:
        return "new"
    if before_ok is not None and after_ok is None:
        return "missing_after"
    return "unchanged"


def summary_excerpt(detector: dict[str, Any] | None) -> dict[str, Any]:
    if detector is None:
        return {}
    excerpt: dict[str, Any] = {"ok": bool(detector.get("ok"))}
    if detector.get("error"):
        excerpt["error"] = detector.get("error")
    summary = detector.get("detector_summary") if isinstance(detector.get("detector_summary"), dict) else {}
    if summary:
        if isinstance(summary.get("signals"), dict):
            excerpt["signals"] = summary["signals"]
        if isinstance(summary.get("interesting_lines"), list):
            excerpt["interesting_line_count"] = len(summary["interesting_lines"])
    return redact_value(excerpt)


def compare_runs(before: Path, after: Path, *, redact: bool = True) -> dict[str, Any]:
    before_manifest = load_manifest(before, redact=redact)
    after_manifest = load_manifest(after, redact=redact)
    before_detectors = detector_map(before_manifest)
    after_detectors = detector_map(after_manifest)
    rows: list[dict[str, Any]] = []
    for slug in sorted(set(before_detectors) | set(after_detectors)):
        before_row = before_detectors.get(slug)
        after_row = after_detectors.get(slug)
        rows.append(
            {
                "detector": slug,
                "before_ok": detector_ok(before_row),
                "after_ok": detector_ok(after_row),
                "verdict": detector_verdict(before_row, after_row),
                "before_summary": summary_excerpt(before_row),
                "after_summary": summary_excerpt(after_row),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "before": {"label": "before", "counts": manifest_counts(before_manifest)},
        "after": {"label": "after", "counts": manifest_counts(after_manifest)},
        "detectors": rows,
        "limits": [
            "Public detector pages are evidence only; capture success is not a guarantee of real-site success.",
            "Network reputation, account history, challenges, and site-specific access controls remain out of scope.",
        ],
        "raw_values_redacted": redact,
    }


def render_markdown(comparison: dict[str, Any]) -> str:
    before_counts = comparison.get("before", {}).get("counts", {}) if isinstance(comparison.get("before"), dict) else {}
    after_counts = comparison.get("after", {}).get("counts", {}) if isinstance(comparison.get("after"), dict) else {}
    lines = [
        "# HBR P4 public detector evidence comparison",
        "",
        f"Generated: {comparison.get('generated_at_utc', 'unknown')}",
        "",
        "## Summary",
        "",
        f"- before captured/nonblank: {before_counts.get('captured', 0)}/{before_counts.get('nonblank', 0)} of {before_counts.get('attempted', 0)}",
        f"- after captured/nonblank: {after_counts.get('captured', 0)}/{after_counts.get('nonblank', 0)} of {after_counts.get('attempted', 0)}",
        "",
        "## Detector verdicts",
        "",
    ]
    for row in comparison.get("detectors", []):
        if not isinstance(row, dict):
            continue
        lines.append(
            f"- {row.get('detector')}: {row.get('verdict')} "
            f"(before_ok={row.get('before_ok')}, after_ok={row.get('after_ok')})"
        )
    lines.extend(["", "## Limits", ""])
    for limit in comparison.get("limits", []):
        lines.append(f"- {limit}")
    lines.append("")
    return "\n".join(lines)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    comparison = compare_runs(args.before, args.after, redact=True)
    write_text(args.out, render_markdown(comparison))
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "detectors": len(comparison["detectors"])}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
