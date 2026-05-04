#!/usr/bin/env python3
"""Read-only Hindsight/Gateway RAM and latency benchmark.

Collects process memory from /proc, Hindsight HTTP endpoint latency, and optional
Prometheus metrics. The default mode is read-only and does not run recall or any
other operation with side effects. A recall latency command runs only when the
caller explicitly supplies --recall-command.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "http://127.0.0.1:9177"
DEFAULT_TIMEOUT = 3.0
_ENDPOINTS = ("health", "version", "metrics")
_DURATION_SUFFIXES = ("_duration_seconds", "_latency_seconds", "_seconds")
_PROM_SAMPLE_RE = re.compile(
    r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(?P<labels>[^}]*)\})?\s+"
    r"(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*$"
)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _kb_to_bytes(value: int) -> int:
    return value * 1024


def parse_meminfo(text: str) -> dict[str, int]:
    """Parse /proc/meminfo into byte-valued fields."""
    result: dict[str, int] = {}
    for line in text.splitlines():
        if not line or ":" not in line:
            continue
        key, rest = line.split(":", 1)
        parts = rest.strip().split()
        if not parts:
            continue
        try:
            value = int(parts[0])
        except ValueError:
            continue
        if len(parts) > 1 and parts[1].lower() == "kb":
            value = _kb_to_bytes(value)
        result[f"{key}_bytes"] = value
    return result


def read_system_meminfo(path: str = "/proc/meminfo") -> dict[str, int]:
    try:
        return parse_meminfo(Path(path).read_text(encoding="utf-8", errors="replace"))
    except OSError as exc:
        return {"error": str(exc)}  # type: ignore[return-value]


def parse_smaps_rollup(text: str) -> dict[str, int]:
    """Parse /proc/<pid>/smaps_rollup memory fields into bytes."""
    mapping = {"Rss": "rss_bytes", "Pss": "pss_bytes", "Swap": "swap_bytes"}
    result: dict[str, int] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        if key not in mapping:
            continue
        parts = rest.strip().split()
        if not parts:
            continue
        try:
            value = int(parts[0])
        except ValueError:
            continue
        if len(parts) > 1 and parts[1].lower() == "kb":
            value = _kb_to_bytes(value)
        result[mapping[key]] = value
    return result


def parse_status_memory(text: str) -> dict[str, int]:
    mapping = {"VmRSS": "rss_bytes", "VmSwap": "swap_bytes"}
    result: dict[str, int] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        if key not in mapping:
            continue
        parts = rest.strip().split()
        if not parts:
            continue
        try:
            value = int(parts[0])
        except ValueError:
            continue
        if len(parts) > 1 and parts[1].lower() == "kb":
            value = _kb_to_bytes(value)
        result[mapping[key]] = value
    return result


def parse_prometheus_metrics(text: str) -> dict[str, Any]:
    """Extract process RSS and operation duration summaries from Prometheus text."""
    parsed: dict[str, Any] = {"duration_metrics": {}}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _PROM_SAMPLE_RE.match(line)
        if not match:
            continue
        name = match.group("name")
        try:
            value = float(match.group("value"))
        except ValueError:
            continue

        if name == "process_resident_memory_bytes":
            parsed["process_resident_memory_bytes"] = value

        base_name = name
        stat = "value"
        for suffix in ("_sum", "_count", "_bucket"):
            if name.endswith(suffix):
                base_name = name[: -len(suffix)]
                stat = suffix[1:]
                break
        if any(base_name.endswith(suffix) for suffix in _DURATION_SUFFIXES):
            metric = parsed["duration_metrics"].setdefault(base_name, {})
            if stat == "bucket":
                metric.setdefault("buckets", []).append(
                    {"labels": match.group("labels") or "", "value": value}
                )
            else:
                metric[stat] = value
    return parsed


def read_cmdline(pid_dir: Path) -> list[str]:
    raw = (pid_dir / "cmdline").read_bytes()
    return [part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part]


def categorize_process(cmdline: list[str]) -> str | None:
    joined = " ".join(cmdline).lower()
    if not joined:
        return None

    executable = Path(cmdline[0]).name.lower() if cmdline else ""
    tokens = [Path(part).name.lower() for part in cmdline]

    # Do not count this benchmark (or a shell running it) as a Hindsight process
    # merely because the script/report filename contains "hindsight".
    if "hindsight_gateway_benchmark.py" in joined:
        return None

    if "gateway/run.py" in joined or "gateway.run" in joined:
        return "gateway"
    if re.search(r"\bhermes(?:-agent)?\b.*\bgateway\b", joined):
        return "gateway"

    if any(token.startswith("hindsight") for token in tokens):
        return "hindsight"
    if "-m" in cmdline and any(part.lower().startswith("hindsight") for part in cmdline):
        return "hindsight"
    if executable.startswith("postgres") and "hindsight" in joined:
        return "hindsight"
    if "/hindsight" in joined or "hindsight-embed" in joined:
        return "hindsight"
    return None


def _read_process_memory(pid_dir: Path) -> tuple[dict[str, int], str]:
    smaps = pid_dir / "smaps_rollup"
    if smaps.exists():
        try:
            return parse_smaps_rollup(smaps.read_text(encoding="utf-8", errors="replace")), "smaps_rollup"
        except OSError:
            pass
    try:
        return parse_status_memory((pid_dir / "status").read_text(encoding="utf-8", errors="replace")), "status"
    except OSError as exc:
        return {"error": str(exc)}, "error"  # type: ignore[return-value]


def collect_processes(proc_root: str = "/proc") -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {"hindsight": [], "gateway": [], "other": []}
    root = Path(proc_root)
    try:
        entries = list(root.iterdir())
    except OSError as exc:
        groups["other"].append({"error": str(exc)})
        return groups

    for pid_dir in entries:
        if not pid_dir.name.isdigit():
            continue
        try:
            cmdline = read_cmdline(pid_dir)
        except OSError:
            continue
        category = categorize_process(cmdline)
        if category is None:
            continue
        memory, source = _read_process_memory(pid_dir)
        item: dict[str, Any] = {
            "pid": int(pid_dir.name),
            "cmdline": cmdline,
            "memory_source": source,
        }
        item.update(memory)
        groups[category].append(item)
    return groups


def fetch_endpoint(base_url: str, endpoint: str, timeout: float) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    started = time.perf_counter()
    request = Request(url, headers={"Accept": "text/plain, application/json;q=0.9, */*;q=0.1"})
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec: local configurable benchmark URL
            body = response.read(2_000_000).decode("utf-8", errors="replace")
            status = int(getattr(response, "status", response.getcode()))
            headers = dict(response.headers.items())
            ok = 200 <= status < 400
    except HTTPError as exc:
        body = exc.read(200_000).decode("utf-8", errors="replace")
        status = exc.code
        headers = dict(exc.headers.items()) if exc.headers else {}
        ok = False
    except (OSError, URLError, TimeoutError) as exc:
        return {
            "ok": False,
            "error": str(exc),
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        }
    return {
        "ok": ok,
        "status": status,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "content_type": headers.get("Content-Type") or headers.get("content-type"),
        "body": body,
    }


def fetch_hindsight(base_url: str, timeout: float) -> dict[str, Any]:
    return {endpoint: fetch_endpoint(base_url, endpoint, timeout) for endpoint in _ENDPOINTS}


def run_recall_command(command: str, timeout: float) -> dict[str, Any]:
    argv = shlex.split(command)
    if not argv:
        return {"enabled": True, "ok": False, "error": "empty recall command"}
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "enabled": True,
            "ok": False,
            "error": str(exc),
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        }
    return {
        "enabled": True,
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "stdout_preview": completed.stdout[:4000],
        "stderr_preview": completed.stderr[:4000],
    }


def build_report(
    *,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    now_func: Callable[[], str] = utc_timestamp,
    meminfo_func: Callable[[], dict[str, Any]] = read_system_meminfo,
    processes_func: Callable[[], dict[str, list[dict[str, Any]]]] = collect_processes,
    http_func: Callable[[str, float], dict[str, Any]] = fetch_hindsight,
    recall_func: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    http = http_func(base_url, timeout)
    metrics_body = http.get("metrics", {}).get("body") if isinstance(http.get("metrics"), dict) else None
    prometheus = parse_prometheus_metrics(metrics_body) if isinstance(metrics_body, str) else {"duration_metrics": {}}
    return {
        "schema_version": 1,
        "timestamp": now_func(),
        "read_only": recall_func is None,
        "system_memory": meminfo_func(),
        "processes": processes_func(),
        "hindsight": {
            "base_url": base_url,
            "endpoints": http,
            "prometheus": prometheus,
        },
        "recall": recall_func() if recall_func is not None else {"enabled": False},
    }


def write_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"Hindsight base URL (default: {DEFAULT_BASE_URL})")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="HTTP command timeout seconds")
    parser.add_argument("--output", type=Path, help="Optional path to also write the JSON report")
    parser.add_argument(
        "--recall-command",
        help="Explicitly run this command and measure latency. Omitted by default to avoid recall side effects.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    recall_func = None
    if args.recall_command:
        recall_func = lambda: run_recall_command(args.recall_command, args.timeout)  # noqa: E731
    report = build_report(base_url=args.base_url, timeout=args.timeout, recall_func=recall_func)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    sys.stdout.write(rendered)
    if args.output:
        write_report(report, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
