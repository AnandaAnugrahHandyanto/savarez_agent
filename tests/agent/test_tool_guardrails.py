"""Pure tool-call guardrail primitive tests."""

import json

from agent.tool_guardrails import (
    ToolCallGuardrailConfig,
    ToolCallGuardrailController,
    ToolCallSignature,
    canonical_tool_args,
    classify_tool_failure,
)


def test_tool_call_signature_hashes_canonical_nested_unicode_args_without_exposing_raw_args():
    args_a = {
        "z": [{"β": "☤", "a": 1}],
        "a": {"y": 2, "x": "secret-token-value"},
    }
    args_b = {
        "a": {"x": "secret-token-value", "y": 2},
        "z": [{"a": 1, "β": "☤"}],
    }

    assert canonical_tool_args(args_a) == canonical_tool_args(args_b)
    sig_a = ToolCallSignature.from_call("web_search", args_a)
    sig_b = ToolCallSignature.from_call("web_search", args_b)

    assert sig_a == sig_b
    assert len(sig_a.args_hash) == 64
    metadata = sig_a.to_metadata()
    assert metadata == {"tool_name": "web_search", "args_hash": sig_a.args_hash}
    assert "secret-token-value" not in json.dumps(metadata)
    assert "☤" not in json.dumps(metadata)


def test_default_config_is_soft_warning_only_with_hard_stop_disabled():
    cfg = ToolCallGuardrailConfig()

    assert cfg.warnings_enabled is True
    assert cfg.hard_stop_enabled is False
    assert cfg.exact_failure_warn_after == 2
    assert cfg.same_tool_failure_warn_after == 3
    assert cfg.no_progress_warn_after == 2
    assert cfg.exact_failure_block_after == 5
    assert cfg.same_tool_failure_halt_after == 8
    assert cfg.no_progress_block_after == 5


def test_config_parses_nested_warn_and_hard_stop_thresholds():
    cfg = ToolCallGuardrailConfig.from_mapping(
        {
            "warnings_enabled": False,
            "hard_stop_enabled": True,
            "warn_after": {
                "exact_failure": 3,
                "same_tool_failure": 4,
                "idempotent_no_progress": 5,
            },
            "hard_stop_after": {
                "exact_failure": 6,
                "same_tool_failure": 7,
                "idempotent_no_progress": 8,
            },
        }
    )

    assert cfg.warnings_enabled is False
    assert cfg.hard_stop_enabled is True
    assert cfg.exact_failure_warn_after == 3
    assert cfg.same_tool_failure_warn_after == 4
    assert cfg.no_progress_warn_after == 5
    assert cfg.exact_failure_block_after == 6
    assert cfg.same_tool_failure_halt_after == 7
    assert cfg.no_progress_block_after == 8


def test_default_repeated_identical_failed_call_warns_without_blocking():
    controller = ToolCallGuardrailController()
    args = {"query": "same"}

    decisions = []
    for _ in range(5):
        assert controller.before_call("web_search", args).action == "allow"
        decisions.append(
            controller.after_call("web_search", args, '{"error":"boom"}', failed=True)
        )

    assert decisions[0].action == "allow"
    assert [d.action for d in decisions[1:]] == ["warn", "warn", "warn", "warn"]
    assert {d.code for d in decisions[1:]} == {"repeated_exact_failure_warning"}
    assert controller.before_call("web_search", args).action == "allow"
    assert controller.halt_decision is None


def test_hard_stop_enabled_blocks_repeated_exact_failure_before_next_execution():
    controller = ToolCallGuardrailController(
        ToolCallGuardrailConfig(
            hard_stop_enabled=True,
            exact_failure_warn_after=2,
            exact_failure_block_after=2,
            same_tool_failure_halt_after=99,
        )
    )
    args = {"query": "same"}

    assert controller.before_call("web_search", args).action == "allow"
    first = controller.after_call("web_search", args, '{"error":"boom"}', failed=True)
    assert first.action == "allow"

    assert controller.before_call("web_search", args).action == "allow"
    second = controller.after_call("web_search", args, '{"error":"boom"}', failed=True)
    assert second.action == "warn"
    assert second.code == "repeated_exact_failure_warning"

    blocked = controller.before_call("web_search", args)
    assert blocked.action == "block"
    assert blocked.code == "repeated_exact_failure_block"
    assert blocked.count == 2


