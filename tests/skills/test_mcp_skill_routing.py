"""Verify that native-mcp outranks mcporter for generic MCP queries (#10341).

The mcporter skill should only be selected when the user explicitly asks for
the mcporter CLI.  General MCP questions ("list my MCP servers", "what MCP
tools do you have?") must route to native-mcp.
"""
from tools.skills_hub import ClawHubSource, SkillMeta


def _make_meta(name: str, description: str) -> SkillMeta:
    return SkillMeta(
        name=name,
        description=description,
        source="official",
        identifier=f"mcp/{name}",
        trust_level="builtin",
    )


# Read current descriptions from the actual SKILL.md files so the test
# stays in sync with the repo.
def _load_description(skill_path: str) -> str:
    import yaml, pathlib

    text = pathlib.Path(skill_path).read_text()
    # Extract YAML frontmatter between --- markers
    parts = text.split("---", 2)
    if len(parts) >= 3:
        fm = yaml.safe_load(parts[1])
        return fm.get("description", "")
    return ""


_NATIVE_DESC = _load_description("skills/mcp/native-mcp/SKILL.md")
_MCPORTER_DESC = _load_description("skills/mcp/mcporter/SKILL.md")


class TestMcpSkillRouting:
    """native-mcp must outscore mcporter for generic MCP queries."""

    def _scores(self, query: str):
        native = _make_meta("native-mcp", _NATIVE_DESC)
        mcporter = _make_meta("mcporter", _MCPORTER_DESC)
        return (
            ClawHubSource._search_score(query, native),
            ClawHubSource._search_score(query, mcporter),
        )

    def test_list_mcp_servers(self):
        native, mcporter = self._scores("list my configured MCP servers")
        assert native > mcporter, f"native={native} should beat mcporter={mcporter}"

    def test_what_mcp_tools(self):
        native, mcporter = self._scores("what MCP tools do you have")
        assert native > mcporter, f"native={native} should beat mcporter={mcporter}"

    def test_show_mcp_setup(self):
        native, mcporter = self._scores("show my MCP setup")
        assert native > mcporter, f"native={native} should beat mcporter={mcporter}"

    def test_mcporter_explicit(self):
        """When the user explicitly asks for mcporter, mcporter should win."""
        native, mcporter = self._scores("mcporter")
        assert mcporter > native, f"mcporter={mcporter} should beat native={native}"

    def test_mcporter_cli_explicit(self):
        native, mcporter = self._scores("use mcporter to list servers")
        assert mcporter > native, f"mcporter={mcporter} should beat native={native}"
