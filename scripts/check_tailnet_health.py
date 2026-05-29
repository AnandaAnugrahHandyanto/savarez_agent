#!/usr/bin/env python3
"""Tailnet health check for Hermes VPS connectivity.

Checks:
- MagicDNS resolution for the peer
- Tailscale reachability to the peer
- Sensitive ports are not listening on non-loopback interfaces

Exit codes:
- 0: healthy
- 2: degraded / unsafe
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Iterable

DEFAULT_PEER = os.environ.get("TAILNET_PEER", "hermes-vps-2.tailfdd900.ts.net")
DEFAULT_PORTS = os.environ.get("SENSITIVE_PORTS", "3000,8642,9119")


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def run(cmd: list[str], timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)


def check_dns(peer: str) -> CheckResult:
    proc = run(["getent", "hosts", peer], timeout=10)
    if proc.returncode == 0 and proc.stdout.strip():
        return CheckResult("dns", True, proc.stdout.strip().splitlines()[0])
    return CheckResult("dns", False, (proc.stderr or proc.stdout or "no DNS result").strip())


def check_tailscale_ping(peer: str) -> CheckResult:
    proc = run(["tailscale", "ping", peer], timeout=30)
    output = (proc.stdout + proc.stderr).strip()
    if proc.returncode == 0 and "pong from" in output:
        first_line = output.splitlines()[0] if output.splitlines() else output
        return CheckResult("tailscale_ping", True, first_line)
    return CheckResult("tailscale_ping", False, output or f"tailscale ping exit {proc.returncode}")


def parse_ports(raw: str) -> list[int]:
    ports: list[int] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        ports.append(int(item))
    return ports


def check_port_binding(ports: Iterable[int]) -> list[CheckResult]:
    proc = run(["ss", "-ltn"], timeout=10)
    if proc.returncode != 0:
        return [CheckResult("socket_bindings", False, (proc.stderr or proc.stdout or "ss failed").strip())]

    lines = proc.stdout.splitlines()
    findings: list[CheckResult] = []
    for port in ports:
        matches = [line for line in lines if f":{port} " in line or line.rstrip().endswith(f":{port}")]
        if not matches:
            findings.append(CheckResult(f"port_{port}", True, "not listening"))
            continue

        unsafe = []
        for line in matches:
            parts = line.split()
            if len(parts) < 4:
                continue
            local_addr = parts[3]
            if local_addr.startswith("0.0.0.0:") or local_addr.startswith("[::]:"):
                unsafe.append(local_addr)
            elif not (local_addr.startswith("127.0.0.1:") or local_addr.startswith("[::1]:")):
                # Any non-loopback bind is treated as unsafe for these ports.
                unsafe.append(local_addr)

        if unsafe:
            findings.append(CheckResult(f"port_{port}", False, f"unsafe bind(s): {', '.join(sorted(set(unsafe)))}"))
        else:
            findings.append(CheckResult(f"port_{port}", True, "; ".join(matches)))

    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--peer", default=DEFAULT_PEER, help="Tailnet peer to probe (MagicDNS name or Tailscale IP)")
    parser.add_argument("--ports", default=DEFAULT_PORTS, help="Comma-separated sensitive ports to verify")
    args = parser.parse_args()

    results: list[CheckResult] = []
    results.append(check_dns(args.peer))
    results.append(check_tailscale_ping(args.peer))
    results.extend(check_port_binding(parse_ports(args.ports)))

    all_ok = all(result.ok for result in results)
    status = "healthy" if all_ok else "degraded"
    print(status)
    for result in results:
        marker = "ok" if result.ok else "fail"
        print(f"- {result.name}: {marker} — {result.detail}")

    return 0 if all_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
