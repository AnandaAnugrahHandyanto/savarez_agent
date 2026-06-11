"""Regression tests for CLI active-agent cleanup wiring.

The agent construction mixin lives in ``hermes_cli.cli_agent_setup_mixin`` but
process cleanup reads ``_active_agent_ref`` from the concrete CLI owner module.
A module-local assignment in the mixin leaves cleanup blind to the live agent, so
memory-provider background threads can survive until interpreter shutdown.
"""

from __future__ import annotations

import sys
import types

import cli as cli_mod
from hermes_cli.cli_agent_setup_mixin import CLIAgentSetupMixin


class _FakeAgent:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.session_id = kwargs.get("session_id")
        self._print_fn = None


class _DummyCLI(CLIAgentSetupMixin):
    def __init__(self):
        self.agent = None
        self.api_key = "test-key"
        self.base_url = "https://example.invalid"
        self.provider = "openai"
        self.api_mode = "chat"
        self.acp_command = None
        self.acp_args = []
        self.model = "test-model"
        self.max_tokens = None
        self.max_turns = 3
        self.enabled_toolsets = []
        self.disabled_toolsets = []
        self.verbose = False
        self.tool_progress_mode = "off"
        self.system_prompt = None
        self.prefill_messages = []
        self.reasoning_config = None
        self.service_tier = None
        self._providers_only = None
        self._providers_ignore = None
        self._providers_order = None
        self._provider_sort = None
        self._provider_require_params = False
        self._provider_data_collection = None
        self._openrouter_min_coding_score = None
        self.session_id = "test-session"
        self._session_db = object()
        self._fallback_model = None
        self.checkpoints_enabled = False
        self.checkpoint_max_snapshots = 0
        self.checkpoint_max_total_size_mb = 0
        self.checkpoint_max_file_size_mb = 0
        self.pass_session_id = False
        self.ignore_rules = False
        self.streaming_enabled = False
        self._inline_diffs_enabled = False
        self._active_agent_route_signature = None
        self._pending_title = None
        self._resumed = False
        self.conversation_history = []
        self.requested_provider = None
        self._explicit_api_key = None
        self._explicit_base_url = None
        self._credential_pool = None

    def _install_tool_callbacks(self):
        pass

    def _ensure_tirith_security(self):
        pass

    def _ensure_runtime_credentials(self):
        return True

    def _clarify_callback(self, *args, **kwargs):
        return ""

    def _current_reasoning_callback(self):
        return None

    def _on_thinking(self, *args, **kwargs):
        pass

    def _on_tool_progress(self, *args, **kwargs):
        pass

    def _on_tool_start(self, *args, **kwargs):
        pass

    def _on_tool_complete(self, *args, **kwargs):
        pass

    def _stream_delta(self, *args, **kwargs):
        pass

    def _on_tool_gen_start(self, *args, **kwargs):
        pass

    def _on_notice(self, *args, **kwargs):
        pass

    def _on_notice_clear(self, *args, **kwargs):
        pass


def _patch_agent_startup(monkeypatch):
    monkeypatch.setattr(cli_mod, "AIAgent", _FakeAgent)
    monkeypatch.setattr(cli_mod, "_prepare_deferred_agent_startup", lambda: None)
    monkeypatch.setattr("hermes_cli.mcp_startup.wait_for_mcp_discovery", lambda: None)


def test_init_agent_updates_cli_module_active_agent_ref(monkeypatch):
    _patch_agent_startup(monkeypatch)
    monkeypatch.setattr(cli_mod, "_active_agent_ref", None)

    dummy = _DummyCLI()

    assert dummy._init_agent() is True
    assert dummy.agent is not None
    assert cli_mod._active_agent_ref is dummy.agent


def test_init_agent_updates_script_owner_module_active_agent_ref(monkeypatch):
    _patch_agent_startup(monkeypatch)
    monkeypatch.setattr(cli_mod, "_active_agent_ref", None)
    owner = types.ModuleType("fake_cli_script_owner")
    setattr(owner, "_active_agent_ref", None)
    monkeypatch.setitem(sys.modules, "fake_cli_script_owner", owner)
    script_like_cli = type(
        "ScriptLikeCLI",
        (_DummyCLI,),
        {"__module__": "fake_cli_script_owner"},
    )

    dummy = script_like_cli()

    assert dummy._init_agent() is True
    assert dummy.agent is not None
    assert owner._active_agent_ref is dummy.agent
    assert cli_mod._active_agent_ref is None
