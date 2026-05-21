import asyncio
import json
import os
import sys
import threading
import types
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import GatewayConfig, HomeChannel, Platform, PlatformConfig
from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    SendResult,
    TopicProfileConfigError,
    resolve_topic_profile,
)
from gateway.session import SessionSource, SessionStore, build_session_key
from hermes_constants import get_hermes_home, hermes_home_context
from hermes_cli.profiles import write_profile_identity_marker


def _mark_profile(profile_home, profile_name=None, profiles_root=None):
    profile_home.mkdir(parents=True, exist_ok=True)
    write_profile_identity_marker(
        profile_name or profile_home.name,
        profile_home,
        profiles_root or profile_home.parent,
        overwrite=True,
    )
    return profile_home


class _CapturingAgent:
    last_init = None
    last_user_message = None
    inits = []
    _lock = threading.Lock()

    def __init__(self, *args, **kwargs):
        from agent.prompt_builder import load_soul_md
        from tools.memory_tool import get_memory_dir

        record = dict(kwargs)
        record["hermes_home_at_init"] = str(get_hermes_home())
        record["soul"] = load_soul_md() or ""
        record["memory_dir"] = str(get_memory_dir())
        try:
            from gateway.session_context import get_session_env
            record["session_env_agent_profile"] = get_session_env("HERMES_SESSION_AGENT_PROFILE", "")
            record["session_env_agent_hermes_home"] = get_session_env("HERMES_SESSION_AGENT_HERMES_HOME", "")
        except Exception:
            record["session_env_agent_profile"] = ""
            record["session_env_agent_hermes_home"] = ""
        with self._lock:
            type(self).last_init = record
            type(self).inits.append(record)
        self.tools = []

    def run_conversation(self, user_message, conversation_history=None, task_id=None, persist_user_message=None):
        type(self).last_user_message = user_message
        return {
            "final_response": "ok",
            "messages": [],
            "api_calls": 1,
            "completed": True,
        }


def _install_fake_agent(monkeypatch):
    fake_run_agent = types.ModuleType("run_agent")
    fake_run_agent.AIAgent = _CapturingAgent
    monkeypatch.setitem(sys.modules, "run_agent", fake_run_agent)
    _CapturingAgent.last_init = None
    _CapturingAgent.last_user_message = None
    _CapturingAgent.inits = []


def _make_runner(config=None, *, gateway_prompt="Gateway prompt"):
    from gateway import run as gateway_run
    from gateway.session import SessionStore

    runner = object.__new__(gateway_run.GatewayRunner)
    runner.adapters = {}
    runner._ephemeral_system_prompt = gateway_prompt
    runner._prefill_messages = [{"role": "system", "content": "gateway prefill"}]
    runner._reasoning_config = None
    runner._service_tier = None
    runner._provider_routing = {"order": ["gateway-provider"], "sort": "latency"}
    runner._fallback_model = None
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._busy_ack_ts = {}
    runner._session_run_generation = {}
    runner._pending_model_notes = {}
    runner._update_prompt_pending = {}
    runner._background_tasks = set()
    runner._pending_native_image_paths_by_session = {}
    runner._pending_approvals = {}
    runner._voice_mode = {}
    runner._session_db = None
    runner._agent_cache = {}
    runner._agent_cache_lock = threading.Lock()
    runner._session_model_overrides = {}
    runner._session_reasoning_overrides = {}
    runner._draining = False
    runner.hooks = SimpleNamespace(loaded_hooks=False, emit=AsyncMock())
    runner.config = config or GatewayConfig()
    runner.session_store = SessionStore(get_hermes_home() / "sessions", runner.config)
    runner._get_or_create_gateway_honcho = lambda session_key: (None, None)
    runner._enrich_message_with_vision = AsyncMock(return_value="ENRICHED")
    return runner


def _provider_runtime(runtime_env=None):
    return {
        "provider": "openrouter",
        "api_mode": "chat_completions",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": (runtime_env or {}).get("OPENROUTER_API_KEY", "sk-test-gateway-key"),
    }


def _write_profile_config(profile_home, *, prompt, model, toolsets=None, disabled=None, provider_routing=None, prefill=None):
    _mark_profile(profile_home)
    prefill_line = f'prefill_messages_file: "{prefill}"\n' if prefill else ""
    provider_lines = ""
    if provider_routing:
        provider_lines = "provider_routing:\n" + "\n".join(
            f"  {key}: {json.dumps(value)}" for key, value in provider_routing.items()
        ) + "\n"
    disabled_lines = ""
    if disabled:
        disabled_lines = "  disabled_toolsets:\n" + "\n".join(f"    - {item}" for item in disabled) + "\n"
    toolset_lines = ""
    if toolsets:
        toolset_lines = "platform_toolsets:\n  telegram:\n" + "\n".join(f"    - {item}" for item in toolsets) + "\n"
    (profile_home / "config.yaml").write_text(
        (
            "model:\n"
            "  provider: openrouter\n"
            f"  default: {model}\n"
            "agent:\n"
            f"  system_prompt: {json.dumps(prompt)}\n"
            "  reasoning_effort: high\n"
            "  service_tier: priority\n"
            f"{disabled_lines}"
            f"{prefill_line}"
            f"{provider_lines}"
            f"{toolset_lines}"
        ),
        encoding="utf-8",
    )
    (profile_home / ".env").write_text("OPENROUTER_API_KEY=sk-test-profile-key\n", encoding="utf-8")


def _write_skill(home, name, description):
    skill_dir = home / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n\n{description}\n",
        encoding="utf-8",
    )
    return skill_dir


def _write_bundle(home, slug, skills):
    bundle_dir = home / "skill-bundles"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / f"{slug}.yaml").write_text(
        f"name: {slug}\nskills:\n" + "\n".join(f"  - {skill}" for skill in skills) + "\n",
        encoding="utf-8",
    )


def _source(**overrides):
    home = overrides.get("agent_hermes_home")
    profile = overrides.get("agent_profile")
    if home and profile:
        home_path = Path(str(home))
        if home_path.is_absolute():
            _mark_profile(home_path, str(profile))
    data = {
        "platform": Platform.TELEGRAM,
        "chat_id": "-1001",
        "chat_type": "group",
        "thread_id": "101",
        "user_id": "42",
    }
    data.update(overrides)
    return SessionSource(**data)


class _KeyCapturingAdapter(BasePlatformAdapter):
    def __init__(self, config=None):
        super().__init__(config or PlatformConfig(enabled=True, token="test"), Platform.TELEGRAM)
        self.captured_session_key = None

    async def connect(self):
        return True

    async def disconnect(self):
        return None

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        return SendResult(success=True, message_id="1")

    async def get_chat_info(self, chat_id):
        return {"id": chat_id}

    def _start_session_processing(self, event, session_key, *, interrupt_event=None):
        self.captured_session_key = session_key
        return True


def test_topic_profile_resolver_matches_exact_topic_and_home(tmp_path):
    profile_home = tmp_path / "profiles" / "alpha-test"
    _mark_profile(profile_home)
    route = resolve_topic_profile(
        {
            "topic_profiles_safe_root": str(tmp_path / "profiles"),
            "topic_profiles": [
                {
                    "match": {"chat_id": "-1001", "thread_id": 101},
                    "profile": "alpha-test",
                    "profile_home": str(profile_home),
                }
            ]
        },
        "-1001",
        "101",
    )

    assert route == {"profile": "alpha-test", "profile_home": str(profile_home)}


def test_topic_profile_resolver_handles_general_topic_and_absent_topic_falls_back(tmp_path):
    profile_home = _mark_profile(tmp_path / "profiles" / "general-test")
    general = resolve_topic_profile(
        {
            "topic_profiles_safe_root": str(profile_home.parent),
            "topic_profiles": [
                {"match": {"chat_id": "-1001", "thread_id": "1"}, "profile": "general-test"},
            ]
        },
        "-1001",
        "1",
    )
    no_topic = resolve_topic_profile(
        {
            "topic_profiles_safe_root": str(profile_home.parent),
            "topic_profiles": [
                {"match": {"chat_id": "-1001", "thread_id": "1"}, "profile": "general-test"},
            ]
        },
        "-1001",
        None,
    )

    assert general == {"profile": "general-test", "profile_home": str(profile_home)}
    assert no_topic is None


def test_topic_profile_resolver_rejects_allowed_topics_mismatch(tmp_path):
    profile_home = _mark_profile(tmp_path / "profiles" / "topic-test")
    with pytest.raises(TopicProfileConfigError, match="allowed_topics would block"):
        resolve_topic_profile(
            {
                "allowed_topics": ["202"],
                "topic_profiles_safe_root": str(profile_home.parent),
                "topic_profiles": [
                    {"match": {"chat_id": "-1001", "thread_id": "101"}, "profile": "topic-test"},
                ],
            },
            "-1001",
            "101",
        )


def test_topic_profile_resolver_rejects_default_profile(tmp_path):
    profiles_root = tmp_path / "profiles"
    profiles_root.mkdir()
    with pytest.raises(TopicProfileConfigError, match="Invalid .*profile"):
        resolve_topic_profile(
            {
                "topic_profiles_safe_root": str(profiles_root),
                "topic_profiles": [
                    {"match": {"chat_id": "-1001", "thread_id": "101"}, "profile": "default"},
                ],
            },
            "-1001",
            "101",
        )


def test_topic_profiles_reject_env_allowed_topics_mismatch(monkeypatch, tmp_path):
    from gateway.config import load_gateway_config

    hermes_home = tmp_path / ".hermes"
    profile_home = hermes_home / "profiles" / "alpha-test"
    _mark_profile(profile_home)
    (hermes_home / "config.yaml").write_text(
        "telegram:\n"
        f"  topic_profiles_safe_root: {hermes_home / 'profiles'}\n"
        "  topic_profiles:\n"
        "    - match:\n"
        "        chat_id: '-1001'\n"
        "        thread_id: 101\n"
        "      profile: alpha-test\n"
        f"      profile_home: {profile_home}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("TELEGRAM_ALLOWED_TOPICS", "202")

    with pytest.raises(TopicProfileConfigError, match="allowed_topics would block"):
        load_gateway_config()


def test_topic_profile_resolver_rejects_invalid_profile_names(tmp_path):
    profiles_root = tmp_path / "profiles"
    profiles_root.mkdir()
    with pytest.raises(TopicProfileConfigError, match="Invalid .*profile"):
        resolve_topic_profile(
            {
                "topic_profiles_safe_root": str(profiles_root),
                "topic_profiles": [
                    {
                        "match": {"chat_id": "-1001", "thread_id": "101"},
                        "profile": "bad:profile",
                    }
                ]
            },
            "-1001",
            "101",
        )


def test_topic_profile_resolver_rejects_missing_thread_id(tmp_path):
    profiles_root = tmp_path / "profiles"
    profiles_root.mkdir()
    with pytest.raises(TopicProfileConfigError, match="requires match.chat_id and match.thread_id"):
        resolve_topic_profile(
            {
                "topic_profiles_safe_root": str(profiles_root),
                "topic_profiles": [
                    {"match": {"chat_id": "-1001"}, "profile": "no-topic-test"},
                ]
            },
            "-1001",
            None,
        )


def test_topic_profile_resolver_rejects_duplicate_routes(tmp_path):
    profiles_root = tmp_path / "profiles"
    profiles_root.mkdir()
    (profiles_root / "a").mkdir()
    (profiles_root / "b").mkdir()
    with pytest.raises(TopicProfileConfigError, match="Duplicate"):
        resolve_topic_profile(
            {
                "topic_profiles_safe_root": str(profiles_root),
                "topic_profiles": [
                    {"match": {"chat_id": "-1001", "thread_id": 101}, "profile": "a"},
                    {"match": {"chat_id": "-1001", "thread_id": "101"}, "profile": "b"},
                ]
            },
            "-1001",
            "101",
        )


def test_topic_profile_resolver_rejects_profile_home_without_safe_root(tmp_path):
    with pytest.raises(TopicProfileConfigError, match="topic_profiles_safe_root is required"):
        resolve_topic_profile(
            {
                "topic_profiles": [
                    {
                        "match": {"chat_id": "-1001", "thread_id": "101"},
                        "profile": "alpha-test",
                        "profile_home": str(tmp_path / "alpha-test"),
                    }
                ]
            },
            "-1001",
            "101",
        )


def test_session_key_includes_valid_profile_and_ignores_invalid_profile():
    routed = build_session_key(_source(agent_profile="alpha-test"))
    invalid = build_session_key(_source(agent_profile="bad:profile"))

    assert routed == "agent:alpha-test:telegram:group:-1001:101"
    assert invalid == "agent:main:telegram:group:-1001:101"


def test_parse_session_key_accepts_routed_profiles():
    from gateway.run import _parse_session_key

    parsed = _parse_session_key("agent:alpha-test:telegram:group:-1001:101")

    assert parsed is not None
    assert parsed["agent_profile"] == "alpha-test"
    assert parsed["platform"] == "telegram"
    assert parsed["chat_type"] == "group"
    assert parsed["chat_id"] == "-1001"


def test_session_key_treats_empty_profile_as_main_without_warning(caplog):
    source = _source(agent_profile="")

    assert build_session_key(source) == "agent:main:telegram:group:-1001:101"
    assert "Ignoring invalid agent profile" not in caplog.text


def test_session_source_roundtrip_preserves_agent_profile_fields(tmp_path):
    source = _source(
        agent_profile="beta-test",
        agent_hermes_home=str(tmp_path / "beta-test"),
    )

    restored = SessionSource.from_dict(source.to_dict())

    assert restored.agent_profile == "beta-test"
    assert restored.agent_hermes_home == str(tmp_path / "beta-test")


def test_completion_event_rebuilds_source_with_routed_profile(tmp_path):
    from gateway.run import GatewayRunner

    gateway_home = tmp_path / "gateway"
    profile_home = tmp_path / "profiles" / "alpha-test"
    gateway_home.mkdir()
    profile_home.mkdir(parents=True)

    with hermes_home_context(gateway_home):
        runner = object.__new__(GatewayRunner)
        runner.config = GatewayConfig()
        runner.session_store = SessionStore(gateway_home / "sessions", runner.config)

        source = runner._build_process_event_source(
            {
                "session_id": "proc_alpha",
                "session_key": "agent:alpha-test:telegram:group:-1001:101",
                "platform": "telegram",
                "chat_type": "group",
                "chat_id": "-1001",
                "thread_id": "101",
                "user_id": "42",
                "agent_profile": "alpha-test",
                "agent_hermes_home": str(profile_home),
            }
        )

    assert source is not None
    assert source.agent_profile == "alpha-test"
    assert source.agent_hermes_home == str(profile_home)
    assert source.thread_id == "101"


@pytest.mark.asyncio
async def test_reload_mcp_reads_profile_cli_config_for_routed_topic(monkeypatch, tmp_path):
    from gateway.run import GatewayRunner
    from tools import mcp_tool

    gateway_home = tmp_path / "gateway"
    profiles_root = tmp_path / "profiles"
    profile_home = profiles_root / "alpha-test"
    gateway_home.mkdir()
    profile_home.mkdir(parents=True)
    captured_homes = []

    def fake_discover_mcp_tools():
        captured_homes.append(str(get_hermes_home()))
        mcp_tool._servers["profile-server"] = object()
        return [{"name": "profile_tool"}]

    monkeypatch.setattr(mcp_tool, "_servers", {})
    monkeypatch.setattr(mcp_tool, "_lock", threading.Lock())
    monkeypatch.setattr(mcp_tool, "shutdown_mcp_servers", lambda: None)
    monkeypatch.setattr(mcp_tool, "discover_mcp_tools", fake_discover_mcp_tools)

    with hermes_home_context(gateway_home):
        runner = object.__new__(GatewayRunner)
        runner.config = GatewayConfig(
            platforms={
                Platform.TELEGRAM: PlatformConfig(
                    extra={"topic_profiles_safe_root": str(profiles_root)}
                )
            }
        )
        runner.session_store = SessionStore(gateway_home / "sessions", runner.config)
        source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))
        event = MessageEvent(
            text="/reload-mcp",
            message_type=MessageType.COMMAND,
            source=source,
        )
        result = await runner._execute_mcp_reload(event)

    assert captured_homes == [str(profile_home)]
    assert "profile-server" in result


