"""Focused tests for automatic compression handoff."""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from agent.conversation_compression import compress_context, create_handoff_packet
from cli import HermesCLI
from hermes_cli.commands import COMMAND_REGISTRY
from hermes_cli.config import DEFAULT_CONFIG
from hermes_cli.web_server import CONFIG_SCHEMA
from run_agent import AIAgent


class FakeCompressor:
    def __init__(self, returned: list[dict[str, str]], count: int = 2):
        self.returned = returned
        self.compression_count = max(0, count - 1)
        self.target_count = count
        self._last_compress_aborted = False
        self._last_summary_error = None
        self._last_aux_model_failure_model = None
        self._last_aux_model_failure_error = None
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
        self.reset_called = False
        self.session_start_calls: list[dict[str, Any]] = []

    def compress(self, *args, **kwargs):
        self.compression_count = self.target_count
        return [m.copy() for m in self.returned]

    def on_session_reset(self):
        self.reset_called = True
        self.compression_count = 0

    def on_session_start(self, session_id: str, **kwargs):
        self.session_start_calls.append({"session_id": session_id, **kwargs})


class FakeTodos:
    def format_for_injection(self):
        return "[Your active task list was preserved across context compression]\n- [>] red-tests. Add failing tests"

    def read(self):
        return [{"id": "red-tests", "content": "Add failing tests", "status": "in_progress"}]


class FakeSessionDB:
    def __init__(self):
        self.ended: list[tuple[str, str]] = []
        self.created: list[dict[str, Any]] = []

    def get_session_title(self, session_id):
        return "Auto handoff feature"

    def end_session(self, session_id, reason):
        self.ended.append((session_id, reason))

    def create_session(self, **kwargs):
        self.created.append(kwargs)

    def get_next_title_in_lineage(self, title):
        return f"{title} 2"

    def set_session_title(self, *args, **kwargs):
        return None

    def update_system_prompt(self, *args, **kwargs):
        return None


class FailingCreateSessionDB(FakeSessionDB):
    def create_session(self, **kwargs):
        raise RuntimeError("create failed")


def make_agent(tmp_path: Path, compressor: FakeCompressor) -> Any:
    agent = cast(Any, object.__new__(AIAgent))
    agent.context_compressor = compressor
    agent.session_id = "session-old"
    agent.model = "test-model"
    agent.provider = "openai-codex"
    agent.platform = "cli"
    agent.logs_dir = tmp_path
    agent._todo_store = FakeTodos()
    agent._memory_manager = None
    agent._session_db = FakeSessionDB()
    agent._cached_system_prompt = None
    agent._compression_feasibility_checked = True
    agent._last_flushed_db_idx = 0
    agent._session_db_created = True
    agent._session_init_model_config = {"max_iterations": 90}
    agent.tools = []
    agent.log_prefix = ""
    agent.status_callback = None
    agent.commit_memory_session = lambda *a, **kw: None
    agent._invalidate_system_prompt = lambda *a, **kw: None
    agent._build_system_prompt = lambda *a, **kw: "new-system-prompt"
    agent._vprint = lambda *a, **kw: None
    agent._emit_status = lambda message: None
    agent._emit_warning = lambda message: None
    return agent


def test_config_defaults_and_schema_are_visible():
    auto = DEFAULT_CONFIG["agent"]["auto_handoff_on_compression"]
    assert auto == {
        "enabled": False,
        "after_compressions": 2,
        "max_auto_handoffs": 1,
        "mode": "prompt_user",
        "handoff_artifact_dir": ".hermes/handoffs",
    }
    for key in auto:
        assert f"agent.auto_handoff_on_compression.{key}" in CONFIG_SCHEMA


def test_aiagent_initializes_auto_handoff_config_from_yaml():
    cfg = {
        "agent": {
            "auto_handoff_on_compression": {
                "enabled": True,
                "after_compressions": "3",
                "max_auto_handoffs": "2",
                "mode": "fresh_session",
                "handoff_artifact_dir": "custom-handoffs",
            }
        }
    }
    with (
        patch("run_agent.get_tool_definitions", return_value=[]),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
        patch("hermes_cli.config.load_config", return_value=cfg),
    ):
        agent = cast(
            Any,
            AIAgent(
                api_key="dummy",
                base_url="https://example.test/v1",
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
            ),
        )
    assert agent._auto_handoff_on_compression_enabled is True
    assert agent._auto_handoff_after_compressions == 3
    assert agent._auto_handoff_max_auto_handoffs == 2
    assert agent._auto_handoff_mode == "fresh_session"
    assert agent._auto_handoff_artifact_dir == "custom-handoffs"
    assert agent._auto_handoff_count == 0


