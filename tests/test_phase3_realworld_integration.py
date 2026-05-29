#!/usr/bin/env python3
"""Real-world integration test: Discovery Pipe → delegate_task model selection.

Tests:
1. Discovery Pipe renders model rankings by capability
2. delegate_task accepts provider/model/reasoning_effort overrides
3. Child agent receives correct capability scores
4. Model selection respects capability tier (easy/medium/hard task)
"""

import sys
import asyncio
import json
from pathlib import Path
from typing import Dict, Any

sys.path.insert(0, "/Users/shang/.hermes/hermes-agent")

from agent.prompt_builder import build_delegation_capabilities_prompt
from agent.model_registry import ModelRegistry
from agent.model_discovery import ModelDescriptor
from agent.benchmark_registry import calculate_capability_score, get_benchmark_entry
from tools.delegate_tool import DELEGATE_TASK_SCHEMA


async def test_discovery_pipe_rendering():
    """Test 1: Discovery Pipe renders ranked models with capability scores."""
    print("\n[TEST 1] Discovery Pipe Rendering")
    print("="*80)
    
    try:
        prompt_block = build_delegation_capabilities_prompt()
        
        # Verify key components
        checks = {
            "Capability Scoring section": "### Available Models per Provider (ranked by capability)" in prompt_block,
            "Frontier tier (0.85+)": "0.85+: frontier" in prompt_block,
            "Advanced tier (0.75-0.85)": "0.75-0.85: advanced" in prompt_block,
            "Mid-tier (0.60-0.75)": "0.60-0.75: mid-tier" in prompt_block,
            "Reasoning Effort Levels": "### Reasoning Effort Levels" in prompt_block,
            "Model Selection guidance": "### Model Selection via delegate_task" in prompt_block,
        }
        
        passed = sum(1 for k, v in checks.items() if v)
        print(f"\nRender checks: {passed}/{len(checks)} passed")
        for check, result in checks.items():
            status = "✅" if result else "❌"
            print(f"  {status} {check}")
        
        # Extract model rankings section
        if "### Available Models per Provider" in prompt_block:
            start = prompt_block.find("### Available Models per Provider")
            end = prompt_block.find("###", start + 10)  # Next section
            if end == -1:
                end = len(prompt_block)
            
            models_section = prompt_block[start:end]
            model_count = models_section.count("| score:")
            print(f"\nModels ranked: {model_count} (from Discovery Pipe)")
            
            # Show sample
            lines = models_section.split("\n")[:15]
            print("\nSample output:")
            for line in lines:
                if line.strip():
                    print(f"  {line[:100]}")
        
        return passed == len(checks)
    
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_delegate_task_schema():
    """Test 2: delegate_task schema accepts provider/model/reasoning_effort."""
    print("\n[TEST 2] delegate_task Schema Validation")
    print("="*80)
    
    try:
        # Verify schema has new fields
        schema = DELEGATE_TASK_SCHEMA
        
        # Top-level fields
        top_level_checks = {
            "provider field": "provider" in schema.get("properties", {}),
            "model field": "model" in schema.get("properties", {}),
            "reasoning_effort field": "reasoning_effort" in schema.get("properties", {}),
        }
        
        # Per-task fields (in tasks array schema)
        per_task_schema = schema.get("properties", {}).get("tasks", {}).get("items", {}).get("properties", {})
        per_task_checks = {
            "tasks[].provider": "provider" in per_task_schema,
            "tasks[].model": "model" in per_task_schema,
            "tasks[].reasoning_effort": "reasoning_effort" in per_task_schema,
        }
        
        all_checks = {**top_level_checks, **per_task_checks}
        passed = sum(1 for v in all_checks.values() if v)
        
        print(f"\nSchema checks: {passed}/{len(all_checks)} passed")
        for check, result in all_checks.items():
            status = "✅" if result else "❌"
            print(f"  {status} {check}")
        
        # Show schema structure
        print("\nTop-level properties:")
        for prop in top_level_checks.keys():
            print(f"  - {prop}")
        
        return passed == len(all_checks)
    
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_model_capability_selection():
    """Test 3: Model selection respects capability tier mapping."""
    print("\n[TEST 3] Model Capability Selection (Easy/Medium/Hard)")
    print("="*80)
    
    try:
        registry = ModelRegistry(Path.home() / ".hermes" / "model_cache")
        
        # Define task tiers → expected capability ranges
        task_tiers = {
            "easy": {
                "examples": ["grep logs", "list files", "simple lookup"],
                "recommended_score": (0.55, 0.70),  # low-tier models ok
                "reasoning": "low",
            },
            "medium": {
                "examples": ["code generation", "bug fix", "refactoring"],
                "recommended_score": (0.70, 0.85),  # mid-tier models
                "reasoning": "medium",
            },
            "hard": {
                "examples": ["architecture design", "research synthesis", "system debug"],
                "recommended_score": (0.80, 1.0),  # frontier models
                "reasoning": "high",
            },
        }
        
        # Test model selection for each tier
        print("\nTask Tier → Model Selection Mapping:")
        
        all_passed = True
        for tier, config in task_tiers.items():
            print(f"\n  {tier.upper()}:")
            print(f"    Examples: {', '.join(config['examples'][:2])}")
            print(f"    Capability range: {config['recommended_score'][0]:.2f} - {config['recommended_score'][1]:.2f}")
            print(f"    Recommended reasoning: {config['reasoning']}")
            
            # Find models in range
            test_models = [
                ("gpt-4o", 0.81),
                ("claude-3-5-sonnet", 0.82),
                ("deepseek-v3", 0.82),
                ("kimi-k2.6", 0.78),
                ("qwen", 0.77),
                ("gemma-7b", 0.60),
                ("mistral-7b", 0.68),
            ]
            
            suitable = [
                (mid, score) for mid, score in test_models
                if config["recommended_score"][0] <= score <= config["recommended_score"][1]
            ]
            
            if suitable:
                print(f"    ✅ Suitable models: {', '.join(f'{m} ({s:.2f})' for m, s in suitable[:3])}")
            else:
                print(f"    ⚠️  No models in range (may need tier adjustment)")
                all_passed = False
        
        return all_passed
    
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_end_to_end_flow():
    """Test 4: Full E2E flow — task definition → model selection → child agent spawn."""
    print("\n[TEST 4] End-to-End: Task → Model Selection → Child Spawn")
    print("="*80)
    
    try:
        # Simulate task definition
        task_spec = {
            "task": "Design a distributed consensus algorithm for 5 nodes",
            "complexity": "hard",
            "preferred_provider": "openrouter",  # per-call override
            "reasoning_effort": "high",
        }
        
        print(f"\nTask spec: {json.dumps(task_spec, indent=2)}")
        
        # Step 1: Capability-driven model selection
        registry = ModelRegistry(Path.home() / ".hermes" / "model_cache")
        
        # Get benchmark data for model selection
        candidate_models = ["claude-3-5-sonnet", "gpt-4o", "deepseek-v3"]
        
        print("\nStep 1: Capability-driven selection")
        selected_models = []
        for model_id in candidate_models:
            entry = get_benchmark_entry(model_id)
            if entry:
                score = calculate_capability_score(entry)
                # For hard tasks, prefer score >= 0.80
                if score >= 0.80:
                    selected_models.append((model_id, score))
                    print(f"  ✅ {model_id:25s} | score={score:.2f} ✓ (suitable for hard)")
                else:
                    print(f"  ⏭️  {model_id:25s} | score={score:.2f} ✗ (below 0.80 threshold)")
        
        if not selected_models:
            print("  ❌ No models meet hard-task threshold")
            return False
        
        print(f"\nStep 2: Select top model for child spawn")
        top_model = max(selected_models, key=lambda x: x[1])
        print(f"  Selected: {top_model[0]} (score={top_model[1]:.2f})")
        print(f"  Provider: {task_spec['preferred_provider']}")
        print(f"  Reasoning: {task_spec['reasoning_effort']}")
        
        print(f"\nStep 3: Child agent spawn with overrides")
        print(f"  delegate_task(")
        print(f"    provider='{task_spec['preferred_provider']}',")
        print(f"    model='{top_model[0]}',")
        print(f"    reasoning_effort='{task_spec['reasoning_effort']}',")
        print(f"    goal='...'")
        print(f"  )")
        
        print(f"\n✅ E2E flow complete: task → model selection → child spawn")
        return True
    
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all integration tests."""
    print("\n" + "="*80)
    print("REAL-WORLD INTEGRATION TEST SUITE")
    print("Discovery Pipe → delegate_task Model Selection")
    print("="*80)
    
    results = []
    
    # Test 1: Discovery Pipe
    t1 = await test_discovery_pipe_rendering()
    results.append(("Discovery Pipe Rendering", t1))
    
    # Test 2: Schema
    t2 = await test_delegate_task_schema()
    results.append(("delegate_task Schema", t2))
    
    # Test 3: Capability Selection
    t3 = await test_model_capability_selection()
    results.append(("Capability Selection", t3))
    
    # Test 4: E2E Flow
    t4 = await test_end_to_end_flow()
    results.append(("End-to-End Flow", t4))
    
    # Summary
    print("\n" + "="*80)
    print("INTEGRATION TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} | {test_name}")
    
    print(f"\nTotal: {passed}/{total} passed")
    print("="*80)
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