def _memory_quota_result(operation="add", store_state_token="opaque:A", **quota_usage):
    payload = {
        "success": False,
        "target": "user",
        "store": "user",
        "store_state_token": store_state_token,
        "error": "Memory at 1,371/1,375 chars. Adding this entry would exceed the limit.",
        "error_code": "memory_quota_exceeded",
        "error_details": {
            "code": "memory_quota_exceeded",
            "operation": operation,
        },
        "quota_usage": {
            "current_chars": 1371,
            "limit_chars": 1375,
            "remaining_chars": 4,
            "attempted_total_chars": 1500,
            "over_by_chars": 125,
            "quota_unit": "serialized_chars",
            **quota_usage,
        },
    }
    return json.dumps(payload)


def test_memory_quota_failure_skips_identical_retry_under_same_store_state():
    controller = ToolCallGuardrailController()
    args = {
        "action": "add",
        "target": "user",
        "content": "same oversized memory",
    }

    assert controller.before_call("memory", args, current_store_state_token="opaque:A").action == "allow"
    first = controller.after_call("memory", args, _memory_quota_result(), failed=True)
    assert first.action == "warn"
    assert first.code == "memory_quota_exceeded_non_retryable"

    skipped = controller.before_call("memory", args, current_store_state_token="opaque:A")
    assert skipped.action == "skip"
    assert skipped.code == "memory_quota_exceeded_non_retryable"
    assert skipped.allows_execution is False
    assert skipped.should_halt is False
    assert "already exceeded quota" in skipped.message


def test_memory_quota_retry_is_allowed_after_store_state_changes():
    controller = ToolCallGuardrailController()
    args = {"action": "add", "target": "user", "content": "same oversized memory"}

    controller.before_call("memory", args, current_store_state_token="opaque:A")
    controller.after_call("memory", args, _memory_quota_result(store_state_token="opaque:A"), failed=True)

    retry = controller.before_call("memory", args, current_store_state_token="opaque:B")
    assert retry.action == "allow"


def test_memory_quota_retry_is_allowed_when_arguments_change():
    controller = ToolCallGuardrailController()
    args = {"action": "add", "target": "user", "content": "same oversized memory"}
    shorter = {"action": "add", "target": "user", "content": "short"}

    controller.before_call("memory", args, current_store_state_token="opaque:A")
    controller.after_call("memory", args, _memory_quota_result(store_state_token="opaque:A"), failed=True)

    retry = controller.before_call("memory", shorter, current_store_state_token="opaque:A")
    assert retry.action == "allow"


def test_memory_quota_fingerprint_normalizes_key_order_and_trailing_content_whitespace():
    controller = ToolCallGuardrailController()
    args_a = {"action": "add", "target": "user", "content": "same oversized memory   "}
    args_b = {"target": "user", "content": "same oversized memory", "action": "add"}

    controller.before_call("memory", args_a, current_store_state_token="opaque:A")
    controller.after_call("memory", args_a, _memory_quota_result(store_state_token="opaque:A"), failed=True)

    skipped = controller.before_call("memory", args_b, current_store_state_token="opaque:A")
    assert skipped.action == "skip"
    assert skipped.should_halt is False


def test_replace_quota_overflow_uses_structured_code_not_error_wording():
    controller = ToolCallGuardrailController()
    args = {"action": "replace", "target": "memory", "old_text": "alpha", "content": "expanded"}
    result = _memory_quota_result(operation="replace", store_state_token="opaque:R")

    controller.before_call("memory", args, current_store_state_token="opaque:R")
    first = controller.after_call("memory", args, result, failed=True)
    assert first.code == "memory_quota_exceeded_non_retryable"

    skipped = controller.before_call("memory", args, current_store_state_token="opaque:R")
    assert skipped.action == "skip"
    assert skipped.should_halt is False


def test_legacy_memory_quota_error_string_does_not_crash_guardrail():
    controller = ToolCallGuardrailController()
    args = {"action": "replace", "target": "memory", "old_text": "alpha", "content": "beta"}
    result = json.dumps({
        "success": False,
        "error": (
            "Replacement would put memory at 1,431/1,375 chars. "
            "Shorten the new content or remove other entries first."
        ),
    })

    controller.before_call("memory", args, current_store_state_token="opaque:A")
    decision = controller.after_call("memory", args, result, failed=True)
    retry = controller.before_call("memory", args, current_store_state_token="opaque:A")

    assert decision.action in {"allow", "warn"}
    assert retry.action == "allow"


