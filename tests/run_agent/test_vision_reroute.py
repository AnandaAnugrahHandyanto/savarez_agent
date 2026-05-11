"""Tests for vision reroute (image->description->main model) in run_agent.py."""

import pytest
from unittest.mock import MagicMock, patch, ANY

from agent.brain.types import RouteDecision
from run_agent import AIAgent


def _make_tool_defs(*names: str) -> list:
    """Minimal tool definition list accepted by AIAgent.__init__."""
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


def _make_vision_decision() -> RouteDecision:
    return RouteDecision(
        route="vision",
        confidence=0.95,
        source="l0_image",
        resolved_model="qwen3-vl-plus",
        resolved_provider="dashscope",
        resolved_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        resolved_api_key="test-vision-key",
        metadata={"reroute_after_extract": True},
    )


def _make_text_decision() -> RouteDecision:
    return RouteDecision(
        route="coding",
        confidence=0.92,
        source="l1_code",
        resolved_model="deepseek-v4-flash",
        resolved_provider="deepseek",
        resolved_base_url="https://api.deepseek.com/v1",
        metadata={"vision_rerouted": True},
    )


# ------------------------------------------------------------------
# Config loading
# ------------------------------------------------------------------

class TestVisionRerouteConfigLoading:

    def test_loaded_when_vision_api_key_present(self):
        config = {
            "auxiliary": {
                "vision": {
                    "api_key": "test-vision-key-123",
                    "model": "custom-vl-model",
                    "base_url": "https://custom.endpoint.com/v1",
                    "max_tokens": 8192,
                    "timeout": 60,
                }
            }
        }
        with (
            patch("run_agent.get_tool_definitions", return_value=_make_tool_defs("web_search")),
            patch("run_agent.check_toolset_requirements", return_value={}),
            patch("run_agent.OpenAI"),
            patch("hermes_cli.config.load_config", return_value=config),
        ):
            a = AIAgent(
                api_key="test-key",
                base_url="https://openrouter.ai/api/v1",
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
            )

        assert a._vision_reroute_config is not None
        assert a._vision_reroute_config["model"] == "custom-vl-model"
        assert a._vision_reroute_config["api_key"] == "test-vision-key-123"
        assert a._vision_reroute_config["base_url"] == "https://custom.endpoint.com/v1/"
        assert a._vision_reroute_config["max_tokens"] == 8192
        assert a._vision_reroute_config["timeout"] == 60

    def test_none_when_no_auxiliary_config(self):
        with (
            patch("run_agent.get_tool_definitions", return_value=_make_tool_defs("web_search")),
            patch("run_agent.check_toolset_requirements", return_value={}),
            patch("run_agent.OpenAI"),
            patch("hermes_cli.config.load_config", return_value={}),
        ):
            a = AIAgent(
                api_key="test-key",
                base_url="https://openrouter.ai/api/v1",
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
            )
        assert a._vision_reroute_config is None

    def test_none_when_no_api_key(self):
        config = {"auxiliary": {"vision": {"model": "qwen3-vl-plus"}}}
        with (
            patch("run_agent.get_tool_definitions", return_value=_make_tool_defs("web_search")),
            patch("run_agent.check_toolset_requirements", return_value={}),
            patch("run_agent.OpenAI"),
            patch("hermes_cli.config.load_config", return_value=config),
        ):
            a = AIAgent(
                api_key="test-key",
                base_url="https://openrouter.ai/api/v1",
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
            )
        assert a._vision_reroute_config is None

    def test_defaults_applied(self):
        config = {"auxiliary": {"vision": {"api_key": "minimal-key"}}}
        with (
            patch("run_agent.get_tool_definitions", return_value=_make_tool_defs("web_search")),
            patch("run_agent.check_toolset_requirements", return_value={}),
            patch("run_agent.OpenAI"),
            patch("hermes_cli.config.load_config", return_value=config),
        ):
            a = AIAgent(
                api_key="test-key",
                base_url="https://openrouter.ai/api/v1",
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
            )
        assert a._vision_reroute_config is not None
        assert a._vision_reroute_config["model"] == "qwen3-vl-plus"
        assert a._vision_reroute_config["base_url"] == "/"
        assert a._vision_reroute_config["max_tokens"] == 4096
        assert a._vision_reroute_config["timeout"] == 120

    def test_load_failure_returns_none(self):
        with (
            patch("run_agent.get_tool_definitions", return_value=_make_tool_defs("web_search")),
            patch("run_agent.check_toolset_requirements", return_value={}),
            patch("run_agent.OpenAI"),
            patch("hermes_cli.config.load_config", side_effect=RuntimeError("boom")),
        ):
            a = AIAgent(
                api_key="test-key",
                base_url="https://openrouter.ai/api/v1",
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
            )
        assert a._vision_reroute_config is None


# ------------------------------------------------------------------
# Integration: vision reroute flow in run_conversation
# ------------------------------------------------------------------

