"""Tests for MODEL_SWITCH_GUIDANCE injection into system prompt.

Verifies that the model-switch reporting guidance (Issue #6213) is:
  1. Defined as a non-empty constant in prompt_builder.
  2. Injected into the system prompt built by AIAgent._build_system_prompt().
"""

import unittest
from unittest.mock import patch, MagicMock


class TestModelSwitchGuidanceConstant(unittest.TestCase):
    """MODEL_SWITCH_GUIDANCE must exist and contain key directives."""

    def test_constant_is_defined(self):
        from agent.prompt_builder import MODEL_SWITCH_GUIDANCE
        self.assertIsInstance(MODEL_SWITCH_GUIDANCE, str)
        self.assertTrue(len(MODEL_SWITCH_GUIDANCE) > 0)

    def test_constant_mentions_model_command(self):
        from agent.prompt_builder import MODEL_SWITCH_GUIDANCE
        self.assertIn("/model", MODEL_SWITCH_GUIDANCE)

    def test_constant_warns_against_config_edit(self):
        from agent.prompt_builder import MODEL_SWITCH_GUIDANCE
        self.assertIn("config.yaml", MODEL_SWITCH_GUIDANCE)

    def test_constant_warns_against_false_success(self):
        from agent.prompt_builder import MODEL_SWITCH_GUIDANCE
        # Must warn against claiming "all set" prematurely
        self.assertIn("all set", MODEL_SWITCH_GUIDANCE.lower())

    def test_constant_mentions_session_restart(self):
        from agent.prompt_builder import MODEL_SWITCH_GUIDANCE
        # Must mention that config edits require a session restart
        self.assertIn("session", MODEL_SWITCH_GUIDANCE.lower())


class TestModelSwitchGuidanceInjection(unittest.TestCase):
    """MODEL_SWITCH_GUIDANCE must be present in the assembled system prompt."""

    def test_guidance_in_system_prompt(self):
        """_build_system_prompt() should include MODEL_SWITCH_GUIDANCE."""
        from agent.prompt_builder import MODEL_SWITCH_GUIDANCE

        # Patch heavy dependencies that _build_system_prompt touches
        with patch("run_agent.load_soul_md", return_value=None), \
             patch("run_agent.build_context_files_prompt", return_value=""), \
             patch("run_agent.build_skills_system_prompt", return_value=""), \
             patch("run_agent.build_nous_subscription_prompt", return_value=""):

            # Create a minimal AIAgent mock that has the fields
            # _build_system_prompt reads.
            from run_agent import AIAgent
            agent = object.__new__(AIAgent)

            # Minimal required attributes
            agent.model = "test-model"
            agent.provider = "openrouter"
            agent.platform = "cli"
            agent.valid_tool_names = set()
            agent.skip_context_files = True
            agent._memory_store = None
            agent._memory_manager = None
            agent._tool_use_enforcement = False
            agent.pass_session_id = False
            agent.session_id = "test-session"
            agent.ephemeral_system_prompt = None

            prompt = agent._build_system_prompt()

            self.assertIn("Model switching rules", prompt)
            self.assertIn("/model", prompt)
            self.assertIn("config.yaml", prompt)


if __name__ == "__main__":
    unittest.main()
