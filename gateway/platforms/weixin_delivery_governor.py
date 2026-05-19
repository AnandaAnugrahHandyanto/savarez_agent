"""Weixin outbound delivery governor.

The governor is intentionally dependency-free so the bridge can ship it as the
canonical implementation and Hermes runtime deployments can vendor or import it
without pulling in an external scheduler stack.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


HEALTHY = "HEALTHY"
OPEN = "OPEN"
HALF_OPEN = "HALF_OPEN"
DRAINING = "DRAINING"

PRIORITY_VALUES = {
    "critical": 100,
    "high": 75,
    "normal": 50,
    "low": 25,
}

RATE_LIMIT_MARKERS = (
    "ret=-2",
    "errcode=-2",
    "rate limited",
    "ratelimited",
    "too many requests",
    "sendmessage rate limited",
)

RAW_ERROR_MARKERS = (
    "ret=-2",
    "errcode=-2",
    "traceback",
    "runtimeerror",
    "httperror",
    "http 5",
    "http 429",
)


@dataclass(frozen=True)
class WeixinDeliveryGovernorConfig:
    enabled: bool = True
    state_dir: Path | str | None = None
    window_seconds: int = 60
    initial_capacity: int = 3
    min_capacity: int = 1
    max_capacity: int = 20
    max_flush_per_window: int = 3
    queue_max_size: int = 500
    base_backoff_seconds: int = 300
    max_backoff_seconds: int = 3600
    backoff_multiplier: float = 2.0
    jitter_seconds: int = 15
    lock_timeout_seconds: float = 2.0
    lock_stale_seconds: float = 30.0
    default_ttl_seconds: int = 7200
    low_priority_ttl_seconds: int = 1800
    high_priority_ttl_seconds: int = 21600
    critical_ttl_seconds: int = 86400
    hash_salt: str = ""

    def resolved_state_dir(self) -> Path:
        if self.state_dir is not None:
            return Path(self.state_dir).expanduser()
        base = os.getenv("WEIXIN_DELIVERY_GOVERNOR_STATE_DIR", "").strip()
        if base:
            return Path(base).expanduser()
        hermes_home = os.getenv("HERMES_HOME", "").strip()
        if hermes_home:
            return Path(hermes_home).expanduser() / "weixin-delivery-governor"
        return Path.home() / ".hermes" / "weixin-delivery-governor"


@dataclass(frozen=True)
class GovernorDecision:
    allowed: bool
    queued: bool
    reason: str
    status: str
    delivery_id: str | None = None
    queue_size: int = 0
    remaining: int = 0
    capacity: int = 0
    next_available_at: float | None = None
    target_hash: str | None = None
    friendly_text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "queued": self.queued,
            "reason": self.reason,
            "status": self.status,
            "delivery_id": self.delivery_id,
            "queue_size": self.queue_size,
            "remaining": self.remaining,
            "capacity": self.capacity,
            "next_available_at": self.next_available_at,
            "target_hash": self.target_hash,
            "friendly_text": self.friendly_text,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class QueuedDelivery:
    delivery_id: str
    message: str
    priority: str
    source: str
    target_hash: str
    created_at: float
    expires_at: float
    attempts: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QueuedDelivery":
        return cls(
            delivery_id=str(data.get("delivery_id") or ""),
            message=str(data.get("message") or ""),
            priority=normalize_priority(data.get("priority")),
            source=str(data.get("source") or "unknown"),
            target_hash=str(data.get("target_hash") or ""),
            created_at=float(data.get("created_at") or 0.0),
            expires_at=float(data.get("expires_at") or 0.0),
            attempts=int(data.get("attempts") or 0),
            metadata=dict(data.get("metadata") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "delivery_id": self.delivery_id,
            "message": self.message,
            "priority": self.priority,
            "source": self.source,
            "target_hash": self.target_hash,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "attempts": self.attempts,
            "metadata": self.metadata,
        }


class WeixinDeliveryGovernor:
    """File-backed rate-limit governor for Weixin/iLink outbound delivery."""

    def __init__(self, config: WeixinDeliveryGovernorConfig | None = None) -> None:
        self.config = config or WeixinDeliveryGovernorConfig()
        self.state_dir = self.config.resolved_state_dir()
        self.state_file = self.state_dir / "state.json"
        self.lock_file = self.state_dir / "state.lock"

    def admit_or_queue(
        self,
        message: str,
        *,
        target_id: str,
        priority: str = "normal",
        source: str = "unknown",
        metadata: dict[str, Any] | None = None,
        now: float | None = None,
    ) -> GovernorDecision:
        current_time = _now(now)
        priority_name = normalize_priority(priority)
        target_hash = self.hash_target(target_id)
        if not self.config.enabled:
            return GovernorDecision(
                allowed=True,
                queued=False,
                reason="governor_disabled",
                status=HEALTHY,
                remaining=self.config.max_capacity,
                capacity=self.config.max_capacity,
                target_hash=target_hash,
            )

        with _StateLock(self.lock_file, self.config.lock_timeout_seconds, self.config.lock_stale_seconds):
            state = self._load_state(current_time)
            state = self._refresh_state(state, current_time)
            status = self._effective_status(state, current_time)
            if self._can_attempt(state, status):
                state["status"] = status if status == HALF_OPEN else (DRAINING if state.get("queue") else HEALTHY)
                state["attempts_in_window"] = int(state.get("attempts_in_window") or 0) + 1
                if status == HALF_OPEN:
                    state["half_open_in_flight"] = True
                self._save_state(state)
                return self._decision(
                    state,
                    allowed=True,
                    queued=False,
                    reason="allowed",
                    target_hash=target_hash,
                    now=current_time,
                )

            delivery = self._build_delivery(
                message,
                target_hash=target_hash,
                priority=priority_name,
                source=source,
                metadata=metadata,
                now=current_time,
            )
            queued, state = self._append_to_queue(state, delivery, current_time)
            self._save_state(state)
            reason = "queued_rate_limited" if status in {OPEN, HALF_OPEN} else "queued_quota_exhausted"
            if not queued:
                reason = "queue_full_expired_low_priority"
            return self._decision(
                state,
                allowed=False,
                queued=queued,
                reason=reason,
                target_hash=target_hash,
                delivery_id=delivery.delivery_id if queued else None,
                now=current_time,
            )

    def queue_delivery(
        self,
        message: str,
        *,
        target_id: str,
        priority: str = "normal",
        source: str = "unknown",
        metadata: dict[str, Any] | None = None,
        now: float | None = None,
    ) -> GovernorDecision:
        current_time = _now(now)
        target_hash = self.hash_target(target_id)
        delivery = self._build_delivery(
            message,
            target_hash=target_hash,
            priority=normalize_priority(priority),
            source=source,
            metadata=metadata,
            now=current_time,
        )
        with _StateLock(self.lock_file, self.config.lock_timeout_seconds, self.config.lock_stale_seconds):
            state = self._load_state(current_time)
            state = self._refresh_state(state, current_time)
            queued, state = self._append_to_queue(state, delivery, current_time)
            self._save_state(state)
            return self._decision(
                state,
                allowed=False,
                queued=queued,
                reason="queued_after_rate_limit" if queued else "queue_full_expired_low_priority",
                target_hash=target_hash,
                delivery_id=delivery.delivery_id if queued else None,
                now=current_time,
            )

    def reserve_next_queued(self, *, target_id: str, now: float | None = None) -> QueuedDelivery | None:
        current_time = _now(now)
        target_hash = self.hash_target(target_id)
        with _StateLock(self.lock_file, self.config.lock_timeout_seconds, self.config.lock_stale_seconds):
            state = self._load_state(current_time)
            state = self._refresh_state(state, current_time)
            status = self._effective_status(state, current_time)
            if not self._can_attempt(state, status):
                self._save_state(state)
                return None

            queue = [QueuedDelivery.from_dict(item) for item in state.get("queue", []) if isinstance(item, dict)]
            matching = [item for item in queue if item.target_hash == target_hash]
            if not matching:
                self._save_state(state)
                return None

            selected = sorted(matching, key=_queue_sort_key)[0]
            remaining_queue = [item for item in queue if item.delivery_id != selected.delivery_id]
            reserved = QueuedDelivery(
                delivery_id=selected.delivery_id,
                message=selected.message,
                priority=selected.priority,
                source=selected.source,
                target_hash=selected.target_hash,
                created_at=selected.created_at,
                expires_at=selected.expires_at,
                attempts=selected.attempts + 1,
                metadata=selected.metadata,
            )
            state["queue"] = [item.to_dict() for item in remaining_queue]
            state["status"] = status if status == HALF_OPEN else (DRAINING if remaining_queue else HEALTHY)
            state["attempts_in_window"] = int(state.get("attempts_in_window") or 0) + 1
            if status == HALF_OPEN:
                state["half_open_in_flight"] = True
            self._save_state(state)
            return reserved

    def requeue_delivery(self, delivery: QueuedDelivery, *, reason: str = "send_failed", now: float | None = None) -> None:
        current_time = _now(now)
        if delivery.expires_at <= current_time:
            return
        metadata = dict(delivery.metadata)
        metadata["last_requeue_reason"] = reason
        queued = QueuedDelivery(
            delivery_id=delivery.delivery_id,
            message=delivery.message,
            priority=delivery.priority,
            source=delivery.source,
            target_hash=delivery.target_hash,
            created_at=delivery.created_at,
            expires_at=delivery.expires_at,
            attempts=delivery.attempts,
            metadata=metadata,
        )
        with _StateLock(self.lock_file, self.config.lock_timeout_seconds, self.config.lock_stale_seconds):
            state = self._load_state(current_time)
            state = self._refresh_state(state, current_time)
            queue = [item for item in state.get("queue", []) if item.get("delivery_id") != delivery.delivery_id]
            queue.append(queued.to_dict())
            state["queue"] = queue
            state["status"] = DRAINING if state.get("status") == HEALTHY else state.get("status", DRAINING)
            self._save_state(state)

    def flush_plan(self, *, target_id: str, limit: int | None = None, now: float | None = None) -> list[QueuedDelivery]:
        planned: list[QueuedDelivery] = []
        max_items = max(0, limit if limit is not None else self.config.max_flush_per_window)
        for _ in range(max_items):
            item = self.reserve_next_queued(target_id=target_id, now=now)
            if item is None:
                break
            planned.append(item)
        return planned

    def record_result(self, *, success: bool, error_text: str | None = None, now: float | None = None) -> dict[str, Any]:
        current_time = _now(now)
        with _StateLock(self.lock_file, self.config.lock_timeout_seconds, self.config.lock_stale_seconds):
            state = self._load_state(current_time)
            state = self._refresh_state(state, current_time)
            rate_limited = is_rate_limited_result(error_text or "")
            if rate_limited:
                consecutive = int(state.get("consecutive_rate_limits") or 0) + 1
                state["consecutive_rate_limits"] = consecutive
                state["window_rate_limited"] = True
                state["status"] = OPEN
                state["open_until"] = current_time + self._backoff_seconds(consecutive)
                state["half_open_in_flight"] = False
                state["capacity"] = max(
                    int(self.config.min_capacity),
                    min(int(state.get("capacity") or self.config.initial_capacity) - 1, int(state.get("capacity") or 1) // 2),
                )
                state["last_rate_limited_at"] = current_time
            elif success:
                state["last_success_at"] = current_time
                state["consecutive_failures"] = 0
                if state.get("status") == HALF_OPEN:
                    state["status"] = DRAINING if state.get("queue") else HEALTHY
                    state["consecutive_rate_limits"] = 0
                    state["open_until"] = None
                    state["half_open_in_flight"] = False
                elif state.get("status") == DRAINING and not state.get("queue"):
                    state["status"] = HEALTHY
            else:
                state["consecutive_failures"] = int(state.get("consecutive_failures") or 0) + 1
                if state.get("status") == HALF_OPEN:
                    state["status"] = OPEN
                    state["open_until"] = current_time + self._backoff_seconds(int(state.get("consecutive_rate_limits") or 1))
                    state["half_open_in_flight"] = False
            self._save_state(state)
            return self._status_from_state(state, current_time)

    def status(self, *, now: float | None = None) -> dict[str, Any]:
        current_time = _now(now)
        with _StateLock(self.lock_file, self.config.lock_timeout_seconds, self.config.lock_stale_seconds):
            state = self._load_state(current_time)
            state = self._refresh_state(state, current_time)
            self._save_state(state)
            return self._status_from_state(state, current_time)

    def hash_target(self, target_id: str) -> str:
        salt = self.config.hash_salt or os.getenv("WEIXIN_GOVERNOR_HASH_SALT", "")
        return hashlib.sha256(f"{salt}:{target_id}".encode("utf-8", errors="replace")).hexdigest()[:20]

    def _build_delivery(
        self,
        message: str,
        *,
        target_hash: str,
        priority: str,
        source: str,
        metadata: dict[str, Any] | None,
        now: float,
    ) -> QueuedDelivery:
        ttl = self._ttl_for_priority(priority)
        return QueuedDelivery(
            delivery_id=f"wxgov-{uuid.uuid4().hex[:16]}",
            message=message,
            priority=priority,
            source=(source or "unknown")[:80],
            target_hash=target_hash,
            created_at=now,
            expires_at=now + ttl,
            metadata=sanitize_metadata(metadata or {}),
        )

    def _append_to_queue(self, state: dict[str, Any], delivery: QueuedDelivery, now: float) -> tuple[bool, dict[str, Any]]:
        queue = [QueuedDelivery.from_dict(item) for item in state.get("queue", []) if isinstance(item, dict)]
        queue = [item for item in queue if item.expires_at > now]
        if len(queue) >= self.config.queue_max_size:
            queue = sorted(queue, key=_queue_sort_key)
            drop_index = next((idx for idx in range(len(queue) - 1, -1, -1) if queue[idx].priority == "low"), None)
            if drop_index is None:
                state["queue"] = [item.to_dict() for item in queue]
                return False, state
            queue.pop(drop_index)
        queue.append(delivery)
        state["queue"] = [item.to_dict() for item in queue]
        if state.get("status") == HEALTHY:
            state["status"] = DRAINING
        return True, state

    def _load_state(self, now: float) -> dict[str, Any]:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        return self._default_state(now) | data

    def _save_state(self, state: dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        temp_file = self.state_file.with_suffix(f".tmp-{uuid.uuid4().hex}")
        temp_file.write_text(payload, encoding="utf-8")
        temp_file.replace(self.state_file)

    def _default_state(self, now: float) -> dict[str, Any]:
        capacity = max(self.config.min_capacity, min(self.config.initial_capacity, self.config.max_capacity))
        return {
            "version": 1,
            "status": HEALTHY,
            "capacity": capacity,
            "window_started_at": now,
            "attempts_in_window": 0,
            "window_rate_limited": False,
            "consecutive_rate_limits": 0,
            "consecutive_failures": 0,
            "open_until": None,
            "half_open_in_flight": False,
            "queue": [],
        }

    def _refresh_state(self, state: dict[str, Any], now: float) -> dict[str, Any]:
        window_started_at = float(state.get("window_started_at") or now)
        if now - window_started_at >= self.config.window_seconds:
            capacity = int(state.get("capacity") or self.config.initial_capacity)
            attempts = int(state.get("attempts_in_window") or 0)
            if state.get("window_rate_limited"):
                capacity = max(self.config.min_capacity, capacity - 1)
            elif attempts >= capacity and state.get("queue"):
                capacity = min(self.config.max_capacity, capacity + 1)
            state["capacity"] = capacity
            state["window_started_at"] = now
            state["attempts_in_window"] = 0
            state["window_rate_limited"] = False

        queue = [QueuedDelivery.from_dict(item) for item in state.get("queue", []) if isinstance(item, dict)]
        state["queue"] = [item.to_dict() for item in queue if item.expires_at > now]
        if state.get("status") == OPEN and state.get("open_until") is not None:
            try:
                if now >= float(state.get("open_until") or 0.0):
                    state["status"] = HALF_OPEN
                    state["half_open_in_flight"] = False
            except (TypeError, ValueError):
                state["status"] = HALF_OPEN
                state["half_open_in_flight"] = False
        if state.get("status") == DRAINING and not state.get("queue"):
            state["status"] = HEALTHY
        return state

    def _effective_status(self, state: dict[str, Any], now: float) -> str:
        status = str(state.get("status") or HEALTHY)
        if status == OPEN:
            open_until = state.get("open_until")
            if open_until is not None and now >= float(open_until):
                return HALF_OPEN
        if status == HEALTHY and state.get("queue"):
            return DRAINING
        return status if status in {HEALTHY, OPEN, HALF_OPEN, DRAINING} else HEALTHY

    def _can_attempt(self, state: dict[str, Any], status: str) -> bool:
        if status == OPEN:
            return False
        capacity = int(state.get("capacity") or self.config.initial_capacity)
        attempts = int(state.get("attempts_in_window") or 0)
        if attempts >= capacity:
            return False
        if status == HALF_OPEN and state.get("half_open_in_flight"):
            return False
        return True

    def _decision(
        self,
        state: dict[str, Any],
        *,
        allowed: bool,
        queued: bool,
        reason: str,
        target_hash: str,
        now: float,
        delivery_id: str | None = None,
    ) -> GovernorDecision:
        status = self._effective_status(state, now)
        capacity = int(state.get("capacity") or self.config.initial_capacity)
        attempts = int(state.get("attempts_in_window") or 0)
        decision = GovernorDecision(
            allowed=allowed,
            queued=queued,
            reason=reason,
            status=status,
            delivery_id=delivery_id,
            queue_size=len(state.get("queue", [])),
            remaining=max(0, capacity - attempts),
            capacity=capacity,
            next_available_at=self._next_available_at(state, now),
            target_hash=target_hash,
            metadata={"window_seconds": self.config.window_seconds},
        )
        return GovernorDecision(**{**decision.to_dict(), "friendly_text": format_governor_decision_card(decision)})

    def _status_from_state(self, state: dict[str, Any], now: float) -> dict[str, Any]:
        status = self._effective_status(state, now)
        capacity = int(state.get("capacity") or self.config.initial_capacity)
        attempts = int(state.get("attempts_in_window") or 0)
        return {
            "enabled": self.config.enabled,
            "status": status,
            "capacity": capacity,
            "attempts_in_window": attempts,
            "remaining": max(0, capacity - attempts),
            "queue_size": len(state.get("queue", [])),
            "next_available_at": self._next_available_at(state, now),
            "window_seconds": self.config.window_seconds,
            "state_file": str(self.state_file),
        }

    def _next_available_at(self, state: dict[str, Any], now: float) -> float | None:
        status = self._effective_status(state, now)
        if status == OPEN and state.get("open_until") is not None:
            return float(state["open_until"])
        capacity = int(state.get("capacity") or self.config.initial_capacity)
        attempts = int(state.get("attempts_in_window") or 0)
        if attempts >= capacity:
            return float(state.get("window_started_at") or now) + self.config.window_seconds
        return None

    def _backoff_seconds(self, consecutive: int) -> float:
        base = self.config.base_backoff_seconds * (self.config.backoff_multiplier ** max(0, consecutive - 1))
        bounded = min(float(self.config.max_backoff_seconds), float(base))
        if self.config.jitter_seconds <= 0:
            return bounded
        return bounded + random.uniform(0, float(self.config.jitter_seconds))

    def _ttl_for_priority(self, priority: str) -> int:
        if priority == "critical":
            return self.config.critical_ttl_seconds
        if priority == "high":
            return self.config.high_priority_ttl_seconds
        if priority == "low":
            return self.config.low_priority_ttl_seconds
        return self.config.default_ttl_seconds


class _StateLock:
    def __init__(self, path: Path, timeout_seconds: float, stale_seconds: float) -> None:
        self.path = path
        self.timeout_seconds = timeout_seconds
        self.stale_seconds = stale_seconds
        self.fd: int | None = None

    def __enter__(self) -> "_StateLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.time() + self.timeout_seconds
        while True:
            try:
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.write(self.fd, str(os.getpid()).encode("ascii", errors="ignore"))
                return self
            except FileExistsError:
                self._remove_stale_lock()
                if time.time() >= deadline:
                    raise TimeoutError(f"Timed out waiting for Weixin governor lock: {self.path}")
                time.sleep(0.05)

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass

    def _remove_stale_lock(self) -> None:
        try:
            if time.time() - self.path.stat().st_mtime > self.stale_seconds:
                self.path.unlink(missing_ok=True)
        except OSError:
            pass


def normalize_priority(priority: Any) -> str:
    value = str(priority or "normal").strip().lower()
    return value if value in PRIORITY_VALUES else "normal"


def is_rate_limited_result(text: Any) -> bool:
    haystack = json.dumps(text, ensure_ascii=False, default=str).lower() if not isinstance(text, str) else text.lower()
    return any(marker in haystack for marker in RATE_LIMIT_MARKERS)


def sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in metadata.items():
        key_text = str(key)
        if any(marker in key_text.lower() for marker in ("token", "secret", "password", "authorization", "chat_id")):
            sanitized[key_text] = "***"
        elif isinstance(value, (str, int, float, bool)) or value is None:
            sanitized[key_text] = value
        elif isinstance(value, list):
            sanitized[key_text] = [item for item in value if isinstance(item, (str, int, float, bool))]
        else:
            sanitized[key_text] = str(value)[:200]
    return sanitized


def format_governor_decision_card(decision: GovernorDecision) -> str:
    if decision.allowed:
        return friendly_card(
            "✅ 微信发送已通过治理检查",
            action="已预留本周期发送名额",
            result=f"本周期剩余 {decision.remaining}/{decision.capacity} 条",
            impact="当前消息会继续发送，不会额外刷屏",
            boundary="统计的是发送尝试次数，失败尝试也会占用额度",
            next_step="如遇限流，我会自动进入保护队列并等待下一周期",
        )
    if decision.reason == "queue_full_expired_low_priority":
        return friendly_card(
            "📭 微信发送保护队列已满",
            action="已丢弃过期或低优先级通知",
            result="本条消息暂未进入微信发送链路",
            impact="避免继续触发 iLink 限流，详细记录保留在本地状态里",
            boundary="不会用微信解释微信限流，避免延长限制窗口",
            next_step="请在本地/Web UI 查看详情，或提高通知优先级后重试",
        )
    return friendly_card(
        "📌 微信发送已进入保护队列",
        action="已暂停直接发送并排队",
        result=f"当前队列 {decision.queue_size} 条，本周期剩余 {decision.remaining}/{decision.capacity} 条",
        impact="你不会收到失败刷屏；通知会在后续可用周期合并或补发",
        boundary="不会把原始错误、ret=-2 或堆栈内容发到聊天里",
        next_step=_next_step_text(decision.next_available_at),
    )


def friendly_card(
    title: str,
    *,
    action: str,
    result: str,
    impact: str,
    boundary: str,
    next_step: str,
    extra_status: list[str] | None = None,
) -> str:
    lines = [
        title,
        "",
        "【状态】",
        f"动作｜{_sanitize_user_visible(action)}",
        f"结果｜{_sanitize_user_visible(result)}",
        f"影响｜{_sanitize_user_visible(impact)}",
        f"边界｜{_sanitize_user_visible(boundary)}",
    ]
    lines.extend(_sanitize_user_visible(line) for line in (extra_status or []))
    lines.extend(["", "【下一步】", _sanitize_user_visible(next_step)])
    return "\n".join(lines)


def _sanitize_user_visible(text: str) -> str:
    sanitized = str(text or "")
    lowered = sanitized.lower()
    if any(marker in lowered for marker in RAW_ERROR_MARKERS):
        return "微信发送链路正在保护中；原始技术细节已转入本地诊断记录。"
    return sanitized


def _next_step_text(next_available_at: float | None) -> str:
    if next_available_at is None:
        return "等待下一个发送名额释放后自动重试；如有多条通知会优先发送高优先级内容。"
    wait_seconds = max(0, int(next_available_at - time.time()))
    return f"预计约 {wait_seconds} 秒后进入下一次可发送窗口；高优先级通知会优先补发。"


def _queue_sort_key(item: QueuedDelivery) -> tuple[int, float, int]:
    return (-PRIORITY_VALUES.get(item.priority, PRIORITY_VALUES["normal"]), item.created_at, item.attempts)


def _now(value: float | None) -> float:
    return float(time.time() if value is None else value)
