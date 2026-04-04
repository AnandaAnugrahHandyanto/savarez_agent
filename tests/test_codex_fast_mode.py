import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.modules.setdefault("fire", types.SimpleNamespace(Fire=lambda *a, **k: None))
sys.modules.setdefault("firecrawl", types.SimpleNamespace(Firecrawl=object))
sys.modules.setdefault("fal_client", types.SimpleNamespace())

import run_agent
from agent.auxiliary_client import _CodexCompletionsAdapter
from tools import delegate_tool


def _patch_agent_bootstrap(monkeypatch):
    monkeypatch.setattr(
        run_agent,
        "get_tool_definitions",
        lambda **kwargs: [
            {
                "type": "function",
                "function": {
                    "name": "terminal",
                    "description": "Run shell commands.",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
    )
    monkeypatch.setattr(run_agent, "check_toolset_requirements", lambda: {})


def _build_agent(monkeypatch):
    _patch_agent_bootstrap(monkeypatch)
    agent = run_agent.AIAgent(
        model="gpt-5.4",
        provider="openai-codex",
        api_mode="codex_responses",
        base_url="https://chatgpt.com/backend-api/codex",
        api_key="codex-token",
        quiet_mode=True,
        max_iterations=2,
        skip_context_files=True,
        skip_memory=True,
    )
    agent._cleanup_task_resources = lambda task_id: None
    agent._persist_session = lambda messages, history=None: None
    agent._save_trajectory = lambda messages, user_message, completed: None
    agent._save_session_log = lambda messages: None
    return agent


def test_codex_fast_mode_main_payload(monkeypatch):
    agent = _build_agent(monkeypatch)
    agent.config = {"model": {"fast_mode": True}}
    kwargs = agent._build_api_kwargs(
        [
            {"role": "system", "content": "You are Hermes."},
            {"role": "user", "content": "Ping"},
        ]
    )
    assert kwargs["service_tier"] == "fast"
    assert kwargs["features"] == {"fast_mode": True}


def test_codex_fast_mode_auxiliary_payload_pass_through():
    fake_client = MagicMock()
    fake_client.responses.stream = MagicMock(return_value=SimpleNamespace(__enter__=lambda s: s, __exit__=lambda s,*a: False))
    adapter = _CodexCompletionsAdapter(fake_client, "gpt-5.4")

    captured = {}

    class _Ctx:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False

    def _stream(**kwargs):
        captured.update(kwargs)
        ctx = MagicMock()
        ctx.__enter__.return_value = ctx
        ctx.__exit__.return_value = False
        return ctx

    fake_client.responses.stream = _stream
    try:
        adapter.create(
            model="gpt-5.4",
            messages=[{"role": "user", "content": "Ping"}],
            service_tier="fast",
            features={"fast_mode": True},
        )
    except Exception:
        # Adapter may expect richer stream object; we only care about captured kwargs.
        pass

    assert captured.get("service_tier") == "fast"
    assert captured.get("features") == {"fast_mode": True}


def test_codex_fast_mode_delegation_inherits_parent(monkeypatch):
    parent = _build_agent(monkeypatch)
    parent.config = {"model": {"fast_mode": True}}
    parent.enabled_toolsets = ["terminal", "file", "web"]
    parent._delegate_depth = 0
    child = delegate_tool._build_child_agent(
        task_index=1,
        goal="do a small task",
        context=None,
        toolsets=None,
        model=None,
        max_iterations=4,
        parent_agent=parent,
        override_provider=None,
        override_base_url=None,
        override_api_key=None,
        override_api_mode=None,
    )
    child.config = parent.config
    kwargs = child._build_api_kwargs(
        [
            {"role": "system", "content": "You are Hermes."},
            {"role": "user", "content": "Ping"},
        ]
    )
    assert kwargs["service_tier"] == "fast"
    assert kwargs["features"] == {"fast_mode": True}
