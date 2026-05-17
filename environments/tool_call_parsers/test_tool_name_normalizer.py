"""
Tests for the heuristic tool-name normalizer.

Run with:
    ./venv/bin/python -m pytest environments/tool_call_parsers/test_tool_name_normalizer.py -v
or:
    ./venv/bin/python -m unittest environments.tool_call_parsers.test_tool_name_normalizer
"""
import unittest
from environments.tool_call_parsers.tool_name_normalizer import normalize_tool_name


class TestNormalizeToolName(unittest.TestCase):

    # ------------------------------------------------------------------ #
    # Werner's three real-world examples                                   #
    # ------------------------------------------------------------------ #

    def test_google_search_with_web_search_available(self):
        """'google/search' -> 'web_search' when web_search is available."""
        result = normalize_tool_name("google/search", ["web_search", "terminal"])
        self.assertEqual(result, "web_search")

    def test_google_search_with_only_terminal_and_process(self):
        """'google/search' with only [terminal, process] — no clear match.

        Strategy 2 won't fire (neither 'terminal' nor 'process' is in 'google/search').
        Strategy 4 fires on token 'search' → candidates ['web_search', 'web', 'search'],
        none of which are in ['terminal', 'process'] → None.
        """
        result = normalize_tool_name("google/search", ["terminal", "process"])
        self.assertIsNone(result)

    def test_google_tool_shell_index_0_to_terminal(self):
        """'google:tool:shell:index:0' with [terminal, process] -> 'terminal' via shell alias."""
        result = normalize_tool_name("google:tool:shell:index:0", ["terminal", "process"])
        self.assertEqual(result, "terminal")

    def test_tool_execute_terminal_to_terminal(self):
        """'tool:execute_terminal' with [terminal, process] -> 'terminal' via substring."""
        result = normalize_tool_name("tool:execute_terminal", ["terminal", "process"])
        self.assertEqual(result, "terminal")

    # ------------------------------------------------------------------ #
    # Exact match                                                          #
    # ------------------------------------------------------------------ #

    def test_exact_match(self):
        """'terminal' with ['terminal'] -> 'terminal' via exact match."""
        result = normalize_tool_name("terminal", ["terminal"])
        self.assertEqual(result, "terminal")

    def test_exact_match_case_insensitive(self):
        """'Terminal' with ['terminal'] -> 'terminal' via case-insensitive exact match."""
        result = normalize_tool_name("Terminal", ["terminal"])
        self.assertEqual(result, "terminal")

    # ------------------------------------------------------------------ #
    # Edge cases                                                           #
    # ------------------------------------------------------------------ #

    def test_empty_hallucinated_returns_none(self):
        """Empty hallucinated name -> None."""
        result = normalize_tool_name("", ["terminal", "process"])
        self.assertIsNone(result)

    def test_none_hallucinated_returns_none(self):
        """None hallucinated name -> None."""
        result = normalize_tool_name(None, ["terminal", "process"])
        self.assertIsNone(result)

    def test_empty_available_returns_none(self):
        """Empty available list -> None."""
        result = normalize_tool_name("terminal", [])
        self.assertIsNone(result)

    def test_no_match_returns_none(self):
        """Completely unrelated name -> None."""
        result = normalize_tool_name("xyz_completely_unknown_xyz", ["terminal", "process"])
        self.assertIsNone(result)

    # ------------------------------------------------------------------ #
    # Substring strategies                                                  #
    # ------------------------------------------------------------------ #

    def test_available_name_substring_of_hallucinated(self):
        """'run_terminal_now' should match 'terminal' via Strategy 2."""
        result = normalize_tool_name("run_terminal_now", ["terminal", "process"])
        self.assertEqual(result, "terminal")

    def test_alias_token_bash_maps_to_terminal(self):
        """Token 'bash' in hallucinated name -> 'terminal'."""
        result = normalize_tool_name("google:bash:run", ["terminal", "process"])
        self.assertEqual(result, "terminal")

    def test_alias_token_exec_maps_to_terminal(self):
        """Token 'exec' in hallucinated name -> 'terminal' when terminal available."""
        result = normalize_tool_name("google:exec:command", ["terminal", "process"])
        self.assertEqual(result, "terminal")

    def test_alias_token_search_maps_to_web_search(self):
        """Token 'search' in hallucinated name -> 'web_search' when available."""
        result = normalize_tool_name("do_search_now", ["web_search", "terminal"])
        self.assertEqual(result, "web_search")

    def test_longest_available_matched_first(self):
        """Longest available name matched first in Strategy 2.

        'execute_terminal' (hypothetical) would beat 'terminal' but since
        only 'terminal' is available it still maps correctly.
        """
        result = normalize_tool_name(
            "run:execute_terminal:v2",
            ["terminal", "process"],
        )
        self.assertEqual(result, "terminal")

    def test_short_hallucinated_name_skips_strategy3(self):
        """Names shorter than 4 chars skip Strategy 3 (weak-signal guard)."""
        # 'run' is only 3 chars; even if it were substring of an available tool,
        # we skip. Here no match should occur at all.
        result = normalize_tool_name("run", ["terminal", "process"])
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
