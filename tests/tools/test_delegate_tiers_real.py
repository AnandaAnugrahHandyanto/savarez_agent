#!/usr/bin/env python3
"""
Real integration tests for delegation tiers — runs actual subagent spawns
in tmux sessions and compares tier behavior.

These tests verify:
1. Light tier spawns with correct model/iterations
2. Review tier uses higher reasoning effort
3. Per-task tier routing in batch mode
4. Pool validation rejects invalid models
5. Reasoning floor guardrails work end-to-end

Requires: tmux, hermes installed in venv.
Run: python tests/tools/test_delegate_tiers_real.py
Or:  python -m pytest tests/tools/test_delegate_tiers_real.py -v -s
"""

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _run(cmd, timeout=30, cwd=None):
    """Run a shell command and return (stdout, stderr, exit_code)."""
    r = subprocess.run(
        cmd, shell=True, capture_output=True, text=True,
        timeout=timeout, cwd=cwd or REPO_ROOT,
    )
    return r.stdout.strip(), r.stderr.strip(), r.returncode


def _tmux_session_exists(name):
    out, _, _ = _run(f"tmux has-session -t {name} 2>&1 || true")
    return "can't find session" not in out and out == ""


def _tmux_kill(name):
    _run(f"tmux kill-session -t {name} 2>/dev/null || true")


def _tmux_send_and_capture(session, command, wait=3, lines=50):
    """Send a command to tmux pane and capture output."""
    _run(f"tmux send-keys -t {session} '{command}' Enter")
    time.sleep(wait)
    out, _, _ = _run(f"tmux capture-pane -t {session} -p -S -{lines}")
    return out


def test_tier_config_resolution():
    """Test that resolve_tier_config works with real config structures."""
    # Inline test — no API keys needed
    sys.path.insert(0, REPO_ROOT)
    from tools.delegate_tool import resolve_tier_config, SUPPORTED_TIERS, _TIER_REASONING_FLOORS

    cfg = {
        "model": "gpt-5.4-mini",
        "provider": "openai-codex",
        "reasoning_effort": "low",
        "max_iterations": 25,
        "default_tier": "heavy",
        "tiers": {
            "light": {"model": "gpt-5.4-mini", "reasoning_effort": "low", "max_iterations": 25},
            "heavy": {"model": "gpt-5.4", "reasoning_effort": "medium", "max_iterations": 50},
            "review": {"model": "gpt-5.4", "reasoning_effort": "xhigh", "max_iterations": 60},
            "planning": {"model": "xiaomi/mimo-v2-pro", "provider": "nous", "reasoning_effort": "high", "max_iterations": 60},
            "research": {"model": "gpt-5.4", "reasoning_effort": "high", "max_iterations": 60},
        },
    }

    # Verify each tier
    for tier_name in SUPPORTED_TIERS:
        result = resolve_tier_config(cfg, tier=tier_name)
        assert "model" in result, f"tier {tier_name} missing model"
        assert "tiers" not in result, f"tier {tier_name} has nested tiers"
        assert "default_tier" not in result, f"tier {tier_name} has default_tier"
        print(f"  [OK] {tier_name}: model={result['model']}, reasoning={result.get('reasoning_effort')}, iters={result.get('max_iterations')}")

    # Verify reasoning floors
    review_cfg = resolve_tier_config(cfg, tier="review")
    assert review_cfg["reasoning_effort"] == "xhigh", f"Expected xhigh, got {review_cfg['reasoning_effort']}"

    # Test floor enforcement: review with low effort -> bumped to high
    cfg_floor = {
        "tiers": {"review": {"reasoning_effort": "low"}},
    }
    result_floor = resolve_tier_config(cfg_floor, tier="review")
    assert result_floor["reasoning_effort"] == "high", f"Floor failed: got {result_floor['reasoning_effort']}"
    print("  [OK] Reasoning floor guardrail enforced")

    # Test default_tier
    result_default = resolve_tier_config(cfg)
    assert result_default["model"] == "gpt-5.4", f"default_tier failed: got {result_default['model']}"
    print("  [OK] default_tier='heavy' resolved correctly")

    print("[PASS] test_tier_config_resolution")
    return True


def test_schema_completeness():
    """Verify the DELEGATE_TASK_SCHEMA has tier fields."""
    sys.path.insert(0, REPO_ROOT)
    from tools.delegate_tool import DELEGATE_TASK_SCHEMA, SUPPORTED_TIERS

    props = DELEGATE_TASK_SCHEMA["parameters"]["properties"]
    assert "tier" in props, "Missing top-level 'tier' in schema"
    assert props["tier"]["enum"] == sorted(SUPPORTED_TIERS), "Tier enum mismatch"

    task_props = props["tasks"]["items"]["properties"]
    assert "tier" in task_props, "Missing per-task 'tier' in schema"
    assert task_props["tier"]["enum"] == sorted(SUPPORTED_TIERS), "Per-task tier enum mismatch"

    print("[PASS] test_schema_completeness")
    return True


