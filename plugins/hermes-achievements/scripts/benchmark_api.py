"""Local benchmark for the Achievements plugin's hot endpoints.

Times ``GET /api/plugins/hermes-achievements/achievements`` against an already
running Hermes dashboard. Reports cache-busted/first-hit and warm (subsequent
cache-friendly hit) latency in milliseconds. It does not clear server-side
snapshot files; for a true cold-cache benchmark, clear/restart the dashboard
outside this script and then run the script immediately.

Safe by design:
* never starts, stops, or restarts any Hermes service
* does not write anywhere outside stdout
* only sends GET requests (no /rescan)
* default 3 cache-busted/first-hit + 3 warm runs

Usage examples::

    # against a local dashboard on the default port:
    python plugins/hermes-achievements/scripts/benchmark_api.py

    # against an explicit base URL with an auth token from the environment:
    HERMES_SESSION_TOKEN=... python plugins/hermes-achievements/scripts/benchmark_api.py \\
        --base-url http://127.0.0.1:9119

    # cache-busted first-hit vs warm cache-friendly comparison (3 each):
    python plugins/hermes-achievements/scripts/benchmark_api.py \\
        --cache-busted-runs 3 --warm-runs 3 --token "$HERMES_SESSION_TOKEN"

The token is sent as ``X-Hermes-Session-Token`` so the dashboard's
session-auth middleware accepts the request. If neither ``--token`` nor
``HERMES_SESSION_TOKEN`` is provided, requests are sent unauthenticated.
"""
from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from typing import Iterable, List, Optional, Tuple
from urllib import error, request
from urllib.parse import urlparse

DEFAULT_BASE_URL = "http://127.0.0.1:9119"
ENDPOINT = "/api/plugins/hermes-achievements/achievements"


def _build_request(base_url: str, token: Optional[str], cache_buster: Optional[int]) -> request.Request:
    url = base_url.rstrip("/") + ENDPOINT
    if cache_buster is not None:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}_cb={cache_buster}"
    req = request.Request(url, method="GET")
    req.add_header("Accept", "application/json")
    if token:
        req.add_header("X-Hermes-Session-Token", token)
    return req


def _time_request(req: request.Request, timeout: float) -> Tuple[float, int, int]:
    start = time.perf_counter()
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            status = resp.status
    except error.HTTPError as exc:  # 4xx/5xx still gives timing data
        body = exc.read() if hasattr(exc, "read") else b""
        status = exc.code
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return elapsed_ms, status, len(body)


def _summarize(label: str, timings_ms: Iterable[float]) -> str:
    timings = list(timings_ms)
    if not timings:
        return f"{label}: (no samples)"
    if len(timings) == 1:
        return f"{label}: {timings[0]:.1f} ms (n=1)"
    return (
        f"{label}: min={min(timings):.1f} ms · median={statistics.median(timings):.1f} ms · "
        f"max={max(timings):.1f} ms (n={len(timings)})"
    )


def run_bench(
    base_url: str,
    token: Optional[str],
    cold_runs: int,
    warm_runs: int,
    timeout: float,
    cache_bust: bool,
) -> int:
    print(f"benchmark target: {base_url}{ENDPOINT}")
    print(f"auth header: {'X-Hermes-Session-Token=***' if token else '(none)'}")
    parsed = urlparse(base_url)
    host = (parsed.hostname or "").lower()
    is_loopback = host in {"127.0.0.1", "localhost", "::1"}
    if token and parsed.scheme != "https" and not is_loopback:
        print(
            "warning: sending X-Hermes-Session-Token to a non-HTTPS, non-loopback URL",
            file=sys.stderr,
        )
    print()

    cold_timings: List[float] = []
    warm_timings: List[float] = []

    for i in range(cold_runs):
        cb = int(time.time() * 1000) + i if cache_bust else None
        req = _build_request(base_url, token, cb)
        try:
            elapsed, status, size = _time_request(req, timeout)
        except Exception as exc:
            print(f"cache-busted run {i + 1}: ERROR {exc!r}", file=sys.stderr)
            return 2
        cold_timings.append(elapsed)
        print(f"cache-busted run {i + 1}: {elapsed:.1f} ms (HTTP {status}, {size} bytes)")

    for i in range(warm_runs):
        req = _build_request(base_url, token, None)
        try:
            elapsed, status, size = _time_request(req, timeout)
        except Exception as exc:
            print(f"warm run {i + 1}: ERROR {exc!r}", file=sys.stderr)
            return 2
        warm_timings.append(elapsed)
        print(f"warm run {i + 1}: {elapsed:.1f} ms (HTTP {status}, {size} bytes)")

    print()
    print(_summarize("cache-busted", cold_timings))
    print(_summarize("warm", warm_timings))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default=os.environ.get("HERMES_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--token", default=os.environ.get("HERMES_SESSION_TOKEN") or None)
    parser.add_argument("--cache-busted-runs", "--cold-runs", dest="cold_runs", type=int, default=3, help="cache-busted/first-hit runs")
    parser.add_argument("--warm-runs", type=int, default=3, help="warm runs (cache-friendly)")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument(
        "--no-cache-bust",
        action="store_true",
        help="Skip the cache-buster query param on cache-busted/first-hit runs (only useful when the dashboard "
             "doesn't gate cache keys on the query string).",
    )
    args = parser.parse_args(argv)
    return run_bench(
        base_url=args.base_url,
        token=args.token,
        cold_runs=max(0, args.cold_runs),
        warm_runs=max(0, args.warm_runs),
        timeout=args.timeout,
        cache_bust=not args.no_cache_bust,
    )


if __name__ == "__main__":
    raise SystemExit(main())
