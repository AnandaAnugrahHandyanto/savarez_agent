"""Tests for Feishu Interactive Card table rendering from markdown tables."""

import json
from typing import Any, Dict, List


def _import_module():
    """Import the feishu module (lark_oapi not required for these tests)."""
    from gateway.platforms.feishu import (
        _build_card_table_elements,
        _build_table_card_payload,
        _detect_column_alignments,
        _find_table_end,
        _is_table_start,
        _parse_markdown_table_segments,
        _split_pipe_cells,
    )
    return {
        "build_card_table_elements": _build_card_table_elements,
        "build_table_card_payload": _build_table_card_payload,
        "detect_column_alignments": _detect_column_alignments,
        "find_table_end": _find_table_end,
        "is_table_start": _is_table_start,
        "parse_markdown_table_segments": _parse_markdown_table_segments,
        "split_pipe_cells": _split_pipe_cells,
    }


class TestSplitPipeCells:
    """Test _split_pipe_cells for parsing markdown table rows."""

    def test_basic_row(self):
        mod = _import_module()
        row = "| Alice | 30 | Beijing |"
        cells = mod["split_pipe_cells"](row)
        assert cells == ["Alice", "30", "Beijing"], f"Got {cells}"

    def test_row_without_outer_pipes(self):
        mod = _import_module()
        row = "Alice | 30 | Beijing"
        cells = mod["split_pipe_cells"](row)
        assert cells == ["Alice", "30", "Beijing"], f"Got {cells}"

    def test_empty_cells(self):
        mod = _import_module()
        row = "|  |  |"
        cells = mod["split_pipe_cells"](row)
        assert cells == ["", ""], f"Got {cells}"

    def test_escaped_pipe(self):
        mod = _import_module()
        row = r"| Cell with \| pipe | Normal |"
        cells = mod["split_pipe_cells"](row)
        assert cells == [r"Cell with \| pipe", "Normal"], f"Got {cells}"

    def test_whitespace_trimming(self):
        mod = _import_module()
        row = "|  spaced  |  values  |"
        cells = mod["split_pipe_cells"](row)
        assert cells == ["spaced", "values"], f"Got {cells}"

    def test_single_cell(self):
        mod = _import_module()
        row = "| only one |"
        cells = mod["split_pipe_cells"](row)
        assert cells == ["only one"], f"Got {cells}"


class TestDetectColumnAlignments:
    """Test alignment detection from separator rows."""

    def test_left_align(self):
        mod = _import_module()
        result = mod["detect_column_alignments"]("| :--- | :--- |")
        assert result == ["left", "left"], f"Got {result}"

    def test_right_align(self):
        mod = _import_module()
        result = mod["detect_column_alignments"]("| ---: | ---: |")
        assert result == ["right", "right"], f"Got {result}"

    def test_center_align(self):
        mod = _import_module()
        result = mod["detect_column_alignments"]("| :---: | :---: |")
        assert result == ["center", "center"], f"Got {result}"

    def test_mixed_align(self):
        mod = _import_module()
        result = mod["detect_column_alignments"]("|:---|:---:|---:|")
        assert result == ["left", "center", "right"], f"Got {result}"

    def test_default_align(self):
        mod = _import_module()
        result = mod["detect_column_alignments"]("|---|---|---|")
        assert result == ["left", "left", "left"], f"Got {result}"


class TestIsTableStart:
    """Test table start detection."""

    def test_valid_table_start(self):
        mod = _import_module()
        lines = [
            "| Name | Age |",
            "|------|-----|",
        ]
        assert mod["is_table_start"](lines, 0) is True

    def test_not_enough_lines(self):
        mod = _import_module()
        lines = ["| Name |"]
        assert mod["is_table_start"](lines, 0) is False

    def test_no_separator(self):
        mod = _import_module()
        lines = [
            "| Name | Age |",
            "Some text here",
        ]
        assert mod["is_table_start"](lines, 0) is False

    def test_no_pipe(self):
        mod = _import_module()
        lines = [
            "Name Age",
            "----- ----",
        ]
        assert mod["is_table_start"](lines, 0) is False


class TestFindTableEnd:
    """Test finding end of a markdown table."""

    def test_single_row_table(self):
        mod = _import_module()
        lines = [
            "| A | B |",
            "|---|---|",
            "| 1 | 2 |",
        ]
        assert mod["find_table_end"](lines, 0) == 2

    def test_multiple_rows(self):
        mod = _import_module()
        lines = [
            "| A | B |",
            "|---|---|",
            "| 1 | 2 |",
            "| 3 | 4 |",
            "Some text after",
        ]
        assert mod["find_table_end"](lines, 0) == 3

    def test_empty_table_stops_early(self):
        mod = _import_module()
        lines = [
            "| A | B |",
            "|---|---|",
            "",
            "after",
        ]
        assert mod["find_table_end"](lines, 0) == 1


