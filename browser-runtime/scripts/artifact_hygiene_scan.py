#!/usr/bin/env python3
"""Sanitize and scan hermes-browser-runtime artifact bundles.

The raw runtime data directory is private by default. This helper creates either:

* an internal-sanitized, internal-review text bundle that preserves reviewed text
  evidence while redacting local capability URLs, or
* a public-redacted bundle made only from generated whitelist summaries.

The public tier is intentionally stricter: it never copies raw detector output,
screenshots, runtime data, local filesystem paths, public IP literals, raw ICE
candidate text, detector hashes, or exact browser fingerprint surfaces.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

REDACTED = "[REDACTED]"
TIER_INTERNAL = "internal-sanitized"
TIER_PUBLIC = "public-redacted"
SENSITIVITY_TIER = {
    TIER_INTERNAL: "internal_sanitized",
    TIER_PUBLIC: "public_redacted",
}
TEXT_SUFFIXES = {".json", ".jsonl", ".md", ".txt", ".log", ".csv"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".avif"}
SESSION_SHAREABLE_NAMES = {"session.json", "events.jsonl"}
PRIVATE_RUNTIME_DIRS = {"profiles", "tmp"}
PRIVATE_BROWSER_STATE_NAMES = {
    "Cookies",
    "Cookies-journal",
    "History",
    "History-journal",
    "Login Data",
    "Login Data For Account",
    "Local Storage",
    "Network",
    "Preferences",
    "Session Storage",
    "Top Sites",
    "Web Data",
    "IndexedDB",
    "Extension State",
}
CDP_WS_RE = re.compile(r"wss?://[^\s\"'<>]+/devtools/browser/[^\s\"'<>]+", re.IGNORECASE)
TAKEOVER_TOKEN_RE = re.compile(
    r"(?P<prefix>https?://[^\s\"'<>]+/takeover/[^?\s\"'<>]+\?[^\s\"'<>]*?token=)"
    r"(?P<token>[^&\s\"'<>]+)",
    re.IGNORECASE,
)
SAFE_TOKEN_VALUES = {"***", REDACTED, "%5BREDACTED%5D"}
IP_LITERAL_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
ICE_CANDIDATE_RE = re.compile(r"(?i)(candidate:|\btyp\s+(?:host|srflx|relay)\b|\bsrflx\b)")
DETECTOR_HASH_RE = re.compile(r"\b[a-fA-F0-9]{32,128}\b")
HOME_PATH_RE = re.compile(r"(?:^|[\s\"'])/home/[^\s\"'<>]*")
SESSION_OR_PROFILE_ID_RE = re.compile(
    r"(?i)\b(?:session|profile)[_-]?id\b|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"
)
PUBLIC_AUTH_OR_REQUEST_RE = re.compile(
    r"(?i)(\bAuthorization\b|\bcookie\b|\bset-cookie\b|\bpassword\b|\bpasswd\b|\bsecret\b|token=|form[_-]?body|request[_-]?body)"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help="artifact bundle paths to scan")
    parser.add_argument("--source", type=Path, help="raw evidence run to sanitize")
    parser.add_argument("--sanitize-to", type=Path, help="destination for a sanitized text bundle")
    parser.add_argument(
        "--tier",
        choices=[TIER_INTERNAL, TIER_PUBLIC],
        default=TIER_INTERNAL,
        help="sanitization/scan tier; public-redacted emits whitelist-only public summaries",
    )
    parser.add_argument("--strict", action="store_true", help="exit non-zero when findings remain")
    parser.add_argument(
        "--json-report",
        type=Path,
        help=(
            "write scan report JSON to this path; defaults to <sanitize-to>/hygiene-scan-report.json "
            "for internal-sanitized or <sanitize-to>/public-redaction-scan-report.json for public-redacted"
        ),
    )
    return parser.parse_args()


def rel_parts(path: Path) -> tuple[str, ...]:
    return tuple(part for part in path.parts if part not in (".", ""))


def is_private_runtime_path(rel: Path) -> bool:
    parts = rel_parts(rel)
    if "runtime-data" in parts:
        idx = parts.index("runtime-data")
        if len(parts) > idx + 1 and parts[idx + 1] in PRIVATE_RUNTIME_DIRS:
            return True
    if "profiles" in parts and any(part in PRIVATE_BROWSER_STATE_NAMES for part in parts):
        return True
    return False


def is_shareable_session_text(rel: Path) -> bool:
    parts = rel_parts(rel)
    return "runtime-data" in parts and "sessions" in parts and rel.name in SESSION_SHAREABLE_NAMES


def is_top_level_or_report_text(rel: Path) -> bool:
    if rel.suffix.lower() not in TEXT_SUFFIXES:
        return False
    parts = rel_parts(rel)
    if not parts:
        return False
    if parts[0] == "runtime-data":
        return is_shareable_session_text(rel)
    # Keep text evidence/report files; skip helper source files and binary screenshots.
    return True


def looks_binary(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:8192]
    except OSError:
        return True
    if b"\0" in chunk:
        return True
    try:
        chunk.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def redact_text(text: str) -> str:
    text = CDP_WS_RE.sub(REDACTED, text)

    def redact_takeover(match: re.Match[str]) -> str:
        token = match.group("token")
        if token in SAFE_TOKEN_VALUES:
            return match.group(0)
        return f"{match.group('prefix')}{REDACTED}"

    return TAKEOVER_TOKEN_RE.sub(redact_takeover, text)


def add_finding(findings: list[dict[str, str]], rel: str, kind: str, match: str = REDACTED) -> None:
    findings.append({"path": rel, "kind": kind, "match": match})


def text_has_ip_literal(text: str) -> bool:
    for token in IP_LITERAL_RE.findall(text):
        octets = token.split(".")
        if all(0 <= int(octet) <= 255 for octet in octets):
            return True
    return False


def scan_text(rel: str, text: str, *, tier: str = TIER_INTERNAL) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for _match in CDP_WS_RE.finditer(text):
        add_finding(findings, rel, "cdp_websocket_url" if tier == TIER_INTERNAL else "capability_url")
    for match in TAKEOVER_TOKEN_RE.finditer(text):
        token = match.group("token")
        if token not in SAFE_TOKEN_VALUES:
            kind = "takeover_token" if tier == TIER_INTERNAL else "capability_url"
            add_finding(findings, rel, kind, f"{match.group('prefix')}{REDACTED}")

    if tier != TIER_PUBLIC:
        return findings

    if text_has_ip_literal(text):
        add_finding(findings, rel, "ip_literal")
    if ".local" in text.lower():
        add_finding(findings, rel, "local_hostname")
    if ICE_CANDIDATE_RE.search(text):
        add_finding(findings, rel, "ice_candidate_text")
    if DETECTOR_HASH_RE.search(text):
        add_finding(findings, rel, "detector_hash")
    if HOME_PATH_RE.search(text):
        add_finding(findings, rel, "home_path")
    if "runtime-data/profiles" in text or "runtime-data/tmp" in text:
        add_finding(findings, rel, "private_runtime_path")
    if SESSION_OR_PROFILE_ID_RE.search(text):
        add_finding(findings, rel, "session_or_profile_id")
    if "devtools/browser" in text.lower() or "/takeover/" in text.lower():
        add_finding(findings, rel, "capability_url")
    if PUBLIC_AUTH_OR_REQUEST_RE.search(text):
        add_finding(findings, rel, "public_auth_or_request_marker")
    return findings


def report_root(root: Path, tier: str) -> str:
    if tier == TIER_PUBLIC:
        return root.name or "public-redacted-bundle"
    return str(root)


def scan_path(root: Path, *, tier: str = TIER_INTERNAL) -> dict[str, object]:
    root = root.resolve()
    report: dict[str, object] = {
        "root": report_root(root, tier),
        "scan_tier": tier,
        "sensitivity_tier": SENSITIVITY_TIER[tier],
        "public_share_safe": False,
        "scanned_text_files": 0,
        "skipped_binary_files": 0,
        "private_paths_present": [],
        "findings": [],
    }
    findings: list[dict[str, str]] = []
    private_paths: list[str] = []
    if not root.exists():
        findings.append({"path": report_root(root, tier), "kind": "missing_path", "match": "path does not exist"})
        report["findings"] = findings
        return report

    files = [root] if root.is_file() else [path for path in root.rglob("*") if path.is_file()]
    for path in files:
        rel_path = path.relative_to(root) if root.is_dir() else Path(path.name)
        rel = rel_path.as_posix()
        if is_private_runtime_path(rel_path):
            private_paths.append(rel)
            if tier == TIER_PUBLIC:
                add_finding(findings, rel, "private_runtime_path")
            continue
        if tier == TIER_PUBLIC and rel_path.suffix.lower() in IMAGE_SUFFIXES:
            report["skipped_binary_files"] = int(report["skipped_binary_files"]) + 1
            add_finding(findings, rel, "public_binary_or_screenshot")
            continue
        if looks_binary(path):
            report["skipped_binary_files"] = int(report["skipped_binary_files"]) + 1
            if tier == TIER_PUBLIC:
                add_finding(findings, rel, "public_binary_or_screenshot")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            report["skipped_binary_files"] = int(report["skipped_binary_files"]) + 1
            if tier == TIER_PUBLIC:
                add_finding(findings, rel, "public_binary_or_screenshot")
            continue
        report["scanned_text_files"] = int(report["scanned_text_files"]) + 1
        findings.extend(scan_text(rel, text, tier=tier))

    report["private_paths_present"] = sorted(private_paths)
    report["findings"] = findings
    report["public_share_safe"] = tier == TIER_PUBLIC and not findings and not private_paths
    return report


def sanitize_internal_bundle(source: Path, dest: Path) -> dict[str, object]:
    copied: list[str] = []
    excluded_private: list[str] = []
    excluded_non_text_or_unreviewed: list[str] = []

    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(source)
        rel_s = rel.as_posix()
        if is_private_runtime_path(rel):
            excluded_private.append(rel_s)
            continue
        if not is_top_level_or_report_text(rel) or looks_binary(path):
            excluded_non_text_or_unreviewed.append(rel_s)
            continue
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        text = path.read_text(encoding="utf-8", errors="replace")
        out.write_text(redact_text(text), encoding="utf-8")
        copied.append(rel_s)

    manifest = {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "source": str(source),
        "destination": str(dest),
        "scan_tier": TIER_INTERNAL,
        "sensitivity_tier": SENSITIVITY_TIER[TIER_INTERNAL],
        "public_share_safe": False,
        "policy": {
            "audience": "internal_review_only",
            "raw_runtime_profiles": "private-local-only; never copied into sanitized evidence",
            "copied_file_scope": "text reports, text detector outputs, session.json, and events.jsonl only",
            "redactions": [
                "Chrome DevTools Protocol websocket URLs",
                "takeover URLs with sensitive query parameters",
            ],
            "unreviewed_binary_screenshots": "excluded from this sanitized bundle",
        },
        "copied_files": copied,
        "excluded_private_files": excluded_private,
        "excluded_non_text_or_unreviewed_files": excluded_non_text_or_unreviewed,
    }
    (dest / "SANITIZED-MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def safe_bool(value: Any) -> bool:
    return bool(value) if isinstance(value, bool) else False


def summarize_probe_report(rel: Path, data: dict[str, Any]) -> dict[str, Any] | None:
    if data.get("schema_version") != "hbr.p4.fingerprint_probe.v1":
        return None
    measurement = data.get("measurement_completeness") if isinstance(data.get("measurement_completeness"), dict) else {}
    measurement_contexts = measurement.get("contexts") if isinstance(measurement.get("contexts"), dict) else {}
    context_statuses: dict[str, dict[str, Any]] = {}
    for name in ("top", "iframe", "worker", "popup"):
        source = measurement_contexts.get(name) if isinstance(measurement_contexts.get(name), dict) else {}
        entry = {
            "measured": safe_bool(source.get("measured")),
            "status": str(source.get("status") or ("measured" if source.get("measured") else "unknown")),
        }
        if not entry["measured"] and source.get("reason"):
            entry["reason"] = str(source.get("reason"))
        context_statuses[name] = entry
    identity = data.get("identity") if isinstance(data.get("identity"), dict) else {}
    red_flags = data.get("red_flags") if isinstance(data.get("red_flags"), list) else []
    webgl = (
        data.get("rendering", {}).get("webgl", {})
        if isinstance(data.get("rendering"), dict) and isinstance(data.get("rendering", {}).get("webgl"), dict)
        else {}
    )
    webrtc = data.get("webrtc") if isinstance(data.get("webrtc"), dict) else {}
    network_classes = webrtc.get("candidate_classes") if isinstance(webrtc.get("candidate_classes"), list) else []
    return {
        "source_file": rel.name,
        "report_type": "fingerprint_probe",
        "measurement_contract_version": data.get("measurement_contract_version"),
        "measurement_complete": safe_bool(measurement.get("complete")),
        "context_statuses": context_statuses,
        "identity_coherent": safe_bool(identity.get("coherent")),
        "identity_mismatch_count": len(identity.get("mismatches") if isinstance(identity.get("mismatches"), list) else []),
        "red_flags": sorted(str(item) for item in red_flags),
        "network_signal_class_count": len(network_classes),
        "network_raw_values_redacted": safe_bool(webrtc.get("raw_values_redacted")),
        "webgl_renderer_class": str(webgl.get("renderer_class") or "unknown"),
        "residual_risk_count": len(data.get("residual_risks") if isinstance(data.get("residual_risks"), list) else []),
    }


def summarize_hygiene_report(rel: Path, data: dict[str, Any]) -> dict[str, Any] | None:
    reports = data.get("reports")
    if not isinstance(reports, list):
        return None
    return {
        "source_file": rel.name,
        "report_type": "hygiene_scan",
        "report_count": len(reports),
        "finding_count": sum(len(report.get("findings", [])) for report in reports if isinstance(report, dict)),
        "private_path_count": sum(len(report.get("private_paths_present", [])) for report in reports if isinstance(report, dict)),
    }


def collect_public_summaries(source: Path) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for path in sorted(source.rglob("*.json")):
        rel = path.relative_to(source)
        if is_private_runtime_path(rel):
            continue
        if looks_binary(path):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        for builder in (summarize_probe_report, summarize_hygiene_report):
            summary = builder(rel, data)
            if summary is not None:
                summaries.append(summary)
                break
    return summaries


def render_public_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Public redacted artifact summary",
        "",
        f"Generated: {summary.get('generated_at_utc', 'unknown')}",
        f"Artifact label: {summary.get('artifact_label', 'unknown')}",
        "",
        "## Scope",
        "",
        "This bundle contains generated whitelist summaries only. Raw detector pages, screenshots, local paths, exact browser identity surfaces, IP literals, hostnames, and local capability URLs are omitted.",
        "",
        "## Reports",
        "",
    ]
    reports = summary.get("reports") if isinstance(summary.get("reports"), list) else []
    if not reports:
        lines.append("- none")
    for report in reports:
        if not isinstance(report, dict):
            continue
        label = report.get("source_file", "unknown")
        report_type = report.get("report_type", "unknown")
        lines.append(f"- {label}: {report_type}")
        if report_type == "fingerprint_probe":
            lines.append(f"  - measurement complete: {report.get('measurement_complete')}")
            lines.append(f"  - identity coherent: {report.get('identity_coherent')}")
            lines.append(f"  - identity mismatch count: {report.get('identity_mismatch_count')}")
            lines.append(f"  - red flags: {', '.join(report.get('red_flags') or ['none'])}")
    lines.extend(
        [
            "",
            "## Limits",
            "",
            "This public summary is not raw benchmark evidence and is not a guarantee of real-site success.",
            "Human-only checkpoints remain pause, takeover, and approval.",
            "No CAPTCHA, OAuth, MFA, OTP, passkey, 3DS, payment, rate-limit, account-abuse, or access-control bypass is measured or claimed.",
            "",
        ]
    )
    return "\n".join(lines)


def sanitize_public_bundle(source: Path, dest: Path) -> dict[str, object]:
    reports = collect_public_summaries(source)
    generated_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    public_summary = {
        "schema_version": "hbr.p5.public_summary.v1",
        "generated_at_utc": generated_at,
        "scan_tier": TIER_PUBLIC,
        "sensitivity_tier": SENSITIVITY_TIER[TIER_PUBLIC],
        "public_share_safe": True,
        "artifact_label": source.name,
        "reports": reports,
        "omitted_detail_policy": [
            "raw detector page output",
            "screenshots and binary captures",
            "local filesystem paths",
            "IP literals and hostnames",
            "exact browser identity and runtime fingerprints",
            "capability URLs and credential-bearing payload details",
        ],
    }
    manifest = {
        "schema_version": "hbr.p5.public_redacted_manifest.v1",
        "generated_at_utc": generated_at,
        "scan_tier": TIER_PUBLIC,
        "sensitivity_tier": SENSITIVITY_TIER[TIER_PUBLIC],
        "public_share_safe": True,
        "source_label": source.name,
        "destination_label": dest.name,
        "policy": {
            "audience": "public_share",
            "copied_file_scope": "generated whitelist summaries only",
            "excluded_detail_classes": public_summary["omitted_detail_policy"],
        },
        "generated_files": [
            "PUBLIC-REDACTED-MANIFEST.json",
            "public-summary.json",
            "public-summary.md",
        ],
        "included_report_count": len(reports),
        "excluded_source_file_count": sum(1 for path in source.rglob("*") if path.is_file()),
    }
    (dest / "PUBLIC-REDACTED-MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (dest / "public-summary.json").write_text(json.dumps(public_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (dest / "public-summary.md").write_text(render_public_markdown(public_summary), encoding="utf-8")
    return manifest


def sanitize_bundle(source: Path, dest: Path, *, tier: str = TIER_INTERNAL) -> dict[str, object]:
    source = source.resolve()
    dest = dest.resolve()
    if tier not in SENSITIVITY_TIER:
        raise SystemExit(f"unsupported tier: {tier}")
    if dest == source or dest.is_relative_to(source):
        raise SystemExit("--sanitize-to must not be inside --source")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    if tier == TIER_PUBLIC:
        return sanitize_public_bundle(source, dest)
    return sanitize_internal_bundle(source, dest)


def default_report_path(args: argparse.Namespace) -> Path | None:
    if args.json_report is not None:
        return args.json_report
    if not args.sanitize_to:
        return None
    if args.tier == TIER_PUBLIC:
        return args.sanitize_to / "public-redaction-scan-report.json"
    return args.sanitize_to / "hygiene-scan-report.json"


def main() -> int:
    args = parse_args()
    reports: list[dict[str, object]] = []

    if args.source or args.sanitize_to:
        if not args.source or not args.sanitize_to:
            print("--source and --sanitize-to must be provided together", file=sys.stderr)
            return 2
        sanitize_bundle(args.source, args.sanitize_to, tier=args.tier)
        reports.append(scan_path(args.sanitize_to, tier=args.tier))

    for path in args.paths:
        reports.append(scan_path(path, tier=args.tier))

    if not reports and not args.sanitize_to:
        print("nothing to scan; provide paths or --source/--sanitize-to", file=sys.stderr)
        return 2

    total_findings = sum(len(report.get("findings", [])) for report in reports)
    total_private = sum(len(report.get("private_paths_present", [])) for report in reports)
    output = {
        "scan_tier": args.tier,
        "sensitivity_tier": SENSITIVITY_TIER[args.tier],
        "public_share_safe": args.tier == TIER_PUBLIC and total_findings == 0 and total_private == 0,
        "reports": reports,
    }
    report_path = default_report_path(args)
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(output, indent=2, sort_keys=True))
    if args.strict and (total_findings or total_private):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
