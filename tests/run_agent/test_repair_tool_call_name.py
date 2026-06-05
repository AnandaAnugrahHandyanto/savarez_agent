"""Tests for AIAgent._repair_tool_call — tool-name normalization.

Regression guard for #14784: Claude-style models sometimes emit
class-like tool-call names (``TodoTool_tool``, ``Patch_tool``,
``BrowserClick_tool``, ``PatchTool``). Before the fix they returned
"Unknown tool" even though the target tool was registered under a
snake_case name. The repair routine now normalizes CamelCase,
strips trailing ``_tool`` / ``-tool`` / ``tool`` suffixes (up to
twice to handle double-tacked suffixes like ``TodoTool_tool``), and
falls back to fuzzy match.

BUG-8 regression guard: the namespace-prefix guard (step 6) prevents
a shared ``kb_`` / ``mcp_knowledge_kb_`` prefix from inflating the
SequenceMatcher ratio enough to allow silent read-to-write repairs
(e.g. ``kb_search`` -> ``kb_add``).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest


VALID = {
    "todo",
    "patch",
    "browser_click",
    "browser_navigate",
    "web_search",
    "read_file",
    "write_file",
    "terminal",
}

# Extended VALID set used by TestNamespacePrefixGuard.  Includes
# sibling operations under the same ``kb_`` and ``mcp_knowledge_kb_``
# prefixes so the guard's cross-op blocking and same-op allowance can
# both be exercised.
VALID_NS = VALID | {
    "kb_search",
    "kb_get",
    "kb_add",
    "kb_update",
    "mcp_knowledge_kb_search",
    "mcp_knowledge_kb_get",
    "mcp_knowledge_kb_add",
}


@pytest.fixture
def repair():
    """Return a bound _repair_tool_call built on a minimal shell agent.

    We avoid constructing a real AIAgent (which pulls in credential
    resolution, session DB, etc.) because the repair routine only
    reads self.valid_tool_names. A SimpleNamespace stub is enough to
    bind the unbound function.
    """
    from run_agent import AIAgent
    stub = SimpleNamespace(valid_tool_names=VALID)
    return AIAgent._repair_tool_call.__get__(stub, AIAgent)


class TestExistingBehaviorStillWorks:
    """Pre-existing repairs must keep working (no regressions)."""

    def test_lowercase_already_matches(self, repair):
        assert repair("browser_click") == "browser_click"

    def test_uppercase_simple(self, repair):
        assert repair("TERMINAL") == "terminal"

    def test_dash_to_underscore(self, repair):
        assert repair("web-search") == "web_search"

    def test_space_to_underscore(self, repair):
        assert repair("write file") == "write_file"

    def test_fuzzy_near_miss(self, repair):
        # One-character typo — fuzzy match at 0.7 cutoff
        assert repair("terminall") == "terminal"

    def test_unknown_returns_none(self, repair):
        assert repair("xyz_no_such_tool") is None


class TestClassLikeEmissions:
    """Regression coverage for #14784 — CamelCase + _tool suffix variants."""

    def test_camel_case_no_suffix(self, repair):
        assert repair("BrowserClick") == "browser_click"

    def test_camel_case_with_underscore_tool_suffix(self, repair):
        assert repair("BrowserClick_tool") == "browser_click"

    def test_camel_case_with_Tool_class_suffix(self, repair):
        assert repair("PatchTool") == "patch"

    def test_double_tacked_class_and_snake_suffix(self, repair):
        # Hardest case from the report: TodoTool_tool — strip both
        # '_tool' (trailing) and 'Tool' (CamelCase embedded) to reach 'todo'.
        assert repair("TodoTool_tool") == "todo"

    def test_simple_name_with_tool_suffix(self, repair):
        assert repair("Patch_tool") == "patch"

    def test_simple_name_with_dash_tool_suffix(self, repair):
        assert repair("patch-tool") == "patch"

    def test_camel_case_preserves_multi_word_match(self, repair):
        assert repair("ReadFile_tool") == "read_file"
        assert repair("WriteFileTool") == "write_file"

    def test_mixed_separators_and_suffix(self, repair):
        assert repair("write-file_Tool") == "write_file"


class TestEdgeCases:
    """Edge inputs that must not crash or produce surprising results."""

    def test_empty_string(self, repair):
        assert repair("") is None

    def test_only_tool_suffix(self, repair):
        # '_tool' by itself is not a valid tool name — must not match
        # anything plausible.
        assert repair("_tool") is None

    def test_none_passed_as_name(self, repair):
        # Defensive: real callers always pass str, but guard against
        # a bug upstream that sends None.
        assert repair(None) is None

    def test_very_long_name_does_not_match_by_accident(self, repair):
        # Fuzzy match should not claim a tool for something obviously unrelated.
        assert repair("ThisIsNotRemotelyARealToolName_tool") is None


@pytest.fixture
def repair_ns():
    """Bound _repair_tool_call using VALID_NS — the extended tool set.

    Why: The base ``repair`` fixture uses VALID which lacks ``kb_*`` and
    ``mcp_knowledge_kb_*`` names.  The namespace-prefix guard tests need
    sibling operations under the same prefix to exercise both the
    blocking and the allow paths.
    What: Returns a bound method identical in structure to ``repair`` but
    backed by VALID_NS.
    Test: Instantiate and call with a known-blocked pair; assert None is
    returned to confirm the fixture is wired correctly.
    """
    from run_agent import AIAgent
    stub = SimpleNamespace(valid_tool_names=VALID_NS)
    return AIAgent._repair_tool_call.__get__(stub, AIAgent)