@pytest.mark.asyncio
async def test_reload_skills_reads_profile_home_for_routed_topic(monkeypatch, tmp_path):
    from agent import skill_commands
    from gateway.run import GatewayRunner

    gateway_home = tmp_path / "gateway"
    profiles_root = tmp_path / "profiles"
    profile_home = profiles_root / "alpha-test"
    gateway_home.mkdir()
    profile_home.mkdir(parents=True)
    captured_homes = []

    def fake_reload_skills():
        captured_homes.append(str(get_hermes_home()))
        return {"added": [], "removed": [], "total": 0}

    monkeypatch.setattr(skill_commands, "reload_skills", fake_reload_skills)

    with hermes_home_context(gateway_home):
        runner = object.__new__(GatewayRunner)
        runner.config = GatewayConfig(
            platforms={
                Platform.TELEGRAM: PlatformConfig(
                    extra={"topic_profiles_safe_root": str(profiles_root)}
                )
            }
        )
        runner.adapters = {}
        runner.session_store = SessionStore(gateway_home / "sessions", runner.config)
        source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))
        event = MessageEvent(
            text="/reload-skills",
            message_type=MessageType.COMMAND,
            source=source,
        )
        result = await runner._handle_reload_skills_command(event)

    assert captured_homes == [str(profile_home)]
    assert "Skills Reloaded" in result


def test_profile_session_store_uses_routed_home_without_changing_global_home(tmp_path):
    from gateway.run import GatewayRunner

    gateway_home = tmp_path / "gateway"
    profile_home = tmp_path / "profiles" / "alpha-test"
    profile_home.mkdir(parents=True)
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(tmp_path / "profiles")}
            )
        }
    )

    with hermes_home_context(gateway_home):
        runner = object.__new__(GatewayRunner)
        runner.config = config
        runner.session_store = SessionStore(gateway_home / "sessions", config)
        source = _source(
            agent_profile="alpha-test",
            agent_hermes_home=str(profile_home),
        )

        profile_store = runner._session_store_for_source(source)

        assert profile_store.sessions_dir == profile_home / "sessions"
        assert profile_store._db.db_path == profile_home / "state.db"
        assert get_hermes_home() == gateway_home
        assert runner._session_key_for_source(source) == (
            "agent:alpha-test:telegram:group:-1001:101"
        )


def test_named_profile_without_explicit_home_stays_isolated_under_profiles_root(tmp_path):
    from gateway.run import GatewayRunner

    gateway_home = tmp_path / "gateway"
    profile_home = _mark_profile(gateway_home / "profiles" / "alpha-test")
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profile_home.parent)}
            )
        }
    )

    with hermes_home_context(gateway_home):
        runner = object.__new__(GatewayRunner)
        runner.config = config
        runner.session_store = SessionStore(gateway_home / "sessions", config)
        source = _source(agent_profile="alpha-test")

        profile_store = runner._session_store_for_source(source)

        assert profile_store.sessions_dir == gateway_home / "profiles" / "alpha-test" / "sessions"
        assert profile_store._db.db_path == gateway_home / "profiles" / "alpha-test" / "state.db"
        assert profile_store is not runner.session_store


@pytest.mark.asyncio
async def test_resume_pending_shutdown_mark_uses_routed_profile_store(tmp_path):
    from tests.gateway.restart_test_helpers import make_restart_runner

    gateway_home = tmp_path / "gateway"
    profile_home = gateway_home / "profiles" / "alpha-test"
    profile_home.mkdir(parents=True)
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                enabled=True,
                token="test",
                extra={
                    "topic_profiles_safe_root": str(gateway_home / "profiles"),
                    "topic_profiles": [
                        {
                            "match": {"chat_id": "-1001", "thread_id": "101"},
                            "profile": "alpha-test",
                            "profile_home": str(profile_home),
                        }
                    ],
                },
            )
        }
    )

    with hermes_home_context(gateway_home):
        runner, adapter = make_restart_runner()
        runner.config = config
        runner.session_store = SessionStore(gateway_home / "sessions", config)
        runner._restart_drain_timeout = 0.05
        source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))
        profile_store = runner._session_store_for_source(source)
        entry = profile_store.get_or_create_session(source)
        runner._running_agents = {entry.session_key: MagicMock()}
        adapter.disconnect = AsyncMock()

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("gateway.status.remove_pid_file", lambda: None)
            mp.setattr("gateway.status.write_runtime_status", lambda *args, **kwargs: None)
            await runner.stop()

        profile_store._ensure_loaded()
        runner.session_store._ensure_loaded()

    assert profile_store._entries[entry.session_key].resume_pending is True
    assert entry.session_key not in runner.session_store._entries


@pytest.mark.asyncio
async def test_startup_auto_resume_scans_routed_profile_store(tmp_path):
    gateway_home = tmp_path / "gateway"
    profile_home = gateway_home / "profiles" / "alpha-test"
    profile_home.mkdir(parents=True)
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                enabled=True,
                token="test",
                extra={
                    "topic_profiles_safe_root": str(gateway_home / "profiles"),
                    "topic_profiles": [
                        {
                            "match": {"chat_id": "-1001", "thread_id": "101"},
                            "profile": "alpha-test",
                            "profile_home": str(profile_home),
                        }
                    ],
                },
            )
        }
    )
    source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))

    with hermes_home_context(gateway_home):
        seed_runner = _make_runner(config)
        profile_store = seed_runner._session_store_for_source(source)
        entry = profile_store.get_or_create_session(source)
        profile_store.mark_resume_pending(entry.session_key, "restart_timeout")

        runner = _make_runner(config)
        adapter = _KeyCapturingAdapter()
        adapter.handle_message = AsyncMock()
        runner.adapters = {Platform.TELEGRAM: adapter}

        scheduled = runner._schedule_resume_pending_sessions()
        await asyncio.sleep(0)

    assert scheduled == 1
    adapter.handle_message.assert_awaited_once()
    event = adapter.handle_message.await_args.args[0]
    assert event.internal is True
    assert event.source.agent_profile == "alpha-test"
    assert event.source.agent_hermes_home == str(profile_home)


def test_relative_explicit_profile_home_is_resolved_inside_safe_root(tmp_path):
    from gateway.run import GatewayRunner

    gateway_home = tmp_path / "gateway"
    profiles_root = tmp_path / "profiles"
    profile_home = profiles_root / "relative-home"
    _mark_profile(profile_home, "alpha-test")
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    with hermes_home_context(gateway_home):
        runner = object.__new__(GatewayRunner)
        runner.config = config
        runner.session_store = SessionStore(gateway_home / "sessions", config)
        source = _source(agent_profile="alpha-test", agent_hermes_home="relative-home")

        profile_store = runner._session_store_for_source(source)

        assert profile_store.sessions_dir == profile_home / "sessions"


def test_missing_named_profile_fails_closed(tmp_path):
    from gateway.run import GatewayRunner, TopicProfileRoutingError

    gateway_home = tmp_path / "gateway"
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(gateway_home / "profiles")}
            )
        }
    )

    with hermes_home_context(gateway_home):
        runner = object.__new__(GatewayRunner)
        runner.config = config
        runner.session_store = SessionStore(gateway_home / "sessions", config)
        source = _source(agent_profile="missing-profile")

        with pytest.raises(TopicProfileRoutingError, match="does not exist"):
            runner._session_store_for_source(source)


def test_routed_profile_runtime_env_is_loaded_without_mutating_process_env(monkeypatch, tmp_path):
    from gateway import run as gateway_run
    from gateway.run import GatewayRunner

    gateway_home = tmp_path / "gateway"
    profile_home = gateway_home / "profiles" / "alpha-test"
    _mark_profile(profile_home)
    (profile_home / ".env").write_text("OPENROUTER_API_KEY=profile-key\n", encoding="utf-8")
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profile_home.parent)}
            )
        }
    )
    captured = {}

    def _capture_runtime(runtime_env=None):
        captured["runtime_env"] = dict(runtime_env or {})
        return {
            "api_key": runtime_env.get("OPENROUTER_API_KEY"),
            "base_url": "https://openrouter.ai/api/v1",
            "provider": "openrouter",
            "api_mode": "chat_completions",
        }

    monkeypatch.setenv("OPENROUTER_API_KEY", "main-key")
    monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", _capture_runtime)

    with hermes_home_context(gateway_home):
        runner = object.__new__(GatewayRunner)
        runner.config = config
        runner.session_store = SessionStore(gateway_home / "sessions", config)
        runner._session_model_overrides = {}
        runner._pending_model_notes = {}
        source = _source(agent_profile="alpha-test")

        model, runtime = runner._resolve_session_agent_runtime(
            source=source,
            user_config={"model": {"default": "test-model"}},
        )

    assert model == "test-model"
    assert runtime["api_key"] == "profile-key"
    assert captured["runtime_env"]["OPENROUTER_API_KEY"] == "profile-key"
    assert captured["runtime_env"]["HERMES_PROFILE_STRICT_AUTH"] == "1"
    assert captured["runtime_env"]["HERMES_HOME"] == str(profile_home)
    assert os.environ["OPENROUTER_API_KEY"] == "main-key"


@pytest.mark.asyncio
async def test_hermes_home_context_is_task_local(tmp_path):
    import asyncio

    gateway_home = tmp_path / "gateway"
    profile_home = tmp_path / "profile"

    async def read_home(path):
        with hermes_home_context(path):
            await asyncio.sleep(0)
            return get_hermes_home()

    first, second = await asyncio.gather(read_home(gateway_home), read_home(profile_home))

    assert first == gateway_home
    assert second == profile_home


def test_config_yaml_bridges_telegram_topic_profiles(monkeypatch, tmp_path):
    from gateway.config import load_gateway_config

    profile_home = _mark_profile(tmp_path / "profiles" / "alpha-test")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        f"""
telegram:
  enabled: true
  token: test-token
  topic_profiles_safe_root: {profile_home.parent}
  topic_profiles:
    - match:
        chat_id: "-1001"
        thread_id: 101
      profile: alpha-test
""",
        encoding="utf-8",
    )

    config = load_gateway_config()

    assert config.platforms[Platform.TELEGRAM].extra["topic_profiles"][0]["profile"] == "alpha-test"


def test_config_yaml_relative_safe_root_survives_runtime_cwd_change(monkeypatch, tmp_path):
    from gateway.config import load_gateway_config

    profile_home = _mark_profile(tmp_path / "profiles" / "alpha-test")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        """
telegram:
  enabled: true
  token: test-token
  topic_profiles_safe_root: profiles
  topic_profiles:
    - match:
        chat_id: "-1001"
        thread_id: 101
      profile: alpha-test
""",
        encoding="utf-8",
    )

    config = load_gateway_config()
    other_cwd = tmp_path / "service-cwd"
    other_cwd.mkdir()
    monkeypatch.chdir(other_cwd)

    route = resolve_topic_profile(
        config.platforms[Platform.TELEGRAM].extra,
        "-1001",
        "101",
    )

    assert route == {"profile": "alpha-test", "profile_home": str(profile_home)}


def test_config_yaml_warns_for_ui_platforms_topic_profiles(monkeypatch, tmp_path, caplog):
    from gateway.config import load_gateway_config

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    (tmp_path / "config.yaml").write_text(
        """
ui:
  platforms:
    telegram:
      topic_profiles:
        - match:
            chat_id: "-1001"
            thread_id: 101
          profile: alpha-test
""",
        encoding="utf-8",
    )

    config = load_gateway_config()

    assert Platform.TELEGRAM not in config.platforms
    assert "Ignoring ui.platforms.telegram.topic_profiles" in caplog.text


def test_telegram_synthetic_message_event_sets_profile_on_event_and_source(tmp_path):
    pytest.importorskip("telegram")
    from telegram.constants import ChatType
    from gateway.platforms.telegram import TelegramAdapter

    profile_home = tmp_path / "alpha-test"
    profile_home.mkdir()
    adapter = TelegramAdapter(
        PlatformConfig(
            enabled=True,
            token="test-token",
            extra={
                "topic_profiles_safe_root": str(tmp_path),
                "topic_profiles": [
                    {
                        "match": {"chat_id": "-1001", "thread_id": "101"},
                        "profile": "alpha-test",
                        "profile_home": str(profile_home),
                    }
                ]
            },
        )
    )
    message = SimpleNamespace(
        chat=SimpleNamespace(
            id=-1001,
            type="supergroup",
            is_forum=True,
            title="Sandbox Forum",
        ),
        from_user=SimpleNamespace(id=42, full_name="Ayo Test"),
        message_thread_id=101,
        is_topic_message=True,
        text="hello",
        caption=None,
        message_id=7,
        reply_to_message=None,
        date=datetime(2026, 5, 1),
    )

    event = adapter._build_message_event(message, msg_type=MessageType.TEXT)

    assert event.agent_profile == "alpha-test"
    assert event.agent_hermes_home == str(profile_home)
    assert event.source.agent_profile == "alpha-test"
    assert event.source.agent_hermes_home == str(profile_home)


