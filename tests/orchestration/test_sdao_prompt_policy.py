import unittest
from unittest.mock import MagicMock, patch

import run_agent
from run_agent import AIAgent


class TestSdaoPromptPolicy(unittest.TestCase):
    def _make_agent(self):
        with (
            patch(
                "run_agent.get_tool_definitions",
                return_value=[
                    {"function": {"name": "delegate_task"}},
                    {"function": {"name": "terminal"}},
                    {"function": {"name": "read_file"}},
                ],
            ),
            patch("run_agent.check_toolset_requirements", return_value={}),
            patch("run_agent.OpenAI"),
        ):
            agent = AIAgent(
                api_key="test-key-1234567890",
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
            )
            agent.client = MagicMock()
            return agent

    def test_prompt_includes_solo_by_default_policy(self):
        agent = self._make_agent()
        prompt = agent._build_system_prompt()
        assert "solo by default" in prompt.lower()

    def test_prompt_prefers_sequential_over_parallel_when_uncertain(self):
        agent = self._make_agent()
        prompt = agent._build_system_prompt()
        assert "prefer sequential over parallel" in prompt.lower()

    def test_prompt_mentions_no_subagent_override(self):
        agent = self._make_agent()
        prompt = agent._build_system_prompt()
        assert "no subagents" in prompt.lower()

    def test_prompt_prohibits_decorative_delegation(self):
        agent = self._make_agent()
        prompt = agent._build_system_prompt()
        assert "decorative delegation" in prompt.lower() or "parallelize for style only" in prompt.lower()

    def test_prompt_requires_internal_justification_before_delegate_task(self):
        agent = self._make_agent()
        prompt = agent._build_system_prompt()
        assert "justify delegation internally before calling delegate_task" in prompt.lower()
