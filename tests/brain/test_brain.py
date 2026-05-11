"""Tests for the Brain routing system."""

import pytest
import time
import tempfile

from agent.brain.types import RouteDecision, SessionAffinityState, LayerTrace, EMPTY_DECISION
from agent.brain.config import BrainConfig, RouteTarget
from agent.brain.layer0 import layer0_preprocess, token_estimate
from agent.brain.layer0_5 import FingerprintCache
from agent.brain.layer1 import layer1_heuristic, is_greeting, is_chitchat, compute_code_score
from agent.brain.layer2 import _extract_json, _trim_history
from agent.brain.affinity import check_affinity, establish_affinity, record_affinity_failure, record_affinity_success
from agent.brain.circuit_breaker import CircuitBreaker
from agent.brain.execution import resolve_model, get_route_timeout
from agent.brain.pipeline import route_message


# ═══════════════════════════════════════════════════════════════
# Types
# ═══════════════════════════════════════════════════════════════

class TestRouteDecision:
    def test_terminal_routes(self):
        assert RouteDecision("vision", 0.95, "l0_image").is_terminal
        assert RouteDecision("doc_extract", 0.95, "l0_document").is_terminal
        assert not RouteDecision("coding", 0.9, "l1_code").is_terminal


# ═══════════════════════════════════════════════════════════════
# Layer 0
# ═══════════════════════════════════════════════════════════════

class TestLayer0:
    def test_token_estimate_english(self):
        assert token_estimate("hello world") == 2  # 11 chars / 4 ≈ 2

    def test_token_estimate_chinese(self):
        assert token_estimate("你好世界") == 2  # 4 CJK / 1.5 ≈ 2

    def test_token_estimate_empty(self):
        assert token_estimate("") == 0

    def test_image_triggers_vision(self):
        config = BrainConfig()
        r = layer0_preprocess("Look at ![img](photo.jpg)", [], config)
        assert r is not None and r.route == "vision"

    def test_document_triggers_doc_extract(self):
        config = BrainConfig()
        r = layer0_preprocess("See [report](file.pdf)", [], config)
        assert r is not None and r.route == "doc_extract"

    def test_normal_text_passes_through(self):
        config = BrainConfig()
        r = layer0_preprocess("Hello world", [], config)
        assert r is None

    def test_long_context_returns_complex(self):
        config = BrainConfig()
        config.layer0.max_context_threshold = 200   # Low threshold
        # ~500 words = ~125 tokens, under 200 → won't trigger
        # Need more: 1000 words = ~250 tokens > 200
        long_msg = "word " * 1200
        r = layer0_preprocess(long_msg, [], config)
        assert r is not None and r.route == "complex"


# ═══════════════════════════════════════════════════════════════
# Layer 0.5
# ═══════════════════════════════════════════════════════════════

class TestFingerprintCache:
    def test_cache_hit(self):
        cache = FingerprintCache(max_entries=10, ttl=3600)
        d = RouteDecision("simple", 0.95, "test")
        cache.set("Hello world", d)
        assert cache.get("Hello world") is not None

    def test_normalization(self):
        cache = FingerprintCache(max_entries=10, ttl=3600)
        cache.set("  Hello   World  ", RouteDecision("simple", 0.95, "test"))
        assert cache.get("hello world") is not None

    def test_cache_miss(self):
        cache = FingerprintCache(max_entries=10, ttl=3600)
        assert cache.get("nonexistent") is None

    def test_ttl_expiry(self):
        cache = FingerprintCache(max_entries=10, ttl=0.01)
        cache.set("test", RouteDecision("simple", 0.95, "test"))
        time.sleep(0.02)
        assert cache.get("test") is None

    def test_lru_eviction(self):
        cache = FingerprintCache(max_entries=2, ttl=3600)
        cache.set("a", RouteDecision("simple", 0.9, "test"))
        cache.set("b", RouteDecision("coding", 0.9, "test"))
        cache.set("c", RouteDecision("complex", 0.9, "test"))
        assert cache.get("a") is None
        assert cache.get("b") is not None


# ═══════════════════════════════════════════════════════════════
# Layer 1
# ═══════════════════════════════════════════════════════════════

class TestLayer1:
    def test_greeting(self):
        r = layer1_heuristic("你好", [], turns=1, est_tokens=5)
        assert r is not None and r.route == "simple" and r.confidence == 1.0

    def test_chitchat(self):
        r = layer1_heuristic("好的", [], turns=3, est_tokens=2)
        assert r is not None and r.route == "simple"

    def test_translation(self):
        r = layer1_heuristic("翻译这段", [], turns=2, est_tokens=10)
        assert r is not None and r.route == "simple"

    def test_code_detection(self):
        r = layer1_heuristic("写个函数 import numpy as np def main():", [], turns=2, est_tokens=30)
        assert r is not None and r.route == "coding"

    def test_negative_context_prevents_coding(self):
        r = layer1_heuristic("帮我查一下 import 怎么用", [], turns=2, est_tokens=25)
        assert r is None or r.route != "coding"

    def test_complex_escalates(self):
        r = layer1_heuristic(
            "设计一个分布式微服务架构包括服务发现负载均衡消息队列",
            [], turns=4, est_tokens=80
        )
        assert r is None  # Should escalate to L2


# ═══════════════════════════════════════════════════════════════
# Layer 2 (unit tests only, no API)
# ═══════════════════════════════════════════════════════════════