class TestBuildCardTableElements:
    """Test building card table elements from markdown table lines."""

    def test_basic_table(self):
        mod = _import_module()
        lines = [
            "| Name | Age | City |",
            "|------|------|------|",
            "| Alice | 30 | Beijing |",
            "| Bob | 25 | Shanghai |",
        ]
        result = mod["build_card_table_elements"](lines)
        assert result["tag"] == "table"
        assert len(result["columns"]) == 3
        assert len(result["rows"]) == 2
        assert result["columns"][0]["display_name"] == "Name"
        assert result["rows"][0]["col_0"] == "Alice"
        assert result["rows"][1]["col_1"] == "25"

    def test_less_than_two_lines_falls_back(self):
        mod = _import_module()
        lines = ["| Only header |"]
        result = mod["build_card_table_elements"](lines)
        assert result["tag"] == "markdown"

    def test_no_data_rows_falls_back(self):
        mod = _import_module()
        lines = [
            "| A | B |",
            "|---|---|",
        ]
        result = mod["build_card_table_elements"](lines)
        assert result["tag"] == "markdown"

    def test_honors_alignment(self):
        mod = _import_module()
        lines = [
            "| Left | Right |",
            "|:-----|------:|",
            "| Text |   123 |",
        ]
        result = mod["build_card_table_elements"](lines)
        assert result["columns"][0]["horizontal_align"] == "left"
        assert result["columns"][1]["horizontal_align"] == "right"

    def test_page_size_respected(self):
        mod = _import_module()
        lines = ["| A |", "|---|"] + [f"| {i} |" for i in range(15)]
        result = mod["build_card_table_elements"](lines)
        assert result["page_size"] == 10  # max 10

    def test_column_width_auto(self):
        mod = _import_module()
        lines = [
            "| A | B |",
            "|---|---|",
            "| 1 | 2 |",
        ]
        result = mod["build_card_table_elements"](lines)
        for col in result["columns"]:
            assert col["width"] == "auto"


class TestParseMarkdownTableSegments:
    """Test splitting content into mixed segments."""

    def test_pure_table(self):
        mod = _import_module()
        content = "| A | B |\n|---|---|\n| 1 | 2 |"
        segments = mod["parse_markdown_table_segments"](content)
        assert len(segments) == 1
        assert segments[0]["tag"] == "table"

    def test_text_before_table(self):
        mod = _import_module()
        content = "Some text\n\n| A | B |\n|---|---|\n| 1 | 2 |"
        segments = mod["parse_markdown_table_segments"](content)
        assert len(segments) == 2
        assert segments[0]["tag"] == "markdown"
        assert "Some text" in segments[0]["content"]
        assert segments[1]["tag"] == "table"

    def test_text_after_table(self):
        mod = _import_module()
        content = "| A | B |\n|---|---|\n| 1 | 2 |\n\nEnd text"
        segments = mod["parse_markdown_table_segments"](content)
        assert len(segments) == 2
        assert segments[0]["tag"] == "table"
        assert segments[1]["tag"] == "markdown"
        assert "End text" in segments[1]["content"]

    def test_multiple_tables(self):
        mod = _import_module()
        content = (
            "First:\n\n| X |\n|---|\n| 1 |\n\n"
            "Second:\n\n| Y |\n|---|\n| 2 |"
        )
        segments = mod["parse_markdown_table_segments"](content)
        assert len(segments) == 4
        assert segments[0]["tag"] == "markdown"
        assert segments[1]["tag"] == "table"
        assert segments[2]["tag"] == "markdown"
        assert segments[3]["tag"] == "table"

    def test_pure_text(self):
        mod = _import_module()
        content = "Just some plain text without any tables."
        segments = mod["parse_markdown_table_segments"](content)
        assert len(segments) == 1
        assert segments[0]["tag"] == "markdown"
        assert segments[0]["content"] == content

    def test_empty_content(self):
        mod = _import_module()
        segments = mod["parse_markdown_table_segments"]("")
        assert len(segments) == 1
        assert segments[0]["tag"] == "markdown"

    def test_text_with_pipes_but_no_table(self):
        mod = _import_module()
        content = "Some | text with | pipes but not | a table"
        segments = mod["parse_markdown_table_segments"](content)
        assert len(segments) == 1
        assert segments[0]["tag"] == "markdown"


class TestBuildTableCardPayload:
    """Test building the full card JSON payload."""

    def test_returns_valid_json(self):
        mod = _import_module()
        content = "| A | B |\n|---|---|\n| 1 | 2 |"
        payload = mod["build_table_card_payload"](content)
        card = json.loads(payload)
        assert "config" in card
        assert "elements" in card
        assert card["config"]["wide_screen_mode"] is True

    def test_card_contains_table_element(self):
        mod = _import_module()
        content = "| Header | Value |\n|--------|------:|\n| Alpha | 100 |\n| Beta | 200 |"
        payload = mod["build_table_card_payload"](content)
        card = json.loads(payload)
        assert len(card["elements"]) == 1
        elem = card["elements"][0]
        assert elem["tag"] == "table"
        assert len(elem["columns"]) == 2
        assert len(elem["rows"]) == 2
        assert elem["columns"][0]["display_name"] == "Header"
        assert elem["columns"][1]["display_name"] == "Value"

    def test_mixed_content_card(self):
        mod = _import_module()
        content = "Summary:\n\n| Item | Count |\n|------|------:|\n| A | 5 |\n| B | 3 |\n\nDone."
        payload = mod["build_table_card_payload"](content)
        card = json.loads(payload)
        assert len(card["elements"]) == 3
        assert card["elements"][0]["tag"] == "markdown"
        assert card["elements"][1]["tag"] == "table"
        assert card["elements"][2]["tag"] == "markdown"

    def test_payload_utf8_safe(self):
        mod = _import_module()
        content = "| 姓名 | 城市 |\n|------|------|\n| 张三 | 北京 |\n| 李四 | 上海 |"
        payload = mod["build_table_card_payload"](content)
        card = json.loads(payload)
        assert len(card["elements"]) == 1
        assert card["elements"][0]["rows"][0]["col_0"] == "张三"
        assert card["elements"][0]["rows"][0]["col_1"] == "北京"
