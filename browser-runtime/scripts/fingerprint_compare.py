#!/usr/bin/env python3
"""Compare sanitized HBR P4 fingerprint probe JSON files.

This is an evidence/risk-delta helper, not an undetectability scorer. It reports
measured identity-coherence changes and residual risks from already-sanitized
probe outputs.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "hbr.p4.fingerprint_compare.v1"
PROBE_SCHEMA = "hbr.p4.fingerprint_probe.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True, help="before sanitized fingerprint-probe JSON")
    parser.add_argument("--after", type=Path, required=True, help="after sanitized fingerprint-probe JSON")
    parser.add_argument("--out", type=Path, required=True, help="write markdown delta report here")
    parser.add_argument("--json-out", type=Path, help="optional machine-readable delta JSON")
    return parser.parse_args()


def load_report(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schema_version") != PROBE_SCHEMA:
        raise SystemExit(f"{path} is not a {PROBE_SCHEMA} report")
    return report


def sorted_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted(str(item) for item in value)


def identity_coherence_delta(before: dict[str, Any], after: dict[str, Any]) -> str:
    before_ok = bool(before.get("identity", {}).get("coherent"))
    after_ok = bool(after.get("identity", {}).get("coherent"))
    if before_ok == after_ok:
        return "unchanged_pass" if after_ok else "unchanged_fail"
    return "improved" if after_ok else "regressed"


def coherence_delta(before_value: Any, after_value: Any) -> dict[str, Any]:
    before_report = before_value if isinstance(before_value, dict) else {}
    after_report = after_value if isinstance(after_value, dict) else {}
    before_known = "coherent" in before_report
    after_known = "coherent" in after_report
    if not before_known and not after_known:
        delta = "not_measured"
    elif before_known != after_known:
        delta = "newly_measured" if after_known else "no_longer_measured"
    else:
        before_ok = bool(before_report.get("coherent"))
        after_ok = bool(after_report.get("coherent"))
        if before_ok == after_ok:
            delta = "unchanged_pass" if after_ok else "unchanged_fail"
        else:
            delta = "improved" if after_ok else "regressed"
    return {"before": before_report, "after": after_report, "delta": delta}


def red_flag_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[str]]:
    before_flags = set(sorted_strings(before.get("red_flags")))
    after_flags = set(sorted_strings(after.get("red_flags")))
    return {
        "resolved": sorted(before_flags - after_flags),
        "new": sorted(after_flags - before_flags),
        "remaining": sorted(before_flags & after_flags),
    }


def class_delta(before: dict[str, Any], after: dict[str, Any], *path: str) -> dict[str, Any]:
    def get(report: dict[str, Any]) -> Any:
        current: Any = report
        for key in path:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
        return current

    before_value = get(before)
    after_value = get(after)
    return {
        "before": before_value,
        "after": after_value,
        "changed": before_value != after_value,
    }


def merge_residual_risks(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    risks = sorted(set(sorted_strings(before.get("residual_risks"))) | set(sorted_strings(after.get("residual_risks"))))
    if "Public detector pages are evidence only and were not measured by this deterministic local probe." not in risks:
        risks.append("Public detector pages are evidence only and may remain not_measured by this local delta.")
    return risks


def compare_reports(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "identity_coherence": identity_coherence_delta(before, after),
        "identity": {
            "before": before.get("identity", {}),
            "after": after.get("identity", {}),
        },
        "surface_coherence": coherence_delta(before.get("surface_coherence"), after.get("surface_coherence")),
        "red_flags": red_flag_delta(before, after),
        "webrtc_candidate_classes": class_delta(before, after, "webrtc", "candidate_classes"),
        "webgl_renderer_class": class_delta(before, after, "rendering", "webgl", "renderer_class"),
        "residual_risks": merge_residual_risks(before, after),
        "limits": [
            "Public detector pages are evidence only; this delta is not a guarantee of real-site success.",
            "No CAPTCHA, OAuth/MFA/OTP/3DS/payment, rate-limit, account-abuse, or access-control bypass is measured or claimed.",
        ],
    }


def render_markdown(delta: dict[str, Any]) -> str:
    red_flags = delta.get("red_flags", {})
    surface = delta.get("surface_coherence", {}) if isinstance(delta.get("surface_coherence"), dict) else {}
    lines = [
        "# HBR P4 fingerprint hygiene risk delta",
        "",
        f"Generated: {delta.get('generated_at_utc', 'unknown')}",
        "",
        "## Summary",
        "",
        f"- identity coherence: {delta.get('identity_coherence')}",
        f"- surface coherence: {surface.get('delta', 'not_measured')}",
        f"- red flags resolved: {', '.join(red_flags.get('resolved') or ['none'])}",
        f"- red flags new: {', '.join(red_flags.get('new') or ['none'])}",
        f"- red flags remaining: {', '.join(red_flags.get('remaining') or ['none'])}",
        "",
        "## Measured deltas",
        "",
        f"- WebRTC candidate classes: {delta.get('webrtc_candidate_classes', {}).get('before')} -> {delta.get('webrtc_candidate_classes', {}).get('after')}",
        f"- WebGL renderer class: {delta.get('webgl_renderer_class', {}).get('before')} -> {delta.get('webgl_renderer_class', {}).get('after')}",
        "",
        "## Residual risks and limits",
        "",
        "Public detector pages are evidence only; this local probe does not prove real-site success.",
    ]
    for risk in delta.get("residual_risks", []):
        lines.append(f"- {risk}")
    for limit in delta.get("limits", []):
        lines.append(f"- {limit}")
    lines.append("")
    return "\n".join(lines)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    before = load_report(args.before)
    after = load_report(args.after)
    delta = compare_reports(before, after)
    write_text(args.out, render_markdown(delta))
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(delta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "identity_coherence": delta["identity_coherence"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
