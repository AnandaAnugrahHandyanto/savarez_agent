#!/usr/bin/env python3
"""Real-browser UAT/regression harness for the Acta dashboard.

This intentionally uses an actual Chromium/Chrome binary instead of DOM-only
unit tests. It catches regressions where the generated HTML exists but the
browser-rendered document no longer preserves Acta's operator feed contract.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


DEV_ROW_RE = re.compile(r"<section\b(?=[^>]*\bclass=\"[^\"]*brief-row)(?=[^>]*\bdata-feed-lane=\"dev\")[\s\S]*?</section>", re.I)
DAILY_ROW_RE = re.compile(r"<section\b(?=[^>]*\bclass=\"[^\"]*brief-row)(?=[^>]*\bdata-feed-lane=\"daily\")[\s\S]*?</section>", re.I)
DEV_JOB_RE = re.compile(
    r"startup sprint|sprint ceo|self-healing sentinel|user[- ]testing sweep|qa pipeline|qa canary|operator sprint|security scan|app security|vesta import|vesta startup|acta startup|minerva startup|praetor startup",
    re.I,
)


@dataclass
class BrowserResult:
    url: str
    dom: str
    screenshot: Path
    browser_path: Path


def _agent_browser_command() -> list[str]:
    env = os.environ.get("ACTA_UAT_AGENT_BROWSER")
    if env:
        return [env]
    direct = shutil.which("agent-browser")
    if direct:
        return [direct]
    npx = shutil.which("npx")
    if npx:
        return [npx, "agent-browser"]
    raise RuntimeError("agent-browser CLI not found. Run `npm install` or install browser tools, then retry.")


def _browser_identity(command: list[str]) -> Path:
    # agent-browser owns browser discovery and launches the installed Chrome for Testing.
    return Path(" ".join(command))


def _target_url(args: argparse.Namespace) -> str:
    if bool(args.html) == bool(args.url):
        raise SystemExit("Pass exactly one of --html or --url")
    if args.url:
        parsed = urlparse(args.url)
        if parsed.scheme not in {"http", "https"}:
            raise SystemExit("--url must be http(s)")
        if parsed.username or parsed.password:
            raise SystemExit("--url must not include userinfo")
        try:
            parsed.port
        except ValueError as exc:
            raise SystemExit(f"Invalid --url port: {exc}") from exc
        if not parsed.hostname:
            raise SystemExit("--url must include a host")
        return args.url
    html_path = Path(args.html).expanduser().resolve()
    if not html_path.exists():
        raise SystemExit(f"HTML file not found: {html_path}")
    return html_path.as_uri()


def _report_url(url: str) -> str:
    """Return a report-safe URL without credentials, query strings, or fragments."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return url
    if parsed.username or parsed.password:
        raise ValueError("Report URL must not include userinfo")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"Invalid report URL port: {exc}") from exc
    if not parsed.hostname:
        raise ValueError("Report URL must include a host")
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = f"{host}:{port}" if port is not None else host
    return f"{parsed.scheme}://{netloc}{parsed.path or '/'}"


def _run_agent_browser(command: list[str], args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*command, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
    )


def _run_chrome(url: str, artifact_dir: Path, timeout: int) -> BrowserResult:
    command = _agent_browser_command()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    screenshot = artifact_dir / "acta-uat.png"
    try:
        opened = _run_agent_browser(command, ["open", url], timeout)
        if opened.returncode != 0:
            raise RuntimeError(f"agent-browser open failed:\n{opened.stdout[-4000:]}")
        # Give any inline read-state script a browser turn before collecting DOM.
        _run_agent_browser(command, ["wait", "250"], timeout)
        dom_result = _run_agent_browser(command, ["eval", "document.documentElement.outerHTML"], timeout)
        if dom_result.returncode != 0:
            raise RuntimeError(f"agent-browser DOM eval failed:\n{dom_result.stdout[-4000:]}")
        shot = _run_agent_browser(command, ["screenshot", str(screenshot)], timeout)
        if shot.returncode != 0:
            raise RuntimeError(f"agent-browser screenshot failed:\n{shot.stdout[-4000:]}")
    finally:
        _run_agent_browser(command, ["close", "--all"], max(5, min(timeout, 10)))

    raw_dom = dom_result.stdout.strip()
    try:
        dom = json.loads(raw_dom)
    except json.JSONDecodeError:
        dom = raw_dom
    if not screenshot.exists():
        raise RuntimeError("Browser rendered DOM but did not create the expected screenshot artifact")
    return BrowserResult(url=url, dom=dom, screenshot=screenshot, browser_path=_browser_identity(command))


