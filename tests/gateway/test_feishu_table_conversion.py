"""Tests for Feishu markdown table auto-conversion.

Feishu's ``md`` renderer has a known bug: markdown tables render as blank,
sometimes swallowing trailing content. The ``_convert_tables_to_text``
function detects markdown table blocks and converts them to plain-text
lists before they reach the renderer.
"""

import json
import unittest


class TestConvertTablesToText(unittest.TestCase):
    """Unit tests for the ``_convert_tables_to_text`` helper."""

    def _call(self, text: str) -> str:
        from gateway.platforms.feishu import _convert_tables_to_text
        return _convert_tables_to_text(text)

    # -- simple table --------------------------------------------------------

    def test_simple_two_column_table(self):
        table = (
            "| 项目 | 值 |\n"
            "|------|-----|\n"
            "| 模型 | mimo |\n"
            "| 状态 | 正常 |"
        )
        result = self._call(table)
        self.assertIn("项目：模型", result)
        self.assertIn("值：mimo", result)
        self.assertIn("项目：状态", result)
        self.assertIn("值：正常", result)
        # Original pipe-delimited form must be gone
        self.assertNotIn("| 模型 |", result)
        self.assertNotIn("|------|", result)

    # -- three column table --------------------------------------------------

    def test_three_column_table(self):
        table = (
            "| 名称 | 值 | 说明 |\n"
            "|------|-----|------|\n"
            "| Alpha | 1 | first |\n"
            "| Beta | 2 | second |"
        )
        result = self._call(table)
        self.assertIn("Alpha", result)
        self.assertIn("1", result)
        self.assertIn("first", result)
        self.assertIn("Beta", result)
        self.assertNotIn("| Alpha |", result)

    # -- table surrounded by prose -------------------------------------------

    def test_table_with_surrounding_text(self):
        content = (
            "前面的文字。\n"
            "\n"
            "| A | B |\n"
            "|---|---|\n"
            "| x | y |\n"
            "\n"
            "后面的文字。"
        )
        result = self._call(content)
        self.assertIn("前面的文字。", result)
        self.assertIn("后面的文字。", result)
        self.assertIn("x", result)
        self.assertIn("y", result)
        self.assertNotIn("| A |", result)

    # -- no table → unchanged ------------------------------------------------

    def test_no_table_unchanged(self):
        content = "这是一段普通文字，**没有表格**。"
        self.assertEqual(self._call(content), content)

    # -- pipe inside code block must NOT be treated as table ------------------

    def test_pipe_in_code_block_ignored(self):
        content = (
            "示例：\n"
            "```\n"
            "| not | a | table |\n"
            "|-----|---|-------|\n"
            "| foo | bar | baz |\n"
            "```\n"
            "结束。"
        )
        result = self._call(content)
        # Code block content must be preserved verbatim
        self.assertIn("| not | a | table |", result)
        self.assertIn("| foo | bar | baz |", result)

    # -- empty cells ---------------------------------------------------------

    def test_empty_cells(self):
        table = (
            "| 名 | 值 |\n"
            "|---|----|\n"
            "| A | |\n"
            "|  | B |"
        )
        result = self._call(table)
        self.assertIn("A", result)
        self.assertIn("B", result)

    # -- single row table ----------------------------------------------------

    def test_single_row_table(self):
        table = (
            "| Key | Value |\n"
            "|-----|-------|\n"
            "| X | 42 |"
        )
        result = self._call(table)
        self.assertIn("Key：X", result)
        self.assertIn("Value：42", result)


class TestBuildMarkdownPostRowsWithTables(unittest.TestCase):
    """Integration test: tables go through _build_markdown_post_rows and
    arrive as list-formatted md rows, not raw table syntax."""

    def _call(self, content: str):
        from gateway.platforms.feishu import _build_markdown_post_rows
        return _build_markdown_post_rows(content)

    def test_table_converted_in_post_rows(self):
        content = (
            "标题\n"
            "\n"
            "| 项目 | 值 |\n"
            "|------|-----|\n"
            "| 模型 | mimo-v2.5-pro |\n"
            "| 状态 | 正常 |\n"
            "\n"
            "后续文字。"
        )
        rows = self._call(content)
        # Flatten all text from all rows
        all_text = "\n".join(
            element["text"]
            for row in rows
            for element in row
        )
        # Table content should be present as list items
        self.assertIn("mimo-v2.5-pro", all_text)
        self.assertIn("正常", all_text)
        self.assertIn("后续文字。", all_text)
        # Raw table syntax should be gone
        self.assertNotIn("| 项目 |", all_text)
        self.assertNotIn("|------|", all_text)

    def test_no_table_content_passes_through(self):
        content = "没有表格的内容，**粗体** 和 `代码`。"
        rows = self._call(content)
        all_text = "\n".join(
            element["text"]
            for row in rows
            for element in row
        )
        self.assertEqual(all_text, content)


if __name__ == "__main__":
    unittest.main()
