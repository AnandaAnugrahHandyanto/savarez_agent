from gateway.platforms.slack import _wrap_markdown_tables_for_slack


class TestWrapMarkdownTablesForSlack:
    def test_basic_table_rewritten_as_aligned_code_block(self):
        text = (
            "Numbers:\n\n"
            "| Keyword | Installs | Revenue |\n"
            "|---------|---------:|--------:|\n"
            "| clara ai | 56 | $153.97 |\n"
            "| voicemail app | 37 | $69.99 |\n"
            "\nDone."
        )

        out = _wrap_markdown_tables_for_slack(text)

        assert out.startswith("Numbers:")
        assert "```" in out
        assert "Keyword        Installs  Revenue" in out
        assert "clara ai       56        $153.97" in out
        assert "voicemail app  37        $69.99" in out
        assert out.endswith("Done.")

    def test_bare_pipe_table_rewritten(self):
        text = "A | B\n--- | ---\n1 | 2"
        out = _wrap_markdown_tables_for_slack(text)
        assert out == "```\nA  B\n-  -\n1  2\n```"

    def test_plain_pipes_not_rewritten(self):
        text = "Use a | pipe in shell commands."
        assert _wrap_markdown_tables_for_slack(text) == text

    def test_existing_code_block_left_alone(self):
        text = "```\n| A | B |\n|---|---|\n| 1 | 2 |\n```"
        assert _wrap_markdown_tables_for_slack(text) == text
