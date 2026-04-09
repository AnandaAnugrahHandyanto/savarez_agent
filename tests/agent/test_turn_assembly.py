from types import SimpleNamespace

from agent.memory_manager import build_memory_context_block
from agent.turn_assembly import (
    apply_turn_assembly_to_user_message,
    assemble_turn_context,
    compose_effective_system_prompt,
    inject_prefill_messages,
)


def test_assemble_turn_context_without_injection_returns_original_user_content():
    assembly = assemble_turn_context("hello")

    assert assembly.assembled_user_message == "hello"
    assert apply_turn_assembly_to_user_message(
        {"role": "user", "content": "hello"},
        assembly,
    ) == {"role": "user", "content": "hello"}


def test_memory_block_appended_before_plugin_user_context():
    assembly = assemble_turn_context(
        "hello",
        memory_context="remember this",
        plugin_user_context="plugin context",
    )

    assert assembly.assembled_user_message == (
        "hello\n\n"
        f"{build_memory_context_block('remember this')}\n\n"
        "plugin context"
    )


def test_reference_result_message_replaces_original_user_text_for_api_call_time_assembly():
    reference_result = SimpleNamespace(
        message="expanded message",
        expanded=True,
        blocked=False,
        warnings=["warn"],
        injected_tokens=12,
        references=[
            SimpleNamespace(kind="file"),
            SimpleNamespace(kind="file"),
            SimpleNamespace(kind="git"),
        ],
    )

    assembly = assemble_turn_context(
        "original message",
        plugin_user_context="plugin context",
        reference_result=reference_result,
    )

    assert assembly.assembled_user_message == "expanded message\n\nplugin context"
    assert assembly.original_user_message == "original message"
    assert assembly.references_expanded is True
    assert assembly.references_blocked is False
    assert assembly.warnings == ["warn"]
    assert assembly.metadata["reference_injected_tokens"] == 12
    assert assembly.metadata["reference_summary"] == {
        "count": 3,
        "kinds": {"file": 2, "git": 1},
    }
    assert assembly.lineage["reference_preprocessed"] is True
    assert assembly.lineage["references_expanded"] is True


def test_apply_turn_assembly_preserves_non_string_user_content():
    assembly = assemble_turn_context("expanded text", plugin_user_context="plugin context")
    message = {
        "role": "user",
        "content": [{"type": "text", "text": "hello"}],
    }

    result = apply_turn_assembly_to_user_message(message, assembly)

    assert result == message
    assert result is not message



def test_build_side_channel_context_skips_blank_contexts():
    assembly = assemble_turn_context(
        "hello",
        memory_context="   ",
        plugin_user_context="  \n\t  ",
    )

    assert assembly.side_channel.flatten() == []
    assert assembly.assembled_user_message == "hello"


def test_compose_effective_system_prompt_joins_base_and_ephemeral_with_one_blank_line():
    assert compose_effective_system_prompt("base", "ephemeral") == "base\n\nephemeral"


def test_inject_prefill_messages_inserts_after_system_message_when_present():
    api_messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "u"},
    ]
    prefill_messages = [
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u1"},
    ]

    result = inject_prefill_messages(api_messages, prefill_messages, "sys")

    assert result == [
        {"role": "system", "content": "sys"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u1"},
        {"role": "user", "content": "u"},
    ]
    assert api_messages == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "u"},
    ]


def test_inject_prefill_messages_inserts_at_start_when_no_system_message():
    api_messages = [{"role": "user", "content": "u"}]
    prefill_messages = [{"role": "assistant", "content": "a1"}]

    result = inject_prefill_messages(api_messages, prefill_messages, "")

    assert result == [
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u"},
    ]