@pytest.mark.asyncio
async def test_base_handle_message_hydrates_event_profile_before_session_key(tmp_path):
    adapter = _KeyCapturingAdapter()
    adapter.set_message_handler(AsyncMock(return_value=None))
    event = MessageEvent(
        text="hi",
        message_type=MessageType.TEXT,
        source=_source(thread_id="10", agent_profile=None, agent_hermes_home=None),
        agent_profile="atlas",
        agent_hermes_home=str(tmp_path / "atlas"),
    )

    await adapter.handle_message(event)

    assert adapter.captured_session_key == "agent:atlas:telegram:group:-1001:10"
    assert event.source.agent_profile == "atlas"
    assert event.source.agent_hermes_home == str(tmp_path / "atlas")


@pytest.mark.asyncio
async def test_runner_fallback_hydrates_topic_profile_before_quick_key(monkeypatch, tmp_path):
    from gateway.run import GatewayRunner

    profiles_root = tmp_path / "profiles"
    profile_home = profiles_root / "atlas"
    _mark_profile(profile_home)
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={
                    "topic_profiles_safe_root": str(profiles_root),
                    "topic_profiles": [
                        {
                            "match": {"chat_id": "-1001", "thread_id": "10"},
                            "profile": "atlas",
                            "profile_home": str(profile_home),
                        }
                    ],
                }
            )
        }
    )
    captured = {}

    async def fake_inner(event, source, quick_key, run_generation):
        captured["quick_key"] = quick_key
        captured["source"] = source
        return "ok"

    with hermes_home_context(tmp_path / "gateway"):
        runner = _make_runner(config)
        runner._is_user_authorized = lambda _source: True
        monkeypatch.setattr(runner, "_handle_message_with_agent", fake_inner)
        event = MessageEvent(
            text="hi",
            message_type=MessageType.TEXT,
            source=_source(thread_id="10", agent_profile=None, agent_hermes_home=None),
        )
        response = await runner._handle_message(event)

    assert response == "ok"
    assert captured["quick_key"] == "agent:atlas:telegram:group:-1001:10"
    assert captured["source"].agent_profile == "atlas"
    assert captured["source"].agent_hermes_home == str(profile_home)


@pytest.mark.asyncio
async def test_runner_fallback_no_topic_profile_match_stays_main(monkeypatch, tmp_path):
    from gateway.run import GatewayRunner

    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    _mark_profile(profiles_root / "atlas")
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={
                    "topic_profiles_safe_root": str(profiles_root),
                    "topic_profiles": [
                        {"match": {"chat_id": "-1001", "thread_id": "10"}, "profile": "atlas"}
                    ],
                }
            )
        }
    )
    captured = {}

    async def fake_inner(event, source, quick_key, run_generation):
        captured["quick_key"] = quick_key
        captured["source"] = source
        return "ok"

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        runner._is_user_authorized = lambda _source: True
        monkeypatch.setattr(runner, "_handle_message_with_agent", fake_inner)
        event = MessageEvent(
            text="hi",
            message_type=MessageType.TEXT,
            source=_source(thread_id="11", agent_profile=None, agent_hermes_home=None),
        )
        response = await runner._handle_message(event)

    assert response == "ok"
    assert captured["quick_key"] == "agent:main:telegram:group:-1001:11"
    assert captured["source"].agent_profile is None


def test_runner_fallback_normalizes_forum_general_topic_from_raw_message(tmp_path):
    from gateway.run import GatewayRunner

    profiles_root = tmp_path / "profiles"
    profile_home = profiles_root / "atlas"
    profile_home.mkdir(parents=True)
    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={
                    "topic_profiles_safe_root": str(profiles_root),
                    "topic_profiles": [
                        {
                            "match": {"chat_id": "-1001", "thread_id": "1"},
                            "profile": "atlas",
                            "profile_home": str(profile_home),
                        }
                    ],
                }
            )
        }
    )
    event = MessageEvent(
        text="general",
        message_type=MessageType.TEXT,
        source=_source(thread_id=None, agent_profile=None, agent_hermes_home=None),
        raw_message=SimpleNamespace(
            message_thread_id=None,
            chat=SimpleNamespace(is_forum=True),
        ),
    )

    runner._hydrate_topic_profile_for_event(event)

    assert event.source.thread_id is None
    assert event.source.agent_profile is None
    assert event.source.agent_hermes_home is None


def test_try_resolve_fallback_provider_uses_scoped_key_env(monkeypatch, tmp_path):
    from gateway import run as gateway_run

    profile_home = tmp_path / "profile"
    profile_home.mkdir()
    (profile_home / "config.yaml").write_text(
        "model:\n"
        "  provider: openrouter\n"
        "  default: primary-model\n"
        "fallback_providers:\n"
        "  - provider: openrouter\n"
        "    model: fallback-model\n"
        "    key_env: PROFILE_FALLBACK_KEY\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PROFILE_FALLBACK_KEY", "global-secret")
    monkeypatch.setenv("OPENROUTER_API_KEY", "global-openrouter")

    with hermes_home_context(profile_home):
        resolved = gateway_run._try_resolve_fallback_provider(
            runtime_env={"PROFILE_FALLBACK_KEY": "profile-secret"}
        )

    assert resolved is not None
    assert resolved["provider"] == "openrouter"
    assert resolved["api_key"] == "profile-secret"
    assert resolved["model"] == "fallback-model"


def test_try_resolve_fallback_provider_fails_closed_when_scoped_key_env_missing(
    monkeypatch, tmp_path
):
    from gateway import run as gateway_run

    profile_home = tmp_path / "profile"
    profile_home.mkdir()
    (profile_home / "config.yaml").write_text(
        "model:\n"
        "  provider: openrouter\n"
        "  default: primary-model\n"
        "fallback_providers:\n"
        "  - provider: openrouter\n"
        "    model: fallback-model\n"
        "    key_env: PROFILE_FALLBACK_KEY\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PROFILE_FALLBACK_KEY", "global-secret")
    monkeypatch.setenv("OPENROUTER_API_KEY", "global-openrouter")

    with hermes_home_context(profile_home):
        resolved = gateway_run._try_resolve_fallback_provider(runtime_env={})

    assert resolved is None


def test_resolve_runtime_agent_kwargs_uses_scoped_fallback_when_primary_has_no_key(
    monkeypatch, tmp_path
):
    from gateway import run as gateway_run

    profile_home = tmp_path / "profile"
    profile_home.mkdir()
    (profile_home / "config.yaml").write_text(
        "model:\n"
        "  provider: openrouter\n"
        "  default: primary-model\n"
        "fallback_providers:\n"
        "  - provider: openrouter\n"
        "    model: fallback-model\n"
        "    key_env: PROFILE_FALLBACK_KEY\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENROUTER_API_KEY", "global-openrouter")
    monkeypatch.setenv("PROFILE_FALLBACK_KEY", "global-fallback")

    with hermes_home_context(profile_home):
        resolved = gateway_run._resolve_runtime_agent_kwargs(
            runtime_env={"PROFILE_FALLBACK_KEY": "profile-fallback"}
        )

    assert resolved["provider"] == "openrouter"
    assert resolved["api_key"] == "profile-fallback"
    assert resolved["model"] == "fallback-model"


def test_resolve_runtime_agent_kwargs_fails_closed_when_scoped_primary_and_fallback_missing(
    monkeypatch, tmp_path
):
    from gateway import run as gateway_run

    profile_home = tmp_path / "profile"
    profile_home.mkdir()
    (profile_home / "config.yaml").write_text(
        "model:\n"
        "  provider: openrouter\n"
        "  default: primary-model\n"
        "fallback_providers:\n"
        "  - provider: openrouter\n"
        "    model: fallback-model\n"
        "    key_env: PROFILE_FALLBACK_KEY\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENROUTER_API_KEY", "global-openrouter")
    monkeypatch.setenv("PROFILE_FALLBACK_KEY", "global-fallback")

    with hermes_home_context(profile_home):
        resolved = gateway_run._resolve_runtime_agent_kwargs(runtime_env={})

    assert resolved["provider"] == "openrouter"
    assert resolved["api_key"] == ""


@pytest.mark.asyncio
async def test_run_agent_returns_visible_auth_failure_for_routed_profile_without_credentials(
    monkeypatch, tmp_path
):
    from gateway import run as gateway_run

    gateway_home = tmp_path / "gateway"
    gateway_home.mkdir()
    profile_home = tmp_path / "profile"
    profile_home.mkdir()
    (profile_home / "config.yaml").write_text(
        "model:\n"
        "  provider: openrouter\n"
        "  default: routed-model\n",
        encoding="utf-8",
    )
    (profile_home / ".env").write_text("", encoding="utf-8")
    monkeypatch.setenv("OPENROUTER_API_KEY", "global-openrouter-should-not-be-used")
    monkeypatch.setattr(gateway_run, "load_dotenv", lambda *args, **kwargs: None)
    _install_fake_agent(monkeypatch)

    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(tmp_path)}
            )
        }
    )
    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
    source = _source(
        agent_profile="profile",
        agent_hermes_home=str(profile_home),
    )

    with hermes_home_context(profile_home):
        result = await runner._run_agent(
            message="hi",
            context_prompt="",
            history=[],
            source=source,
            session_id="session-auth-fail",
            session_key=build_session_key(source),
        )

    assert "Provider authentication failed" in result["final_response"]
    assert "profile-scoped provider credentials" in result["final_response"]
    assert _CapturingAgent.last_init is None


def test_telegram_batch_keys_are_profile_aware_from_event(tmp_path):
    pytest.importorskip("telegram")
    from gateway.platforms.telegram import TelegramAdapter

    adapter = TelegramAdapter(PlatformConfig(enabled=True, token="test-token", extra={}))
    event = MessageEvent(
        text="hi",
        message_type=MessageType.TEXT,
        source=_source(thread_id="10", agent_profile=None),
        agent_profile="atlas",
    )
    msg = SimpleNamespace(media_group_id=None)

    assert adapter._text_batch_key(event) == "agent:atlas:telegram:group:-1001:10"
    assert adapter._photo_batch_key(event, msg) == "agent:atlas:telegram:group:-1001:10:photo-burst"
    assert adapter._media_group_batch_key(event, "album-1") == (
        "agent:atlas:telegram:group:-1001:10:album:album-1"
    )


@pytest.mark.asyncio
async def test_adapter_resolver_hydrates_profile_before_adapter_session_key(tmp_path):
    profiles_root = tmp_path / "profiles"
    profile_home = profiles_root / "atlas"
    profile_home.mkdir(parents=True)
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={
                    "topic_profiles_safe_root": str(profiles_root),
                    "topic_profiles": [
                        {
                            "match": {"chat_id": "-1001", "thread_id": "10"},
                            "profile": "atlas",
                            "profile_home": str(profile_home),
                        }
                    ],
                }
            )
        }
    )
    with hermes_home_context(tmp_path / "gateway"):
        runner = _make_runner(config)
    adapter = _KeyCapturingAdapter(PlatformConfig(enabled=True, token="test-token", extra={}))
    adapter.set_message_handler(AsyncMock(return_value=None))
    adapter.set_topic_profile_route_resolver(runner._hydrate_topic_profile_for_event)
    event = MessageEvent(
        text="hi",
        message_type=MessageType.TEXT,
        source=_source(thread_id="10", agent_profile=None, agent_hermes_home=None),
    )

    await adapter.handle_message(event)

    assert adapter.captured_session_key == "agent:atlas:telegram:group:-1001:10"
    assert event.source.agent_profile == "atlas"
    assert event.source.agent_hermes_home == str(profile_home)


@pytest.mark.asyncio
async def test_real_telegram_adapter_handle_message_routes_full_turn_to_profile(
    monkeypatch,
    tmp_path,
):
    pytest.importorskip("telegram")
    from telegram.constants import ChatType
    from gateway import run as gateway_run
    from gateway.platforms.telegram import TelegramAdapter

    gateway_home = tmp_path / "gateway"
    profiles_root = tmp_path / "profiles"
    profile_home = profiles_root / "atlas"
    gateway_home.mkdir()
    profile_home.mkdir(parents=True)
    (gateway_home / "SOUL.md").write_text("Gateway SOUL", encoding="utf-8")
    (profile_home / "SOUL.md").write_text("Atlas SOUL", encoding="utf-8")
    _write_profile_config(
        profile_home,
        prompt="Atlas prompt",
        model="openrouter/atlas-model",
        toolsets=["web"],
    )
    route_extra = {
        "topic_profiles_safe_root": str(profiles_root),
        "topic_profiles": [
            {
                "match": {"chat_id": "-1001", "thread_id": "10"},
                "profile": "atlas",
                "profile_home": str(profile_home),
            }
        ],
    }
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(extra=route_extra)
        }
    )
    _install_fake_agent(monkeypatch)
    monkeypatch.delenv("HERMES_EPHEMERAL_SYSTEM_PROMPT", raising=False)
    monkeypatch.delenv("HERMES_PREFILL_MESSAGES_FILE", raising=False)
    monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", _provider_runtime)
    monkeypatch.setattr(gateway_run, "load_dotenv", lambda *args, **kwargs: None)

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        runner._is_user_authorized = lambda _source: True
        adapter = TelegramAdapter(
            PlatformConfig(enabled=True, token="test-token", extra=route_extra)
        )
        adapter.set_message_handler(runner._handle_message)
        adapter.set_topic_profile_route_resolver(runner._hydrate_topic_profile_for_event)
        adapter._send_with_retry = AsyncMock(return_value=SendResult(success=True, message_id="99"))
        adapter.send_typing = AsyncMock()
        adapter.stop_typing = AsyncMock()
        runner.adapters = {Platform.TELEGRAM: adapter}

        message = SimpleNamespace(
            chat=SimpleNamespace(
                id=-1001,
                type="supergroup",
                is_forum=True,
                title="Sandbox Forum",
            ),
            from_user=SimpleNamespace(id=42, full_name="Ayo Test"),
            message_thread_id=10,
            is_topic_message=True,
            text="hello",
            caption=None,
            message_id=7,
            reply_to_message=None,
            date=datetime(2026, 5, 1),
        )
        event = adapter._build_message_event(message, msg_type=MessageType.TEXT)

        await adapter.handle_message(event)
        await asyncio.gather(*list(adapter._background_tasks))

    captured = _CapturingAgent.last_init
    assert captured is not None
    assert captured["gateway_session_key"] == "agent:atlas:telegram:group:-1001:10"
    assert captured["hermes_home_at_init"] == str(profile_home)
    assert captured["soul"] == "Atlas SOUL"
    assert captured["model"] == "openrouter/atlas-model"
    assert "web" in set(captured["enabled_toolsets"])


