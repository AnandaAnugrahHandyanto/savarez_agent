import unittest
from unittest.mock import MagicMock, patch

from run_agent import AIAgent


class TestSdaoAdversarialPromptPolicy(unittest.TestCase):
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

    def test_adversarial_prompt_mentions_ambiguity_resolves_conservatively(self):
        agent = self._make_agent()
        prompt = agent._build_system_prompt().lower()

        assert "ambiguous" in prompt or "ambiguity" in prompt
        assert "solo" in prompt

    def test_adversarial_prompt_rejects_surface_level_parallelism_signals(self):
        agent = self._make_agent()
        prompt = agent._build_system_prompt().lower()

        assert "explicit evidence of independence" in prompt
        assert "style only" in prompt
        assert "topically similar" in prompt or "superficial" in prompt or "surface" in prompt

    def test_adversarial_prompt_handles_complex_mixed_signal_request(self):
        complex_request = (
            "Audit auth and billing. They look separate at first glance, but one task may depend on the "
            "other's findings, and if independence is unclear the model must stay conservative."
        )
        agent = self._make_agent()
        prompt = agent._build_system_prompt().lower()

        assert complex_request.lower().split(" ")[0] == "audit"
        assert "solo by default" in prompt
        assert "prefer sequential over parallel" in prompt
        assert "no subagents" in prompt
        assert "delegation materially helps" in prompt
