"""Тесты обхода бага kilo gateway для DeepSeek thinking-моделей.

Проблема: kilo gateway срезает reasoning_content/reasoning/reasoning_details
при форварде в upstream DeepSeek. Для thinking-моделей (deepseek-v3.2+,
v4-pro/flash, deepseek-reasoner) DeepSeek на history с tool_calls требует
reasoning_content и вдобавок не переносит user-сообщение после tool-результата,
— иначе отвечает 400:
"The `reasoning_content` in the thinking mode must be passed back to the API."

Обход:
1) на assistant+tool_calls без reasoning подставляем reasoning_content="."
2) сливаем user/assistant-text после последнего tool в его content.
"""

import sys
import types

sys.modules.setdefault("fire", types.SimpleNamespace(Fire=lambda *a, **k: None))
sys.modules.setdefault("firecrawl", types.SimpleNamespace(Firecrawl=object))
sys.modules.setdefault("fal_client", types.SimpleNamespace())

from run_agent import AIAgent


class _FakeOpenAI:
    def __init__(self, **kw):
        self.api_key = kw.get("api_key", "test")
        self.base_url = kw.get("base_url", "http://test")
    def close(self):
        pass


def _tool_defs(*names):
    return [
        {
            "type": "function",
            "function": {
                "name": n,
                "description": f"{n} tool",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for n in names
    ]


def _make_agent(monkeypatch, base_url, model):
    monkeypatch.setattr("run_agent.get_tool_definitions", lambda **kw: _tool_defs("terminal"))
    monkeypatch.setattr("run_agent.check_toolset_requirements", lambda: {})
    monkeypatch.setattr("run_agent.OpenAI", _FakeOpenAI)
    return AIAgent(
        api_key="test-key",
        base_url=base_url,
        provider="kilocode",
        api_mode="chat_completions",
        max_iterations=4,
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
        model=model,
    )


class TestNeedsDeepseekThinkingToolMerge:
    def test_kilo_plus_deepseek_v4_pro_triggers(self, monkeypatch):
        agent = _make_agent(monkeypatch, "https://api.kilo.ai/api/gateway", "deepseek/deepseek-v4-pro")
        assert agent._needs_deepseek_thinking_tool_merge() is True

    def test_kilo_plus_deepseek_v4_flash_triggers(self, monkeypatch):
        agent = _make_agent(monkeypatch, "https://api.kilo.ai/api/gateway", "deepseek/deepseek-v4-flash")
        assert agent._needs_deepseek_thinking_tool_merge() is True

    def test_kilo_plus_deepseek_reasoner_triggers(self, monkeypatch):
        agent = _make_agent(monkeypatch, "https://api.kilo.ai/api/gateway", "deepseek/deepseek-reasoner")
        assert agent._needs_deepseek_thinking_tool_merge() is True

    def test_kilo_plus_deepseek_chat_does_not_trigger(self, monkeypatch):
        # deepseek-chat — non-thinking, бага не происходит
        agent = _make_agent(monkeypatch, "https://api.kilo.ai/api/gateway", "deepseek/deepseek-chat")
        assert agent._needs_deepseek_thinking_tool_merge() is False

    def test_kilo_plus_non_deepseek_does_not_trigger(self, monkeypatch):
        agent = _make_agent(monkeypatch, "https://api.kilo.ai/api/gateway", "anthropic/claude-sonnet-4.6")
        assert agent._needs_deepseek_thinking_tool_merge() is False

    def test_non_kilo_plus_deepseek_does_not_trigger(self, monkeypatch):
        agent = _make_agent(monkeypatch, "https://openrouter.ai/api/v1", "deepseek/deepseek-v4-pro")
        assert agent._needs_deepseek_thinking_tool_merge() is False


class TestMergePostToolTextIntoTool:
    def test_no_messages_returns_empty(self):
        assert AIAgent._merge_post_tool_text_into_tool([]) == []

    def test_no_tool_message_returns_unchanged(self):
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        assert AIAgent._merge_post_tool_text_into_tool(msgs) == msgs

    def test_no_trailing_after_tool_returns_unchanged(self):
        msgs = [
            {"role": "user", "content": "check"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function",
                "function": {"name": "terminal", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "ok"},
        ]
        assert AIAgent._merge_post_tool_text_into_tool(msgs) == msgs

    def test_trailing_user_merges_into_last_tool(self):
        msgs = [
            {"role": "user", "content": "check"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function",
                "function": {"name": "terminal", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "ok"},
            {"role": "user", "content": "thanks"},
        ]
        fixed = AIAgent._merge_post_tool_text_into_tool(msgs)
        assert len(fixed) == 3
        assert fixed[-1]["role"] == "tool"
        assert "ok" in fixed[-1]["content"]
        assert "thanks" in fixed[-1]["content"]

    def test_multiple_trailing_users_all_merged(self):
        msgs = [
            {"role": "user", "content": "check"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function",
                "function": {"name": "terminal", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "ok"},
            {"role": "user", "content": "msg1"},
            {"role": "user", "content": "msg2"},
            {"role": "user", "content": "msg3"},
        ]
        fixed = AIAgent._merge_post_tool_text_into_tool(msgs)
        assert len(fixed) == 3
        for mark in ("msg1", "msg2", "msg3"):
            assert mark in fixed[-1]["content"]

    def test_trailing_asst_text_and_user_merged(self):
        msgs = [
            {"role": "user", "content": "check"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function",
                "function": {"name": "terminal", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "ok"},
            {"role": "assistant", "content": "Всё в порядке."},
            {"role": "user", "content": "спасибо"},
        ]
        fixed = AIAgent._merge_post_tool_text_into_tool(msgs)
        assert len(fixed) == 3
        assert "Всё в порядке" in fixed[-1]["content"]
        assert "спасибо" in fixed[-1]["content"]

    def test_trailing_asst_with_tool_calls_does_not_merge(self):
        # Если после последнего tool идёт ещё один tool-round,
        # сливать нельзя — это нарушит структуру.
        msgs = [
            {"role": "user", "content": "check"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function",
                "function": {"name": "terminal", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "ok"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "c2", "type": "function",
                "function": {"name": "terminal", "arguments": "{}"}}]},
        ]
        fixed = AIAgent._merge_post_tool_text_into_tool(msgs)
        assert fixed == msgs

    def test_does_not_mutate_input_list(self):
        original = [
            {"role": "user", "content": "check"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function",
                "function": {"name": "terminal", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "ok"},
            {"role": "user", "content": "thanks"},
        ]
        snapshot = [dict(m) for m in original]
        AIAgent._merge_post_tool_text_into_tool(original)
        assert original == snapshot

    def test_multiple_tool_rounds_only_last_gets_merge(self):
        msgs = [
            {"role": "user", "content": "check twice"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function",
                "function": {"name": "terminal", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "first"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "c2", "type": "function",
                "function": {"name": "terminal", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c2", "content": "second"},
            {"role": "user", "content": "done?"},
        ]
        fixed = AIAgent._merge_post_tool_text_into_tool(msgs)
        assert len(fixed) == 5
        # первый tool не тронут
        assert fixed[2]["content"] == "first"
        # второй tool — с примёрженным user
        assert "second" in fixed[-1]["content"]
        assert "done?" in fixed[-1]["content"]


class TestCopyReasoningContentForKiloDeepseek:
    def test_dot_injected_on_tool_calls_when_no_reasoning(self, monkeypatch):
        agent = _make_agent(monkeypatch, "https://api.kilo.ai/api/gateway", "deepseek/deepseek-v4-pro")
        src = {"role": "assistant", "content": None,
               "tool_calls": [{"id": "c1", "type": "function",
                              "function": {"name": "terminal", "arguments": "{}"}}]}
        api_msg = dict(src)
        agent._copy_reasoning_content_for_api(src, api_msg)
        assert api_msg["reasoning_content"] == "."

    def test_explicit_reasoning_content_preserved(self, monkeypatch):
        agent = _make_agent(monkeypatch, "https://api.kilo.ai/api/gateway", "deepseek/deepseek-v4-pro")
        src = {"role": "assistant", "content": "ok",
               "reasoning_content": "мой прошлый reasoning",
               "tool_calls": [{"id": "c1", "type": "function",
                              "function": {"name": "terminal", "arguments": "{}"}}]}
        api_msg = dict(src)
        agent._copy_reasoning_content_for_api(src, api_msg)
        assert api_msg["reasoning_content"] == "мой прошлый reasoning"

    def test_reasoning_converted_to_reasoning_content(self, monkeypatch):
        agent = _make_agent(monkeypatch, "https://api.kilo.ai/api/gateway", "deepseek/deepseek-v4-pro")
        src = {"role": "assistant", "content": "ok",
               "reasoning": "openrouter-формат",
               "tool_calls": [{"id": "c1", "type": "function",
                              "function": {"name": "terminal", "arguments": "{}"}}]}
        api_msg = dict(src)
        agent._copy_reasoning_content_for_api(src, api_msg)
        assert api_msg["reasoning_content"] == "openrouter-формат"

    def test_no_injection_on_non_deepseek_thinking_provider(self, monkeypatch):
        agent = _make_agent(monkeypatch, "https://openrouter.ai/api/v1", "deepseek/deepseek-v4-pro")
        src = {"role": "assistant", "content": None,
               "tool_calls": [{"id": "c1", "type": "function",
                              "function": {"name": "terminal", "arguments": "{}"}}]}
        api_msg = dict(src)
        agent._copy_reasoning_content_for_api(src, api_msg)
        # на openrouter ничего не должно подставиться
        assert "reasoning_content" not in api_msg

    def test_no_injection_when_no_tool_calls(self, monkeypatch):
        agent = _make_agent(monkeypatch, "https://api.kilo.ai/api/gateway", "deepseek/deepseek-v4-pro")
        src = {"role": "assistant", "content": "просто текст"}
        api_msg = dict(src)
        agent._copy_reasoning_content_for_api(src, api_msg)
        assert "reasoning_content" not in api_msg