async def _run_captured_agent(monkeypatch, runner, source, hermes_home, *, context_prompt="", channel_prompt=None):
    from gateway import run as gateway_run

    _install_fake_agent(monkeypatch)
    monkeypatch.delenv("HERMES_EPHEMERAL_SYSTEM_PROMPT", raising=False)
    monkeypatch.delenv("HERMES_PREFILL_MESSAGES_FILE", raising=False)
    monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", _provider_runtime)
    monkeypatch.setattr(gateway_run, "load_dotenv", lambda *args, **kwargs: None)

    with hermes_home_context(hermes_home):
        result = await runner._run_agent(
            message="hi",
            context_prompt=context_prompt,
            history=[],
            source=source,
            session_id=f"session-{source.thread_id or 'main'}",
            session_key=build_session_key(source),
            channel_prompt=channel_prompt,
        )

    assert result["final_response"] == "ok"
    assert _CapturingAgent.last_init is not None
    return _CapturingAgent.last_init


class _CompressingAgent(_CapturingAgent):
    """Capturing agent that mutates ``session_id`` mid-turn to simulate the
    auto-compression code path: when ``run_conversation`` finishes, the
    agent's ``session_id`` differs from the one ``_run_agent`` was invoked
    with, which triggers the compression-split entry update at
    ``gateway/run.py:13041`` (bug E)."""

    new_session_id = "session-after-compression"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Constructor is invoked with ``session_id=...``; rewrite to a
        # different value so the post-result block sees a split.
        self.session_id = self.new_session_id


@pytest.mark.asyncio
async def test_run_agent_compression_split_writes_to_profile_session_store(
    monkeypatch, tmp_path
):
    """Bug E regression: when auto-compression mid-turn rotates the
    agent's ``session_id``, ``_run_agent`` must update the entry on the
    routed profile's SessionStore — not the gateway-global store.

    Before the fix, ``self.session_store._entries.get(...)`` and
    ``self.session_store._save()`` (gateway/run.py:13041 + :13044) wrote
    to the gateway store, leaving the profile entry stuck on the old
    ``session_id`` and making the compressed transcript unreachable on
    the next routed turn.
    """
    from gateway import run as gateway_run

    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    profile_home.mkdir(parents=True)
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    fake_run_agent = types.ModuleType("run_agent")
    fake_run_agent.AIAgent = _CompressingAgent
    monkeypatch.setitem(sys.modules, "run_agent", fake_run_agent)
    _CompressingAgent.last_init = None
    _CompressingAgent.inits = []
    monkeypatch.delenv("HERMES_EPHEMERAL_SYSTEM_PROMPT", raising=False)
    monkeypatch.delenv("HERMES_PREFILL_MESSAGES_FILE", raising=False)
    monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", _provider_runtime)
    monkeypatch.setattr(gateway_run, "load_dotenv", lambda *args, **kwargs: None)

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        source = _source(
            chat_type="dm",
            thread_id=None,
            agent_profile="alpha-test",
            agent_hermes_home=str(profile_home),
        )
        session_key = build_session_key(source)

        profile_store = runner._session_store_for_source(source)
        gateway_store = runner.session_store

        original_session_id = "session-before-compression"
        profile_entry = profile_store.get_or_create_session(source)
        profile_entry.session_id = original_session_id
        profile_store._save()
        monkeypatch.setattr(
            profile_store._db,
            "get_telegram_topic_binding_by_session",
            lambda *, session_id: (
                {"thread_id": "303"}
                if session_id == _CompressingAgent.new_session_id
                else None
            ),
        )
        gateway_entry = gateway_store.get_or_create_session(source)
        gateway_entry.session_id = "gateway-untouched"
        gateway_store._save()

        with hermes_home_context(profile_home):
            result = await runner._run_agent(
                message="hi",
                context_prompt="",
                history=[],
                source=source,
                session_id=original_session_id,
                session_key=session_key,
            )

    assert result["final_response"] == "ok"

    # Profile store entry must reflect the post-compression session id.
    profile_entry_after = profile_store._entries.get(session_key)
    assert profile_entry_after is not None
    assert profile_entry_after.session_id == _CompressingAgent.new_session_id
    assert source.thread_id == "303"

    # Gateway store must NOT have been written. Its entry, if present, keeps
    # the original placeholder id; either the entry is absent or untouched.
    gw_entry_after = gateway_store._entries.get(session_key)
    if gw_entry_after is not None:
        assert gw_entry_after.session_id == "gateway-untouched"


def test_routed_profile_session_db_fail_closed_without_profile_db(tmp_path):
    gateway_home = tmp_path / "gateway"
    profile_home = tmp_path / "profiles" / "alpha-test"
    profile_home.mkdir(parents=True)
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profile_home.parent)}
            )
        }
    )

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        runner._is_user_authorized = lambda _source: True
        source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))
        runner._session_db = SimpleNamespace(name="global-db")
        runner._session_store_for_source = lambda _source: SimpleNamespace(_db=None)
        with pytest.raises(Exception, match="session DB is unavailable"):
            runner._session_db_for_source(source)


@pytest.mark.asyncio
async def test_run_agent_auto_title_writes_to_profile_session_db(
    monkeypatch, tmp_path
):
    """Bug E regression: auto-title generation at ``gateway/run.py:13056``
    must call ``maybe_auto_title`` with the routed profile's SessionDB,
    not ``self._session_db`` (which is the gateway-global one)."""
    from gateway import run as gateway_run

    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    profile_home.mkdir(parents=True)
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    _install_fake_agent(monkeypatch)
    monkeypatch.delenv("HERMES_EPHEMERAL_SYSTEM_PROMPT", raising=False)
    monkeypatch.delenv("HERMES_PREFILL_MESSAGES_FILE", raising=False)
    monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", _provider_runtime)
    monkeypatch.setattr(gateway_run, "load_dotenv", lambda *args, **kwargs: None)

    captured_dbs = []

    def _fake_maybe_auto_title(session_db, session_id, message, final_response, all_msgs, **kwargs):
        captured_dbs.append(session_db)

    import agent.title_generator as title_module
    monkeypatch.setattr(title_module, "maybe_auto_title", _fake_maybe_auto_title)

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        # Force the gateway-global _session_db to a sentinel so any leak is
        # observable in the captured arguments.
        gateway_db_sentinel = MagicMock(name="gateway_session_db")
        runner._session_db = gateway_db_sentinel

        source = _source(
            agent_profile="alpha-test",
            agent_hermes_home=str(profile_home),
        )
        profile_store = runner._session_store_for_source(source)
        profile_db = profile_store._db
        assert profile_db is not gateway_db_sentinel

        with hermes_home_context(profile_home):
            await runner._run_agent(
                message="hi",
                context_prompt="",
                history=[],
                source=source,
                session_id="session-init",
                session_key=build_session_key(source),
            )

    assert captured_dbs, "maybe_auto_title was never called"
    assert captured_dbs[0] is profile_db
    assert captured_dbs[0] is not gateway_db_sentinel


@pytest.mark.asyncio
async def test_routed_profile_system_prompt_uses_profile_config_not_gateway_config(monkeypatch, tmp_path):
    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    profile_home.mkdir(parents=True)
    (gateway_home / "config.yaml").write_text(
        'agent:\n  system_prompt: "Gateway config prompt"\n',
        encoding="utf-8",
    )
    _write_profile_config(
        profile_home,
        prompt="Profile config prompt",
        model="anthropic/claude-sonnet-4",
        toolsets=["web"],
    )
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    with hermes_home_context(gateway_home):
        runner = _make_runner(config, gateway_prompt="Gateway runtime prompt")
    source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))

    captured = await _run_captured_agent(
        monkeypatch,
        runner,
        source,
        profile_home,
        context_prompt="Context prompt",
        channel_prompt="Channel prompt",
    )

    assert captured["ephemeral_system_prompt"] == (
        "Context prompt\n\nChannel prompt\n\nProfile config prompt"
    )
    assert "Gateway" not in captured["ephemeral_system_prompt"]


@pytest.mark.asyncio
async def test_non_routed_system_prompt_keeps_existing_gateway_behavior(monkeypatch, tmp_path):
    gateway_home = tmp_path / "gateway"
    gateway_home.mkdir()
    (gateway_home / "config.yaml").write_text(
        'agent:\n  system_prompt: "Gateway config prompt"\n',
        encoding="utf-8",
    )

    with hermes_home_context(gateway_home):
        runner = _make_runner(gateway_prompt="Gateway runtime prompt")
    source = _source(agent_profile=None, agent_hermes_home=None)

    captured = await _run_captured_agent(
        monkeypatch,
        runner,
        source,
        gateway_home,
        context_prompt="Context prompt",
        channel_prompt="Channel prompt",
    )

    assert captured["ephemeral_system_prompt"] == (
        "Context prompt\n\nChannel prompt\n\nGateway runtime prompt"
    )


@pytest.mark.asyncio
async def test_routed_profile_soul_identity_is_loaded_from_profile_home(monkeypatch, tmp_path):
    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    profile_home.mkdir(parents=True)
    (gateway_home / "SOUL.md").write_text("Gateway SOUL", encoding="utf-8")
    (profile_home / "SOUL.md").write_text("Profile SOUL", encoding="utf-8")
    _write_profile_config(profile_home, prompt="Profile prompt", model="profile-model", toolsets=["web"])
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
    source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))

    captured = await _run_captured_agent(monkeypatch, runner, source, profile_home)

    assert captured["soul"] == "Profile SOUL"
    assert captured["hermes_home_at_init"] == str(profile_home)


@pytest.mark.asyncio
async def test_handle_message_routes_full_turn_through_topic_profile(monkeypatch, tmp_path):
    from gateway import run as gateway_run

    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    profile_home.mkdir(parents=True)
    (gateway_home / "SOUL.md").write_text("Gateway SOUL", encoding="utf-8")
    (profile_home / "SOUL.md").write_text("Profile SOUL", encoding="utf-8")
    _write_profile_config(
        profile_home,
        prompt="Profile prompt",
        model="openrouter/profile-model",
        toolsets=["web"],
    )
    (profile_home / ".env").write_text(
        "OPENROUTER_API_KEY=sk-test-profile-key\nHERMES_MAX_ITERATIONS=7\n",
        encoding="utf-8",
    )
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                enabled=True,
                token="gateway-token",
                home_channel=HomeChannel(
                    platform=Platform.TELEGRAM,
                    chat_id="-100999",
                    name="GatewayHome",
                ),
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    _install_fake_agent(monkeypatch)
    monkeypatch.delenv("HERMES_EPHEMERAL_SYSTEM_PROMPT", raising=False)
    monkeypatch.delenv("HERMES_PREFILL_MESSAGES_FILE", raising=False)
    monkeypatch.setenv("HERMES_MAX_ITERATIONS", "99")
    monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", _provider_runtime)
    monkeypatch.setattr(gateway_run, "load_dotenv", lambda *args, **kwargs: None)

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        runner._detect_stale_code = lambda: False
        runner._trigger_stale_code_restart = lambda: None
        runner._is_user_authorized = lambda _source: True
        source = _source(
            agent_profile="alpha-test",
            agent_hermes_home=str(profile_home),
        )
        event = MessageEvent(text="hi", message_type=MessageType.TEXT, source=source)

        response = await runner._handle_message(event)

        assert get_hermes_home() == gateway_home

    assert response == "ok"
    captured = _CapturingAgent.last_init
    assert captured is not None
    assert captured["hermes_home_at_init"] == str(profile_home)
    assert captured["soul"] == "Profile SOUL"
    assert captured["model"] == "openrouter/profile-model"
    assert captured["max_iterations"] == 7
    assert "web" in set(captured["enabled_toolsets"])
    assert "GatewayHome" not in captured["ephemeral_system_prompt"]
    assert "Home Channels" not in captured["ephemeral_system_prompt"]


@pytest.mark.asyncio
async def test_quick_and_plugin_commands_disabled_for_routed_profile_topics(monkeypatch, tmp_path):
    from hermes_cli import plugins

    gateway_home = tmp_path / "gateway"
    profile_home = gateway_home / "profiles" / "alpha-test"
    profile_home.mkdir(parents=True)
    executed = {"quick": False, "plugin": False}

    async def fake_subprocess_shell(*_args, **_kwargs):
        executed["quick"] = True
        raise AssertionError("quick command should not execute")

    def fake_plugin_handler(_name):
        def _handler(_args):
            executed["plugin"] = True
            return "plugin result"

        return _handler

    monkeypatch.setattr(asyncio, "create_subprocess_shell", fake_subprocess_shell)
    monkeypatch.setattr(
        plugins,
        "get_plugin_commands",
        lambda: {"plugin-test": {"description": "Plugin test", "handler": fake_plugin_handler("plugin-test")}},
    )
    monkeypatch.setattr(plugins, "get_plugin_command_handler", fake_plugin_handler)

    config = GatewayConfig(
        quick_commands={
            "limits": {"type": "exec", "command": "echo gateway"},
            "status-alias": {"type": "alias", "target": "/status"},
        },
    )
    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        runner.hooks.emit_collect = AsyncMock(
            side_effect=AssertionError("plugin hooks should not run in routed profile topics")
        )
        runner._is_user_authorized = lambda _source: True
        source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))

        quick_response = await runner._handle_message(
            MessageEvent(text="/limits", message_type=MessageType.TEXT, source=source)
        )
        alias_response = await runner._handle_message(
            MessageEvent(text="/status-alias", message_type=MessageType.TEXT, source=source)
        )
        plugin_response = await runner._handle_message(
            MessageEvent(text="/plugin-test", message_type=MessageType.TEXT, source=source)
        )

    assert "disabled in routed profile topics" in quick_response
    assert "disabled in routed profile topics" in alias_response
    assert "disabled in routed profile topics" in plugin_response
    assert executed == {"quick": False, "plugin": False}


@pytest.mark.asyncio
async def test_sethome_disabled_for_routed_profile_topics(monkeypatch, tmp_path):
    from hermes_cli import config as hermes_config
    from hermes_cli import plugins

    gateway_home = tmp_path / "gateway"
    profile_home = gateway_home / "profiles" / "alpha-test"
    profile_home.mkdir(parents=True)

    def fail_save_env_value(*_args, **_kwargs):
        raise AssertionError("/sethome must not write gateway env from a routed topic")

    monkeypatch.setattr(hermes_config, "save_env_value", fail_save_env_value)
    monkeypatch.setattr(
        plugins,
        "invoke_hook",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("pre_gateway_dispatch must not run in routed profile topics")
        ),
    )

    with hermes_home_context(gateway_home):
        runner = _make_runner(
            GatewayConfig(
                platforms={
                    Platform.TELEGRAM: PlatformConfig(
                        extra={"topic_profiles_safe_root": str(gateway_home / "profiles")}
                    )
                }
            )
        )
        runner.hooks.emit_collect = AsyncMock(
            side_effect=AssertionError("command hooks must not run in routed profile topics")
        )
        runner._detect_stale_code = lambda: False
        runner._trigger_stale_code_restart = lambda: None
        runner._is_user_authorized = lambda _source: True
        source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))
        event = MessageEvent(text="/sethome", message_type=MessageType.TEXT, source=source)
        response = await runner._handle_message(event)

    assert "disabled in routed profile topics" in response