def test_memory_quota_fallback_classifier_matches_display_full_suffix():
    structured = _memory_quota_result(operation="replace", store_state_token="opaque:R")
    legacy = json.dumps({
        "success": False,
        "error": (
            "Replacement would put memory at 1,431/1,375 chars. "
            "Shorten the new content or remove other entries first."
        ),
    })

    assert classify_tool_failure("memory", structured) == (True, " [full]")
    assert classify_tool_failure("memory", legacy) == (True, " [full]")


def test_memory_quota_budget_suppresses_further_space_increasing_writes_without_halting():
    controller = ToolCallGuardrailController(
        ToolCallGuardrailConfig(memory_quota_failure_suppress_after=2)
    )

    first_args = {"action": "add", "target": "user", "content": "oversized one"}
    second_args = {"action": "add", "target": "user", "content": "oversized two"}

    controller.before_call("memory", first_args, current_store_state_token="opaque:A")
    controller.after_call("memory", first_args, _memory_quota_result(store_state_token="opaque:A"), failed=True)
    controller.before_call("memory", second_args, current_store_state_token="opaque:A")
    controller.after_call("memory", second_args, _memory_quota_result(store_state_token="opaque:A"), failed=True)

    suppressed = controller.before_call(
        "memory",
        {"action": "add", "target": "user", "content": "oversized three"},
        current_store_state_token="opaque:A",
    )
    assert suppressed.action == "skip"
    assert suppressed.code == "memory_quota_write_suppressed"
    assert suppressed.allows_execution is False
    assert suppressed.should_halt is False

    remove = controller.before_call(
        "memory",
        {"action": "remove", "target": "user", "old_text": "obsolete"},
        current_store_state_token="opaque:A",
    )
    assert remove.action == "allow"


def test_memory_quota_budget_allows_clearly_shrinking_replace():
    controller = ToolCallGuardrailController(
        ToolCallGuardrailConfig(memory_quota_failure_suppress_after=2)
    )

    first_args = {"action": "add", "target": "user", "content": "oversized one"}
    second_args = {"action": "add", "target": "user", "content": "oversized two"}

    controller.before_call("memory", first_args, current_store_state_token="opaque:A")
    controller.after_call("memory", first_args, _memory_quota_result(store_state_token="opaque:A"), failed=True)
    controller.before_call("memory", second_args, current_store_state_token="opaque:A")
    controller.after_call("memory", second_args, _memory_quota_result(store_state_token="opaque:A"), failed=True)

    shrinking_replace = controller.before_call(
        "memory",
        {
            "action": "replace",
            "target": "user",
            "old_text": "long obsolete memory entry",
            "content": "short",
        },
        current_store_state_token="opaque:A",
    )
    assert shrinking_replace.action == "allow"


def test_memory_quota_budget_allows_replace_when_old_text_is_only_selector():
    controller = ToolCallGuardrailController(
        ToolCallGuardrailConfig(memory_quota_failure_suppress_after=2)
    )

    first_args = {"action": "add", "target": "user", "content": "oversized one"}
    second_args = {"action": "add", "target": "user", "content": "oversized two"}

    controller.before_call("memory", first_args, current_store_state_token="opaque:A")
    controller.after_call("memory", first_args, _memory_quota_result(store_state_token="opaque:A"), failed=True)
    controller.before_call("memory", second_args, current_store_state_token="opaque:A")
    controller.after_call("memory", second_args, _memory_quota_result(store_state_token="opaque:A"), failed=True)

    selector_replace = controller.before_call(
        "memory",
        {"action": "replace", "target": "user", "old_text": "abc", "content": "compact replacement"},
        current_store_state_token="opaque:A",
    )

    assert selector_replace.action == "allow"


