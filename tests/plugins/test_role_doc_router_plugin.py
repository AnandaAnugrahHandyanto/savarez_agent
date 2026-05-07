"""Tests for the bundled role-doc-router plugin."""

import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _isolate_env(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    yield hermes_home


def _load_plugin_init():
    repo_root = Path(__file__).resolve().parents[2]
    plugin_dir = repo_root / "plugins" / "role-doc-router"
    spec = importlib.util.spec_from_file_location(
        "hermes_plugins.role_doc_router",
        plugin_dir / "__init__.py",
        submodule_search_locations=[str(plugin_dir)],
    )
    if "hermes_plugins" not in sys.modules:
        ns = types.ModuleType("hermes_plugins")
        ns.__path__ = []
        sys.modules["hermes_plugins"] = ns
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "hermes_plugins.role_doc_router"
    mod.__path__ = [str(plugin_dir)]
    sys.modules["hermes_plugins.role_doc_router"] = mod
    spec.loader.exec_module(mod)
    return mod


class _FakeCtx:
    def __init__(self, dispatch_result: str = ""):
        self.dispatch_result = dispatch_result
        self.hooks = {}
        self.last_tool_call = None
        self._manager = MagicMock()
        self._manager._cli_ref = None

    def register_hook(self, hook_name, callback):
        self.hooks[hook_name] = callback

    def dispatch_tool(self, tool_name, args, **kwargs):
        self.last_tool_call = (tool_name, args, kwargs)
        return self.dispatch_result


class TestRoleDocLoading:
    def test_load_role_doc_index_reads_index_file(self, tmp_path, monkeypatch):
        mod = _load_plugin_init()
        docs_dir = tmp_path / "role-docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "index.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "count": 1,
                    "roles": [
                        {
                            "path": "backend/python.md",
                            "title": "Python Backend",
                            "summary": "Use concise Python engineering guidance.",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("ROLE_DOC_ROUTER_DIR", str(docs_dir))

        docs = mod._load_role_doc_index(docs_dir)

        assert len(docs) == 1
        assert docs[0].path == "backend/python.md"
        assert docs[0].title == "Python Backend"
        assert docs[0].summary == "Use concise Python engineering guidance."


class TestRoleDocHook:
    def test_pre_llm_call_injects_selected_role_doc(self, tmp_path, monkeypatch):
        mod = _load_plugin_init()
        docs_dir = tmp_path / "role-docs"
        (docs_dir / "backend").mkdir(parents=True)
        (docs_dir / "index.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "count": 2,
                    "roles": [
                        {
                            "path": "backend/python.md",
                            "title": "Python Backend",
                            "summary": "适合 FastAPI、后端接口、数据模型和边界设计。",
                        },
                        {
                            "path": "backend/unused.md",
                            "title": "Unused",
                            "summary": "这个角色与当前请求无关。",
                        },
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (docs_dir / "backend" / "python.md").write_text(
            "# Python Backend\n\nFULL ROLE CONTENT: Prefer FastAPI, pydantic models, and clear API boundaries.",
            encoding="utf-8",
        )
        (docs_dir / "backend" / "unused.md").write_text(
            "# Unused\n\nThis content should not be loaded into router context.",
            encoding="utf-8",
        )
        monkeypatch.setenv("ROLE_DOC_ROUTER_DIR", str(docs_dir))

        router_output = json.dumps(
            {
                "results": [
                    {
                        "summary": json.dumps(
                            {
                                "selected": ["backend/python.md"],
                                "reason": "当前问题是 Python 后端接口开发",
                            },
                            ensure_ascii=False,
                        )
                    }
                ]
            },
            ensure_ascii=False,
        )
        ctx = _FakeCtx(dispatch_result=router_output)
        mod.register(ctx)

        agent = MagicMock()
        agent._delegate_depth = 0

        result = ctx.hooks["pre_llm_call"](
            session_id="s1",
            user_message="帮我写一个 FastAPI 的用户接口",
            conversation_history=[{"role": "user", "content": "这是一个后端服务"}],
            agent=agent,
        )

        assert result is not None
        assert "Project-selected role documents for this turn." in result["context"]
        assert "[role-doc: backend/python.md]" in result["context"]
        assert "FULL ROLE CONTENT" in result["context"]
        assert ctx.last_tool_call[0] == "delegate_task"
        assert ctx.last_tool_call[1]["role"] == "leaf"
        assert "候选角色索引" in ctx.last_tool_call[1]["context"]
        assert "适合 FastAPI、后端接口、数据模型和边界设计。" in ctx.last_tool_call[1]["context"]
        assert "FULL ROLE CONTENT" not in ctx.last_tool_call[1]["context"]

    def test_pre_llm_call_skips_delegated_child_agents(self, tmp_path, monkeypatch):
        mod = _load_plugin_init()
        docs_dir = tmp_path / "role-docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "index.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "count": 1,
                    "roles": [
                        {
                            "path": "general.md",
                            "title": "General",
                            "summary": "General role.",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (docs_dir / "general.md").write_text("# General\n\nGeneral role.", encoding="utf-8")
        monkeypatch.setenv("ROLE_DOC_ROUTER_DIR", str(docs_dir))

        ctx = _FakeCtx(dispatch_result='{"results": [{"summary": "{}"}]}')
        mod.register(ctx)

        agent = MagicMock()
        agent._delegate_depth = 1

        result = ctx.hooks["pre_llm_call"](
            session_id="s1",
            user_message="你好",
            conversation_history=[],
            agent=agent,
        )

        assert result is None
        assert ctx.last_tool_call is None

    def test_non_selected_missing_file_does_not_break_routing(self, tmp_path, monkeypatch):
        mod = _load_plugin_init()
        docs_dir = tmp_path / "role-docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "index.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "count": 2,
                    "roles": [
                        {
                            "path": "picked.md",
                            "title": "Picked",
                            "summary": "应该被选中的角色。",
                        },
                        {
                            "path": "missing.md",
                            "title": "Missing",
                            "summary": "文件已缺失，但不应影响未选中的路由。",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (docs_dir / "picked.md").write_text("# Picked\n\nChosen content.", encoding="utf-8")
        monkeypatch.setenv("ROLE_DOC_ROUTER_DIR", str(docs_dir))

        router_output = json.dumps(
            {
                "results": [
                    {
                        "summary": json.dumps(
                            {"selected": ["picked.md"], "reason": "命中当前问题"},
                            ensure_ascii=False,
                        )
                    }
                ]
            },
            ensure_ascii=False,
        )
        ctx = _FakeCtx(dispatch_result=router_output)
        mod.register(ctx)

        agent = MagicMock()
        agent._delegate_depth = 0

        result = ctx.hooks["pre_llm_call"](
            session_id="s1",
            user_message="请选择命中的角色",
            conversation_history=[],
            agent=agent,
        )

        assert result is not None
        assert "Chosen content." in result["context"]


class TestRoleDocHistorySnippet:
    def test_history_defaults_to_recent_user_messages_only(self, monkeypatch):
        mod = _load_plugin_init()

        history = [
            {"role": "user", "content": "第一轮用户问题"},
            {"role": "assistant", "content": "第一轮模型长回复，不该默认带上"},
            {"role": "user", "content": "第二轮用户补充"},
            {"role": "assistant", "content": "第二轮模型回复，也不该默认带上"},
            {"role": "user", "content": "第三轮用户问题"},
            {"role": "user", "content": "第四轮用户问题"},
            {"role": "user", "content": "第五轮用户问题"},
        ]

        snippet = mod._recent_history_snippet(history)

        assert "assistant" not in snippet
        assert "第一轮用户问题" not in snippet
        assert "第二轮用户补充" in snippet
        assert "第五轮用户问题" in snippet

    def test_history_can_optionally_include_assistant_messages(self, monkeypatch):
        mod = _load_plugin_init()
        monkeypatch.setenv("ROLE_DOC_ROUTER_INCLUDE_ASSISTANT_HISTORY", "true")
        monkeypatch.setenv("ROLE_DOC_ROUTER_HISTORY_MESSAGES", "2")

        history = [
            {"role": "user", "content": "用户问题"},
            {"role": "assistant", "content": "模型回复"},
        ]

        snippet = mod._recent_history_snippet(history)

        assert "- user: 用户问题" in snippet
        assert "- assistant: 模型回复" in snippet