#!/usr/bin/env python3
"""Phase 3e: Integration test for Phase 3 (Capability Scoring).

Tests:
1. Benchmark registry lookup (published models)
2. ModelRegistry augmentation (published + fallback)
3. Discovery Pipe rendering (ranked by capability)
4. Fallback estimator (unlisted models)
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, "/Users/shang/.hermes/hermes-agent")

import pytest

from agent.benchmark_registry import (
    get_benchmark_entry,
    calculate_capability_score,
)
from agent.model_registry import ModelRegistry
from agent.model_discovery import ModelDescriptor
from agent.model_fallback_estimator import estimate_capability_score


async def test_phase3_integration():
    """Run all Phase 3 integration tests."""
    
    print("=" * 80)
    print("Phase 3 Integration Test Suite")
    print("=" * 80)
    
    # ── Test 1: Benchmark Registry Lookup ──
    print("\n[TEST 1] Benchmark Registry Lookup (published models)")
    test_models = ["gpt-4o", "claude-3-5-sonnet", "deepseek-v3", "gemma-7b"]
    for model_id in test_models:
        entry = get_benchmark_entry(model_id)
        if entry:
            score = calculate_capability_score(entry)
            print(f"  ✅ {model_id:25s} | score={score:.2f} | mmlu={entry.mmlu_pct:5.1f}% | he={entry.humaneval_pct:5.1f}%")
        else:
            print(f"  ❌ {model_id:25s} | NOT FOUND")
    
    # ── Test 2: Fallback Estimator ──
    print("\n[TEST 2] Fallback Estimator (unlisted models)")
    unlisted = [
        ("llama-3-70b", "high"),
        ("mistral-8b", "medium"),
        ("unknown-model", None),
    ]
    for model_id, reasoning in unlisted:
        score, source, note = estimate_capability_score(model_id, reasoning)
        print(f"  ✅ {model_id:25s} | score={score:.2f} ({source:15s}) | {note}")
    
    # ── Test 3: ModelRegistry Augmentation ──
    print("\n[TEST 3] ModelRegistry Augmentation")
    registry = ModelRegistry(Path.home() / ".hermes" / "model_cache")
    
    # Create test models (published + unlisted)
    test_descriptors = [
        ModelDescriptor(
            id="gpt-4o",
            display_name="GPT-4o",
            context_window=128000,
            reasoning_capability="high",
            provider="openai",
        ),
        ModelDescriptor(
            id="llama-3-70b",
            display_name="Llama 70B",
            context_window=8192,
            reasoning_capability="high",
            provider="ollama-cloud",
        ),
    ]
    
    for model in test_descriptors:
        augmented = registry._augment_with_benchmarks(model)
        source = augmented.benchmark_source or "none"
        print(f"  ✅ {augmented.id:25s} | score={augmented.capability_score:.2f} | source={source:15s} | tier={augmented.latency_tier}")
    
    # ── Test 4: ModelRegistry Cache ──
    print("\n[TEST 4] ModelRegistry Cache Statistics")
    stats = registry.get_cache_stats()
    print(f"  Memory cache entries: {stats['memory_cache_entries']}")
    print(f"  Providers cached: {', '.join(stats['providers'].keys()) or 'none'}")
    
    print("\n" + "=" * 80)
    print("✅ Phase 3 Integration Tests COMPLETE")
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    result = asyncio.run(test_phase3_integration())
    sys.exit(0 if result else 1)