def test_memory_quota_budget_allows_space_increasing_write_after_store_state_changes():
    controller = ToolCallGuardrailController(
        ToolCallGuardrailConfig(memory_quota_failure_suppress_after=2)
    )

    args = {"action": "add", "target": "user", "content": "oversized one"}
    second_args = {"action": "add", "target": "user", "content": "oversized two"}

    controller.before_call("memory", args, current_store_state_token="opaque:A")
    controller.after_call("memory", args, _memory_quota_result(store_state_token="opaque:A"), failed=True)
    controller.before_call("memory", second_args, current_store_state_token="opaque:A")
    controller.after_call("memory", second_args, _memory_quota_result(store_state_token="opaque:A"), failed=True)

    controller.after_call(
        "memory",
        {"action": "remove", "target": "user", "old_text": "obsolete"},
        json.dumps({"success": True, "target": "user", "store": "user", "store_state_token": "opaque:B"}),
        failed=False,
    )

    retry = controller.before_call("memory", args, current_store_state_token="opaque:B")
    assert retry.action == "allow"


def test_structured_memory_quota_failure_is_detected_when_failed_flag_is_omitted():
    controller = ToolCallGuardrailController()
    args = {"action": "add", "target": "user", "content": "same oversized memory"}
    result = _memory_quota_result(store_state_token="opaque:A")
    payload = json.loads(result)
    payload.pop("error")
    result = json.dumps(payload)

    controller.before_call("memory", args, current_store_state_token="opaque:A")
    first = controller.after_call("memory", args, result)
    assert first.action == "warn"
    assert first.code == "memory_quota_exceeded_non_retryable"

    skipped = controller.before_call("memory", args, current_store_state_token="opaque:A")
    assert skipped.action == "skip"
    assert skipped.code == "memory_quota_exceeded_non_retryable"


def test_structured_memory_quota_failure_overrides_false_failed_flag():
    controller = ToolCallGuardrailController()
    args = {"action": "add", "target": "user", "content": "same oversized memory"}
    result = _memory_quota_result(store_state_token="opaque:A")
    payload = json.loads(result)
    payload.pop("error")
    result = json.dumps(payload)

    controller.before_call("memory", args, current_store_state_token="opaque:A")
    first = controller.after_call("memory", args, result, failed=False)
    assert first.action == "warn"
    assert first.code == "memory_quota_exceeded_non_retryable"

    skipped = controller.before_call("memory", args, current_store_state_token="opaque:A")
    assert skipped.action == "skip"
    assert skipped.code == "memory_quota_exceeded_non_retryable"
def test_success_resets_exact_signature_failure_streak():
    controller = ToolCallGuardrailController(
        ToolCallGuardrailConfig(hard_stop_enabled=True, exact_failure_block_after=2, same_tool_failure_halt_after=99)
    )
    args = {"query": "same"}

    controller.after_call("web_search", args, '{"error":"boom"}', failed=True)
    controller.after_call("web_search", args, '{"ok":true}', failed=False)

    assert controller.before_call("web_search", args).action == "allow"
    controller.after_call("web_search", args, '{"error":"boom"}', failed=True)
    assert controller.before_call("web_search", args).action == "allow"


def test_file_mutation_lint_error_result_is_not_a_tool_failure():
    write_result = json.dumps({
        "bytes_written": 12,
        "lint": {"status": "error", "output": "SyntaxError: invalid syntax"},
    })
    patch_result = json.dumps({
        "success": True,
        "diff": "--- a/tmp.py\n+++ b/tmp.py\n",
        "lsp_diagnostics": "<diagnostics>ERROR [1:1] type mismatch</diagnostics>",
    })

    assert classify_tool_failure("write_file", write_result) == (False, "")
    assert classify_tool_failure("patch", patch_result) == (False, "")


def test_same_tool_varying_args_warns_by_default_without_halting():
    controller = ToolCallGuardrailController(
        ToolCallGuardrailConfig(same_tool_failure_warn_after=2, same_tool_failure_halt_after=3)
    )

    first = controller.after_call("terminal", {"command": "cmd-1"}, '{"exit_code":1}', failed=True)
    second = controller.after_call("terminal", {"command": "cmd-2"}, '{"exit_code":1}', failed=True)
    third = controller.after_call("terminal", {"command": "cmd-3"}, '{"exit_code":1}', failed=True)
    fourth = controller.after_call("terminal", {"command": "cmd-4"}, '{"exit_code":1}', failed=True)

    assert first.action == "allow"
    assert [second.action, third.action, fourth.action] == ["warn", "warn", "warn"]
    assert {second.code, third.code, fourth.code} == {"same_tool_failure_warning"}
    assert "Do not switch to text-only replies" in second.message
    assert "keep using tools" in second.message
    assert "diagnose before retrying" in second.message
    assert "different tool" in second.message
    assert controller.halt_decision is None


