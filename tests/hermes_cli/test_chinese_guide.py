"""Tests for the built-in Chinese guide."""

from __future__ import annotations

import argparse
import os
from unittest.mock import patch


def test_render_topic_config_mentions_profile_aware_paths():
    from hermes_cli.chinese_guide import render_topic

    with patch.dict(os.environ, {"HERMES_HOME": "/tmp/hermes-zh-home"}):
        text = render_topic("config")

    assert "config.yaml" in text
    assert ".env" in text
    assert "/tmp/hermes-zh-home" in text


def test_render_topic_accepts_aliases():
    from hermes_cli.chinese_guide import render_topic

    text = render_topic("install")
    assert "中文快速上手" in text
    assert "hermes setup" in text


def test_render_topic_unknown_topic_shows_available_topics():
    from hermes_cli.chinese_guide import render_topic

    text = render_topic("bogus-topic")
    assert "未找到这个主题" in text
    assert "quickstart" in text
    assert "hermes zh topics" in text


def test_render_topic_markdown_mode_uses_heading():
    from hermes_cli.chinese_guide import render_topic

    text = render_topic("gateway", markdown=True)
    assert text.startswith("## ")
    assert "Gateway" in text


def test_cmd_zh_prints_requested_topic(capsys):
    from hermes_cli.main import cmd_zh

    args = argparse.Namespace(topic="commands", list_topics=False, markdown=False)
    cmd_zh(args)

    output = capsys.readouterr().out
    assert "常用命令中文说明" in output
    assert "/zh [topic]" in output
