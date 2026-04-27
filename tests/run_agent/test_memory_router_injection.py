"""Tests for AIAgent current-turn memory context preparation."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _bare_agent():
    from run_agent import AIAgent

    agent = AIAgent.__new__(AIAgent)
    agent._memory_manager = MagicMock()
    agent._memory_manager.prefetch_all.return_value = ""
    agent._memory_manager.recall_now_all.return_value = "Nutrition plan: 2 meals/day, high protein."
    agent.session_id = "session-1"
    agent._user_turn_count = 1
    return agent


def _make_tool_defs(*names: str) -> list:
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": f"{name} tool",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for name in names
    ]


def _mock_response(content="Final answer", finish_reason="stop"):
    message = SimpleNamespace(content=content, tool_calls=None)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice], model="test/model", usage=None)


def _real_agent():
    from run_agent import AIAgent

    with (
        patch("run_agent.get_tool_definitions", return_value=_make_tool_defs("web_search")),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        agent = AIAgent(
            api_key="test",
            base_url="https://openrouter.ai/api/v1",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
    agent._cached_system_prompt = "You are helpful."
    agent._use_prompt_caching = False
    agent.tool_delay = 0
    agent.compression_enabled = False
    agent.save_trajectories = False
    agent._memory_manager = MagicMock()
    agent._memory_manager.prefetch_all.return_value = ""
    agent._memory_manager.recall_now_all.return_value = "Nutrition plan: 2 meals/day, high protein."
    return agent


def test_first_nutrition_turn_uses_current_turn_recall_and_caches_capsule():
    agent = _bare_agent()

    context = agent._prepare_external_memory_context_for_turn(
        "На завтрак был съеден омлет из 2 яиц с сыром"
    )

    assert "Nutrition plan" in context
    agent._memory_manager.recall_now_all.assert_called_once_with(
        "На завтрак был съеден омлет из 2 яиц с сыром",
        session_id="session-1",
        max_tokens=800,
    )

    agent._memory_manager.recall_now_all.reset_mock()
    agent._memory_manager.prefetch_all.return_value = ""
    agent._user_turn_count = 2

    followup = agent._prepare_external_memory_context_for_turn("а йогурт можно?")

    assert "Nutrition plan" in followup
    agent._memory_manager.recall_now_all.assert_not_called()


def test_explicit_same_topic_memory_request_bypasses_cached_capsule():
    agent = _bare_agent()

    agent._prepare_external_memory_context_for_turn("На завтрак был омлет")
    agent._memory_manager.recall_now_all.reset_mock()
    agent._memory_manager.prefetch_all.return_value = ""
    agent._memory_manager.recall_now_all.return_value = "Fresh yogurt context"
    agent._user_turn_count = 2

    context = agent._prepare_external_memory_context_for_turn("помнишь, какой йогурт мы обсуждали?")

    assert context == "Fresh yogurt context"
    agent._memory_manager.recall_now_all.assert_called_once_with(
        "помнишь, какой йогурт мы обсуждали?",
        session_id="session-1",
        max_tokens=800,
    )

    agent._memory_manager.recall_now_all.reset_mock()
    agent._user_turn_count = 3

    followup = agent._prepare_external_memory_context_for_turn("а сколько там белка?")

    assert followup == "Fresh yogurt context"
    agent._memory_manager.recall_now_all.assert_not_called()


def test_fresh_current_turn_recall_suppresses_stale_warm_prefetch():
    agent = _bare_agent()
    agent._memory_manager.prefetch_all.return_value = "WARM PREFETCH FROM PREVIOUS TURN"
    agent._memory_manager.recall_now_all.return_value = "FRESH RECALL FOR CURRENT QUERY"

    context = agent._prepare_external_memory_context_for_turn("помнишь, что решили по памяти?")

    assert context == "FRESH RECALL FOR CURRENT QUERY"
    agent._memory_manager.prefetch_all.assert_not_called()


def test_prefetch_only_provider_still_works_when_current_turn_recall_unavailable():
    agent = _bare_agent()
    agent._memory_manager.prefetch_all.return_value = "PREFETCH-ONLY MEMORY"
    agent._memory_manager.recall_now_all.return_value = ""

    context = agent._prepare_external_memory_context_for_turn("помнишь, что решили по памяти?")

    assert context == "PREFETCH-ONLY MEMORY"
    agent._memory_manager.prefetch_all.assert_called_once_with("помнишь, что решили по памяти?")


def test_same_topic_hindsight_prefetch_fallback_refreshes_capsule():
    agent = _bare_agent()
    agent._memory_manager.recall_now_all.return_value = "OLD CAPSULE"
    agent._prepare_external_memory_context_for_turn("На завтрак был йогурт")

    agent._memory_manager.recall_now_all.reset_mock()
    agent._memory_manager.prefetch_all.reset_mock()
    agent._memory_manager.recall_now_all.return_value = ""
    agent._memory_manager.prefetch_all.return_value = "NEW PREFETCH CONTEXT"
    agent._user_turn_count = 2

    context = agent._prepare_external_memory_context_for_turn("помнишь, какой йогурт мы обсуждали?")

    assert context == "NEW PREFETCH CONTEXT"

    agent._memory_manager.recall_now_all.reset_mock()
    agent._memory_manager.prefetch_all.reset_mock()
    agent._memory_manager.prefetch_all.return_value = ""
    agent._user_turn_count = 3

    followup = agent._prepare_external_memory_context_for_turn("а сколько там белка?")

    assert followup == "NEW PREFETCH CONTEXT"
    agent._memory_manager.recall_now_all.assert_not_called()


def test_non_topic_hindsight_empty_recall_clears_prior_capsule():
    agent = _bare_agent()
    agent._memory_manager.recall_now_all.return_value = "OLD CAPSULE"
    agent._prepare_external_memory_context_for_turn("На завтрак был йогурт")

    agent._memory_manager.recall_now_all.reset_mock()
    agent._memory_manager.prefetch_all.return_value = ""
    agent._memory_manager.recall_now_all.return_value = ""
    agent._user_turn_count = 2

    assert agent._prepare_external_memory_context_for_turn("помнишь, что мы решили по проекту?") == ""

    agent._memory_manager.recall_now_all.reset_mock()
    agent._memory_manager.recall_now_all.return_value = "FRESH DOMAIN RECALL"
    agent._user_turn_count = 3

    followup = agent._prepare_external_memory_context_for_turn("а сколько там белка?")

    assert followup == "FRESH DOMAIN RECALL"
    agent._memory_manager.recall_now_all.assert_called_once()


def test_warm_prefetch_still_included_without_immediate_recall():
    agent = _bare_agent()
    agent._memory_manager.recall_now_all.return_value = ""
    agent._memory_manager.prefetch_all.return_value = "Warm cached memory"

    context = agent._prepare_external_memory_context_for_turn("hello there")

    assert context == "Warm cached memory"
    agent._memory_manager.prefetch_all.assert_called_once_with("hello there")


def test_no_memory_manager_returns_empty_context():
    from run_agent import AIAgent

    agent = AIAgent.__new__(AIAgent)
    agent._memory_manager = None

    assert agent._prepare_external_memory_context_for_turn("На завтрак омлет") == ""


def test_run_conversation_injects_recall_context_without_persisting_it():
    agent = _real_agent()
    seen = {}

    def _capture_api_call(api_kwargs):
        seen["messages"] = api_kwargs["messages"]
        return _mock_response("Logged")

    user_text = "На завтрак был съеден омлет из 2 яиц с сыром"
    with (
        patch.object(agent, "_interruptible_api_call", side_effect=_capture_api_call),
        patch.object(agent, "_persist_session"),
        patch.object(agent, "_save_trajectory"),
        patch.object(agent, "_cleanup_task_resources"),
    ):
        result = agent.run_conversation(user_text)

    api_user_messages = [m for m in seen["messages"] if m.get("role") == "user"]
    assert len(api_user_messages) == 1
    assert api_user_messages[0]["content"].startswith(user_text)
    assert "<memory-context>" in api_user_messages[0]["content"]
    assert "Nutrition plan" in api_user_messages[0]["content"]
    assert result["messages"][0]["content"] == user_text