def test_hard_stop_enabled_halts_same_tool_varying_args_failure_streak():
    controller = ToolCallGuardrailController(
        ToolCallGuardrailConfig(
            hard_stop_enabled=True,
            exact_failure_block_after=99,
            same_tool_failure_warn_after=2,
            same_tool_failure_halt_after=3,
        )
    )

    first = controller.after_call("terminal", {"command": "cmd-1"}, '{"exit_code":1}', failed=True)
    assert first.action == "allow"
    second = controller.after_call("terminal", {"command": "cmd-2"}, '{"exit_code":1}', failed=True)
    assert second.action == "warn"
    assert second.code == "same_tool_failure_warning"
    third = controller.after_call("terminal", {"command": "cmd-3"}, '{"exit_code":1}', failed=True)
    assert third.action == "halt"
    assert third.code == "same_tool_failure_halt"
    assert third.count == 3


def test_idempotent_no_progress_repeated_result_warns_without_blocking_by_default():
    controller = ToolCallGuardrailController(
        ToolCallGuardrailConfig(no_progress_warn_after=2, no_progress_block_after=2)
    )
    args = {"path": "/tmp/same.txt"}
    result = "same file contents"

    for _ in range(4):
        assert controller.before_call("read_file", args).action == "allow"
        decision = controller.after_call("read_file", args, result, failed=False)

    assert decision.action == "warn"
    assert decision.code == "idempotent_no_progress_warning"
    assert controller.before_call("read_file", args).action == "allow"
    assert controller.halt_decision is None


def test_hard_stop_enabled_blocks_idempotent_no_progress_future_repeat():
    controller = ToolCallGuardrailController(
        ToolCallGuardrailConfig(
            hard_stop_enabled=True,
            no_progress_warn_after=2,
            no_progress_block_after=2,
        )
    )
    args = {"path": "/tmp/same.txt"}
    result = "same file contents"

    assert controller.before_call("read_file", args).action == "allow"
    assert controller.after_call("read_file", args, result, failed=False).action == "allow"
    assert controller.before_call("read_file", args).action == "allow"
    warn = controller.after_call("read_file", args, result, failed=False)
    assert warn.action == "warn"
    assert warn.code == "idempotent_no_progress_warning"

    blocked = controller.before_call("read_file", args)
    assert blocked.action == "block"
    assert blocked.code == "idempotent_no_progress_block"


def test_mutating_or_unknown_tools_are_not_blocked_for_repeated_identical_success_output_by_default():
    controller = ToolCallGuardrailController(
        ToolCallGuardrailConfig(no_progress_warn_after=2, no_progress_block_after=2)
    )

    for _ in range(3):
        assert controller.before_call("write_file", {"path": "/tmp/x", "content": "x"}).action == "allow"
        assert controller.after_call("write_file", {"path": "/tmp/x", "content": "x"}, "ok", failed=False).action == "allow"
        assert controller.before_call("custom_tool", {"x": 1}).action == "allow"
        assert controller.after_call("custom_tool", {"x": 1}, "ok", failed=False).action == "allow"


def test_reset_for_turn_clears_bounded_guardrail_state():
    controller = ToolCallGuardrailController(
        ToolCallGuardrailConfig(hard_stop_enabled=True, exact_failure_block_after=2, no_progress_block_after=2)
    )
    controller.after_call("web_search", {"query": "same"}, '{"error":"boom"}', failed=True)
    controller.after_call("web_search", {"query": "same"}, '{"error":"boom"}', failed=True)
    controller.after_call("read_file", {"path": "/tmp/x"}, "same", failed=False)
    controller.after_call("read_file", {"path": "/tmp/x"}, "same", failed=False)

    assert controller.before_call("web_search", {"query": "same"}).action == "block"
    assert controller.before_call("read_file", {"path": "/tmp/x"}).action == "block"

    controller.reset_for_turn()

    assert controller.before_call("web_search", {"query": "same"}).action == "allow"
    assert controller.before_call("read_file", {"path": "/tmp/x"}).action == "allow"