class TestNamespacePrefixGuard:
    """BUG-8 regression: namespace-prefix guard prevents read->write repairs.

    The guard strips the shared leading ``_``-segment prefix from both the
    emitted name and any fuzzy-match candidate, then requires the operation
    suffixes to also score >= 0.7.  This stops ``kb_search`` from silently
    repairing to ``kb_add`` just because the shared ``kb_`` prefix pushes
    the full-name SequenceMatcher ratio above the cutoff.
    """

    def test_kb_search_exact_match_fast_path(self, repair_ns):
        # ``kb_search`` is in VALID_NS — the fast-path (exact lowercased
        # match) returns before the fuzzy guard even runs.  Confirm the
        # guard does not inadvertently block exact-match repairs.
        assert repair_ns("kb_search") == "kb_search"

    def test_kb_search_typo_same_op_allowed(self, repair_ns):
        # ``kb_saerch`` is not in VALID_NS.  The fuzzy match finds
        # ``kb_search``; op suffixes ``saerch`` vs ``search`` score
        # ~0.82 >= 0.7, so the guard allows the repair.
        assert repair_ns("kb_saerch") == "kb_search"

    def test_kb_get_exact_match_fast_path(self, repair_ns):
        # ``kb_get`` is in VALID_NS — direct match, no fuzzy needed.
        # Confirm it does not accidentally map to ``kb_add``.
        assert repair_ns("kb_get") == "kb_get"

    def test_guard_blocks_cross_op_fuzzy_match(self, repair_ns):
        # Construct a name that would score above 0.7 against ``kb_add``
        # purely because of the shared ``kb_`` prefix but whose op suffix
        # diverges from ``add``.  ``kb_aed`` shares prefix ``kb_`` with
        # all kb_* tools; its op suffix ``aed`` vs ``add`` = 2/3 ~0.67
        # which is below 0.7, so the guard must block it.
        # (Without the guard, fuzzy would return ``kb_add``.)
        result = repair_ns("kb_aed")
        assert result is None

    def test_legitimate_typo_same_op_allowed(self, repair_ns):
        # ``kb_searc`` is a one-character truncation of ``kb_search``.
        # Op suffixes: ``searc`` vs ``search`` — SequenceMatcher ~0.91.
        # The guard must allow this repair.
        assert repair_ns("kb_searc") == "kb_search"

    def test_non_namespaced_typo_still_works(self, repair_ns):
        # ``terminall`` has no shared namespace prefix with any candidate.
        # The guard is a no-op when there is no shared prefix (the op
        # suffix falls back to the full name), so the original fuzzy
        # logic should still return ``terminal``.
        assert repair_ns("terminall") == "terminal"

    def test_mcp_namespaced_typo_in_op_suffix_allowed(self, repair_ns):
        # ``mcp_knowledge_kb_serach`` is a typo in the op portion.
        # Shared prefix: ``mcp_knowledge_kb_``; op suffix: ``serach``
        # vs ``search`` — ratio ~0.91 >= 0.7, so the guard allows it.
        assert repair_ns("mcp_knowledge_kb_serach") == "mcp_knowledge_kb_search"

    def test_mcp_namespaced_cross_op_blocked(self, repair_ns):
        # ``mcp_knowledge_kb_aet`` fuzzy-matches ``mcp_knowledge_kb_add``
        # (closest candidate) but op suffix ``aet`` vs ``add`` = 2/3
        # ~0.67 < 0.7 — the guard must block it.
        result = repair_ns("mcp_knowledge_kb_aet")
        assert result is None

    def test_destructive_peer_same_op_allowed_different_ops_blocked(self, repair_ns):
        """Guard allows same-op typos, blocks cross-op repairs to kb_delete.

        Why: With kb_delete present, a typo like ``kb_delet`` (same op,
        one char truncated) must repair to kb_delete.  But a different-op
        typo like ``kb_seatch`` or ``kb_saerch`` must NOT cross-repair to
        kb_delete or kb_add even if the full-name ratio would exceed 0.7.
        What: Uses a VALID set that includes kb_delete alongside the other
        kb_* tools and asserts both the allow and block cases.
        Test: Call with ``kb_delet`` → expect ``kb_delete``; call with
        ``kb_seatch`` → expect ``kb_search`` (not kb_delete/kb_add); call
        with ``kb_saerch`` → expect ``kb_search`` (not kb_delete/kb_add).
        """
        from run_agent import AIAgent

        valid_with_delete = VALID_NS | {"kb_delete"}
        stub = SimpleNamespace(valid_tool_names=valid_with_delete)
        repair_del = AIAgent._repair_tool_call.__get__(stub, AIAgent)

        # Same op, one char truncated → allowed
        assert repair_del("kb_delet") == "kb_delete"

        # Different op: ``kb_seatch`` is a transposition of ``kb_search``.
        # It must repair to ``kb_search``, NOT kb_delete or kb_add.
        result_seatch = repair_del("kb_seatch")
        assert result_seatch == "kb_search", (
            f"Expected kb_search, got {result_seatch!r} — "
            "guard failed to prevent cross-op repair to destructive peer"
        )

        # Different op: ``kb_saerch`` must also repair to ``kb_search``, not elsewhere.
        result_saerch = repair_del("kb_saerch")
        assert result_saerch == "kb_search", (
            f"Expected kb_search, got {result_saerch!r} — "
            "guard failed to prevent cross-op repair to destructive peer"
        )