@pytest.mark.asyncio
async def test_insights_command_uses_profile_session_db_for_routed_topic(monkeypatch, tmp_path):
    from agent import insights as insights_module

    class _FakeInsightsEngine:
        captured_db = None
        captured_source = None

        def __init__(self, db):
            type(self).captured_db = db

        def generate(self, *, days, source=None):
            type(self).captured_source = source
            return {"days": days}

        def format_gateway(self, report):
            return f"profile insights {report['days']}"

    gateway_home = tmp_path / "gateway"
    profile_home = gateway_home / "profiles" / "alpha-test"
    profile_home.mkdir(parents=True)
    monkeypatch.setattr(insights_module, "InsightsEngine", _FakeInsightsEngine)

    with hermes_home_context(gateway_home):
        runner = _make_runner(
            GatewayConfig(
                platforms={
                    Platform.TELEGRAM: PlatformConfig(
                        extra={"topic_profiles_safe_root": str(gateway_home / "profiles")}
                    )
                }
            )
        )
        source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))
        profile_store = runner._session_store_for_source(source)
        runner._session_db = runner.session_store._db
        event = MessageEvent(
            text="/insights --days 7 --source telegram",
            message_type=MessageType.TEXT,
            source=source,
        )
        response = await runner._handle_insights_command(event)

    assert response == "profile insights 7"
    assert _FakeInsightsEngine.captured_db is profile_store._db
    assert _FakeInsightsEngine.captured_source == "telegram"


@pytest.mark.asyncio
async def test_auto_compression_hygiene_uses_profile_runtime_home_and_session_db(monkeypatch, tmp_path):
    from gateway import run as gateway_run

    class _HygieneAgent:
        inits = []
        home_at_compress = None

        def __init__(self, *args, **kwargs):
            self.session_id = kwargs["session_id"]
            self.context_compressor = SimpleNamespace(
                _last_compress_aborted=False,
                _last_summary_error=None,
                _last_aux_model_failure_model=None,
                _last_aux_model_failure_error=None,
            )
            type(self).inits.append(
                {
                    **kwargs,
                    "hermes_home_at_init": str(get_hermes_home()),
                }
            )

        def _compress_context(self, messages, *_args, **_kwargs):
            type(self).home_at_compress = str(get_hermes_home())
            self.session_id = "hygiene-compressed-session"
            return ([messages[0], messages[-1]], "")

        def run_conversation(self, user_message, conversation_history=None, task_id=None, persist_user_message=None):
            return {
                "final_response": "ok",
                "messages": [],
                "api_calls": 1,
                "completed": True,
            }

        def shutdown_memory_provider(self):
            return None

        def close(self):
            return None

    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    profile_home.mkdir(parents=True)
    _write_profile_config(profile_home, prompt="Profile prompt", model="profile-model")
    with (profile_home / "config.yaml").open("a", encoding="utf-8") as fh:
        fh.write("compression:\n  enabled: true\n  hygiene_hard_message_limit: 4\n")
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    fake_run_agent = types.ModuleType("run_agent")
    fake_run_agent.AIAgent = _HygieneAgent
    monkeypatch.setitem(sys.modules, "run_agent", fake_run_agent)
    monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", _provider_runtime)
    monkeypatch.setattr(gateway_run, "load_dotenv", lambda *args, **kwargs: None)

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        runner._detect_stale_code = lambda: False
        runner._trigger_stale_code_restart = lambda: None
        runner._is_user_authorized = lambda _source: True
        source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))
        profile_store = runner._session_store_for_source(source)
        profile_entry = profile_store.get_or_create_session(source)
        profile_store.rewrite_transcript(
            profile_entry.session_id,
            [
                {"role": "user", "content": "one"},
                {"role": "assistant", "content": "two"},
                {"role": "user", "content": "three"},
                {"role": "assistant", "content": "four"},
            ],
        )
        profile_entry.last_prompt_tokens = 10
        profile_store._save()

        event = MessageEvent(text="continue", message_type=MessageType.TEXT, source=source)
        response = await runner._handle_message(event)

    assert response == "ok"
    hygiene_init = _HygieneAgent.inits[0]
    assert hygiene_init["hermes_home_at_init"] == str(profile_home)
    assert _HygieneAgent.home_at_compress == str(profile_home)
    assert hygiene_init["runtime_env"]["OPENROUTER_API_KEY"] == "sk-test-profile-key"
    assert hygiene_init["runtime_env"]["HERMES_PROFILE_STRICT_AUTH"] == "1"
    assert hygiene_init["runtime_env"]["HERMES_HOME"] == str(profile_home)
    assert hygiene_init["session_db"] is profile_store._db
    assert hygiene_init["api_key"] == "sk-test-profile-key"


@pytest.mark.asyncio
async def test_routed_profile_skill_slash_command_uses_profile_skills(monkeypatch, tmp_path):
    from agent import skill_commands
    from gateway import run as gateway_run

    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    gateway_home.mkdir()
    profile_home.mkdir(parents=True)
    _write_skill(gateway_home, "gateway-only", "gateway skill body")
    _write_skill(profile_home, "profile-only", "profile skill body")
    _write_profile_config(
        profile_home,
        prompt="Profile prompt",
        model="openrouter/profile-model",
        toolsets=["web"],
    )
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    _install_fake_agent(monkeypatch)
    monkeypatch.setattr(skill_commands, "_skill_commands", {}, raising=False)
    monkeypatch.setattr(skill_commands, "_skill_commands_platform", None, raising=False)
    monkeypatch.setattr(skill_commands, "_skill_commands_home", None, raising=False)
    monkeypatch.delenv("HERMES_EPHEMERAL_SYSTEM_PROMPT", raising=False)
    monkeypatch.delenv("HERMES_PREFILL_MESSAGES_FILE", raising=False)
    monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", _provider_runtime)
    monkeypatch.setattr(gateway_run, "load_dotenv", lambda *args, **kwargs: None)

    with hermes_home_context(gateway_home):
        # Prime the process-global slash-command cache with gateway skills.
        assert "/gateway-only" in skill_commands.get_skill_commands()
        runner = _make_runner(config)
        runner._detect_stale_code = lambda: False
        runner._trigger_stale_code_restart = lambda: None
        runner._is_user_authorized = lambda _source: True
        source = _source(
            agent_profile="alpha-test",
            agent_hermes_home=str(profile_home),
        )
        event = MessageEvent(
            text="/profile-only use profile-local instructions",
            message_type=MessageType.TEXT,
            source=source,
        )

        response = await runner._handle_message(event)

    assert response == "ok"
    assert _CapturingAgent.last_user_message is not None
    assert "profile skill body" in _CapturingAgent.last_user_message
    assert "gateway skill body" not in _CapturingAgent.last_user_message


@pytest.mark.asyncio
async def test_routed_profile_skill_bundle_uses_profile_bundle_and_skills(monkeypatch, tmp_path):
    from agent import skill_bundles

    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    gateway_home.mkdir()
    profile_home.mkdir(parents=True)
    _write_skill(gateway_home, "gateway-only", "gateway skill body")
    _write_skill(profile_home, "profile-only", "profile skill body")
    _write_bundle(gateway_home, "research", ["gateway-only"])
    _write_bundle(profile_home, "research", ["profile-only"])
    _write_profile_config(profile_home, prompt="Profile prompt", model="openrouter/profile-model")
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    _install_fake_agent(monkeypatch)
    monkeypatch.delenv("HERMES_BUNDLES_DIR", raising=False)
    monkeypatch.delenv("HERMES_EPHEMERAL_SYSTEM_PROMPT", raising=False)
    monkeypatch.delenv("HERMES_PREFILL_MESSAGES_FILE", raising=False)
    monkeypatch.setattr(skill_bundles, "_bundles_cache", {}, raising=False)
    monkeypatch.setattr(skill_bundles, "_bundles_cache_mtime", None, raising=False)

    with hermes_home_context(gateway_home):
        assert skill_bundles.resolve_bundle_command_key("research") == "/research"
        runner = _make_runner(config)
        runner._detect_stale_code = lambda: False
        runner._trigger_stale_code_restart = lambda: None
        runner._is_user_authorized = lambda _source: True
        source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))
        event = MessageEvent(
            text="/research use bundle instructions",
            message_type=MessageType.TEXT,
            source=source,
        )

        response = await runner._handle_message(event)

    assert response == "ok"
    assert _CapturingAgent.last_user_message is not None
    assert "profile skill body" in _CapturingAgent.last_user_message
    assert "gateway skill body" not in _CapturingAgent.last_user_message


@pytest.mark.asyncio
async def test_routed_profile_help_and_commands_list_profile_skills(monkeypatch, tmp_path):
    from agent import skill_commands

    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    gateway_home.mkdir()
    profile_home.mkdir(parents=True)
    _write_skill(gateway_home, "gateway-only", "gateway skill body")
    _write_skill(profile_home, "profile-only", "profile skill body")
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    monkeypatch.setattr(skill_commands, "_skill_commands", {}, raising=False)
    monkeypatch.setattr(skill_commands, "_skill_commands_platform", None, raising=False)
    monkeypatch.setattr(skill_commands, "_skill_commands_home", None, raising=False)

    with hermes_home_context(gateway_home):
        assert "/gateway-only" in skill_commands.get_skill_commands()
        runner = _make_runner(config)
        source = _source(
            agent_profile="alpha-test",
            agent_hermes_home=str(profile_home),
        )
        help_text = await runner._handle_help_command(
            MessageEvent(text="/help", message_type=MessageType.TEXT, source=source)
        )
        commands_text = await runner._handle_commands_command(
            MessageEvent(text="/commands 999", message_type=MessageType.TEXT, source=source)
        )

    assert "/profile_only" in help_text
    assert "/gateway_only" not in help_text
    assert "/profile_only" in commands_text
    assert "/gateway_only" not in commands_text


@pytest.mark.asyncio
async def test_background_task_uses_routed_profile_config_env_and_session_db(monkeypatch, tmp_path):
    from gateway import run as gateway_run

    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    gateway_home.mkdir()
    profile_home.mkdir(parents=True)
    (gateway_home / "SOUL.md").write_text("Gateway SOUL", encoding="utf-8")
    (profile_home / "SOUL.md").write_text("Profile SOUL", encoding="utf-8")
    _write_profile_config(
        profile_home,
        prompt="Profile prompt",
        model="openrouter/profile-background-model",
        toolsets=["web"],
        provider_routing={"order": ["profile-provider"], "sort": "throughput"},
    )
    (profile_home / ".env").write_text(
        "OPENROUTER_API_KEY=sk-test-profile-key\nHERMES_MAX_ITERATIONS=7\n",
        encoding="utf-8",
    )
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    _install_fake_agent(monkeypatch)
    monkeypatch.delenv("HERMES_EPHEMERAL_SYSTEM_PROMPT", raising=False)
    monkeypatch.delenv("HERMES_PREFILL_MESSAGES_FILE", raising=False)
    monkeypatch.setenv("HERMES_MAX_ITERATIONS", "99")
    monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", _provider_runtime)
    monkeypatch.setattr(gateway_run, "load_dotenv", lambda *args, **kwargs: None)

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        mock_adapter = AsyncMock()
        mock_adapter.send = AsyncMock()
        mock_adapter.extract_media = MagicMock(return_value=([], "ok"))
        mock_adapter.extract_images = MagicMock(return_value=([], "ok"))
        runner.adapters = {Platform.TELEGRAM: mock_adapter}
        source = _source(
            agent_profile="alpha-test",
            agent_hermes_home=str(profile_home),
        )
        profile_db = runner._session_store_for_source(source)._db

        await runner._run_background_task("background prompt", source, "bg_profile")

    captured = _CapturingAgent.last_init
    assert captured is not None
    assert captured["hermes_home_at_init"] == str(profile_home)
    assert captured["soul"] == "Profile SOUL"
    assert captured["model"] == "openrouter/profile-background-model"
    assert captured["runtime_env"]["OPENROUTER_API_KEY"] == "sk-test-profile-key"
    assert captured["runtime_env"]["HERMES_MAX_ITERATIONS"] == "7"
    assert captured["max_iterations"] == 7
    assert captured["session_db"] is profile_db
    assert captured["session_env_agent_profile"] == "alpha-test"
    assert captured["session_env_agent_hermes_home"] == str(profile_home)
    assert "web" in set(captured["enabled_toolsets"])
    assert captured["providers_order"] == ["profile-provider"]
    assert captured["provider_sort"] == "throughput"


@pytest.mark.asyncio
async def test_routed_profile_model_toolsets_and_disabled_toolsets_come_from_profile_config(monkeypatch, tmp_path):
    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    profile_home.mkdir(parents=True)
    _write_profile_config(
        profile_home,
        prompt="Profile prompt",
        model="openrouter/profile-model",
        toolsets=["web"],
        disabled=["memory"],
    )
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
    source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))

    captured = await _run_captured_agent(monkeypatch, runner, source, profile_home)

    assert captured["model"] == "openrouter/profile-model"
    assert "web" in set(captured["enabled_toolsets"])
    assert captured["disabled_toolsets"] == ["memory"]


def test_routed_profile_tool_isolation_diagnostic_for_gateway_only_tools():
    from gateway.run import _topic_profile_tool_isolation_notice

    notice = _topic_profile_tool_isolation_notice(
        {
            "platform_toolsets": {"telegram": ["web", "browser"]},
            "mcp_servers": {"search": {"command": "npx", "args": ["server"]}},
        },
        {},
        "telegram",
    )

    assert notice is not None
    assert "platform_toolsets.telegram" in notice
    assert "mcp_servers" in notice
    assert "not inherited" in notice

    no_notice = _topic_profile_tool_isolation_notice(
        {
            "platform_toolsets": {"telegram": ["web", "browser"]},
            "mcp_servers": {"search": {"command": "npx", "args": ["server"]}},
        },
        {
            "platform_toolsets": {"telegram": ["memory"]},
            "mcp_servers": {"profile-search": {"command": "npx"}},
        },
        "telegram",
    )
    assert no_notice is None


