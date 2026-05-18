"""Safety controls for VRChat OSC writes from the Hypura harness."""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


class SafetyGateBlocked(Exception):
    """Raised when a VRChat action is blocked by policy."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass
class VrchatSafetyGate:
    """Rate limit, cooldown, and emergency-stop gate for VRChat OSC."""

    global_rate_limit_per_second: int = 10
    default_action_cooldown_ms: int = 1500
    chatbox_enabled: bool = False
    chatbox_public_enabled: bool = False
    chatbox_max_chars: int = 144
    chatbox_max_lines: int = 9
    chatbox_cooldown_ms: int = 8000
    movement_enabled: bool = False
    movement_allow_axes: bool = False
    movement_auto_reset_ms: int = 120
    emergency_stop: bool = False
    _action_last_sent: dict[str, float] = field(default_factory=dict)
    _chatbox_last_sent: float = 0.0
    _recent_osc_sends: deque[float] = field(default_factory=deque)

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "VrchatSafetyGate":
        vrchat = config.get("vrchat") if isinstance(config.get("vrchat"), dict) else {}
        safety = vrchat.get("safety") if isinstance(vrchat.get("safety"), dict) else {}
        chatbox = vrchat.get("chatBox") if isinstance(vrchat.get("chatBox"), dict) else {}
        movement = vrchat.get("movement") if isinstance(vrchat.get("movement"), dict) else {}
        return cls(
            global_rate_limit_per_second=int(safety.get("globalOscRateLimitPerSecond", 10)),
            default_action_cooldown_ms=int(safety.get("actionCooldownMs", 1500)),
            chatbox_enabled=bool(chatbox.get("enabled", False)),
            chatbox_public_enabled=bool(chatbox.get("publicEnabled", False)),
            chatbox_max_chars=int(chatbox.get("maxChars", 144)),
            chatbox_max_lines=int(chatbox.get("maxLines", 9)),
            chatbox_cooldown_ms=int(chatbox.get("cooldownMs", 8000)),
            movement_enabled=bool(movement.get("enabled", False)),
            movement_allow_axes=bool(movement.get("allowAxes", False)),
            movement_auto_reset_ms=int(movement.get("autoResetMs", 120)),
        )

    def reset(self) -> None:
        self.emergency_stop = False
        self._action_last_sent.clear()
        self._chatbox_last_sent = 0.0
        self._recent_osc_sends.clear()

    def trigger_emergency_stop(self) -> None:
        self.emergency_stop = True

    def ensure_not_stopped(self) -> None:
        if self.emergency_stop:
            raise SafetyGateBlocked("emergency_stop_active", "Emergency stop is active")

    def ensure_osc_rate(self) -> None:
        self.ensure_not_stopped()
        now = time.monotonic()
        while self._recent_osc_sends and now - self._recent_osc_sends[0] > 1.0:
            self._recent_osc_sends.popleft()
        if len(self._recent_osc_sends) >= self.global_rate_limit_per_second:
            raise SafetyGateBlocked("rate_limited", "Global OSC rate limit exceeded")
        self._recent_osc_sends.append(now)

    def ensure_action_allowed(self, action: str, cooldown_ms: int | None = None) -> None:
        self.ensure_osc_rate()
        now = time.monotonic()
        cooldown_source = self.default_action_cooldown_ms if cooldown_ms is None else cooldown_ms
        cooldown = cooldown_source / 1000
        last_sent = self._action_last_sent.get(action)
        if last_sent is not None and now - last_sent < cooldown:
            raise SafetyGateBlocked("action_cooldown", f"Action {action} is cooling down")
        self._action_last_sent[action] = now

    def truncate_chatbox_text(self, text: str) -> str:
        lines = text.splitlines()[: self.chatbox_max_lines]
        compact = "\n".join(lines)
        if len(compact) > self.chatbox_max_chars:
            return compact[: self.chatbox_max_chars]
        return compact

    def ensure_chatbox_allowed(self, *, public_instance: bool = False) -> None:
        self.ensure_osc_rate()
        if not self.chatbox_enabled:
            raise SafetyGateBlocked("chatbox_disabled", "VRChat ChatBox is disabled")
        if public_instance and not self.chatbox_public_enabled:
            raise SafetyGateBlocked("chatbox_public_disabled", "VRChat ChatBox is disabled in Public")
        now = time.monotonic()
        if now - self._chatbox_last_sent < self.chatbox_cooldown_ms / 1000:
            raise SafetyGateBlocked("chatbox_rate_limited", "VRChat ChatBox cooldown is active")
        self._chatbox_last_sent = now

    def ensure_movement_allowed(self, *, axes: bool = False) -> None:
        self.ensure_osc_rate()
        if not self.movement_enabled:
            raise SafetyGateBlocked("movement_disabled", "VRChat movement is disabled")
        if axes and not self.movement_allow_axes:
            raise SafetyGateBlocked("movement_axes_disabled", "VRChat movement axes are disabled")
