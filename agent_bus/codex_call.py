"""Centralized codex-cli invocation with §9 throttle + stats persistence.

Any code that wants to call `codex exec` should go through `invoke_codex()`
so that:
  1. Rate limiting is enforced (protects Brian's subscription from bursts)
  2. Every call is tracked (count, latency, success/fail) for the dashboard
  3. Errors are normalized into a single return shape

Caller receives:
    CodexResult(ok=True,  stdout=..., duration_ms=..., attempt="codex")
    CodexResult(ok=False, error="throttled"|"timeout"|"non_zero"|"not_found",
                stderr=..., duration_ms=..., attempt="codex")

Env vars
--------
HERMES_CODEX_THROTTLE_MIN_INTERVAL_SEC  default 30
HERMES_CODEX_BURST_COUNT                default 3
HERMES_CODEX_BURST_WINDOW_SEC           default 60
HERMES_CODEX_STATS_PATH                 default ~/.hermes/codex-calls.jsonl
HERMES_CODEX_DISABLE                    if "1", every call returns throttled
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Deque, Optional

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_CALL_TIMES: Deque[float] = deque(maxlen=32)


@dataclass
class CodexResult:
    ok: bool
    stdout: str
    stderr: str
    duration_ms: float
    attempt: str  # caller tag e.g. "memory-extract" / "llm-summarize"
    error: Optional[str] = None  # "throttled" | "timeout" | "non_zero" | "not_found" | "disabled"
    returncode: Optional[int] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ts"] = datetime.now(timezone.utc).isoformat()
        return d


def _stats_path() -> Path:
    return Path(os.environ.get(
        "HERMES_CODEX_STATS_PATH",
        str(Path.home() / ".hermes" / "codex-calls.jsonl"),
    )).expanduser()


def _persist_stat(result: CodexResult) -> None:
    try:
        path = _stats_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            # Keep stderr short so file doesn't blow up
            row = result.to_dict()
            row["stderr"] = (row.get("stderr") or "")[:200]
            row["stdout_len"] = len(row.pop("stdout", "") or "")
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        # Rotate if over 5k lines
        try:
            with path.open("r", encoding="utf-8") as f:
                lines = f.readlines()
            if len(lines) > 5_000:
                with path.open("w", encoding="utf-8") as f:
                    f.writelines(lines[-2_500:])
        except Exception:
            pass
    except Exception as exc:  # pragma: no cover
        logger.debug("codex stat persist failed: %s", exc)


def _throttle_check() -> tuple[bool, Optional[str]]:
    """Returns (allowed, reason)."""
    if os.environ.get("HERMES_CODEX_DISABLE", "").strip() == "1":
        return False, "disabled via HERMES_CODEX_DISABLE=1"

    try:
        min_interval = float(os.environ.get("HERMES_CODEX_THROTTLE_MIN_INTERVAL_SEC", "30"))
        burst_count = int(os.environ.get("HERMES_CODEX_BURST_COUNT", "3"))
        burst_window = float(os.environ.get("HERMES_CODEX_BURST_WINDOW_SEC", "60"))
    except ValueError:
        min_interval, burst_count, burst_window = 30.0, 3, 60.0

    now = time.time()
    with _LOCK:
        # Drop entries outside burst window
        while _CALL_TIMES and now - _CALL_TIMES[0] > burst_window:
            _CALL_TIMES.popleft()

        if _CALL_TIMES and now - _CALL_TIMES[-1] < min_interval:
            remaining = round(min_interval - (now - _CALL_TIMES[-1]), 1)
            return False, f"min interval {min_interval}s, wait {remaining}s"

        if len(_CALL_TIMES) >= burst_count:
            return False, f"burst cap {burst_count} in last {burst_window}s"

    return True, None


def _throttle_record() -> None:
    with _LOCK:
        _CALL_TIMES.append(time.time())


def invoke_codex(
    prompt: str,
    *,
    attempt: str = "unknown",
    timeout_sec: int = 60,
    extra_args: Optional[list[str]] = None,
) -> CodexResult:
    """Run `codex exec` with throttle + stats. Always returns a CodexResult.

    Caller never sees raw exceptions; inspect result.ok / result.error.
    """
    start = time.time()

    # 0. CLI availability
    if not shutil.which("codex"):
        r = CodexResult(
            ok=False, stdout="", stderr="", duration_ms=0.0,
            attempt=attempt, error="not_found",
        )
        _persist_stat(r)
        return r

    # 1. Throttle
    allowed, reason = _throttle_check()
    if not allowed:
        r = CodexResult(
            ok=False, stdout="", stderr="", duration_ms=0.0,
            attempt=attempt, error=f"throttled:{reason}",
        )
        _persist_stat(r)
        logger.info("codex call throttled (attempt=%s): %s", attempt, reason)
        return r

    _throttle_record()

    # 2. Subprocess
    args = ["codex", "exec", "--skip-git-repo-check", "--sandbox", "read-only"]
    if extra_args:
        args += list(extra_args)
    args.append(prompt)

    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        r = CodexResult(
            ok=False, stdout="", stderr="", duration_ms=timeout_sec * 1000.0,
            attempt=attempt, error="timeout",
        )
        _persist_stat(r)
        return r
    except Exception as exc:
        r = CodexResult(
            ok=False, stdout="", stderr=str(exc)[:200],
            duration_ms=round((time.time() - start) * 1000.0, 2),
            attempt=attempt, error=f"exception:{type(exc).__name__}",
        )
        _persist_stat(r)
        return r

    duration_ms = round((time.time() - start) * 1000.0, 2)
    if proc.returncode != 0:
        r = CodexResult(
            ok=False, stdout=proc.stdout or "", stderr=proc.stderr or "",
            duration_ms=duration_ms, attempt=attempt,
            error="non_zero", returncode=proc.returncode,
        )
        _persist_stat(r)
        return r

    r = CodexResult(
        ok=True, stdout=proc.stdout or "", stderr=proc.stderr or "",
        duration_ms=duration_ms, attempt=attempt, returncode=0,
    )
    _persist_stat(r)
    return r


def summarize_stats(window_hours: int = 24) -> dict:
    """Aggregate stats for dashboard. Reads JSONL, returns counts + latencies."""
    path = _stats_path()
    if not path.exists():
        return {"exists": False, "total": 0, "by_attempt": {}, "by_error": {}}
    cutoff = time.time() - window_hours * 3600
    total = 0
    ok_count = 0
    durations: list[float] = []
    by_attempt: dict[str, int] = {}
    by_error: dict[str, int] = {}
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # Row doesn't carry epoch; ts is iso. Convert coarsely.
                ts_iso = row.get("ts")
                if ts_iso:
                    try:
                        row_epoch = datetime.fromisoformat(
                            ts_iso.replace("Z", "+00:00")
                        ).timestamp()
                    except Exception:
                        row_epoch = cutoff  # include if unparseable
                    if row_epoch < cutoff:
                        continue
                total += 1
                attempt = row.get("attempt") or "unknown"
                by_attempt[attempt] = by_attempt.get(attempt, 0) + 1
                if row.get("ok"):
                    ok_count += 1
                    dur = row.get("duration_ms")
                    if isinstance(dur, (int, float)):
                        durations.append(float(dur))
                else:
                    err = (row.get("error") or "unknown").split(":", 1)[0]
                    by_error[err] = by_error.get(err, 0) + 1
    except Exception as exc:  # pragma: no cover
        logger.debug("summarize_stats failed: %s", exc)

    avg = round(sum(durations) / len(durations), 2) if durations else None
    p95 = None
    if durations:
        s = sorted(durations)
        p95 = round(s[int(len(s) * 0.95)], 2) if len(s) > 1 else s[0]

    return {
        "exists": True,
        "window_hours": window_hours,
        "total": total,
        "ok": ok_count,
        "fail": total - ok_count,
        "avg_ms": avg,
        "p95_ms": p95,
        "by_attempt": by_attempt,
        "by_error": by_error,
    }


def _reset_for_test() -> None:
    """Test helper — clear internal throttle state."""
    with _LOCK:
        _CALL_TIMES.clear()