@pytest.mark.asyncio
async def test_routed_profile_provider_routing_comes_from_profile_config(monkeypatch, tmp_path):
    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    profile_home.mkdir(parents=True)
    _write_profile_config(
        profile_home,
        prompt="Profile prompt",
        model="openrouter/profile-model",
        toolsets=["web"],
        provider_routing={
            "only": ["anthropic"],
            "ignore": ["deepinfra"],
            "order": ["anthropic", "google"],
            "sort": "throughput",
            "require_parameters": True,
            "data_collection": "deny",
        },
    )
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
    source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))

    captured = await _run_captured_agent(monkeypatch, runner, source, profile_home)

    assert captured["providers_allowed"] == ["anthropic"]
    assert captured["providers_ignored"] == ["deepinfra"]
    assert captured["providers_order"] == ["anthropic", "google"]
    assert captured["provider_sort"] == "throughput"
    assert captured["provider_require_parameters"] is True
    assert captured["provider_data_collection"] == "deny"


@pytest.mark.asyncio
async def test_routed_profile_prefill_file_resolves_relative_to_profile_home(monkeypatch, tmp_path):
    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    profile_home.mkdir(parents=True)
    profile_prefill = [{"role": "system", "content": "profile prefill"}]
    gateway_prefill = [{"role": "system", "content": "gateway prefill"}]
    (profile_home / "prefill.json").write_text(json.dumps(profile_prefill), encoding="utf-8")
    _write_profile_config(
        profile_home,
        prompt="Profile prompt",
        model="openrouter/profile-model",
        toolsets=["web"],
        prefill="prefill.json",
    )
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        runner._prefill_messages = gateway_prefill
    source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))

    captured = await _run_captured_agent(monkeypatch, runner, source, profile_home)

    assert captured["prefill_messages"] == profile_prefill
    assert captured["prefill_messages"] != gateway_prefill


def test_agent_cache_signature_changes_when_profile_prompt_provider_or_prefill_changes():
    from gateway.run import GatewayRunner

    runtime = {
        "provider": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api_mode": "chat_completions",
        "api_key": "***",
    }
    base_keys = {
        "provider_routing.digest": GatewayRunner._stable_config_digest({"order": ["anthropic"]}),
        "prefill_messages.digest": GatewayRunner._stable_config_digest(
            [{"role": "system", "content": "prefill-a"}]
        ),
    }
    base = GatewayRunner._agent_config_signature(
        "model-a",
        runtime,
        ["web"],
        "prompt-a",
        cache_keys=base_keys,
    )
    changed_prompt = GatewayRunner._agent_config_signature(
        "model-a",
        runtime,
        ["web"],
        "prompt-b",
        cache_keys=base_keys,
    )
    changed_provider = GatewayRunner._agent_config_signature(
        "model-a",
        runtime,
        ["web"],
        "prompt-a",
        cache_keys={
            **base_keys,
            "provider_routing.digest": GatewayRunner._stable_config_digest({"order": ["google"]}),
        },
    )
    changed_prefill = GatewayRunner._agent_config_signature(
        "model-a",
        runtime,
        ["web"],
        "prompt-a",
        cache_keys={
            **base_keys,
            "prefill_messages.digest": GatewayRunner._stable_config_digest(
                [{"role": "system", "content": "prefill-b"}]
            ),
        },
    )
    changed_fallback = GatewayRunner._agent_config_signature(
        "model-a",
        runtime,
        ["web"],
        "prompt-a",
        cache_keys={
            **base_keys,
            "fallback.digest": GatewayRunner._stable_config_digest(
                [{"provider": "openrouter", "model": "fallback-b"}]
            ),
        },
    )
    changed_runtime_env = GatewayRunner._agent_config_signature(
        "model-a",
        runtime,
        ["web"],
        "prompt-a",
        cache_keys={
            **base_keys,
            "runtime_env.digest": GatewayRunner._stable_config_digest(
                {"PROFILE_FALLBACK_KEY": "fallback-b"}
            ),
        },
    )

    assert changed_prompt != base
    assert changed_provider != base
    assert changed_prefill != base
    assert changed_fallback != base
    assert changed_runtime_env != base


def test_agent_cache_signature_changes_when_profile_home_or_soul_changes(tmp_path):
    from gateway.run import GatewayRunner

    profile_a = tmp_path / "profiles" / "alpha-test"
    profile_b = tmp_path / "profiles" / "beta-test"
    profile_a.mkdir(parents=True)
    profile_b.mkdir(parents=True)
    (profile_a / "SOUL.md").write_text("SOUL A", encoding="utf-8")
    (profile_b / "SOUL.md").write_text("SOUL A", encoding="utf-8")
    runtime = {"provider": "openrouter", "base_url": "", "api_mode": "chat_completions", "api_key": "***"}

    base = GatewayRunner._agent_config_signature(
        "model-a",
        runtime,
        ["web"],
        "prompt-a",
        cache_keys={
            "hermes_home": str(profile_a),
            "soul_md.digest": GatewayRunner._file_content_digest(profile_a / "SOUL.md"),
        },
    )
    changed_home = GatewayRunner._agent_config_signature(
        "model-a",
        runtime,
        ["web"],
        "prompt-a",
        cache_keys={
            "hermes_home": str(profile_b),
            "soul_md.digest": GatewayRunner._file_content_digest(profile_b / "SOUL.md"),
        },
    )
    (profile_a / "SOUL.md").write_text("SOUL B", encoding="utf-8")
    changed_soul = GatewayRunner._agent_config_signature(
        "model-a",
        runtime,
        ["web"],
        "prompt-a",
        cache_keys={
            "hermes_home": str(profile_a),
            "soul_md.digest": GatewayRunner._file_content_digest(profile_a / "SOUL.md"),
        },
    )

    assert changed_home != base
    assert changed_soul != base


def test_agent_max_turns_config_is_cache_busting():
    from gateway.run import GatewayRunner

    base = GatewayRunner._extract_cache_busting_config({"agent": {"max_turns": 7}})
    changed = GatewayRunner._extract_cache_busting_config({"agent": {"max_turns": 9}})

    assert base["agent.max_turns"] == 7
    assert changed["agent.max_turns"] == 9
    assert GatewayRunner._stable_config_digest(base) != GatewayRunner._stable_config_digest(changed)


@pytest.mark.asyncio
async def test_routed_profile_soul_change_busts_cached_agent(monkeypatch, tmp_path):
    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    profile_home.mkdir(parents=True)
    _write_profile_config(profile_home, prompt="Profile prompt", model="profile-model", toolsets=["web"])
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
    source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))

    _install_fake_agent(monkeypatch)
    monkeypatch.delenv("HERMES_EPHEMERAL_SYSTEM_PROMPT", raising=False)
    monkeypatch.delenv("HERMES_PREFILL_MESSAGES_FILE", raising=False)
    from gateway import run as gateway_run
    monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", _provider_runtime)
    monkeypatch.setattr(gateway_run, "load_dotenv", lambda *args, **kwargs: None)

    with hermes_home_context(profile_home):
        await runner._run_agent(
            message="hi",
            context_prompt="",
            history=[],
            source=source,
            session_id=f"session-{source.thread_id or 'main'}",
            session_key=build_session_key(source),
        )
    (profile_home / "SOUL.md").write_text("Profile SOUL after first turn", encoding="utf-8")
    with hermes_home_context(profile_home):
        await runner._run_agent(
            message="hi",
            context_prompt="",
            history=[],
            source=source,
            session_id=f"session-{source.thread_id or 'main'}",
            session_key=build_session_key(source),
        )

    assert len(_CapturingAgent.inits) == 2
    assert _CapturingAgent.inits[-1]["soul"] == "Profile SOUL after first turn"


@pytest.mark.asyncio
async def test_routed_profile_runtime_env_change_busts_cached_agent(monkeypatch, tmp_path):
    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    profile_home.mkdir(parents=True)
    _write_profile_config(profile_home, prompt="Profile prompt", model="profile-model", toolsets=["web"])
    profile_cfg = (profile_home / "config.yaml").read_text(encoding="utf-8")
    (profile_home / "config.yaml").write_text(
        profile_cfg
        + "fallback_providers:\n"
        + "  - provider: openrouter\n"
        + "    model: anthropic/claude-sonnet-4\n"
        + "    key_env: PROFILE_FALLBACK_KEY\n",
        encoding="utf-8",
    )
    (profile_home / ".env").write_text(
        "OPENROUTER_API_KEY=stable-primary\nPROFILE_FALLBACK_KEY=fallback-one\n",
        encoding="utf-8",
    )
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
    source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))

    _install_fake_agent(monkeypatch)
    monkeypatch.delenv("HERMES_EPHEMERAL_SYSTEM_PROMPT", raising=False)
    monkeypatch.delenv("HERMES_PREFILL_MESSAGES_FILE", raising=False)
    from gateway import run as gateway_run

    def stable_primary_runtime(runtime_env=None):
        return {
            "provider": "openrouter",
            "api_mode": "chat_completions",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": "stable-primary",
        }

    monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", stable_primary_runtime)
    monkeypatch.setattr(gateway_run, "load_dotenv", lambda *args, **kwargs: None)

    with hermes_home_context(profile_home):
        await runner._run_agent(
            message="hi",
            context_prompt="",
            history=[],
            source=source,
            session_id=f"session-{source.thread_id or 'main'}",
            session_key=build_session_key(source),
        )
    (profile_home / ".env").write_text(
        "OPENROUTER_API_KEY=stable-primary\nPROFILE_FALLBACK_KEY=fallback-two\n",
        encoding="utf-8",
    )
    with hermes_home_context(profile_home):
        await runner._run_agent(
            message="hi",
            context_prompt="",
            history=[],
            source=source,
            session_id=f"session-{source.thread_id or 'main'}",
            session_key=build_session_key(source),
        )

    assert len(_CapturingAgent.inits) == 2
    assert _CapturingAgent.inits[0]["runtime_env"]["PROFILE_FALLBACK_KEY"] == "fallback-one"
    assert _CapturingAgent.inits[1]["runtime_env"]["PROFILE_FALLBACK_KEY"] == "fallback-two"


@pytest.mark.asyncio
async def test_reset_command_uses_profile_session_store_for_routed_topic(tmp_path):
    from gateway import run as gateway_run

    gateway_home = tmp_path / "gateway"
    profile_home = gateway_home / "profiles" / "alpha-test"
    profile_home.mkdir(parents=True)
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(gateway_home / "profiles")}
            )
        }
    )

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        runner.hooks = SimpleNamespace(loaded_hooks=False, emit=AsyncMock())
        source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))
        profile_store = runner._session_store_for_source(source)
        old_entry = profile_store.get_or_create_session(source)
        gateway_store = runner.session_store
        gateway_run._hermes_home = gateway_home

        event = MessageEvent(text="/new", message_type=MessageType.TEXT, source=source)
        await runner._handle_reset_command(event)

    profile_entry = profile_store.get_or_create_session(source)
    assert profile_entry.session_id != old_entry.session_id
    assert runner._session_key_for_source(source) not in gateway_store._entries


@pytest.mark.asyncio
async def test_reset_command_displays_routed_profile_model_info(tmp_path):
    from gateway import run as gateway_run

    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    profile_home.mkdir(parents=True)
    gateway_home.mkdir(exist_ok=True)
    (gateway_home / "config.yaml").write_text(
        "model:\n"
        "  provider: openai-codex\n"
        "  default: routed-model\n"
        "  context_length: 272000\n",
        encoding="utf-8",
    )
    (profile_home / "config.yaml").write_text(
        "model:\n"
        "  provider: custom:routed-proxy\n"
        "  default: claude-opus-4-7\n"
        "custom_providers:\n"
        "  - name: routed-proxy\n"
        "    base_url: http://127.0.0.1:8318/v1\n"
        "    key_env: ROUTED_PROXY_API_KEY\n"
        "    model: claude-opus-4-7\n"
        "    context_length: 200000\n",
        encoding="utf-8",
    )
    (profile_home / ".env").write_text("ROUTED_PROXY_API_KEY=sk-test-profile\n", encoding="utf-8")
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    gateway_run._hermes_home = gateway_home
    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))
        runner._session_store_for_source(source).get_or_create_session(source)
        event = MessageEvent(text="/new", message_type=MessageType.TEXT, source=source)
        response = await runner._handle_reset_command(event)

    text = str(response)
    assert "claude-opus-4-7" in text
    assert "custom:routed-proxy" in text
    assert "127.0.0.1:8318" in text
    assert "200K" in text
    assert "routed-model" not in text
    assert "openai-codex" not in text


@pytest.mark.asyncio
async def test_reset_command_session_info_does_not_borrow_global_credentials(monkeypatch, tmp_path):
    from gateway import run as gateway_run

    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    profile_home.mkdir(parents=True)
    gateway_home.mkdir(exist_ok=True)
    (gateway_home / "config.yaml").write_text(
        "model:\n  provider: openai-codex\n  default: routed-model\n",
        encoding="utf-8",
    )
    (profile_home / "config.yaml").write_text(
        "model:\n"
        "  provider: custom:routed-proxy\n"
        "  default: claude-opus-4-7\n"
        "custom_providers:\n"
        "  - name: routed-proxy\n"
        "    base_url: http://127.0.0.1:8318/v1\n"
        "    key_env: ROUTED_PROXY_API_KEY\n"
        "    model: claude-opus-4-7\n",
        encoding="utf-8",
    )
    (profile_home / ".env").write_text("", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-global-must-not-leak")
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    gateway_run._hermes_home = gateway_home
    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))
        runner._session_store_for_source(source).get_or_create_session(source)
        event = MessageEvent(text="/new", message_type=MessageType.TEXT, source=source)
        response = await runner._handle_reset_command(event)

    text = str(response)
    assert "claude-opus-4-7" in text
    assert "custom:routed-proxy" in text
    assert "routed-model" not in text
    assert "openai-codex" not in text


@pytest.mark.asyncio
async def test_reset_command_displays_profile_scoped_fallback_model(tmp_path):
    from gateway import run as gateway_run

    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    profile_home.mkdir(parents=True)
    gateway_home.mkdir(exist_ok=True)
    (gateway_home / "config.yaml").write_text(
        "model:\n  provider: openai-codex\n  default: routed-model\n",
        encoding="utf-8",
    )
    (profile_home / "config.yaml").write_text(
        "model:\n"
        "  provider: custom:routed-proxy\n"
        "  default: claude-opus-4-7\n"
        "custom_providers:\n"
        "  - name: routed-proxy\n"
        "    base_url: http://127.0.0.1:8318/v1\n"
        "    key_env: ROUTED_PROXY_API_KEY\n"
        "    model: claude-opus-4-7\n"
        "fallback_providers:\n"
        "  - provider: openrouter\n"
        "    model: openrouter/fallback-model\n"
        "    key_env: OPENROUTER_API_KEY\n",
        encoding="utf-8",
    )
    (profile_home / ".env").write_text("OPENROUTER_API_KEY=sk-profile-fallback\n", encoding="utf-8")
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    gateway_run._hermes_home = gateway_home
    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))
        runner._session_store_for_source(source).get_or_create_session(source)
        event = MessageEvent(text="/new", message_type=MessageType.TEXT, source=source)
        response = await runner._handle_reset_command(event)

    text = str(response)
    assert "openrouter/fallback-model" in text
    assert "Provider: openrouter" in text
    assert "routed-model" not in text
    assert "openai-codex" not in text


