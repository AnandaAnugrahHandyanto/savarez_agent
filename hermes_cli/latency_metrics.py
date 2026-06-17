from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from time import time


@dataclass(frozen=True, slots=True)
class LatencyMetricRow:
    """Sanitized one-call latency experiment record.

    Deliberately stores identifiers and aggregate counters only — never raw
    user/assistant text — so it is safe to append from API hook payloads.
    """

    arm: str
    turn_class: str
    latency_ms: float
    cache_hit: bool
    input_tokens: int
    estimated_cost_usd: float
    model: str
    error: bool
    tool_calls: int
    timestamp: float = 0.0
    session_id: str = ""
    platform: str = ""
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


@dataclass(frozen=True, slots=True)
class LatencySummaryRow:
    arm: str
    turn_class: str
    count: int
    p50_latency_ms: float
    p90_latency_ms: float
    p99_latency_ms: float
    cache_hit_percent: float
    mean_input_tokens: float
    estimated_cost_usd: float
    opus_percent: float
    error_rate_percent: float
    tool_call_rate_percent: float


def append_latency_metric(path: Path, row: LatencyMetricRow) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not row.timestamp:
        row = LatencyMetricRow(**{**asdict(row), "timestamp": time()})
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(row), sort_keys=True) + "\n")


def latency_metric_from_hook_payload(
    payload: dict[str, object],
    *,
    error: bool = False,
) -> LatencyMetricRow | None:
    """Build a sanitized metric row from API hook payload metadata.

    The hook payloads can contain request/response snapshots with message text;
    this helper intentionally ignores those fields and only extracts route
    decision metadata plus numeric counters needed for the comparison table.
    """
    decision = payload.get("routing_decision")
    if not isinstance(decision, dict) or decision.get("enabled") is not True:
        return None
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        usage = {}
    cache_read = _int_value(usage.get("cache_read_tokens"))
    cache_write = _int_value(usage.get("cache_write_tokens"))
    input_tokens = _int_value(usage.get("input_tokens"))
    return LatencyMetricRow(
        arm=str(decision.get("arm") or "control"),
        turn_class=str(decision.get("class") or "unknown"),
        latency_ms=round(_float_value(payload.get("api_duration")) * 1000, 4),
        cache_hit=cache_read > 0,
        input_tokens=input_tokens,
        estimated_cost_usd=_float_value(payload.get("estimated_cost_usd")),
        model=str(payload.get("model") or decision.get("effective_model") or ""),
        error=error,
        tool_calls=_int_value(payload.get("assistant_tool_call_count")),
        timestamp=_float_value(payload.get("ended_at")) or time(),
        session_id=str(payload.get("session_id") or ""),
        platform=str(payload.get("platform") or ""),
        output_tokens=_int_value(usage.get("output_tokens")),
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
    )


def summarize_latency_metrics(path: Path) -> dict[tuple[str, str], LatencySummaryRow]:
    groups: dict[tuple[str, str], list[LatencyMetricRow]] = {}
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = _row_from_json(json.loads(line))
            groups.setdefault((row.arm, row.turn_class), []).append(row)
    return {
        key: _summarize_group(key[0], key[1], rows)
        for key, rows in sorted(groups.items())
    }


def format_latency_summary(summary: dict[tuple[str, str], LatencySummaryRow]) -> str:
    header = (
        "arm | class | n | p50 | p90 | p99 | cache_hit% | "
        "mean_input | cost_usd | opus% | error% | tool_call%"
    )
    lines = [header]
    for row in summary.values():
        lines.append(
            " | ".join(
                [
                    row.arm,
                    row.turn_class,
                    str(row.count),
                    f"{row.p50_latency_ms:.1f}",
                    f"{row.p90_latency_ms:.1f}",
                    f"{row.p99_latency_ms:.1f}",
                    f"{row.cache_hit_percent:.1f}",
                    f"{row.mean_input_tokens:.1f}",
                    f"{row.estimated_cost_usd:.4f}",
                    f"{row.opus_percent:.1f}",
                    f"{row.error_rate_percent:.1f}",
                    f"{row.tool_call_rate_percent:.1f}",
                ]
            )
        )
    return "\n".join(lines)


def _row_from_json(raw: dict[str, object]) -> LatencyMetricRow:
    return LatencyMetricRow(
        arm=str(raw.get("arm") or ""),
        turn_class=str(raw.get("turn_class") or ""),
        latency_ms=_float_value(raw.get("latency_ms")),
        cache_hit=raw.get("cache_hit") is True,
        input_tokens=_int_value(raw.get("input_tokens")),
        estimated_cost_usd=_float_value(raw.get("estimated_cost_usd")),
        model=str(raw.get("model") or ""),
        error=raw.get("error") is True,
        tool_calls=_int_value(raw.get("tool_calls")),
        timestamp=_float_value(raw.get("timestamp")),
        session_id=str(raw.get("session_id") or ""),
        platform=str(raw.get("platform") or ""),
        output_tokens=_int_value(raw.get("output_tokens")),
        cache_read_tokens=_int_value(raw.get("cache_read_tokens")),
        cache_write_tokens=_int_value(raw.get("cache_write_tokens")),
    )


def _summarize_group(arm: str, turn_class: str, rows: list[LatencyMetricRow]) -> LatencySummaryRow:
    count = len(rows)
    latencies = sorted(row.latency_ms for row in rows)
    return LatencySummaryRow(
        arm=arm,
        turn_class=turn_class,
        count=count,
        p50_latency_ms=_percentile(latencies, 50),
        p90_latency_ms=_percentile(latencies, 90),
        p99_latency_ms=_percentile(latencies, 99),
        cache_hit_percent=_percent(row.cache_hit for row in rows),
        mean_input_tokens=round(sum(row.input_tokens for row in rows) / count, 4),
        estimated_cost_usd=round(sum(row.estimated_cost_usd for row in rows), 4),
        opus_percent=_percent("claude-opus" in row.model.lower() for row in rows),
        error_rate_percent=_percent(row.error for row in rows),
        tool_call_rate_percent=_percent(row.tool_calls > 0 for row in rows),
    )


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return round(values[0], 4)
    position = (len(values) - 1) * percentile / 100
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower
    return round(values[lower] * (1 - weight) + values[upper] * weight, 4)


def _percent(values: Iterable[bool]) -> float:
    collected = list(values)
    if not collected:
        return 0.0
    return round(100.0 * sum(1 for value in collected if value) / len(collected), 4)


def _float_value(raw: object) -> float:
    if isinstance(raw, bool) or raw is None:
        return 0.0
    if not isinstance(raw, (str, int, float)):
        return 0.0
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _int_value(raw: object) -> int:
    if isinstance(raw, bool) or raw is None:
        return 0
    if not isinstance(raw, (str, int, float)):
        return 0
    try:
        return int(raw)
    except ValueError:
        return 0
