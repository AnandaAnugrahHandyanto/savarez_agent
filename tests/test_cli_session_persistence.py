"""Regression tests for CLI session indexing/persistence on early exit paths."""

from __future__ import annotations

import importlib
import os
import sys
from unittest.mock import MagicMock, patch

from hermes_state import SessionDB


def _make_cli(env_overrides=None, config_overrides=None, **kwargs):
    """Create a HermesCLI instance with minimal prompt_toolkit mocking."""
    clean_config = {
        "model": {
            "default": "anthropic/claude-opus-4.6",
            "base_url": "https://openrouter.ai/api/v1",
            "provider": "auto",
        },
        "display": {"compact": False, "tool_progress": "all"},
        "agent": {},
        "terminal": {"env_type": "local"},
    }
    if config_overrides:
        clean_config.update(config_overrides)
    clean_env = {"LLM_MODEL": "", "HERMES_MAX_ITERATIONS": ""}
    if env_overrides:
        clean_env.update(env_overrides)

    prompt_toolkit_stubs = {
        "prompt_toolkit": MagicMock(),
        "prompt_toolkit.history": MagicMock(),
        "prompt_toolkit.styles": MagicMock(),
        "prompt_toolkit.patch_stdout": MagicMock(),
        "prompt_toolkit.application": MagicMock(),
        "prompt_toolkit.layout": MagicMock(),
        "prompt_toolkit.layout.processors": MagicMock(),
        "prompt_toolkit.filters": MagicMock(),
        "prompt_toolkit.layout.dimension": MagicMock(),
        "prompt_toolkit.layout.menus": MagicMock(),
        "prompt_toolkit.widgets": MagicMock(),
        "prompt_toolkit.key_binding": MagicMock(),
        "prompt_toolkit.completion": MagicMock(),
        "prompt_toolkit.formatted_text": MagicMock(),
        "prompt_toolkit.auto_suggest": MagicMock(),
    }

    with patch.dict(sys.modules, prompt_toolkit_stubs), patch.dict(
        os.environ, clean_env, clear=False
    ):
        import cli as cli_mod

        cli_mod = importlib.reload(cli_mod)
        with patch.object(cli_mod, "get_tool_definitions", return_value=[]), patch.dict(
            cli_mod.__dict__, {"CLI_CONFIG": clean_config}
        ):
            return cli_mod.HermesCLI(**kwargs)


def test_chat_indexes_new_session_before_agent_init(tmp_path):
    cli = _make_cli()
    cli._session_db = SessionDB(db_path=tmp_path / "state.db")
    cli._ensure_runtime_credentials = MagicMock(return_value=True)
    cli._resolve_turn_agent_config = MagicMock(
        return_value={
            "signature": ("test/model", "auto", None, None),
            "model": "test/model",
            "runtime": {"provider": "auto", "base_url": None, "api_key": None, "api_mode": None, "command": None, "args": []},
            "label": "default",
        }
    )
    cli._init_agent = MagicMock(return_value=False)

    assert cli._session_db.get_session(cli.session_id) is None

    assert cli.chat("hello") is None

    session = cli._session_db.get_session(cli.session_id)
    assert session is not None
    assert session["source"] == "cli"
    assert session["model"] == "test/model"


def test_persist_session_on_exit_closes_preindexed_session_without_agent(tmp_path):
    cli = _make_cli()
    cli._session_db = SessionDB(db_path=tmp_path / "state.db")

    cli._ensure_current_session_indexed(model_override="test/model")
    cli._persist_session_on_exit()

    session = cli._session_db.get_session(cli.session_id)
    assert session is not None
    assert session["model"] == "test/model"
    assert session["end_reason"] == "cli_close"


def test_persist_session_on_exit_flushes_pending_history_and_closes_session(tmp_path):
    cli = _make_cli()
    cli._session_db = SessionDB(db_path=tmp_path / "state.db")
    cli.conversation_history = [{"role": "user", "content": "hello"}]

    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False):
        from run_agent import AIAgent

        agent = AIAgent(
            model="test/model",
            quiet_mode=True,
            session_db=cli._session_db,
            session_id=cli.session_id,
            skip_context_files=True,
            skip_memory=True,
        )

    cli.agent = agent
    cli._persist_session_on_exit()

    session = cli._session_db.get_session(cli.session_id)
    assert session is not None
    assert session["end_reason"] == "cli_close"

    restored = cli._session_db.get_messages_as_conversation(cli.session_id)
    assert restored == cli.conversation_history
