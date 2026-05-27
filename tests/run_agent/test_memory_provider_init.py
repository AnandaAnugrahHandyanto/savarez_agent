"""Regression tests for memory provider selection during AIAgent init."""

import json
import sys
import textwrap
from types import SimpleNamespace
from unittest.mock import patch


class RecordingMemoryProvider:
    def __init__(self, name="memory-fabric", tools=None, available=True):
        self._name = name
        self._tools = tools or []
        self._available = available
        self.initialized = False
        self.init_kwargs = {}

    @property
    def name(self):
        return self._name

    def is_available(self):
        return self._available

    def initialize(self, session_id, **kwargs):
        self.initialized = True
        self.init_kwargs = {"session_id": session_id, **kwargs}

    def get_tool_schemas(self):
        return list(self._tools)


class FakeSessionDB:
    def get_session_title(self, session_id):
        return f"title-for-{session_id}"


def _agent_with_memory_config(config, provider, **agent_kwargs):
    with (
        patch("hermes_cli.config.load_config", return_value=config),
        patch("plugins.memory.load_memory_provider", return_value=provider),
        patch("hermes_cli.profiles.get_active_profile_name", return_value="coder"),
        patch("agent.model_metadata.get_model_context_length", return_value=204_800),
        patch("run_agent.get_tool_definitions", return_value=[]),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        from run_agent import AIAgent

        return AIAgent(
            api_key="test-key-1234567890",
            base_url="https://openrouter.ai/api/v1",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=False,
            **agent_kwargs,
        )


def test_blank_memory_provider_does_not_auto_enable_honcho():
    """Blank memory.provider should remain opt-out even if Honcho fallback looks configured."""
    cfg = {"memory": {"provider": ""}, "agent": {}}
    honcho_cfg = SimpleNamespace(enabled=True, api_key="stale-key", base_url=None)

    with (
        patch("hermes_cli.config.load_config", return_value=cfg),
        patch("hermes_cli.config.save_config") as save_config,
        patch(
            "plugins.memory.honcho.client.HonchoClientConfig.from_global_config",
            return_value=honcho_cfg,
        ) as from_global_config,
        patch("plugins.memory.load_memory_provider") as load_memory_provider,
        patch("agent.model_metadata.get_model_context_length", return_value=204_800),
        patch("run_agent.get_tool_definitions", return_value=[]),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        from run_agent import AIAgent

        agent = AIAgent(
            api_key="test-key-1234567890",
            base_url="https://openrouter.ai/api/v1",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=False,
        )

    assert agent._memory_manager is None
    from_global_config.assert_not_called()
    load_memory_provider.assert_not_called()
    save_config.assert_not_called()


def test_provider_specific_memory_config_passed_as_runtime_config():
    provider_config = {
        "candidate_jsonl_path": "/tmp/candidates.jsonl",
        "project_scope": "hermes-memory-fabric",
        "memory_limit": 5,
        "context_budget_chars": 4000,
    }
    cfg = {
        "memory": {
            "provider": "memory-fabric",
            "memory_enabled": False,
            "user_profile_enabled": False,
            "memory-fabric": provider_config,
        },
        "agent": {},
    }
    provider = RecordingMemoryProvider("memory-fabric")

    _agent_with_memory_config(
        cfg,
        provider,
        session_id="session-runtime-config",
        platform="telegram",
        user_id="user-1",
        chat_id="chat-1",
        session_db=FakeSessionDB(),
    )

    assert provider.initialized is True
    assert provider.init_kwargs["session_id"] == "session-runtime-config"
    assert provider.init_kwargs["platform"] == "telegram"
    assert provider.init_kwargs["agent_context"] == "primary"
    assert provider.init_kwargs["session_title"] == "title-for-session-runtime-config"
    assert provider.init_kwargs["user_id"] == "user-1"
    assert provider.init_kwargs["chat_id"] == "chat-1"
    assert provider.init_kwargs["agent_identity"] == "coder"
    assert provider.init_kwargs["agent_workspace"] == "hermes"
    assert provider.init_kwargs["runtime_config"] == provider_config
    assert provider.init_kwargs["runtime_config"] is not provider_config


def test_non_dict_provider_specific_memory_config_is_ignored():
    cfg = {
        "memory": {
            "provider": "memory-fabric",
            "memory_enabled": False,
            "user_profile_enabled": False,
            "memory-fabric": "not-a-dict",
        },
        "agent": {},
    }
    provider = RecordingMemoryProvider("memory-fabric")

    _agent_with_memory_config(cfg, provider)

    assert provider.initialized is True
    assert "runtime_config" not in provider.init_kwargs


def test_existing_memory_provider_init_still_receives_core_kwargs():
    cfg = {
        "memory": {
            "provider": "mem0",
            "memory_enabled": False,
            "user_profile_enabled": False,
        },
        "agent": {},
    }
    provider = RecordingMemoryProvider("mem0")

    _agent_with_memory_config(cfg, provider, platform="cli")

    assert provider.initialized is True
    assert provider.init_kwargs["platform"] == "cli"
    assert provider.init_kwargs["agent_context"] == "primary"
    assert provider.init_kwargs["hermes_home"]
    assert provider.init_kwargs["runtime_config"] == {}


def test_memory_fabric_runtime_config_smoke_prefetches_jsonl(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes-home"
    plugins_dir = hermes_home / "plugins" / "memory-fabric"
    plugins_dir.mkdir(parents=True)
    candidate_path = tmp_path / "candidates.jsonl"
    candidate_path.write_text(
        json.dumps({"text": "Runtime config memory reached provider."}) + "\n",
        encoding="utf-8",
    )
    (hermes_home / "config.yaml").write_text(
        textwrap.dedent(
            f"""
            memory:
              provider: memory-fabric
              memory_enabled: false
              user_profile_enabled: false
              memory-fabric:
                candidate_jsonl_path: {json.dumps(str(candidate_path))}
                project_scope: hermes-memory-fabric
                memory_limit: 5
                context_budget_chars: 4000
            agent: {{}}
            """
        ),
        encoding="utf-8",
    )
    (plugins_dir / "__init__.py").write_text(
        textwrap.dedent(
            """
            import json
            from pathlib import Path

            from agent.memory_provider import MemoryProvider


            class MemoryFabricProvider(MemoryProvider):
                def __init__(self):
                    self.runtime_config = {}
                    self.init_kwargs = {}

                @property
                def name(self):
                    return "memory-fabric"

                def is_available(self):
                    return True

                def initialize(self, session_id, **kwargs):
                    self.session_id = session_id
                    self.init_kwargs = dict(kwargs)
                    self.runtime_config = dict(kwargs.get("runtime_config") or {})

                def prefetch(self, query, *, session_id=""):
                    path = self.runtime_config.get("candidate_jsonl_path")
                    if not path:
                        return ""
                    rows = []
                    for line in Path(path).read_text(encoding="utf-8").splitlines():
                        if not line.strip():
                            continue
                        row = json.loads(line)
                        text = row.get("text") or row.get("content") or row.get("context") or ""
                        if text:
                            rows.append(text)
                    return "\\n".join(rows)

                def get_tool_schemas(self):
                    return []


            def register(ctx):
                ctx.register_memory_provider(MemoryFabricProvider())
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    for name in list(sys.modules):
        if name.startswith("_hermes_user_memory.memory-fabric"):
            sys.modules.pop(name, None)
    import hermes_cli.config as config_mod
    config_mod._LOAD_CONFIG_CACHE.clear()
    config_mod._RAW_CONFIG_CACHE.clear()

    with (
        patch("agent.model_metadata.get_model_context_length", return_value=204_800),
        patch("run_agent.get_tool_definitions", return_value=[]),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        from run_agent import AIAgent

        agent = AIAgent(
            api_key="test-key-1234567890",
            base_url="https://openrouter.ai/api/v1",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=False,
        )

    provider = agent._memory_manager.get_provider("memory-fabric")
    assert provider is not None
    assert provider.runtime_config["candidate_jsonl_path"] == str(candidate_path)
    assert provider.runtime_config["project_scope"] == "hermes-memory-fabric"
    assert provider.runtime_config["memory_limit"] == 5
    assert provider.runtime_config["context_budget_chars"] == 4000
    assert provider.get_tool_schemas() == []
    assert agent._memory_manager.get_all_tool_schemas() == []
    assert (
        agent._memory_manager.prefetch_all("runtime config")
        == "Runtime config memory reached provider."
    )