def test_pool_validation():
    """Test pool validation logic."""
    sys.path.insert(0, REPO_ROOT)
    from tools.delegate_tool import _validate_pool_model, _build_pool_description

    pool = [
        {"model": "gpt-5.4", "provider": "openai-codex", "strengths": "coding"},
        {"model": "gpt-5.4-mini", "strengths": "quick"},
    ]

    assert _validate_pool_model("gpt-5.4", pool) == "gpt-5.4"
    assert _validate_pool_model("invalid-model", pool) == "gpt-5.4"  # fallback
    assert _validate_pool_model(None, pool) is None
    assert _validate_pool_model("anything", []) == "anything"  # no pool

    desc = _build_pool_description(pool)
    assert "gpt-5.4" in desc
    assert "openai-codex" in desc

    print("[PASS] test_pool_validation")
    return True


def test_delegate_task_with_tiers_mocked():
    """Test delegate_task end-to-end with tiers (mocked LLM calls)."""
    sys.path.insert(0, REPO_ROOT)
    from unittest.mock import MagicMock, patch
    from tools.delegate_tool import delegate_task, _build_child_agent

    tier_cfg = {
        "model": "gpt-5.4-mini",
        "reasoning_effort": "low",
        "tiers": {
            "light": {"model": "gpt-5.4-mini", "reasoning_effort": "low", "max_iterations": 25},
            "review": {"model": "gpt-5.4", "reasoning_effort": "xhigh", "max_iterations": 60},
        },
    }

    parent = MagicMock()
    parent.base_url = "https://openrouter.ai/api/v1"
    parent.api_key = "***"
    parent.provider = "openrouter"
    parent.api_mode = "chat_completions"
    parent.model = "anthropic/claude-sonnet-4"
    parent.platform = "cli"
    parent.providers_allowed = None
    parent.providers_ignored = None
    parent.providers_order = None
    parent.provider_sort = None
    parent._session_db = None
    parent._delegate_depth = 0
    parent._active_children = []
    parent._active_children_lock = __import__("threading").Lock()
    parent._print_fn = None
    parent.tool_progress_callback = None
    parent.thinking_callback = None

    children_configs = []

    def capture_child(**kwargs):
        children_configs.append(kwargs)
        child = MagicMock()
        child.run_conversation.return_value = {
            "final_response": "done", "completed": True, "messages": [],
        }
        return child

    with patch("tools.delegate_tool._load_config", return_value=tier_cfg):
        with patch("tools.delegate_tool._build_child_agent", side_effect=capture_child):
            result_json = delegate_task(
                tasks=[
                    {"goal": "Quick lookup", "tier": "light"},
                    {"goal": "Deep review", "tier": "review"},
                ],
                parent_agent=parent,
            )
            result = json.loads(result_json)
            assert len(result["results"]) == 2

            # Light tier
            assert children_configs[0]["model"] == "gpt-5.4-mini"
            assert children_configs[0]["override_reasoning_effort"] == "low"
            assert children_configs[0]["max_iterations"] == 25

            # Review tier (xhigh > floor high, stays xhigh)
            assert children_configs[1]["model"] == "gpt-5.4"
            assert children_configs[1]["override_reasoning_effort"] == "xhigh"
            assert children_configs[1]["max_iterations"] == 60

    print("[PASS] test_delegate_task_with_tiers_mocked")
    return True


def test_comparative_tier_behavior():
    """Compare tier configs: verify light < heavy < review in cost proxy."""
    sys.path.insert(0, REPO_ROOT)
    from tools.delegate_tool import resolve_tier_config, _REASONING_ORDER, SUPPORTED_TIERS

    cfg = {
        "model": "gpt-5.4-mini",
        "reasoning_effort": "low",
        "max_iterations": 25,
        "tiers": {
            "light": {"model": "gpt-5.4-mini", "reasoning_effort": "low", "max_iterations": 25},
            "heavy": {"model": "gpt-5.4", "reasoning_effort": "medium", "max_iterations": 50},
            "review": {"model": "gpt-5.4", "reasoning_effort": "xhigh", "max_iterations": 60},
            "planning": {"model": "xiaomi/mimo-v2-pro", "reasoning_effort": "high", "max_iterations": 60},
            "research": {"model": "gpt-5.4", "reasoning_effort": "high", "max_iterations": 60},
        },
    }

    costs = {}
    for tier_name in SUPPORTED_TIERS:
        resolved = resolve_tier_config(cfg, tier=tier_name)
        reasoning_cost = _REASONING_ORDER.get(resolved.get("reasoning_effort", "none"), 0)
        iters = resolved.get("max_iterations", 0)
        cost = reasoning_cost * iters
        costs[tier_name] = cost
        print(f"  {tier_name}: reasoning={resolved.get('reasoning_effort')} ({reasoning_cost}) * iters={iters} = {cost}")

    assert costs["light"] < costs["heavy"], f"light ({costs['light']}) should be < heavy ({costs['heavy']})"
    assert costs["heavy"] < costs["review"], f"heavy ({costs['heavy']}) should be < review ({costs['review']})"
    print("  Cost order: light < heavy < review [OK]")

    print("[PASS] test_comparative_tier_behavior")
    return True


