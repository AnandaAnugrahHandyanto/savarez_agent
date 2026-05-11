#!/usr/bin/env python3
"""Brain smoke test — validates the full pipeline with the real credential system.

Usage:
  cd ~/.hermes/hermes-agent && source venv/bin/activate
  python scripts/smoke_test_brain.py
"""

import sys
sys.path.insert(0, '/home/devin/.hermes/hermes-agent')

from agent.brain.pipeline import route_message, _fingerprint_cache
from agent.brain.config import BrainConfig
from agent.brain.layer2 import layer2_planner

# Prevent cached results from interfering
_fingerprint_cache.clear()

config = BrainConfig()
config.enabled = True

tests = [
    ("你好", "simple", "greeting → simple"),
    ("OK", "simple", "chitchat → simple"),
    ("翻译一下这段话", "simple", "translation → simple"),
    ("写个Python函数 import numpy as np def main():", "coding", "code → coding"),
    ("看看这张图 ![img](photo.jpg)", "vision", "image → vision"),
    ("设计一个分布式微服务架构", None, "complex query → L2 planner (API call)"),
]

print("=" * 60)
print("Brain Smoke Test")
print("=" * 60)

passed = 0
failed = 0
for msg, expected, label in tests:
    r = route_message(msg, [], config)
    if expected:
        ok = r.route == expected
        status = "PASS" if ok else f"FAIL (got {r.route})"
        if ok:
            passed += 1
        else:
            failed += 1
    else:
        # Complex test: just verify it didn't crash
        ok = r.resolved_model is not None
        status = "PASS" if ok else "FAIL (no resolved model)"
        if ok:
            passed += 1
        else:
            failed += 1
    
    print(f"  [{status}] {label}")
    print(f"         route={r.route}, model={r.resolved_model}, source={r.source}")
    if r.metadata:
        meta_str = ", ".join(f"{k}={v}" for k, v in r.metadata.items() if k in ("attempts", "reason", "auto_upgraded"))
        if meta_str:
            print(f"         meta: {meta_str}")

print()
print(f"Results: {passed} passed, {failed} failed")

# ── Test L2 planner with real API ──
print()
print("-" * 60)
print("Layer 2 Planner (real API call)")
print("-" * 60)
try:
    l2_result = layer2_planner(
        "设计一个分布式系统架构，包括负载均衡、数据库分片、缓存策略",
        [], config,
    )
    print(f"  route={l2_result.route}, confidence={l2_result.confidence:.2f}, source={l2_result.source}")
    if l2_result.metadata:
        print(f"  meta: {l2_result.metadata}")
    if l2_result.source == "l2_planner":
        print("  ✓ L2 planner API call succeeded")
    else:
        print(f"  ⚠ L2 planner returned fallback: {l2_result.source}")
except Exception as e:
    print(f"  ✗ L2 planner crashed: {e}")

print()
if failed == 0:
    print("🎉 All smoke tests passed!")
    sys.exit(0)
else:
    print(f"⚠ {failed} test(s) failed")
    sys.exit(1)
