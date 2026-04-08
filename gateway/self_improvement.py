"""Gateway self-improvement telemetry, signatures, and adaptive policy tuning."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


class GatewaySelfImprover:
    """Persist gateway telemetry and adapt bounded runtime thresholds."""

    # Safety boundary: self-improvement is config-threshold tuning only.
    # No source-code mutation is ever performed by this subsystem.
    AUTO_REMEDIATION_SCOPE: Dict[str, Any] = {
        "mode": "config_thresholds_only",
        "auto_applied": [
            "agent_timeout_s",
            "reconnect_max_attempts",
            "reconnect_backoff_cap_s",
            "history_hygiene_threshold",
        ],
        "requires_explicit_approval": ["any_source_code_change"],
    }

    DEFAULT_POLICY: Dict[str, float] = {
        "agent_timeout_s": 1800.0,
        "reconnect_max_attempts": 20.0,
        "reconnect_backoff_cap_s": 300.0,
        "history_hygiene_threshold": 0.85,
    }

    def __init__(self, hermes_home: Path):
        self._dir = Path(hermes_home)
        self._events_path = self._dir / "gateway_telemetry.jsonl"
        self._signatures_path = self._dir / "gateway_failure_signatures.json"
        self._policy_path = self._dir / "gateway_adaptive_policy.json"
        self._policy: Dict[str, float] = self._load_policy()

    @property
    def policy(self) -> Dict[str, float]:
        return dict(self._policy)

    def record_event(self, kind: str, **payload: Any) -> None:
        event = {"ts": int(time.time()), "kind": kind}
        event.update(payload)
        self._events_path.parent.mkdir(parents=True, exist_ok=True)
        with self._events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def record_failure_signature(self, category: str, message: str, platform: Optional[str] = None) -> str:
        signature = self._normalize_signature(category=category, message=message, platform=platform)
        data = self._load_json(self._signatures_path, default={})
        now = int(time.time())

        row = data.get(signature)
        if not isinstance(row, dict):
            row = {
                "count": 0,
                "first_seen": now,
                "last_seen": now,
                "category": category,
                "platform": platform,
                "examples": [],
            }

        row["count"] = int(row.get("count", 0)) + 1
        row["last_seen"] = now
        examples = row.get("examples") if isinstance(row.get("examples"), list) else []
        sample = (message or "")[:280]
        if sample and sample not in examples:
            examples.append(sample)
        row["examples"] = examples[-3:]
        data[signature] = row

        self._write_json(self._signatures_path, data)
        return signature

    def evaluate_and_update(self) -> Dict[str, Any]:
        events = self._load_recent_events(max_events=4000, lookback_seconds=7 * 24 * 3600)
        if not events:
            return {"updated": False, "reason": "no_events"}

        current = dict(self._policy)
        next_policy = dict(current)

        turn_durations = [
            float(e.get("duration_s"))
            for e in events
            if e.get("kind") == "agent_turn" and isinstance(e.get("duration_s"), (int, float))
        ]
        timeout_events = [
            e for e in events
            if e.get("kind") == "agent_failure" and e.get("reason") == "inactivity_timeout"
        ]

        reconnect_success = sum(1 for e in events if e.get("kind") == "reconnect_result" and e.get("success") is True)
        reconnect_fail = sum(1 for e in events if e.get("kind") == "reconnect_result" and e.get("success") is False)

        hygiene_fail = sum(1 for e in events if e.get("kind") == "history_hygiene" and e.get("status") == "failed")

        p95_turn = self._percentile(turn_durations, 95) if turn_durations else None

        timeout_s = float(next_policy["agent_timeout_s"])
        if len(timeout_events) >= 3:
            timeout_s += 300
        elif len(timeout_events) == 0 and p95_turn is not None and p95_turn < 45:
            timeout_s -= 60
        next_policy["agent_timeout_s"] = _clamp(timeout_s, 600, 7200)

        backoff_cap = float(next_policy["reconnect_backoff_cap_s"])
        max_attempts = float(next_policy["reconnect_max_attempts"])
        total_reconnect = reconnect_success + reconnect_fail
        if total_reconnect >= 6:
            fail_ratio = reconnect_fail / total_reconnect
            if fail_ratio > 0.6:
                backoff_cap += 60
                max_attempts += 2
            elif fail_ratio < 0.25:
                backoff_cap -= 30
                max_attempts -= 1
        next_policy["reconnect_backoff_cap_s"] = _clamp(backoff_cap, 120, 1800)
        next_policy["reconnect_max_attempts"] = _clamp(max_attempts, 5, 60)

        hyg = float(next_policy["history_hygiene_threshold"])
        if hygiene_fail >= 3:
            hyg -= 0.05
        elif hygiene_fail == 0 and len(events) >= 40:
            hyg += 0.01
        next_policy["history_hygiene_threshold"] = _clamp(hyg, 0.70, 0.95)

        changed = any(abs(float(next_policy[k]) - float(current[k])) > 1e-9 for k in self.DEFAULT_POLICY)
        if not changed:
            return {"updated": False, "reason": "stable", "policy": dict(self._policy)}

        self._policy = next_policy
        payload = {
            "updated_at": int(time.time()),
            "policy": next_policy,
            "summary": {
                "events_considered": len(events),
                "p95_turn_seconds": p95_turn,
                "timeouts": len(timeout_events),
                "reconnect_success": reconnect_success,
                "reconnect_fail": reconnect_fail,
                "hygiene_fail": hygiene_fail,
            },
            "auto_remediation_scope": dict(self.AUTO_REMEDIATION_SCOPE),
        }
        self._write_json(self._policy_path, payload)
        return {"updated": True, "policy": dict(next_policy), "summary": payload["summary"]}

    def _load_policy(self) -> Dict[str, float]:
        data = self._load_json(self._policy_path, default={})
        raw_policy = data.get("policy") if isinstance(data, dict) else {}
        policy = dict(self.DEFAULT_POLICY)
        if isinstance(raw_policy, dict):
            for key in policy:
                val = raw_policy.get(key)
                if isinstance(val, (int, float)):
                    policy[key] = float(val)
        return policy

    def _load_recent_events(self, max_events: int, lookback_seconds: int) -> List[Dict[str, Any]]:
        if not self._events_path.exists():
            return []
        cutoff = int(time.time()) - int(lookback_seconds)
        rows: List[Dict[str, Any]] = []
        with self._events_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(obj, dict):
                    continue
                ts = obj.get("ts")
                if isinstance(ts, (int, float)) and int(ts) >= cutoff:
                    rows.append(obj)
        if len(rows) > max_events:
            rows = rows[-max_events:]
        return rows

    @staticmethod
    def _normalize_signature(category: str, message: str, platform: Optional[str]) -> str:
        base = str(message or "").lower()
        base = re.sub(r"\b\d+\b", "<n>", base)
        base = re.sub(r"\s+", " ", base).strip()
        base = base[:180]
        prefix = f"{category}:{platform or 'any'}:"
        return prefix + base

    @staticmethod
    def _load_json(path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        tmp.replace(path)

    @staticmethod
    def _percentile(values: List[float], pct: int) -> Optional[float]:
        if not values:
            return None
        values = sorted(values)
        if len(values) == 1:
            return values[0]
        rank = (pct / 100.0) * (len(values) - 1)
        low = int(rank)
        high = min(low + 1, len(values) - 1)
        frac = rank - low
        return values[low] * (1.0 - frac) + values[high] * frac
