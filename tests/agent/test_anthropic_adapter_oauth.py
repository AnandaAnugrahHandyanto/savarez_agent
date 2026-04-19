"""OAuth-specific adapter tests for agent/anthropic_adapter.py.

These complement ``tests/agent/test_anthropic_adapter.py`` — this file only
covers OAuth transforms (billing/identity system blocks, tool name PascalCase
prefixing, per-request headers, 1M context env gate).  Cases already covered
by ``test_anthropic_adapter.py`` (auth detection, model normalization,
``_to_plain_data``, conversion of plain message/tool formats, etc.) are NOT
duplicated here.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from agent.anthropic_adapter import (
    _is_long_context_1m_enabled,
    _mcp_prefix_tool_name,
    _oauth_betas_for_model,
    _snake_to_pascal,
    _unmcp_prefix_tool_name,
    build_anthropic_kwargs,
    build_mcp_tool_name_map,
    normalize_anthropic_response,
)


# ---------------------------------------------------------------------------
# Snake / Pascal / MCP prefix helpers
# ---------------------------------------------------------------------------


class TestSnakeToPascal:
    def test_snake_case(self):
        assert _snake_to_pascal("read_file") == "ReadFile"

    def test_camel_case_is_title_cased(self):
        assert _snake_to_pascal("readFile") == "ReadFile"

    def test_kebab_case(self):
        assert _snake_to_pascal("read-file") == "ReadFile"

    def test_pascal_case_is_idempotent(self):
        assert _snake_to_pascal("ReadFile") == "ReadFile"

    def test_empty_string(self):
        assert _snake_to_pascal("") == ""

    def test_multi_part_snake(self):
        assert _snake_to_pascal("read_file_contents") == "ReadFileContents"


class TestMcpPrefix:
    def test_prefixes_snake_case(self):
        assert _mcp_prefix_tool_name("read_file") == "mcp_ReadFile"

    def test_idempotent_when_already_prefixed(self):
        assert _mcp_prefix_tool_name("mcp_already") == "mcp_already"

    def test_empty_string_passes_through(self):
        assert _mcp_prefix_tool_name("") == ""


class TestUnmcpPrefix:
    def test_without_map_strips_prefix_only(self):
        # PascalCase step is lossy — without the map the dispatcher gets the
        # PascalCase form.
        assert _unmcp_prefix_tool_name("mcp_ReadFile") == "ReadFile"

    def test_map_wins_over_pascal_stripping(self):
        result = _unmcp_prefix_tool_name(
            "mcp_ReadFile", {"mcp_ReadFile": "read_file"}
        )
        assert result == "read_file"

    def test_non_prefixed_name_passes_through(self):
        assert _unmcp_prefix_tool_name("plain_name") == "plain_name"


class TestBuildMcpToolNameMap:
    def test_top_level_name(self):
        assert build_mcp_tool_name_map([{"name": "x"}]) == {"mcp_X": "x"}

    def test_nested_function_name(self):
        assert build_mcp_tool_name_map(
            [{"function": {"name": "y"}}]
        ) == {"mcp_Y": "y"}

    def test_mixed_list(self):
        tools = [
            {"name": "a"},
            {"function": {"name": "b_tool"}},
        ]
        assert build_mcp_tool_name_map(tools) == {
            "mcp_A": "a",
            "mcp_BTool": "b_tool",
        }

    def test_none_returns_empty_dict(self):
        assert build_mcp_tool_name_map(None) == {}

    def test_empty_list_returns_empty_dict(self):
        assert build_mcp_tool_name_map([]) == {}

    def test_skips_tools_without_a_name(self):
        assert build_mcp_tool_name_map([{"foo": "bar"}]) == {}


# ---------------------------------------------------------------------------
# _oauth_betas_for_model
# ---------------------------------------------------------------------------


class TestOAuthBetasForModel:
    def test_opus_4_7_includes_expected_betas(self):
        betas = _oauth_betas_for_model("claude-opus-4-7-20250101")
        for required in (
            "effort-2025-11-24",
            "claude-code-20250219",
            "oauth-2025-04-20",
            "prompt-caching-scope-2026-01-05",
            "context-management-2025-06-27",
        ):
            assert required in betas, f"missing {required} in {betas}"

    def test_haiku_excludes_interleaved_thinking(self):
        # Haiku rejects interleaved-thinking; the function must drop it even
        # though it's not in the OAuth-only base list (defense in depth).
        betas = _oauth_betas_for_model("claude-haiku-4-5")
        assert "interleaved-thinking-2025-05-14" not in betas

    def test_opus_4_6_includes_1m_context_when_enabled(self):
        betas = _oauth_betas_for_model(
            "claude-opus-4-6", enable_1m_context=True
        )
        assert "context-1m-2025-08-07" in betas

    def test_opus_4_6_omits_1m_context_by_default(self):
        betas = _oauth_betas_for_model("claude-opus-4-6")
        assert "context-1m-2025-08-07" not in betas

    def test_haiku_never_gets_1m_context(self):
        # 1M context is Opus/Sonnet 4.6+ only — Haiku doesn't qualify.
        betas = _oauth_betas_for_model(
            "claude-haiku-4-5", enable_1m_context=True
        )
        assert "context-1m-2025-08-07" not in betas

    def test_exclude_removes_specific_beta(self):
        betas = _oauth_betas_for_model(
            "claude-opus-4-7", exclude={"effort-2025-11-24"}
        )
        assert "effort-2025-11-24" not in betas
        # Other OAuth-only betas should still be present.
        assert "oauth-2025-04-20" in betas


# ---------------------------------------------------------------------------
# _is_long_context_1m_enabled — env gate
# ---------------------------------------------------------------------------


class TestIsLongContext1mEnabled:
    def test_env_1_enables(self, monkeypatch):
        monkeypatch.setenv("HERMES_ANTHROPIC_1M_CONTEXT", "1")
        assert _is_long_context_1m_enabled() is True

    def test_env_true_enables(self, monkeypatch):
        monkeypatch.setenv("HERMES_ANTHROPIC_1M_CONTEXT", "true")
        assert _is_long_context_1m_enabled() is True

    def test_env_0_disables(self, monkeypatch):
        monkeypatch.setenv("HERMES_ANTHROPIC_1M_CONTEXT", "0")
        assert _is_long_context_1m_enabled() is False

    def test_env_false_disables(self, monkeypatch):
        monkeypatch.setenv("HERMES_ANTHROPIC_1M_CONTEXT", "false")
        assert _is_long_context_1m_enabled() is False

    def test_unset_env_returns_false_absent_config(self, monkeypatch):
        # The autouse test fixtures already isolate HERMES_HOME so
        # load_config() falls through to the default (which has no
        # anthropic.enable_1m_context set).
        monkeypatch.delenv("HERMES_ANTHROPIC_1M_CONTEXT", raising=False)
        assert _is_long_context_1m_enabled() is False


# ---------------------------------------------------------------------------
# build_anthropic_kwargs — OAuth behavioural tests
# ---------------------------------------------------------------------------


def _minimal_oauth_kwargs(model: str = "claude-opus-4-7", **overrides):
    """Helper: call build_anthropic_kwargs with OAuth defaults."""
    base = dict(
        model=model,
        messages=[{"role": "user", "content": "hi"}],
        tools=None,
        max_tokens=4096,
        reasoning_config=None,
        is_oauth=True,
    )
    base.update(overrides)
    return build_anthropic_kwargs(**base)


class TestBuildAnthropicKwargsOAuthSystem:
    def test_billing_block_is_system_index_0(self):
        kwargs = _minimal_oauth_kwargs()
        assert isinstance(kwargs["system"], list)
        assert kwargs["system"][0]["text"].startswith(
            "x-anthropic-billing-header:"
        )

    def test_identity_block_is_system_index_1(self):
        kwargs = _minimal_oauth_kwargs()
        assert (
            kwargs["system"][1]["text"]
            == "You are Claude Code, Anthropic's official CLI for Claude."
        )

    def test_system_list_has_exactly_two_entries(self):
        kwargs = _minimal_oauth_kwargs()
        assert len(kwargs["system"]) == 2

    def test_third_party_system_is_relocated_into_first_user_message(self):
        # Pre-existing system prose must move into the first user message.
        kwargs = build_anthropic_kwargs(
            model="claude-opus-4-7",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "hi"},
            ],
            tools=None,
            max_tokens=4096,
            reasoning_config=None,
            is_oauth=True,
        )

        # (a) system stays at 2 entries (billing + identity only).
        assert len(kwargs["system"]) == 2
        assert kwargs["system"][0]["text"].startswith("x-anthropic-billing-header:")
        assert kwargs["system"][1]["text"].startswith("You are Claude Code")

        # (b) Third-party prose was prepended to the first user message.
        first_user = next(
            m for m in kwargs["messages"] if m["role"] == "user"
        )
        content = first_user["content"]
        if isinstance(content, str):
            assert "You are a helpful assistant." in content
            assert content.startswith("You are a helpful assistant.")
        else:
            # Content is a list of blocks.
            joined = "".join(
                b.get("text", "") for b in content if isinstance(b, dict)
            )
            assert "You are a helpful assistant." in joined


class TestBuildAnthropicKwargsOAuthTools:
    def test_tool_names_are_pascal_mcp_prefixed(self):
        kwargs = _minimal_oauth_kwargs(
            tools=[
                {
                    "function": {
                        "name": "read_file",
                        "description": "x",
                        "parameters": {},
                    }
                }
            ],
        )
        tools = kwargs["tools"]
        assert len(tools) == 1
        assert tools[0]["name"] == "mcp_ReadFile"

    def test_historical_tool_use_blocks_are_renamed(self):
        # An earlier assistant tool_use block with the pre-transform name
        # must be rewritten so the model sees consistent names across turns.
        kwargs = build_anthropic_kwargs(
            model="claude-opus-4-7",
            messages=[
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "t1",
                            "name": "read_file",
                            "input": {},
                        }
                    ],
                },
                # Matching tool_result so the orphan-stripping pass doesn't
                # remove the tool_use before we can inspect it.
                {"role": "tool", "tool_call_id": "t1", "content": "result"},
            ],
            tools=[
                {
                    "function": {
                        "name": "read_file",
                        "description": "x",
                        "parameters": {},
                    }
                }
            ],
            max_tokens=4096,
            reasoning_config=None,
            is_oauth=True,
        )

        assistant = next(
            m for m in kwargs["messages"] if m["role"] == "assistant"
        )
        tool_use_blocks = [
            b for b in assistant["content"] if b.get("type") == "tool_use"
        ]
        assert len(tool_use_blocks) == 1
        assert tool_use_blocks[0]["name"] == "mcp_ReadFile"


class TestBuildAnthropicKwargsOAuthExtraHeaders:
    def test_x_client_request_id_is_a_uuid(self):
        kwargs = _minimal_oauth_kwargs()
        req_id = kwargs["extra_headers"]["x-client-request-id"]
        assert isinstance(req_id, str)
        # Raises ValueError on invalid UUID — test fails fast.
        uuid.UUID(req_id)

    def test_anthropic_beta_includes_effort_for_opus_4_7(self):
        kwargs = _minimal_oauth_kwargs(model="claude-opus-4-7")
        beta = kwargs["extra_headers"]["anthropic-beta"]
        assert "effort-2025-11-24" in beta

    def test_anthropic_beta_includes_effort_for_opus_4_6(self):
        kwargs = _minimal_oauth_kwargs(model="claude-opus-4-6")
        beta = kwargs["extra_headers"]["anthropic-beta"]
        assert "effort-2025-11-24" in beta

    def test_anthropic_beta_includes_oauth_only_betas(self):
        kwargs = _minimal_oauth_kwargs()
        beta = kwargs["extra_headers"]["anthropic-beta"]
        for required in (
            "oauth-2025-04-20",
            "claude-code-20250219",
            "prompt-caching-scope-2026-01-05",
            "context-management-2025-06-27",
        ):
            assert required in beta


class TestBuildAnthropicKwargsNonOAuth:
    def test_is_oauth_false_does_not_inject_billing_block(self):
        kwargs = build_anthropic_kwargs(
            model="claude-opus-4-7",
            messages=[
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "hi"},
            ],
            tools=None,
            max_tokens=4096,
            reasoning_config=None,
            is_oauth=False,
        )
        system = kwargs.get("system")
        # system can be string or list; in either case the billing prefix
        # must NOT appear.
        if isinstance(system, list):
            for block in system:
                text = block.get("text", "") if isinstance(block, dict) else ""
                assert not text.startswith("x-anthropic-billing-header:")
                assert not text.startswith(
                    "You are Claude Code, Anthropic's official CLI"
                )
        else:
            assert isinstance(system, (str, type(None)))
            if system:
                assert not system.startswith("x-anthropic-billing-header:")

    def test_is_oauth_false_does_not_mcp_prefix_tools(self):
        kwargs = build_anthropic_kwargs(
            model="claude-opus-4-7",
            messages=[{"role": "user", "content": "hi"}],
            tools=[
                {
                    "function": {
                        "name": "read_file",
                        "description": "x",
                        "parameters": {},
                    }
                }
            ],
            max_tokens=4096,
            reasoning_config=None,
            is_oauth=False,
        )
        assert kwargs["tools"][0]["name"] == "read_file"


# ---------------------------------------------------------------------------
# normalize_anthropic_response — strip_tool_prefix path
# ---------------------------------------------------------------------------


class TestNormalizeAnthropicResponseStripPrefix:
    def _fake_response(self, *, name: str, stop_reason: str = "tool_use"):
        return SimpleNamespace(
            content=[
                SimpleNamespace(
                    type="tool_use",
                    id="t1",
                    name=name,
                    input={"path": "/tmp"},
                )
            ],
            stop_reason=stop_reason,
        )

    def test_map_recovers_original_snake_case_name(self):
        response = self._fake_response(name="mcp_ReadFile")
        msg, finish = normalize_anthropic_response(
            response,
            strip_tool_prefix=True,
            tool_name_map={"mcp_ReadFile": "read_file"},
        )
        assert msg.tool_calls is not None
        assert msg.tool_calls[0].function.name == "read_file"
        assert finish == "tool_calls"

    def test_strip_without_map_falls_back_to_pascal(self):
        response = self._fake_response(name="mcp_ReadFile")
        msg, _ = normalize_anthropic_response(
            response, strip_tool_prefix=True, tool_name_map=None
        )
        # Without the map the PascalCase step is lossy — dispatcher accepts
        # either form, but the function returns the stripped PascalCase name.
        assert msg.tool_calls[0].function.name == "ReadFile"

    def test_no_strip_leaves_name_intact(self):
        response = self._fake_response(name="mcp_ReadFile")
        msg, _ = normalize_anthropic_response(
            response, strip_tool_prefix=False
        )
        assert msg.tool_calls[0].function.name == "mcp_ReadFile"
