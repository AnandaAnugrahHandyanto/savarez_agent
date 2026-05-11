"""Circuit Breaker — persistent failure-aware model gating.

Two-level scoping:
  1. Model-level: provider+model → opens after N consecutive failures
  2. Provider-level: provider → opens after M failures across all models

State persists to disk (~/.hermes/state/circuit_breakers.json) so that
gateway restarts don't immediately retry known-broken endpoints.

States: closed → open (after threshold failures, with cooldown) →
half_open (after cooldown, allow one probe) → closed (on success) or
open (on failure).
"""

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict

from agent.brain.config import CircuitBreakerConfig
from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)


@dataclass
class BreakerState:
    state: str = "closed"          # "closed" | "open" | "half_open"
    failure_count: int = 0
    opened_at: float = 0.0
    cooldown_until: float = 0.0
    last_failure: float = 0.0


class CircuitBreaker:
    """
    Persistent circuit breaker.

    Usage:
        cb = CircuitBreaker(config)
        if cb.is_open("deepseek", "deepseek-v4-pro"):
            # Skip this model
        ...
        cb.record_success("deepseek", "deepseek-v4-pro")  # on success
        cb.record_failure("deepseek", "deepseek-v4-pro")  # on failure
    """

    def __init__(self, config: CircuitBreakerConfig):
        self._cfg = config
        self._state_file = Path(
            config.state_file.replace("~", str(Path.home()))
        )
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._model_states: Dict[str, BreakerState] = {}    # "provider:model" → state
        self._provider_states: Dict[str, BreakerState] = {}  # "provider" → state
        self._lock = threading.Lock()
        self._load()

    def _key(self, provider: str, model: str = "") -> str:
        return f"{provider}:{model}" if model else provider

    # ── Public API ──

    def is_open(self, provider: str, model: str = "") -> bool:
        """Check if circuit is open for a model or provider."""
        with self._lock:
            # Provider-level check first (coarser, blocks everything)
            ps = self._provider_states.get(provider)
            if ps and self._is_open_local(ps):
                return True

            if model:
                ms = self._model_states.get(self._key(provider, model))
                if ms and self._is_open_local(ms):
                    return True

        return False

    def record_failure(self, provider: str, model: str = ""):
        """Record a failure. May open the circuit."""
        now = time.time()
        with self._lock:
            # Model-level
            if model:
                mkey = self._key(provider, model)
                ms = self._model_states.setdefault(mkey, BreakerState())
                ms.failure_count += 1
                ms.last_failure = now
                if ms.failure_count >= self._cfg.threshold:
                    self._open_breaker(ms, now, self._cfg.cooldown)

            # Provider-level
            ps = self._provider_states.setdefault(provider, BreakerState())
            ps.failure_count += 1
            ps.last_failure = now
            if ps.failure_count >= self._cfg.provider_threshold:
                self._open_breaker(ps, now, self._cfg.provider_cooldown)

            self._save()

    def record_success(self, provider: str, model: str = ""):
        """Record a success. Closes half-open circuits."""
        with self._lock:
            changed = False

            if model:
                mkey = self._key(provider, model)
                ms = self._model_states.get(mkey)
                if ms and ms.state == "half_open":
                    ms.state = "closed"
                    ms.failure_count = 0
                    changed = True

            ps = self._provider_states.get(provider)
            if ps and ps.state == "half_open":
                ps.state = "closed"
                ps.failure_count = 0
                changed = True

            if changed:
                self._save()

    # ── Internal ──

    def _is_open_local(self, bs: BreakerState) -> bool:
        """Check a single breaker state (lock already held)."""
        if bs.state == "closed":
            return False
        if bs.state == "open":
            if time.time() >= bs.cooldown_until:
                bs.state = "half_open"
                self._save()
                return False
            return True
        # half_open: allow probe requests
        return False

    def _open_breaker(self, bs: BreakerState, now: float, cooldown: int):
        bs.state = "open"
        bs.opened_at = now
        bs.cooldown_until = now + cooldown
        logger.warning(
            "Circuit breaker opened (failures=%d, cooldown=%ds)",
            bs.failure_count, cooldown,
        )

    # ── Persistence ──

    def _save(self):
        try:
            data = {
                "models": {
                    k: asdict(v) for k, v in self._model_states.items()
                },
                "providers": {
                    k: asdict(v) for k, v in self._provider_states.items()
                },
            }
            with open(self._state_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning("Circuit breaker state save failed: %s", e)

    def _load(self):
        if not self._state_file.exists():
            return
        try:
            with open(self._state_file) as f:
                data = json.load(f)
            for k, v in data.get("models", {}).items():
                self._model_states[k] = BreakerState(**v)
            for k, v in data.get("providers", {}).items():
                self._provider_states[k] = BreakerState(**v)
        except Exception as e:
            logger.warning("Circuit breaker state load failed: %s", e)
