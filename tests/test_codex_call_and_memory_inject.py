"""Tests for codex_call throttle + stats, auto-memory inject, and sandbox
wire-in dispatch translation.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest import mock

import pytest

from agent_bus.middleware import MiddlewareChain, MiddlewareContext, clear_registry


@pytest.fixture(autouse=True)
def reset_registry():
    clear_registry()
    yield
    clear_registry()


# ==================================================================
#  codex_call.invoke_codex — throttle + stats
# ==================================================================
class TestCodexThrottle:
    def test_throttle_blocks_rapid_second_call(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_CODEX_STATS_PATH", str(tmp_path / "codex.jsonl"))
        monkeypatch.setenv("HERMES_CODEX_THROTTLE_MIN_INTERVAL_SEC", "30")
        from agent_bus import codex_call
        codex_call._reset_for_test()

        class FakeProc:
            returncode = 0
            stdout = "hello"
            stderr = ""

        with mock.patch("shutil.which", return_value="/fake/codex"):
            with mock.patch("subprocess.run", return_value=FakeProc()):
                r1 = codex_call.invoke_codex("p", attempt="test1")
                r2 = codex_call.invoke_codex("p", attempt="test2")
        assert r1.ok
        assert not r2.ok
        assert r2.error and r2.error.startswith("throttled")

    def test_disabled_env_blocks_everything(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_CODEX_STATS_PATH", str(tmp_path / "codex.jsonl"))
        monkeypatch.setenv("HERMES_CODEX_DISABLE", "1")
        from agent_bus import codex_call
        codex_call._reset_for_test()
        with mock.patch("shutil.which", return_value="/fake/codex"):
            r = codex_call.invoke_codex("p", attempt="x")
        assert not r.ok
        assert "disabled" in (r.error or "")

    def test_not_found_when_cli_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_CODEX_STATS_PATH", str(tmp_path / "codex.jsonl"))
        from agent_bus import codex_call
        codex_call._reset_for_test()
        with mock.patch("shutil.which", return_value=None):
            r = codex_call.invoke_codex("p", attempt="x")
        assert not r.ok and r.error == "not_found"

    def test_stats_persistence_and_summary(self, tmp_path, monkeypatch):
        stats_path = tmp_path / "codex.jsonl"
        monkeypatch.setenv("HERMES_CODEX_STATS_PATH", str(stats_path))
        monkeypatch.setenv("HERMES_CODEX_THROTTLE_MIN_INTERVAL_SEC", "0")  # allow rapid
        monkeypatch.setenv("HERMES_CODEX_BURST_COUNT", "100")
        from agent_bus import codex_call
        codex_call._reset_for_test()

        class FakeProc:
            returncode = 0
            stdout = "x"
            stderr = ""

        with mock.patch("shutil.which", return_value="/fake/codex"):
            with mock.patch("subprocess.run", return_value=FakeProc()):
                codex_call.invoke_codex("p", attempt="a")
                codex_call.invoke_codex("p", attempt="b")
                codex_call.invoke_codex("p", attempt="a")
        assert stats_path.exists()
        lines = [ln for ln in stats_path.read_text().splitlines() if ln.strip()]
        assert len(lines) == 3
        rows = [json.loads(line) for line in lines]
        assert all(r["ok"] for r in rows)

        summary = codex_call.summarize_stats(window_hours=24)
        assert summary["total"] == 3
        assert summary["ok"] == 3
        assert summary["by_attempt"]["a"] == 2
        assert summary["by_attempt"]["b"] == 1

    def test_summary_handles_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_CODEX_STATS_PATH", str(tmp_path / "nope.jsonl"))
        from agent_bus import codex_call
        s = codex_call.summarize_stats()
        assert s["exists"] is False
        assert s["total"] == 0


# ==================================================================
#  MemoryExtractionMiddleware.before_model — fact injection
# ==================================================================
class TestMemoryInjection:
    def _reg(self):
        from agent_bus.middlewares import register_defaults
        register_defaults()

    def test_injects_when_facts_exist(self, tmp_path, monkeypatch):
        store = tmp_path / "memory-auto.json"
        store.write_text(json.dumps({
            "facts": [
                {"id": "f1", "content": "Brian prefers black coffee",
                 "category": "preference", "confidence": 0.9,
                 "created_at": time.time(), "source": "codex:gpt-5"},
                {"id": "f2", "content": "Brian is a night owl",
                 "category": "preference", "confidence": 0.85,
                 "created_at": time.time(), "source": "codex:gpt-5"},
            ],
            "updated_at": time.time(),
        }))
        monkeypatch.setenv("HERMES_AUTO_MEMORY_PATH", str(store))
        self._reg()
        chain = MiddlewareChain.build()
        ctx = MiddlewareContext(
            thread_id="t-inject",
            messages=[{"role": "user", "content": "hi"}],
        )
        ctx = chain.run("before_model", ctx)
        # system injection at position 0
        assert ctx.messages[0].get("_auto_memory_inject") is True
        assert "<memory>" in ctx.messages[0]["content"]
        assert "Brian prefers black coffee" in ctx.messages[0]["content"]
        assert ctx.messages[0]["_fact_count"] == 2

    def test_idempotent_re_injection(self, tmp_path, monkeypatch):
        store = tmp_path / "memory-auto.json"
        store.write_text(json.dumps({
            "facts": [{"id": "f1", "content": "X", "category": "context",
                       "confidence": 0.9, "created_at": time.time(),
                       "source": "test"}],
            "updated_at": time.time(),
        }))
        monkeypatch.setenv("HERMES_AUTO_MEMORY_PATH", str(store))
        self._reg()
        chain = MiddlewareChain.build()
        ctx = MiddlewareContext(
            thread_id="t-idem",
            messages=[{"role": "user", "content": "hi"}],
        )
        chain.run("before_model", ctx)
        chain.run("before_model", ctx)  # re-run
        inj_count = sum(1 for m in ctx.messages if m.get("_auto_memory_inject"))
        assert inj_count == 1  # idempotent

    def test_placed_after_existing_system_message(self, tmp_path, monkeypatch):
        store = tmp_path / "memory-auto.json"
        store.write_text(json.dumps({
            "facts": [{"id": "f1", "content": "X", "category": "context",
                       "confidence": 0.9, "created_at": time.time(),
                       "source": "test"}],
        }))
        monkeypatch.setenv("HERMES_AUTO_MEMORY_PATH", str(store))
        self._reg()
        chain = MiddlewareChain.build()
        ctx = MiddlewareContext(
            thread_id="t",
            messages=[
                {"role": "system", "content": "orig system"},
                {"role": "user", "content": "hi"},
            ],
        )
        ctx = chain.run("before_model", ctx)
        # Order: orig system → inject → user
        assert ctx.messages[0]["content"] == "orig system"
        assert ctx.messages[1].get("_auto_memory_inject") is True
        assert ctx.messages[2]["role"] == "user"

    def test_inject_disabled(self, tmp_path, monkeypatch):
        store = tmp_path / "memory-auto.json"
        store.write_text(json.dumps({"facts": [{"id": "f1", "content": "X",
            "category": "context", "confidence": 0.9,
            "created_at": time.time(), "source": "t"}]}))
        monkeypatch.setenv("HERMES_AUTO_MEMORY_PATH", str(store))
        monkeypatch.setenv("HERMES_AUTO_MEMORY_INJECT", "off")
        self._reg()
        chain = MiddlewareChain.build()
        ctx = MiddlewareContext(thread_id="t", messages=[{"role": "user", "content": "hi"}])
        ctx = chain.run("before_model", ctx)
        assert not any(m.get("_auto_memory_inject") for m in ctx.messages)

    def test_low_confidence_filtered_out(self, tmp_path, monkeypatch):
        store = tmp_path / "memory-auto.json"
        store.write_text(json.dumps({"facts": [
            {"id": "f1", "content": "High", "category": "context",
             "confidence": 0.9, "created_at": time.time(), "source": "t"},
            {"id": "f2", "content": "Low", "category": "context",
             "confidence": 0.2, "created_at": time.time(), "source": "t"},
        ]}))
        monkeypatch.setenv("HERMES_AUTO_MEMORY_PATH", str(store))
        monkeypatch.setenv("HERMES_AUTO_MEMORY_INJECT_MIN_CONFIDENCE", "0.6")
        self._reg()
        chain = MiddlewareChain.build()
        ctx = MiddlewareContext(thread_id="t", messages=[{"role": "user", "content": "hi"}])
        ctx = chain.run("before_model", ctx)
        content = ctx.messages[0]["content"]
        assert "High" in content
        assert "Low" not in content


# ==================================================================
#  tools.registry.dispatch — sandbox wire path translation
# ==================================================================
class TestSandboxWire:
    def test_wire_off_leaves_args(self, monkeypatch):
        monkeypatch.setenv("HERMES_SANDBOX_WIRE", "off")
        from tools.registry import _maybe_translate_sandbox_paths
        args = {"path": "/mnt/user-data/workspace/x.md"}
        out = _maybe_translate_sandbox_paths(args, "t1")
        assert out == args  # unchanged

    def test_wire_on_translates_virtual(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_SANDBOX_WIRE", "on")
        monkeypatch.setenv("HERMES_THREADS_ROOT", str(tmp_path / "threads"))
        from tools.registry import _maybe_translate_sandbox_paths
        args = {"path": "/mnt/user-data/workspace/x.md"}
        out = _maybe_translate_sandbox_paths(args, "t1")
        assert out["path"] != args["path"]
        assert "threads/t1/user-data/workspace/x.md" in out["path"]

    def test_non_virtual_path_preserved(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_SANDBOX_WIRE", "on")
        monkeypatch.setenv("HERMES_THREADS_ROOT", str(tmp_path / "threads"))
        from tools.registry import _maybe_translate_sandbox_paths
        args = {"path": "/etc/hosts"}
        out = _maybe_translate_sandbox_paths(args, "t1")
        assert out["path"] == "/etc/hosts"

    def test_multiple_path_keys(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_SANDBOX_WIRE", "on")
        monkeypatch.setenv("HERMES_THREADS_ROOT", str(tmp_path / "threads"))
        from tools.registry import _maybe_translate_sandbox_paths
        args = {
            "source": "/mnt/user-data/workspace/a.md",
            "destination": "/mnt/user-data/outputs/a.md",
            "unrelated": "not a path",
        }
        out = _maybe_translate_sandbox_paths(args, "t1")
        assert "threads/t1/user-data/workspace/a.md" in out["source"]
        assert "threads/t1/user-data/outputs/a.md" in out["destination"]
        assert out["unrelated"] == "not a path"

    def test_no_task_id_no_translation(self, monkeypatch):
        monkeypatch.setenv("HERMES_SANDBOX_WIRE", "on")
        from tools.registry import _maybe_translate_sandbox_paths
        args = {"path": "/mnt/user-data/workspace/x.md"}
        out = _maybe_translate_sandbox_paths(args, None)
        assert out == args  # no task_id → no translation