def test_fresh_session_handoff_replaces_context_and_resets_compressor(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    compressor = FakeCompressor(
        [
            {"role": "user", "content": "compressed summary"},
            {"role": "assistant", "content": "tail"},
            {"role": "user", "content": "Continue the implementation"},
        ]
    )
    agent = make_agent(tmp_path, compressor)
    agent._auto_handoff_on_compression_enabled = True
    agent._auto_handoff_after_compressions = 2
    agent._auto_handoff_max_auto_handoffs = 1
    agent._auto_handoff_count = 0
    agent._auto_handoff_mode = "fresh_session"
    agent._auto_handoff_artifact_dir = "handoffs"

    messages, prompt = compress_context(
        agent,
        [
            {"role": "user", "content": "one"},
            {"role": "assistant", "content": "two"},
            {"role": "user", "content": "three"},
            {"role": "assistant", "content": "four"},
        ],
        "",
        approx_tokens=250_000,
    )

    assert prompt == "new-system-prompt"
    assert agent._auto_handoff_count == 1
    assert compressor.reset_called is True
    assert agent._session_db.ended == [("session-old", "compression_handoff")]
    assert agent._session_db.created[-1]["parent_session_id"] == "session-old"
    assert compressor.session_start_calls[-1]["boundary_reason"] == "compression_handoff"
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert "# Hermes handoff packet" in messages[0]["content"]
    assert "verify live repo state before editing" in messages[0]["content"].lower()
    assert "red-tests" in messages[0]["content"]
    assert len(list((tmp_path / "handoffs").glob("*.md"))) == 1


def test_prompt_user_writes_packet_but_keeps_compression_boundary(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    returned = [
        {"role": "user", "content": "summary"},
        {"role": "assistant", "content": "tail"},
    ]
    compressor = FakeCompressor(returned)
    agent = make_agent(tmp_path, compressor)
    agent._auto_handoff_on_compression_enabled = True
    agent._auto_handoff_after_compressions = 2
    agent._auto_handoff_max_auto_handoffs = 1
    agent._auto_handoff_count = 0
    agent._auto_handoff_mode = "prompt_user"
    agent._auto_handoff_artifact_dir = "handoffs"

    messages, _ = compress_context(
        agent,
        [
            {"role": "user", "content": "one"},
            {"role": "assistant", "content": "two"},
            {"role": "user", "content": "three"},
            {"role": "assistant", "content": "four"},
        ],
        "",
        approx_tokens=1,
    )

    assert compressor.reset_called is False
    assert agent._session_db.ended == [("session-old", "compression")]
    assert compressor.session_start_calls[-1]["boundary_reason"] == "compression"
    assert messages[:2] == returned
    assert len(list((tmp_path / "handoffs").glob("*.md"))) == 1


def test_auto_handoff_is_bounded_by_max_auto_handoffs(tmp_path):
    returned = [{"role": "user", "content": "summary"}, {"role": "assistant", "content": "tail"}]
    compressor = FakeCompressor(returned, count=3)
    agent = make_agent(tmp_path, compressor)
    agent._auto_handoff_on_compression_enabled = True
    agent._auto_handoff_after_compressions = 2
    agent._auto_handoff_max_auto_handoffs = 1
    agent._auto_handoff_count = 1
    agent._auto_handoff_mode = "fresh_session"
    agent._auto_handoff_artifact_dir = "handoffs"

    messages, _ = compress_context(
        agent,
        [
            {"role": "user", "content": "one"},
            {"role": "assistant", "content": "two"},
            {"role": "user", "content": "three"},
            {"role": "assistant", "content": "four"},
        ],
        "",
        approx_tokens=1,
    )

    assert compressor.reset_called is False
    assert agent._session_db.ended == [("session-old", "compression")]
    assert messages[:2] == returned
    assert not (tmp_path / "handoffs").exists()


def test_fresh_session_handoff_requires_session_db_rotation(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    returned = [{"role": "user", "content": "summary"}, {"role": "assistant", "content": "tail"}]
    compressor = FakeCompressor(returned)
    agent = make_agent(tmp_path, compressor)
    agent._session_db = None
    agent._auto_handoff_on_compression_enabled = True
    agent._auto_handoff_after_compressions = 2
    agent._auto_handoff_max_auto_handoffs = 1
    agent._auto_handoff_count = 0
    agent._auto_handoff_mode = "fresh_session"
    agent._auto_handoff_artifact_dir = "handoffs"

    messages, _ = compress_context(
        agent,
        [
            {"role": "user", "content": "one"},
            {"role": "assistant", "content": "two"},
            {"role": "user", "content": "three"},
            {"role": "assistant", "content": "four"},
        ],
        "",
        approx_tokens=1,
    )

    assert agent.session_id == "session-old"
    assert agent._auto_handoff_count == 0
    assert compressor.reset_called is False
    assert compressor.session_start_calls == []
    assert messages[:2] == returned
    assert not (tmp_path / "handoffs").exists()


def test_fresh_session_handoff_downgrades_when_child_session_creation_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    returned = [{"role": "user", "content": "summary"}, {"role": "assistant", "content": "tail"}]
    compressor = FakeCompressor(returned)
    agent = make_agent(tmp_path, compressor)
    failing_db = FailingCreateSessionDB()
    agent._session_db = failing_db
    agent._auto_handoff_on_compression_enabled = True
    agent._auto_handoff_after_compressions = 2
    agent._auto_handoff_max_auto_handoffs = 1
    agent._auto_handoff_count = 0
    agent._auto_handoff_mode = "fresh_session"
    agent._auto_handoff_artifact_dir = "handoffs"

    messages, _ = compress_context(
        agent,
        [
            {"role": "user", "content": "one"},
            {"role": "assistant", "content": "two"},
            {"role": "user", "content": "three"},
            {"role": "assistant", "content": "four"},
        ],
        "",
        approx_tokens=1,
    )

    assert agent.session_id == "session-old"
    assert agent._session_db_created is True
    assert agent._auto_handoff_count == 0
    assert failing_db.ended == []
    assert compressor.reset_called is False
    assert compressor.session_start_calls == []
    assert messages[:2] == returned
    assert not (tmp_path / "handoffs").exists()

def test_manual_packet_and_cli_command_do_not_rotate_session(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    compressor = FakeCompressor([{"role": "user", "content": "unused"}])
    agent = make_agent(tmp_path, compressor)
    agent._auto_handoff_artifact_dir = "handoffs"

    packet, path = create_handoff_packet(agent, [{"role": "user", "content": "Current task"}], approx_tokens=123)
    assert path is not None and path.exists()
    assert "manual packet; no new session started" in packet
    assert agent.session_id == "session-old"
    assert agent._session_db.ended == []

    cli = cast(Any, HermesCLI.__new__(HermesCLI))
    cli.agent = agent
    cli.conversation_history = [{"role": "user", "content": "Need handoff"}]
    cli._busy_command = lambda message: nullcontext()
    outputs: list[str] = []
    with patch("cli._cprint", lambda message="": outputs.append(str(message))):
        cli._handle_handoff_packet_command("/handoff-packet before risky edit")
    assert agent.session_id == "session-old"
    assert any("Handoff packet written" in line for line in outputs)


def test_handoff_artifact_dir_cannot_escape_hermes_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    compressor = FakeCompressor([{"role": "user", "content": "unused"}])
    agent = make_agent(tmp_path, compressor)
    agent._auto_handoff_artifact_dir = "../outside"

    packet, path = create_handoff_packet(agent, [{"role": "user", "content": "secret-ish context"}])

    assert "# Hermes handoff packet" in packet
    assert path is None
    assert not (tmp_path / "outside").exists()


def test_handoff_packet_command_is_registered():
    command = next(cmd for cmd in COMMAND_REGISTRY if cmd.name == "handoff-packet")
    assert command.cli_only is True
    assert "handoff_packet" in command.aliases
