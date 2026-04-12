"""Tests for selecting the repo-shipped LCM engine during AIAgent init."""

from unittest.mock import MagicMock, patch

from run_agent import AIAgent


class TestLCMContextEngineInit:
    def test_aiagent_initializes_lcm_engine_with_context_length_and_tools(self):
        config = {
            "context": {"engine": "lcm"},
            "model": {"context_length": 131072},
            "compression": {"enabled": True},
        }

        with (
            patch("hermes_cli.config.load_config", return_value=config),
            patch("run_agent.get_tool_definitions", return_value=[]),
            patch("run_agent.check_toolset_requirements", return_value={}),
            patch("run_agent.OpenAI"),
        ):
            agent = AIAgent(
                api_key="test-key-1234567890",
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
            )

        assert agent.context_compressor.name == "lcm"
        assert agent.context_compressor.context_length == 131072
        assert agent.context_compressor.threshold_tokens == int(131072 * 0.75)
        assert {"lcm_grep", "lcm_describe", "lcm_expand"}.issubset(agent.valid_tool_names)
        assert {"lcm_grep", "lcm_describe", "lcm_expand"}.issubset(agent._context_engine_tool_names)

    def test_compress_context_supports_legacy_engine_without_focus_topic(self):
        config = {
            "model": {"context_length": 131072},
            "compression": {"enabled": True},
        }

        class LegacyEngine:
            name = "legacy"
            threshold_tokens = 999999
            compression_count = 0
            last_prompt_tokens = 0
            last_completion_tokens = 0

            def __init__(self):
                self.seen_current_tokens = None

            def compress(self, messages, current_tokens=None):
                self.seen_current_tokens = current_tokens
                return list(messages)

        with (
            patch("hermes_cli.config.load_config", return_value=config),
            patch("run_agent.get_tool_definitions", return_value=[]),
            patch("run_agent.check_toolset_requirements", return_value={}),
            patch("run_agent.OpenAI"),
        ):
            agent = AIAgent(
                api_key="test-key-1234567890",
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
            )

        agent.flush_memories = MagicMock()
        engine = LegacyEngine()
        agent.context_compressor = engine

        messages = [
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"},
            {"role": "assistant", "content": "a2"},
        ]

        compressed, _ = agent._compress_context(
            messages,
            "",
            approx_tokens=1234,
            focus_topic="database schema",
        )

        assert compressed == messages
        assert engine.seen_current_tokens == 1234
