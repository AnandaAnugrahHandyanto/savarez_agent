"""Regression tests for built-in foreground CLI control.

These cover the local phone→desktop CLI routing rules that prevent cross-talk
between multiple visible Hermes CLI windows.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace


def _load_module():
    return importlib.import_module("gateway.foreground_cli_control")


def _event(text: str):
    source = SimpleNamespace(
        platform=SimpleNamespace(value="feishu"),
        chat_id="chat-a",
        thread_id="main",
        user_id="david",
    )
    return SimpleNamespace(text=text, source=source)


def test_bound_direct_mode_rejects_explicit_send_to_other_cli(monkeypatch, tmp_path):
    mod = _load_module()
    monkeypatch.setattr(mod, "BIND_PATH", tmp_path / "bindings.json")

    tasks = [
        {"num": 1, "alias": "任务一", "bridge_key": "cli-one", "pid": 111, "status": "idle"},
        {"num": 2, "alias": "任务二", "bridge_key": "cli-two", "pid": 222, "status": "idle"},
    ]
    monkeypatch.setattr(mod, "_tasks", lambda: tasks)

    sent = []

    def fake_send(t, payload, event):
        sent.append((t["bridge_key"], payload))
        return {"action": "reply", "text": "sent"}

    monkeypatch.setattr(mod, "_send_to_task", fake_send)

    bind_result = mod.maybe_handle_message(event=_event("绑定1"))
    assert bind_result["action"] == "reply"
    assert "cli" in bind_result["text"].lower() or "编号1" in bind_result["text"]

    result = mod.maybe_handle_message(event=_event("发送给2：这条不该串到第二个窗口"))

    assert result["action"] == "reply"
    assert "已绑定" in result["text"]
    assert "解绑" in result["text"]
    assert sent == []


def test_bound_direct_mode_allows_explicit_send_to_same_cli(monkeypatch, tmp_path):
    mod = _load_module()
    monkeypatch.setattr(mod, "BIND_PATH", tmp_path / "bindings.json")

    tasks = [
        {"num": 1, "alias": "任务一", "bridge_key": "cli-one", "pid": 111, "status": "idle"},
        {"num": 2, "alias": "任务二", "bridge_key": "cli-two", "pid": 222, "status": "idle"},
    ]
    monkeypatch.setattr(mod, "_tasks", lambda: tasks)

    sent = []

    def fake_send(t, payload, event):
        sent.append((t["bridge_key"], payload))
        return {"action": "reply", "text": "sent"}

    monkeypatch.setattr(mod, "_send_to_task", fake_send)

    mod.maybe_handle_message(event=_event("绑定1"))
    result = mod.maybe_handle_message(event=_event("发送给1：继续这个任务"))

    assert result == {"action": "reply", "text": "sent"}
    assert sent == [("cli-one", "继续这个任务")]