def test_reset_session_info_call_sites_preserve_source_context():
    import inspect

    from gateway.run import GatewayRunner

    message_handler = inspect.getsource(GatewayRunner._handle_message_with_agent)
    reset_handler = inspect.getsource(GatewayRunner._handle_reset_command)

    assert "_format_session_info(source)" in message_handler
    assert "_format_session_info(source)" in reset_handler
    assert "_format_session_info()" not in message_handler
    assert "_format_session_info()" not in reset_handler


@pytest.mark.asyncio
async def test_undo_command_rewrites_profile_transcript_only_for_routed_topic(tmp_path):
    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    profile_home.mkdir(parents=True)
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))
        profile_store = runner._session_store_for_source(source)
        profile_entry = profile_store.get_or_create_session(source)
        gateway_entry = runner.session_store.get_or_create_session(source)
        profile_store.rewrite_transcript(
            profile_entry.session_id,
            [
                {"role": "user", "content": "profile keep"},
                {"role": "assistant", "content": "profile kept"},
                {"role": "user", "content": "profile remove"},
                {"role": "assistant", "content": "profile removed"},
            ],
        )
        runner.session_store.rewrite_transcript(
            gateway_entry.session_id,
            [
                {"role": "user", "content": "gateway keep"},
                {"role": "assistant", "content": "gateway kept"},
                {"role": "user", "content": "gateway remove"},
                {"role": "assistant", "content": "gateway removed"},
            ],
        )

        event = MessageEvent(text="/undo", message_type=MessageType.TEXT, source=source)
        response = await runner._handle_undo_command(event)

    assert "profile remove" in response
    assert [m["content"] for m in profile_store.load_transcript(profile_entry.session_id)] == [
        "profile keep",
        "profile kept",
    ]
    assert [m["content"] for m in runner.session_store.load_transcript(gateway_entry.session_id)] == [
        "gateway keep",
        "gateway kept",
        "gateway remove",
        "gateway removed",
    ]


@pytest.mark.asyncio
async def test_retry_command_rewrites_profile_transcript_only_for_routed_topic(tmp_path):
    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    profile_home.mkdir(parents=True)
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        runner._handle_message = AsyncMock(return_value="retried")
        source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))
        profile_store = runner._session_store_for_source(source)
        profile_entry = profile_store.get_or_create_session(source)
        gateway_entry = runner.session_store.get_or_create_session(source)
        profile_store.rewrite_transcript(
            profile_entry.session_id,
            [
                {"role": "user", "content": "profile keep"},
                {"role": "assistant", "content": "profile kept"},
                {"role": "user", "content": "profile retry"},
                {"role": "assistant", "content": "profile answer"},
            ],
        )
        runner.session_store.rewrite_transcript(
            gateway_entry.session_id,
            [
                {"role": "user", "content": "gateway keep"},
                {"role": "assistant", "content": "gateway kept"},
                {"role": "user", "content": "gateway retry"},
                {"role": "assistant", "content": "gateway answer"},
            ],
        )

        event = MessageEvent(text="/retry", message_type=MessageType.TEXT, source=source)
        response = await runner._handle_retry_command(event)

    assert response == "retried"
    retry_event = runner._handle_message.await_args.args[0]
    assert retry_event.text == "profile retry"
    assert [m["content"] for m in profile_store.load_transcript(profile_entry.session_id)] == [
        "profile keep",
        "profile kept",
    ]
    assert [m["content"] for m in runner.session_store.load_transcript(gateway_entry.session_id)] == [
        "gateway keep",
        "gateway kept",
        "gateway retry",
        "gateway answer",
    ]


@pytest.mark.asyncio
async def test_title_command_uses_profile_session_db_for_routed_topic(tmp_path):
    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    profile_home.mkdir(parents=True)
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))
        profile_store = runner._session_store_for_source(source)
        profile_entry = profile_store.get_or_create_session(source)
        gateway_entry = runner.session_store.get_or_create_session(source)
        runner._session_db = runner.session_store._db

        event = MessageEvent(text="/title Profile Title", message_type=MessageType.TEXT, source=source)
        response = await runner._handle_title_command(event)

    assert "Profile Title" in response
    assert profile_store._db.get_session_title(profile_entry.session_id) == "Profile Title"
    assert runner.session_store._db.get_session_title(gateway_entry.session_id) is None


@pytest.mark.asyncio
async def test_status_command_reads_profile_session_db_for_routed_topic(tmp_path):
    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    profile_home.mkdir(parents=True)
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))
        profile_store = runner._session_store_for_source(source)
        profile_entry = profile_store.get_or_create_session(source)
        profile_store._db.set_session_title(profile_entry.session_id, "Profile DB Title")
        runner._session_db = runner.session_store._db

        event = MessageEvent(text="/status", message_type=MessageType.TEXT, source=source)
        response = await runner._handle_status_command(event)

    assert "Profile DB Title" in response


@pytest.mark.asyncio
async def test_status_command_recap_reads_profile_transcript_only(monkeypatch, tmp_path):
    from hermes_cli import session_recap

    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    profile_home.mkdir(parents=True)
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )
    captured = {}

    def fake_recap(history, **kwargs):
        captured["history"] = list(history)
        return "profile recap"

    monkeypatch.setattr(session_recap, "build_recap", fake_recap)

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))
        profile_store = runner._session_store_for_source(source)
        profile_entry = profile_store.get_or_create_session(source)
        gateway_entry = runner.session_store.get_or_create_session(source)
        profile_entry = profile_store.switch_session(profile_entry.session_key, "same-session")
        gateway_entry = runner.session_store.switch_session(gateway_entry.session_key, "same-session")
        assert profile_entry is not None
        assert gateway_entry is not None
        profile_store._db.create_session(session_id="same-session", source="telegram", user_id="42")
        runner.session_store._db.create_session(session_id="same-session", source="telegram", user_id="42")
        profile_store.rewrite_transcript(
            "same-session",
            [{"role": "user", "content": "profile transcript only"}],
        )
        runner.session_store.rewrite_transcript(
            "same-session",
            [{"role": "user", "content": "gateway transcript leak"}],
        )
        runner._session_db = runner.session_store._db

        event = MessageEvent(text="/status", message_type=MessageType.TEXT, source=source)
        response = await runner._handle_status_command(event)

    assert "profile recap" in response
    assert captured["history"] == [{"role": "user", "content": "profile transcript only"}]


@pytest.mark.asyncio
async def test_compress_command_uses_profile_runtime_home_and_session_db(monkeypatch, tmp_path):
    from gateway import run as gateway_run

    class _ManualCompressAgent:
        last_init = None
        home_at_compress = None

        def __init__(self, *args, **kwargs):
            self.session_id = kwargs["session_id"]
            self._cached_system_prompt = "profile prompt"
            self.tools = []
            self.context_compressor = SimpleNamespace(
                has_content_to_compress=lambda messages: True,
                _last_compress_aborted=False,
                _last_summary_error=None,
                _last_aux_model_failure_model=None,
                _last_aux_model_failure_error=None,
            )
            type(self).last_init = {
                **kwargs,
                "hermes_home_at_init": str(get_hermes_home()),
            }

        def _compress_context(self, messages, *_args, **_kwargs):
            type(self).home_at_compress = str(get_hermes_home())
            self.session_id = "profile-compressed-session"
            return ([messages[0], messages[-1]], "")

        def shutdown_memory_provider(self):
            return None

        def close(self):
            return None

    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    profile_home.mkdir(parents=True)
    gateway_home.mkdir(exist_ok=True)
    (gateway_home / ".env").write_text("OPENROUTER_API_KEY=sk-test-gateway-key\n", encoding="utf-8")
    _write_profile_config(profile_home, prompt="Profile prompt", model="profile-model")
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )
    fake_run_agent = types.ModuleType("run_agent")
    fake_run_agent.AIAgent = _ManualCompressAgent
    monkeypatch.setitem(sys.modules, "run_agent", fake_run_agent)
    captured_runtime = {}

    def _capturing_provider_runtime(runtime_env=None):
        from hermes_cli.auth import profile_strict_auth_enabled
        from gateway.session_context import get_session_env

        captured_runtime["resolver_home"] = str(get_hermes_home())
        captured_runtime["runtime_env"] = runtime_env
        captured_runtime["strict_auth"] = profile_strict_auth_enabled()
        captured_runtime["session_home"] = get_session_env("HERMES_SESSION_AGENT_HERMES_HOME", "")
        return _provider_runtime(runtime_env=runtime_env)

    monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", _capturing_provider_runtime)
    monkeypatch.setattr(gateway_run, "load_dotenv", lambda *args, **kwargs: None)

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))
        profile_store = runner._session_store_for_source(source)
        profile_entry = profile_store.get_or_create_session(source)
        profile_store.rewrite_transcript(
            profile_entry.session_id,
            [
                {"role": "user", "content": "one"},
                {"role": "assistant", "content": "two"},
                {"role": "user", "content": "three"},
                {"role": "assistant", "content": "four"},
            ],
        )
        runner._session_db = runner.session_store._db

        event = MessageEvent(text="/compress", message_type=MessageType.TEXT, source=source)
        response = await runner._handle_compress_command(event)

    assert "Compressed:" in response
    init = _ManualCompressAgent.last_init
    assert init["hermes_home_at_init"] == str(profile_home)
    assert _ManualCompressAgent.home_at_compress == str(profile_home)
    assert init["runtime_env"]["OPENROUTER_API_KEY"] == "sk-test-profile-key"
    assert init["runtime_env"]["HERMES_PROFILE_STRICT_AUTH"] == "1"
    assert init["runtime_env"]["HERMES_HOME"] == str(profile_home)
    assert init["session_db"] is profile_store._db
    assert init["api_key"] == "sk-test-profile-key"
    assert captured_runtime["resolver_home"] == str(profile_home)
    assert captured_runtime["runtime_env"]["OPENROUTER_API_KEY"] == "sk-test-profile-key"
    assert captured_runtime["runtime_env"]["HERMES_PROFILE_STRICT_AUTH"] == "1"
    assert captured_runtime["runtime_env"]["HERMES_HOME"] == str(profile_home)
    assert captured_runtime["strict_auth"] is True
    assert captured_runtime["session_home"] == str(profile_home)


def test_gateway_config_file_loader_validates_topic_profile_identity(tmp_path):
    from gateway.run import _load_gateway_config_from_file

    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    profile_home.mkdir(parents=True)
    config_path = tmp_path / "gateway-config.yaml"
    config_path.write_text(
        "platforms:\n"
        "  telegram:\n"
        "    enabled: true\n"
        "    token: test-token\n"
        "    extra:\n"
        f"      topic_profiles_safe_root: {profiles_root}\n"
        "      topic_profiles:\n"
        "        - match:\n"
        "            chat_id: '-1001'\n"
        "            thread_id: '101'\n"
        "          profile: alpha-test\n",
        encoding="utf-8",
    )

    with hermes_home_context(gateway_home), pytest.raises(
        TopicProfileConfigError,
        match="Missing .hermes_profile.json",
    ):
        _load_gateway_config_from_file(config_path)


@pytest.mark.asyncio
async def test_profile_command_reports_routed_profile_home(tmp_path):
    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    profile_home.mkdir(parents=True)
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))
        event = MessageEvent(text="/profile", message_type=MessageType.TEXT, source=source)
        response = await runner._handle_profile_command(event)

    assert "alpha-test" in response
    assert str(profile_home) in response


def test_relative_safe_root_resolves_against_gateway_home_under_profile_override(tmp_path):
    from hermes_constants import reset_hermes_home_override, set_hermes_home_override

    gateway_home = tmp_path / "gateway"
    profile_home = gateway_home / "profiles" / "alpha-test"
    profile_home.mkdir(parents=True)
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": "profiles"}
            )
        }
    )

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))
        token = set_hermes_home_override(profile_home)
        try:
            assert runner._profile_home_for_source(source) == profile_home
        finally:
            reset_hermes_home_override(token)


@pytest.mark.asyncio
async def test_reload_mcp_is_disabled_for_routed_profile_topics(tmp_path):
    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    profile_home.mkdir(parents=True)
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))
        event = MessageEvent(text="/reload-mcp", message_type=MessageType.TEXT, source=source)
        response = await runner._handle_reload_mcp_command(event)

    assert "disabled" in response
    assert "process-global" in response


@pytest.mark.asyncio
async def test_proxy_mode_is_disabled_for_routed_profile_topics(monkeypatch, tmp_path):
    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    profile_home.mkdir(parents=True)
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )
    monkeypatch.setenv("GATEWAY_PROXY_URL", "http://example.invalid:8642")

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))
        result = await runner._run_agent(
            message="hello",
            context_prompt="",
            history=[],
            source=source,
            session_id="sess-profile",
            session_key=build_session_key(source),
        )

    assert result["api_calls"] == 0
    assert "Proxy mode is disabled" in result["final_response"]


@pytest.mark.asyncio
async def test_global_config_commands_disabled_for_routed_profile_topics(tmp_path):
    gateway_home = tmp_path / "gateway"
    profile_home = gateway_home / "profiles" / "alpha-test"
    profile_home.mkdir(parents=True)
    gateway_config_path = gateway_home / "config.yaml"
    gateway_config = (
        "agent:\n"
        "  reasoning_effort: medium\n"
        "display:\n"
        "  tool_progress_command: true\n"
        "  runtime_footer:\n"
        "    enabled: false\n"
    )
    gateway_config_path.write_text(gateway_config, encoding="utf-8")

    with hermes_home_context(gateway_home):
        runner = _make_runner(GatewayConfig())
        source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))

        model_response = await runner._handle_model_command(
            MessageEvent(text="/model sandbox-alpha-model", message_type=MessageType.TEXT, source=source)
        )
        runtime_response = await runner._handle_codex_runtime_command(
            MessageEvent(text="/codex-runtime auto", message_type=MessageType.TEXT, source=source)
        )
        reasoning_response = await runner._handle_reasoning_command(
            MessageEvent(text="/reasoning high --global", message_type=MessageType.TEXT, source=source)
        )
        verbose_response = await runner._handle_verbose_command(
            MessageEvent(text="/verbose", message_type=MessageType.TEXT, source=source)
        )
        footer_response = await runner._handle_footer_command(
            MessageEvent(text="/footer on", message_type=MessageType.TEXT, source=source)
        )

    assert "disabled in routed profile topics" in model_response
    assert "disabled in routed profile topics" in runtime_response
    assert "disabled in routed profile topics" in reasoning_response
    assert "disabled in routed profile topics" in verbose_response
    assert "disabled in routed profile topics" in footer_response
    assert gateway_config_path.read_text(encoding="utf-8") == gateway_config


