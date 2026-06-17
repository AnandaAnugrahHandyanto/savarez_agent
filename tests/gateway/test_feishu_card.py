"""Tests for gateway.platforms.feishu_card."""
from __future__ import annotations
import pytest
from gateway.platforms.feishu_card import format_token_count

class TestFormatTokenCount:
    @pytest.mark.parametrize(
        "value, expected",
        [
            (0, "0"),
            (48, "48"),
            (999, "999"),
            (1000, "1.0k"),
            (1100, "1.1k"),
            (11100, "11.1k"),
            (999999, "1000.0k"),
            (1000000, "1.0M"),
            (3400000, "3.4M"),
        ],
    )
    def test_format_token_count(self, value, expected):
        assert format_token_count(value) == expected

    def test_format_token_count_negative_returns_zero(self):
        assert format_token_count(-5) == "0"


from gateway.platforms.feishu_card import get_tool_display

class TestGetToolDisplay:
    @pytest.mark.parametrize(
        "tool_name, expected",
        [
            ("Read", "Read · 阅读文件"),
            ("read_file", "Read · 阅读文件"),
            ("Bash", "Bash · 执行命令"),
            ("terminal", "Bash · 执行命令"),
            ("Edit", "Edit · 改代码"),
            ("edit_file", "Edit · 改代码"),
            ("Write", "Write · 写文件"),
            ("write_file", "Write · 写文件"),
            ("MultiEdit", "MultiEdit · 批量改代码"),
            ("Grep", "Grep · 搜索代码"),
            ("Glob", "Glob · 查找文件"),
            ("WebFetch", "WebFetch · 抓取网页"),
            ("web_fetch", "WebFetch · 抓取网页"),
            ("WebSearch", "WebSearch · 搜索网络"),
            ("web_search", "WebSearch · 搜索网络"),
            ("Task", "Agent · 派出子任务"),
            ("Agent", "Agent · 派出子任务"),
            ("TodoWrite", "TodoWrite · 更新任务"),
            ("unknown_tool_xyz", "unknown_tool_xyz"),
        ],
    )
    def test_get_tool_display(self, tool_name, expected):
        assert get_tool_display(tool_name) == expected


from gateway.platforms.feishu_card import parse_markdown_tables

class TestParseMarkdownTables:
    def test_no_table_returns_single_text(self):
        result = parse_markdown_tables("just some text")
        assert result == [("text", "just some text")]

    def test_simple_table(self):
        md = "before\n\n| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n\nafter"
        result = parse_markdown_tables(md)
        assert len(result) == 3
        assert result[0] == ("text", "before")
        assert result[1][0] == "table"
        table = result[1][1]
        assert table["columns"] == [
            {"name": "col_0", "display_name": "A"},
            {"name": "col_1", "display_name": "B"},
        ]
        assert table["rows"] == [
            {"col_0": "1", "col_1": "2"},
            {"col_0": "3", "col_1": "4"},
        ]
        assert result[2] == ("text", "after")

    def test_empty_input(self):
        result = parse_markdown_tables("")
        assert result == [("text", "")]

    def test_table_only(self):
        md = "| X |\n|---|\n| 1 |"
        result = parse_markdown_tables(md)
        assert len(result) == 1
        assert result[0][0] == "table"

    def test_multiple_tables(self):
        md = "| A |\n|---|\n| 1 |\n\nmiddle\n\n| B |\n|---|\n| 2 |"
        result = parse_markdown_tables(md)
        assert len(result) == 3
        assert result[0][0] == "table"
        assert result[1] == ("text", "middle")
        assert result[2][0] == "table"


import json
from gateway.platforms.feishu_card import build_card_json

class TestBuildCardJson:
    def test_simple_text(self):
        card = build_card_json(content="hello world")
        assert card["config"]["wide_screen_mode"] is True
        assert card["config"]["update_multi"] is True
        assert len(card["elements"]) == 1
        assert card["elements"][0]["tag"] == "markdown"
        assert card["elements"][0]["content"] == "hello world"
        assert "header" not in card

    def test_with_footer(self):
        card = build_card_json(
            content="response text",
            footer_line="📊 ↑48 | ↓11.1k | $0.01 | ⏳12s | 🧠gpt-5.5",
            status_text="✅ 回复完毕",
        )
        elements = card["elements"]
        assert elements[0]["tag"] == "markdown"
        assert elements[0]["content"] == "response text"
        assert elements[1]["tag"] == "hr"
        assert elements[2]["tag"] == "note"
        assert "📊" in elements[2]["elements"][0]["content"]
        assert elements[3]["tag"] == "note"
        assert "✅" in elements[3]["elements"][0]["content"]

    def test_with_tool_status(self):
        card = build_card_json(
            content="some text",
            tool_status="⏳ Bash · 执行命令...",
        )
        elements = card["elements"]
        assert len(elements) == 1
        assert "⏳ Bash · 执行命令..." in elements[0]["content"]

    def test_with_table_content(self):
        md = "intro\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\nend"
        card = build_card_json(content=md)
        tags = [e["tag"] for e in card["elements"]]
        assert "table" in tags
        assert tags.count("markdown") == 2

    def test_ack_card(self):
        card = build_card_json(content="⏳ 正在思考...")
        assert card["elements"][0]["content"] == "⏳ 正在思考..."

    def test_error_card(self):
        card = build_card_json(
            content="❌ 处理出错，请重试",
            status_text="❌ 出错",
        )
        assert card["elements"][-1]["tag"] == "note"


import subprocess
from unittest.mock import patch, MagicMock
from gateway.platforms.feishu_card import detect_git_context

class TestDetectGitContext:
    def test_in_git_repo(self, tmp_path):
        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(
            ["git", "checkout", "-b", "feat/test"],
            cwd=str(tmp_path), capture_output=True,
        )
        result = detect_git_context(str(tmp_path))
        assert result == f"{tmp_path.name}:feat/test"

    def test_not_a_git_repo(self, tmp_path):
        result = detect_git_context(str(tmp_path))
        assert result == ""

    def test_empty_cwd(self):
        result = detect_git_context("")
        assert result == ""

    @patch("gateway.platforms.feishu_card.subprocess.run")
    def test_timeout_returns_empty(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=1)
        result = detect_git_context("/some/path")
        assert result == ""


from gateway.platforms.feishu_card import build_card_footer_line

class TestBuildCardFooterLine:
    def test_full_footer(self):
        result = build_card_footer_line(
            input_tokens=48,
            output_tokens=11100,
            cache_tokens=3400000,
            cost_usd=2.9475,
            git_context="nine:feat/xxx",
            elapsed_seconds=34.2,
            model="openai/gpt-5.5",
        )
        assert result == "📊 ↑48 | ↓11.1k | cache:3.4M | $2.9475 | @nine:feat/xxx | ⏳34s | 🧠gpt-5.5"

    def test_no_cache(self):
        result = build_card_footer_line(
            input_tokens=1200,
            output_tokens=5600,
            cache_tokens=0,
            cost_usd=0.015,
            git_context="nine:main",
            elapsed_seconds=12.0,
            model="anthropic/claude-opus-4",
        )
        assert result == "📊 ↑1.2k | ↓5.6k | $0.0150 | @nine:main | ⏳12s | 🧠claude-opus-4"

    def test_no_git(self):
        result = build_card_footer_line(
            input_tokens=100,
            output_tokens=200,
            cache_tokens=0,
            cost_usd=0.001,
            git_context="",
            elapsed_seconds=5.0,
            model="gpt-5.5",
        )
        assert result == "📊 ↑100 | ↓200 | $0.0010 | ⏳5s | 🧠gpt-5.5"