class TestVisionRerouteFlow:

    @pytest.fixture()
    def agent_with_vision(self):
        vision_config = {
            "brain": {
                "enabled": True,
                "execution": {
                    "routes": {
                        "simple": {"model": "deepseek-v4-flash", "max_tokens": 4096},
                        "coding": {"model": "deepseek-v4-flash", "max_tokens": 16384},
                        "complex": {"model": "deepseek-v4-pro", "max_tokens": 32768},
                        "vision": {
                            "model": "qwen3-vl-plus",
                            "provider": "dashscope",
                            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                            "max_tokens": 4096,
                        },
                    }
                },
                "circuit_breaker": {"enabled": False, "max_failures": 3},
            },
            "auxiliary": {
                "vision": {
                    "api_key": "test-vision-key",
                    "model": "qwen3-vl-plus",
                    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "max_tokens": 4096,
                    "timeout": 120,
                }
            },
        }

        vision_desc = (
            "\u4e00\u5f20\u5305\u542b\u84dd\u8272\u56fe\u8868\u548c\u7ea2\u8272\u6807\u6ce8\u7684\u6280\u672f\u793a\u610f\u56fe\uff0c"
            "\u663e\u793a\u6570\u636e\u6d41\u4ece\u8f93\u5165\u5230\u8f93\u51fa\u7684\u8def\u5f84\u3002"
        )

        mock_vr_choice = MagicMock()
        mock_vr_choice.message.content = vision_desc

        mock_vr_resp = MagicMock()
        mock_vr_resp.choices = [mock_vr_choice]

        mock_vr_client = MagicMock()
        mock_vr_client.chat.completions.create.return_value = mock_vr_resp

        mock_vr_openai = MagicMock(return_value=mock_vr_client)

        mock_main_choice = MagicMock()
        mock_main_choice.message.content = "I see an architecture diagram."

        mock_main_resp = MagicMock()
        mock_main_resp.choices = [mock_main_choice]
        mock_main_resp.tool_calls = None

        with (
            patch("run_agent.get_tool_definitions", return_value=_make_tool_defs("web_search")),
            patch("run_agent.check_toolset_requirements", return_value={}),
            patch("run_agent.OpenAI"),
            patch("hermes_cli.config.load_config", return_value=vision_config),
            patch("agent.brain.pipeline.route_message", return_value=_make_vision_decision()),
            patch("agent.brain.pipeline.post_vision_reroute", return_value=_make_text_decision()),
            patch("agent.brain.affinity.establish_affinity", return_value=None),
            patch("openai.OpenAI", mock_vr_openai),
        ):
            a = AIAgent(
                api_key="test-key",
                base_url="https://openrouter.ai/api/v1",
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
            )
            a.client = MagicMock()
            a.client.chat.completions.create.return_value = mock_main_resp

            yield a, vision_desc

    def test_injects_vision_context(self, agent_with_vision):
        a, vision_desc = agent_with_vision
        history = []
        a.run_conversation("\u5206\u6790\u8fd9\u5f20\u56fe\u7247", conversation_history=history)

        vision_msgs = [m for m in history if m.get("role") == "system"
                       and "[视觉上下文]" in m.get("content", "")]
        assert len(vision_msgs) == 1
        assert vision_desc in vision_msgs[0]["content"]

    def test_vision_reroute_source_has_model_update_path(self):
        import inspect
        src = inspect.getsource(AIAgent.run_conversation)
        # The reroute code must set self.model before the _emit_status call
        assert "self.model = _vr_decision.resolved_model" in src
        # And restore at turn end
        assert "_brain_original" in src
        assert "self.model = _brain_original" in src

    def test_updates_brain_route(self, agent_with_vision):
        a, _ = agent_with_vision
        history = []
        a.run_conversation("\u5206\u6790\u8fd9\u5f20\u56fe\u7247", conversation_history=history)
        # _brain_route is NOT restored at turn end
        assert a._brain_route == "coding"

    def test_skips_on_text_route(self, agent_with_vision):
        a, _ = agent_with_vision
        text_decision = RouteDecision(
            route="coding",
            confidence=0.95,
            source="l1_code",
            resolved_model="deepseek-v4-flash",
            resolved_provider="deepseek",
        )

        with patch("agent.brain.pipeline.route_message", return_value=text_decision):
            history = []
            a.run_conversation("write a sort algorithm", conversation_history=history)
            vision_msgs = [m for m in history if m.get("role") == "system"
                           and "[视觉上下文]" in m.get("content", "")]
            assert len(vision_msgs) == 0

    def test_graceful_on_api_error(self, agent_with_vision):
        a, _ = agent_with_vision

        with patch("openai.OpenAI", side_effect=Exception("Vision API unavailable")):
            history = []
            a.run_conversation("\u5206\u6790\u8fd9\u5f20\u56fe\u7247", conversation_history=history)
            vision_msgs = [m for m in history if m.get("role") == "system"
                           and "[视觉上下文]" in m.get("content", "")]
            assert len(vision_msgs) == 0

    def test_skips_when_no_reroute_flag(self, agent_with_vision):
        a, _ = agent_with_vision
        no_reroute = RouteDecision(
            route="vision",
            confidence=0.95,
            source="l0_image",
            resolved_model="qwen3-vl-plus",
            resolved_provider="dashscope",
            metadata={},
        )

        with patch("agent.brain.pipeline.route_message", return_value=no_reroute):
            history = []
            a.run_conversation("\u5206\u6790\u8fd9\u5f20\u56fe\u7247", conversation_history=history)
            vision_msgs = [m for m in history if m.get("role") == "system"
                           and "[视觉上下文]" in m.get("content", "")]
            assert len(vision_msgs) == 0