@pytest.mark.asyncio
async def test_bundles_command_uses_routed_profile_home(monkeypatch, tmp_path):
    from agent import skill_bundles

    gateway_home = tmp_path / "gateway"
    profile_home = gateway_home / "profiles" / "alpha-test"
    gateway_home.mkdir()
    profile_home.mkdir(parents=True)
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profile_home.parent)}
            )
        }
    )
    _write_bundle(gateway_home, "global-bundle", ["global-skill"])
    _write_bundle(profile_home, "profile-bundle", ["profile-skill"])

    monkeypatch.delenv("HERMES_BUNDLES_DIR", raising=False)
    monkeypatch.setattr(skill_bundles, "_bundles_cache", {}, raising=False)
    monkeypatch.setattr(skill_bundles, "_bundles_cache_mtime", None, raising=False)
    monkeypatch.setattr(skill_bundles, "_bundles_cache_dir", None, raising=False)

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))
        response = await runner._handle_bundles_command(
            MessageEvent(text="/bundles", message_type=MessageType.TEXT, source=source)
        )

    assert "profile-bundle" in response
    assert "global-bundle" not in response


@pytest.mark.asyncio
async def test_agents_command_filters_agents_and_processes_to_profile_scope(monkeypatch, tmp_path):
    from tools import process_registry as process_registry_module

    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    alpha_home = profiles_root / "alpha-test"
    beta_home = profiles_root / "beta-test"
    _mark_profile(alpha_home)
    _mark_profile(beta_home)
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    def fake_list_sessions(task_id=None):
        from gateway.session_context import get_session_env

        active_profile = get_session_env("HERMES_SESSION_AGENT_PROFILE", "")
        active_home = get_session_env("HERMES_SESSION_AGENT_HERMES_HOME", "")
        if active_profile == "beta-test":
            assert active_home == str(beta_home)
            return [
                {
                    "session_id": "proc-beta",
                    "command": "beta command",
                    "uptime_seconds": 1,
                    "status": "running",
                }
            ]
        return [
            {
                "session_id": "proc-alpha",
                "command": "alpha command",
                "uptime_seconds": 1,
                "status": "running",
            }
        ]

    monkeypatch.setattr(process_registry_module.process_registry, "list_sessions", fake_list_sessions)

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        alpha_source = _source(agent_profile="alpha-test", agent_hermes_home=str(alpha_home))
        beta_source = _source(agent_profile="beta-test")
        alpha_key = build_session_key(alpha_source)
        beta_key = build_session_key(beta_source)
        main_key = build_session_key(_source(agent_profile=None, agent_hermes_home=None))
        runner._running_agents = {
            alpha_key: SimpleNamespace(session_id="sess-alpha", model="alpha-model"),
            beta_key: SimpleNamespace(session_id="sess-beta", model="beta-model"),
            main_key: SimpleNamespace(session_id="sess-main", model="main-model"),
        }
        runner._running_agents_ts = {alpha_key: 1.0, beta_key: 1.0, main_key: 1.0}

        class _FakeTask:
            def __init__(self, *, profile="", home=""):
                self._hermes_agent_profile = profile
                self._hermes_agent_hermes_home = home

            def done(self):
                return False

        runner._background_tasks = {
            _FakeTask(profile="alpha-test", home=str(alpha_home)),
            _FakeTask(profile="beta-test", home=str(beta_home)),
            _FakeTask(),
        }

        event = MessageEvent(text="/agents", message_type=MessageType.TEXT, source=beta_source)
        response = await runner._handle_agents_command(event)

    assert "sess-beta" in response
    assert "proc-beta" in response
    assert "**Gateway async jobs:** 1" in response
    assert "sess-alpha" not in response
    assert "proc-alpha" not in response
    assert "sess-main" not in response


@pytest.mark.asyncio
async def test_personality_command_is_disabled_for_routed_profile_topics(tmp_path):
    from gateway import run as gateway_run

    gateway_home = tmp_path / "gateway"
    profile_home = gateway_home / "profiles" / "alpha-test"
    profile_home.mkdir(parents=True)
    gateway_home.mkdir(exist_ok=True)
    gateway_config = gateway_home / "config.yaml"
    gateway_config.write_text('agent:\n  system_prompt: "Gateway prompt"\n', encoding="utf-8")
    (profile_home / "config.yaml").write_text(
        "agent:\n"
        "  personalities:\n"
        "    analyst: Routed analyst prompt\n",
        encoding="utf-8",
    )
    config = GatewayConfig()

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        gateway_run._hermes_home = gateway_home
    source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))
    event = MessageEvent(text="/personality analyst", message_type=MessageType.TEXT, source=source)

    with hermes_home_context(profile_home):
        response = await runner._handle_personality_command(event)

    assert "disabled" in response.lower()
    assert "Gateway prompt" in gateway_config.read_text(encoding="utf-8")
    assert "Routed analyst prompt" not in gateway_config.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_personality_command_still_works_for_non_routed_gateway_sessions(tmp_path):
    from gateway import run as gateway_run

    gateway_home = tmp_path / "gateway"
    gateway_home.mkdir()
    gateway_config = gateway_home / "config.yaml"
    gateway_config.write_text(
        "agent:\n"
        "  personalities:\n"
        "    analyst: Gateway analyst prompt\n",
        encoding="utf-8",
    )
    config = GatewayConfig()

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
        gateway_run._hermes_home = gateway_home
        source = _source(agent_profile=None, agent_hermes_home=None)
        event = MessageEvent(text="/personality analyst", message_type=MessageType.TEXT, source=source)
        response = await runner._handle_personality_command(event)

    assert "set to" in response.lower()
    assert "Gateway analyst prompt" in gateway_config.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_routed_profile_memory_store_uses_profile_memories_dir(monkeypatch, tmp_path):
    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_home = profiles_root / "alpha-test"
    profile_home.mkdir(parents=True)
    _write_profile_config(profile_home, prompt="Profile prompt", model="profile-model", toolsets=["web"])
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    with hermes_home_context(gateway_home):
        runner = _make_runner(config)
    source = _source(agent_profile="alpha-test", agent_hermes_home=str(profile_home))

    captured = await _run_captured_agent(monkeypatch, runner, source, profile_home)

    assert captured["memory_dir"] == str(profile_home / "memories")


@pytest.mark.asyncio
async def test_concurrent_routed_profiles_do_not_cross_contaminate_prompt_env_or_toolsets(monkeypatch, tmp_path):
    from gateway import run as gateway_run

    gateway_home = tmp_path / "gateway"
    profiles_root = gateway_home / "profiles"
    profile_a = profiles_root / "alpha-test"
    profile_b = profiles_root / "beta-test"
    profile_a.mkdir(parents=True)
    profile_b.mkdir(parents=True)
    _write_profile_config(profile_a, prompt="Prompt A", model="model-a", toolsets=["web"])
    _write_profile_config(profile_b, prompt="Prompt B", model="model-b", toolsets=["todo"])
    (profile_a / ".env").write_text("OPENROUTER_API_KEY=sk-test-profile-a\n", encoding="utf-8")
    (profile_b / ".env").write_text("OPENROUTER_API_KEY=sk-test-profile-b\n", encoding="utf-8")
    config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                extra={"topic_profiles_safe_root": str(profiles_root)}
            )
        }
    )

    _install_fake_agent(monkeypatch)
    monkeypatch.delenv("HERMES_EPHEMERAL_SYSTEM_PROMPT", raising=False)
    monkeypatch.delenv("HERMES_PREFILL_MESSAGES_FILE", raising=False)
    monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", _provider_runtime)
    monkeypatch.setattr(gateway_run, "load_dotenv", lambda *args, **kwargs: None)
    with hermes_home_context(gateway_home):
        runner = _make_runner(config)

    source_a = _source(
        thread_id="101",
        agent_profile="alpha-test",
        agent_hermes_home=str(profile_a),
    )
    source_b = _source(
        thread_id="202",
        agent_profile="beta-test",
        agent_hermes_home=str(profile_b),
    )

    async def run_one(source, home):
        with hermes_home_context(home):
            return await runner._run_agent(
                message="hi",
                context_prompt="",
                history=[],
                source=source,
                session_id=f"session-{source.agent_profile}",
                session_key=build_session_key(source),
            )

    result_a, result_b = await asyncio.gather(
        run_one(source_a, profile_a),
        run_one(source_b, profile_b),
    )

    assert result_a["final_response"] == "ok"
    assert result_b["final_response"] == "ok"
    by_key = {item["gateway_session_key"]: item for item in _CapturingAgent.inits}
    captured_a = by_key["agent:alpha-test:telegram:group:-1001:101"]
    captured_b = by_key["agent:beta-test:telegram:group:-1001:202"]
    assert captured_a["model"] == "model-a"
    assert captured_b["model"] == "model-b"
    assert captured_a["ephemeral_system_prompt"] == "Prompt A"
    assert captured_b["ephemeral_system_prompt"] == "Prompt B"
    assert captured_a["api_key"] == "sk-test-profile-a"
    assert captured_b["api_key"] == "sk-test-profile-b"
    assert "web" in set(captured_a["enabled_toolsets"])
    assert "todo" in set(captured_b["enabled_toolsets"])


@pytest.mark.asyncio
async def test_two_routed_topics_concurrent_background_processes_route_correctly(tmp_path):
    from gateway.run import GatewayRunner
    from tools.process_registry import ProcessSession, process_registry

    gateway_home = tmp_path / "gateway"
    profile_a = tmp_path / "profiles" / "alpha-test"
    profile_b = tmp_path / "profiles" / "beta-test"
    for home in (gateway_home, profile_a, profile_b):
        home.mkdir(parents=True)

    delivered = []

    class _Adapter:
        async def handle_message(self, event):
            delivered.append(event)

    with hermes_home_context(gateway_home):
        runner = object.__new__(GatewayRunner)
        runner.config = GatewayConfig()
        runner.session_store = SessionStore(gateway_home / "sessions", runner.config)
        runner.adapters = {Platform.TELEGRAM: _Adapter()}
        runner._load_background_notifications_mode = lambda: "result"

    process_registry._running.clear()
    process_registry._finished.clear()
    process_registry._completion_consumed.clear()

    session_a = ProcessSession(
        id="proc_alpha",
        command="printf alpha",
        task_id="default",
        session_key="agent:alpha-test:telegram:group:-1001:101",
        agent_profile="alpha-test",
        agent_hermes_home=str(profile_a),
        pid=111,
        started_at=1.0,
        exited=True,
        exit_code=0,
        output_buffer="alpha done",
        notify_on_complete=True,
    )
    session_b = ProcessSession(
        id="proc_beta",
        command="printf beta",
        task_id="default",
        session_key="agent:beta-test:telegram:group:-1001:202",
        agent_profile="beta-test",
        agent_hermes_home=str(profile_b),
        pid=222,
        started_at=1.0,
        exited=True,
        exit_code=0,
        output_buffer="beta done",
        notify_on_complete=True,
    )
    process_registry._running[session_a.id] = session_a
    process_registry._running[session_b.id] = session_b

    watcher_a = {
        "session_id": session_a.id,
        "check_interval": 0,
        "session_key": session_a.session_key,
        "platform": "telegram",
        "chat_id": "-1001",
        "thread_id": "101",
        "user_id": "42",
        "user_name": "alice",
        "agent_profile": "alpha-test",
        "agent_hermes_home": str(profile_a),
        "notify_on_complete": True,
    }
    watcher_b = {
        "session_id": session_b.id,
        "check_interval": 0,
        "session_key": session_b.session_key,
        "platform": "telegram",
        "chat_id": "-1001",
        "thread_id": "202",
        "user_id": "43",
        "user_name": "bob",
        "agent_profile": "beta-test",
        "agent_hermes_home": str(profile_b),
        "notify_on_complete": True,
    }

    await asyncio.gather(
        runner._run_process_watcher(watcher_a),
        runner._run_process_watcher(watcher_b),
    )

    by_profile = {event.source.agent_profile: event for event in delivered}
    assert set(by_profile) == {"alpha-test", "beta-test"}
    assert by_profile["alpha-test"].source.thread_id == "101"
    assert by_profile["alpha-test"].source.agent_hermes_home == str(profile_a)
    assert "alpha done" in by_profile["alpha-test"].text
    assert by_profile["beta-test"].source.thread_id == "202"
    assert by_profile["beta-test"].source.agent_hermes_home == str(profile_b)
    assert "beta done" in by_profile["beta-test"].text


@pytest.mark.asyncio
async def test_routed_process_text_notifications_use_profile_thread_metadata(tmp_path):
    from gateway.run import GatewayRunner
    from tools.process_registry import ProcessSession, process_registry

    gateway_home = tmp_path / "gateway"
    profile_home = tmp_path / "profiles" / "alpha-test"
    for home in (gateway_home, profile_home):
        home.mkdir(parents=True)

    sent = []

    class _Adapter:
        async def send(self, chat_id, content, metadata=None):
            sent.append((chat_id, content, metadata))

    with hermes_home_context(gateway_home):
        runner = object.__new__(GatewayRunner)
        runner.config = GatewayConfig()
        runner.session_store = SessionStore(gateway_home / "sessions", runner.config)
        runner.adapters = {Platform.TELEGRAM: _Adapter()}
        runner._load_background_notifications_mode = lambda: "result"

    process_registry._running.clear()
    process_registry._finished.clear()
    process_registry._completion_consumed.clear()

    session = ProcessSession(
        id="proc_alpha",
        command="printf alpha",
        task_id="default",
        session_key="agent:alpha-test:telegram:group:-1001:101",
        agent_profile="alpha-test",
        agent_hermes_home=str(profile_home),
        pid=111,
        started_at=1.0,
        exited=True,
        exit_code=0,
        output_buffer="alpha done",
        notify_on_complete=False,
    )
    process_registry._running[session.id] = session

    watcher = {
        "session_id": session.id,
        "check_interval": 0,
        "session_key": session.session_key,
        "platform": "telegram",
        "chat_id": "-1001",
        "thread_id": "101",
        "user_id": "42",
        "user_name": "alice",
        "agent_profile": "alpha-test",
        "agent_hermes_home": str(profile_home),
        "notify_on_complete": False,
    }

    await runner._run_process_watcher(watcher)

    assert len(sent) == 1
    assert sent[0][0] == "-1001"
    assert sent[0][2]["thread_id"] == "101"
    assert sent[0][2]["disable_thread_fallback"] is True
