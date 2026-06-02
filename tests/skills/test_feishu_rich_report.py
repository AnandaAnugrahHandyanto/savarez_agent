"""Tests for feishu-rich-report helper (no live lark-cli calls)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "devops"
    / "feishu-rich-report"
    / "scripts"
    / "feishu_rich_send.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("feishu_rich_send", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["feishu_rich_send"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_build_lark_args_send():
    mod = _load()
    args = mod.build_lark_args(
        chat_id="oc_test",
        markdown="## Hi\n| a | b |\n|---|---|\n| 1 | 2 |",
    )
    assert args[:4] == ["lark-cli", "im", "--as", "bot"]
    assert "+messages-send" in args
    assert "--chat-id" in args
    assert "oc_test" in args
    assert "--markdown" in args


def test_build_lark_args_reply():
    mod = _load()
    args = mod.build_lark_args(
        chat_id="oc_test",
        markdown="## reply",
        thread_id="om_thread",
    )
    assert "+messages-reply" in args
    assert "--message-id" in args
    assert "om_thread" in args
    assert "--reply-in-thread" in args


def test_send_markdown_dry_run():
    mod = _load()
    out = mod.send_markdown("oc_x", "## t", dry_run=True)
    assert out["dry_run"] is True
    assert out["chars"] == 4
    assert out["side_delivery"]["status"] == "dry_run"
    assert out["completion_ack_required"] is False


def test_wrap_side_delivery_result_done():
    mod = _load()
    out = mod.wrap_side_delivery_result(
        {"data": {"message_id": "om_abc123"}},
        chat_id="oc_test",
        task_label="验收",
        doc_link="https://example.feishu.cn/docx/abc",
    )
    assert out["side_delivery"]["status"] == "done"
    assert out["side_delivery"]["message_id"] == "om_abc123"
    assert out["completion_ack_required"] is True
    assert "✅ 已完成：验收" in out["suggested_chat_reply"]
    assert "https://example.feishu.cn/docx/abc" in out["suggested_chat_reply"]
    assert "om_abc123" in out["suggested_chat_reply"]


def test_format_completion_ack_minimal():
    mod = _load()
    text = mod.format_completion_ack(task_label="联调")
    assert text == "✅ 已完成：联调"
