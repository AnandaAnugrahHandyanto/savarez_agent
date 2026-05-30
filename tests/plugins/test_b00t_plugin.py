"""Tests for the b00t guard interposition plugin."""

from __future__ import annotations

import importlib
import io
import subprocess
import sys


def _fresh_b00t():
    sys.modules.pop("plugins.b00t", None)
    return importlib.import_module("plugins.b00t")


def test_warn_jsonl_rewrites_terminal_command(monkeypatch):
    mod = _fresh_b00t()

    def _fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout='{"action":"warn","message":"use uv","redirect":"uv pip install pytest"}\n',
            stderr="",
        )

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)
    result = mod._b00t_pre_tool_hook("terminal", {"command": "pip install pytest"})
    assert result == {"action": "rewrite", "args": {"command": "uv pip install pytest"}}


def test_block_jsonl_returns_block_directive(monkeypatch):
    mod = _fresh_b00t()

    def _fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout='{"action":"block","message":"blocked by policy"}\n',
            stderr="",
        )

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)
    result = mod._b00t_pre_tool_hook("terminal", {"command": "rm -rf /"})
    assert result == {"action": "block", "message": "blocked by policy"}


def test_non_json_output_falls_back_to_emoji_scrape_and_forwards_stderr(monkeypatch):
    mod = _fresh_b00t()
    captured_stderr = io.StringIO()
    monkeypatch.setattr(mod.sys, "stderr", captured_stderr)

    def _fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="not-json\n",
            stderr="🦨 guard warning\nsuggested: uv pip install pytest\n",
        )

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)
    result = mod._b00t_pre_tool_hook("terminal", {"command": "pip install pytest"})
    assert result == {"action": "rewrite", "args": {"command": "uv pip install pytest"}}
    assert "🦨 guard warning" in captured_stderr.getvalue()