def _section_index(dom: str, text: str) -> int:
    return dom.casefold().find(text.casefold())


def _validate_feed_contract(dom: str) -> list[str]:
    failures: list[str] = []
    if "Sign in to Acta" in dom or "Acta access token" in dom:
        return ["Acta sign-in wall rendered; pass a local --html artifact or validate with authenticated browser storage"]
    output_streams = _section_index(dom, "Output Streams")
    daily = _section_index(dom, "Daily life feed")
    dev = _section_index(dom, "Development sprint cycles")
    if output_streams < 0:
        failures.append("Output Streams heading is missing")
    if daily < 0:
        failures.append("Daily life feed section is missing")
    if dev < 0:
        failures.append("Development sprint cycles section is missing")
    if daily >= 0 and dev >= 0 and daily > dev:
        failures.append("Daily life feed must render before Development sprint cycles")
    daily_rows = DAILY_ROW_RE.findall(dom)
    dev_rows = DEV_ROW_RE.findall(dom)
    if not daily_rows:
        failures.append("No browser-rendered daily feed rows found")
    if not dev_rows:
        failures.append("No browser-rendered development feed rows found")
    daily_text = "\n".join(daily_rows)
    dev_text = "\n".join(dev_rows)
    if DEV_JOB_RE.search(daily_text):
        failures.append("Development sprint output is commingled into Daily life feed")
    if not DEV_JOB_RE.search(dev_text):
        failures.append("Development sprint feed has no recognized sprint/QA/security rows")
    if "lane-chip" not in dom:
        failures.append("Lane chips are missing from rendered rows")
    return failures


def run(args: argparse.Namespace) -> int:
    artifact_dir = Path(args.artifact_dir).expanduser().resolve()
    url = _target_url(args)
    try:
        result = _run_chrome(url, artifact_dir, args.timeout)
        failures = _validate_feed_contract(result.dom)
    except Exception as exc:  # noqa: BLE001 - CLI harness should print actionable failure text.
        print("FAIL Acta browser UAT")
        print(str(exc))
        return 1

    report = {
        "url": _report_url(result.url),
        "browser": str(result.browser_path),
        "screenshot": str(result.screenshot),
        "daily_rows": len(DAILY_ROW_RE.findall(result.dom)),
        "dev_rows": len(DEV_ROW_RE.findall(result.dom)),
        "failures": failures,
    }
    report_path = artifact_dir / "acta-uat-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    if failures:
        print("FAIL Acta browser UAT")
        for failure in failures:
            print(f"- {failure}")
        print(f"Screenshot: {result.screenshot}")
        print(f"Report: {report_path}")
        return 1

    print("PASS Acta browser UAT")
    print(f"Daily rows: {report['daily_rows']}")
    print(f"Development rows: {report['dev_rows']}")
    print(f"Screenshot: {result.screenshot}")
    print(f"Report: {report_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Real-browser UAT harness for Acta dashboard feed separation")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--html", help="Path to a generated Acta dashboard HTML file")
    target.add_argument("--url", help="Published Acta URL to validate")
    parser.add_argument("--artifact-dir", default=".hermes/uat/acta", help="Directory for screenshot and JSON report")
    parser.add_argument("--timeout", type=int, default=30, help="Chrome render timeout in seconds")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
