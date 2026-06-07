import sys
import types

import cli as cli_module
from cli import HermesCLI


def _shell_for_init_test():
    shell = HermesCLI.__new__(HermesCLI)
    shell.agent = None
    shell._session_db = None
    shell._resumed = False
    shell.conversation_history = []
    shell.tool_progress_mode = "all"
    shell.api_key = ""
    shell.base_url = ""
    shell.provider = "openrouter"
    shell.api_mode = None
    shell.acp_command = None
    shell.acp_args = []
    shell._credential_pool = None
    shell.model = "test-model"
    shell.max_tokens = None
    shell.max_turns = 1
    shell.enabled_toolsets = None
    shell.disabled_toolsets = None
    shell.verbose = False
    shell.system_prompt = None
    shell.prefill_messages = []
    shell.reasoning_config = None
    shell.service_tier = None
    shell._providers_only = None
    shell._providers_ignore = None
    shell._providers_order = None
    shell._provider_sort = None
    shell._provider_require_params = None
    shell._provider_data_collection = None
    shell._openrouter_min_coding_score = None
    shell.session_id = "test-session"
    shell._clarify_callback = None
    shell._current_reasoning_callback = lambda: None
    shell._fallback_model = None
    shell._on_thinking = None
    shell.checkpoints_enabled = False
    shell.checkpoint_max_snapshots = 0
    shell.checkpoint_max_total_size_mb = 0
    shell.checkpoint_max_file_size_mb = 0
    shell.pass_session_id = False
    shell.ignore_rules = False
    shell._inline_diffs_enabled = False
    shell.streaming_enabled = False
    shell._on_tool_progress = None
    shell._on_notice = None
    shell._on_notice_clear = None
    shell._pending_title = None
    return shell


def _patch_cli_init_dependencies(monkeypatch):
    class _BrokenSessionDB:
        def __init__(self):
            raise SyntaxError("invalid decimal literal")

    fake_hermes_state = types.SimpleNamespace(SessionDB=_BrokenSessionDB)
    monkeypatch.setitem(sys.modules, "hermes_state", fake_hermes_state)

    import hermes_cli.mcp_startup as mcp_startup

    monkeypatch.setattr(mcp_startup, "wait_for_mcp_discovery", lambda: None)
    monkeypatch.setattr(HermesCLI, "_install_tool_callbacks", lambda self: None)
    monkeypatch.setattr(HermesCLI, "_ensure_tirith_security", lambda self: None)
    monkeypatch.setattr(HermesCLI, "_ensure_runtime_credentials", lambda self: True)
    reached_agent_build = {"value": False}

    def _fake_agent(*args, **kwargs):
        reached_agent_build["value"] = True
        return types.SimpleNamespace()

    monkeypatch.setattr(cli_module, "AIAgent", _fake_agent)
    return reached_agent_build


def test_cli_init_agent_rejects_unindexed_session_by_default(monkeypatch):
    """Interactive CLI must not silently continue when state.db cannot open."""
    reached_agent_build = _patch_cli_init_dependencies(monkeypatch)
    monkeypatch.delenv("HERMES_ALLOW_UNINDEXED_SESSION", raising=False)
    shell = _shell_for_init_test()

    assert shell._init_agent() is False
    assert shell.agent is None
    assert reached_agent_build["value"] is False


def test_cli_init_agent_allows_explicit_unindexed_escape_hatch(monkeypatch):
    """The dangerous live-only mode requires an explicit environment opt-in."""
    reached_agent_build = _patch_cli_init_dependencies(monkeypatch)
    monkeypatch.setenv("HERMES_ALLOW_UNINDEXED_SESSION", "1")
    shell = _shell_for_init_test()

    assert shell._init_agent() is True
    assert shell.agent is not None
    assert reached_agent_build["value"] is True