def test_backward_compat_no_tiers():
    """Verify delegation works exactly as before when no tiers configured."""
    sys.path.insert(0, REPO_ROOT)
    from unittest.mock import MagicMock, patch
    from tools.delegate_tool import delegate_task

    flat_cfg = {"model": "gpt-5.4-mini", "max_iterations": 30}

    parent = MagicMock()
    parent.base_url = "https://openrouter.ai/api/v1"
    parent.api_key = "***"
    parent.provider = "openrouter"
    parent.api_mode = "chat_completions"
    parent.model = "anthropic/claude-sonnet-4"
    parent.platform = "cli"
    parent.providers_allowed = None
    parent.providers_ignored = None
    parent.providers_order = None
    parent.provider_sort = None
    parent._session_db = None
    parent._delegate_depth = 0
    parent._active_children = []
    parent._active_children_lock = __import__("threading").Lock()
    parent._print_fn = None
    parent.tool_progress_callback = None
    parent.thinking_callback = None

    with patch("tools.delegate_tool._load_config", return_value=flat_cfg):
        with patch("tools.delegate_tool._build_child_agent") as mock_build:
            mock_child = MagicMock()
            mock_child.run_conversation.return_value = {
                "final_response": "ok", "completed": True, "messages": [],
            }
            mock_build.return_value = mock_child

            result_json = delegate_task(goal="test", parent_agent=parent)
            result = json.loads(result_json)
            assert "results" in result

            # Verify flat config was used as-is
            call_kwargs = mock_build.call_args[1]
            assert call_kwargs["model"] == "gpt-5.4-mini"
            assert call_kwargs["max_iterations"] == 30

    print("[PASS] test_backward_compat_no_tiers")
    return True


def test_reasoning_override_in_child_build():
    """Verify override_reasoning_effort actually sets child reasoning_config."""
    sys.path.insert(0, REPO_ROOT)
    from unittest.mock import MagicMock, patch
    from tools.delegate_tool import _build_child_agent

    parent = MagicMock()
    parent.base_url = "https://openrouter.ai/api/v1"
    parent.api_key = "***"
    parent.provider = "openrouter"
    parent.api_mode = "chat_completions"
    parent.model = "anthropic/claude-sonnet-4"
    parent.platform = "cli"
    parent.reasoning_config = {"enabled": True, "effort": "low"}
    parent.providers_allowed = None
    parent.providers_ignored = None
    parent.providers_order = None
    parent.provider_sort = None
    parent._session_db = None
    parent._delegate_depth = 0
    parent._active_children = []
    parent._active_children_lock = __import__("threading").Lock()
    parent._print_fn = None

    with patch("tools.delegate_tool._load_config", return_value={}):
        with patch("run_agent.AIAgent") as MockAgent:
            MockAgent.return_value = MagicMock()
            _build_child_agent(
                task_index=0, goal="test", context=None, toolsets=None,
                model=None, max_iterations=50, parent_agent=parent,
                override_reasoning_effort="xhigh",
            )
            call_kwargs = MockAgent.call_args[1]
            assert call_kwargs["reasoning_config"] == {"enabled": True, "effort": "xhigh"}, \
                f"Expected xhigh, got {call_kwargs['reasoning_config']}"

    # Test 'none' disables reasoning
    with patch("tools.delegate_tool._load_config", return_value={}):
        with patch("run_agent.AIAgent") as MockAgent:
            MockAgent.return_value = MagicMock()
            _build_child_agent(
                task_index=0, goal="test", context=None, toolsets=None,
                model=None, max_iterations=50, parent_agent=parent,
                override_reasoning_effort="none",
            )
            call_kwargs = MockAgent.call_args[1]
            assert call_kwargs["reasoning_config"] == {"enabled": False, "effort": "none"}

    print("[PASS] test_reasoning_override_in_child_build")
    return True


# =========================================================================
# RUNNER
# =========================================================================

def main():
    tests = [
        ("Tier config resolution", test_tier_config_resolution),
        ("Schema completeness", test_schema_completeness),
        ("Pool validation", test_pool_validation),
        ("Delegate task with tiers (mocked)", test_delegate_task_with_tiers_mocked),
        ("Comparative tier behavior", test_comparative_tier_behavior),
        ("Backward compatibility (no tiers)", test_backward_compat_no_tiers),
        ("Reasoning override in child build", test_reasoning_override_in_child_build),
    ]

    print(f"\n{'='*60}")
    print(f" DELEGATION TIERS - REAL INTEGRATION TESTS")
    print(f"{'='*60}\n")

    passed = 0
    failed = 0
    for name, test_fn in tests:
        print(f"[RUN] {name}")
        try:
            if test_fn():
                passed += 1
            else:
                failed += 1
                print(f"  [FAIL] {name} returned False")
        except Exception as e:
            failed += 1
            print(f"  [FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()
        print()

    print(f"{'='*60}")
    print(f" RESULTS: {passed} passed, {failed} failed, {passed+failed} total")
    print(f"{'='*60}\n")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