class TestLayer2Parsing:
    def test_basic_json(self):
        assert _extract_json('{"task_type": "simple", "confidence": 0.9, "reason": "test"}') is not None

    def test_markdown_fence(self):
        r = _extract_json('```json\n{"task_type": "coding", "confidence": 0.8, "reason": "code"}\n```')
        assert r is not None and r["task_type"] == "coding"

    def test_trailing_comma(self):
        r = _extract_json('{"task_type": "simple", "confidence": 0.9,}')
        assert r is not None and r["task_type"] == "simple"

    def test_empty(self):
        assert _extract_json("") is None

    def test_garbage(self):
        assert _extract_json("not json at all") is None


# ═══════════════════════════════════════════════════════════════
# Affinity
# ═══════════════════════════════════════════════════════════════

class TestAffinity:
    def test_no_lock_simple(self):
        from agent.brain.config import AffinityConfig
        cfg = AffinityConfig(enabled=True)
        r = establish_affinity(None, RouteDecision("simple", 0.95, "test"), cfg)
        assert r is None

    def test_lock_coding(self):
        from agent.brain.config import AffinityConfig
        cfg = AffinityConfig(enabled=True)
        r = establish_affinity(None, RouteDecision("coding", 0.90, "test"), cfg)
        assert r is not None and r.route == "coding"

    def test_low_confidence_no_lock(self):
        from agent.brain.config import AffinityConfig
        cfg = AffinityConfig(enabled=True, min_confidence=0.90)
        r = establish_affinity(None, RouteDecision("complex", 0.70, "test"), cfg)
        assert r is None

    def test_reuse_affinity(self):
        from agent.brain.config import AffinityConfig
        cfg = AffinityConfig(enabled=True)
        state = SessionAffinityState(route="coding", model="test", locked_at=time.time())
        r = check_affinity(state, None, cfg)
        assert r is not None and r.route == "coding"

    def test_l1_conflict_releases(self):
        from agent.brain.config import AffinityConfig
        cfg = AffinityConfig(enabled=True)
        state = SessionAffinityState(route="coding", model="test", locked_at=time.time())
        l1 = RouteDecision("simple", 0.98, "l1_greeting")
        r = check_affinity(state, l1, cfg)
        assert r is None  # Should release

    def test_two_failures_release(self):
        state = SessionAffinityState(route="coding", model="test", locked_at=time.time())
        assert not record_affinity_failure(state)
        assert record_affinity_failure(state)


# ═══════════════════════════════════════════════════════════════
# Circuit Breaker
# ═══════════════════════════════════════════════════════════════

class TestCircuitBreaker:
    def test_opens_after_threshold(self):
        import tempfile, os
        tmp = tempfile.mktemp(suffix=".json")
        from agent.brain.config import CircuitBreakerConfig
        cfg = CircuitBreakerConfig(threshold=3, cooldown=1, state_file=tmp)
        cb = CircuitBreaker(cfg)
        assert not cb.is_open("test", "model")
        for _ in range(3):
            cb.record_failure("test", "model")
        assert cb.is_open("test", "model")
        os.unlink(tmp)

    def test_half_open_recovery(self):
        import tempfile, os
        tmp = tempfile.mktemp(suffix=".json")
        from agent.brain.config import CircuitBreakerConfig
        cfg = CircuitBreakerConfig(threshold=1, cooldown=0.01, state_file=tmp)
        cb = CircuitBreaker(cfg)
        cb.record_failure("test", "model")
        assert cb.is_open("test", "model")
        time.sleep(0.02)
        assert not cb.is_open("test", "model")  # Half-open
        cb.record_success("test", "model")
        os.unlink(tmp)


# ═══════════════════════════════════════════════════════════════
# Execution Layer
# ═══════════════════════════════════════════════════════════════

class TestExecution:
    def test_simple_routing(self):
        config = BrainConfig()
        from agent.brain.config import CircuitBreakerConfig
        cb = CircuitBreaker(CircuitBreakerConfig())
        d = RouteDecision("simple", 0.95, "l1_greeting")
        resolve_model(d, config, cb)
        assert d.resolved_model == "deepseek-v4-flash"

    def test_coding_routing(self):
        config = BrainConfig()
        from agent.brain.config import CircuitBreakerConfig
        cb = CircuitBreaker(CircuitBreakerConfig())
        d = RouteDecision("coding", 0.90, "l1_code")
        resolve_model(d, config, cb)
        assert d.resolved_model == "deepseek-v4-pro"

    def test_auto_upgrade(self):
        config = BrainConfig()
        from agent.brain.config import CircuitBreakerConfig
        cb = CircuitBreaker(CircuitBreakerConfig())
        d = RouteDecision("simple", 0.95, "l1_greeting")
        resolve_model(d, config, cb, estimated_tokens=20000)
        assert d.route == "complex"

    def test_timeout_values(self):
        config = BrainConfig()
        assert get_route_timeout("simple", config) == 10
        assert get_route_timeout("coding", config) == 30


# ═══════════════════════════════════════════════════════════════
# Pipeline (no L2 API calls)
# ═══════════════════════════════════════════════════════════════

class TestPipeline:
    def test_greeting_routed_to_simple(self):
        config = BrainConfig()
        config.enabled = True
        from agent.brain.pipeline import _fingerprint_cache
        _fingerprint_cache.clear()
        r = route_message("你好", [], config)
        assert r.route == "simple"

    def test_disabled_returns_empty(self):
        config = BrainConfig()
        r = route_message("anything", [], config)
        assert r.source == "none"

    def test_image_routed_to_vision(self):
        config = BrainConfig()
        config.enabled = True
        r = route_message("Look at ![img](photo.jpg)", [], config)
        assert r.route == "vision"
