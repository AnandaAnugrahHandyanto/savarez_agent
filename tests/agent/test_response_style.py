"""Tests for response style helpers."""

from agent.response_style import build_response_style_guidance, normalize_response_style


class TestNormalizeResponseStyle:
    def test_accepts_valid_values(self):
        assert normalize_response_style("normal") == "normal"
        assert normalize_response_style("brief") == "brief"
        assert normalize_response_style("ultra") == "ultra"

    def test_normalizes_case_and_whitespace(self):
        assert normalize_response_style("  BRIEF ") == "brief"

    def test_defaults_invalid_to_normal(self):
        assert normalize_response_style(None) == "normal"
        assert normalize_response_style("") == "normal"
        assert normalize_response_style("caveman") == "normal"


class TestBuildResponseStyleGuidance:
    def test_brief_includes_brief_policy(self):
        text = build_response_style_guidance("brief", auto_clarity=True)
        assert "brief response style" in text.lower()
        assert "auto-clarity override" in text.lower()
        assert "lead with the direct answer" in text.lower()

    def test_ultra_disables_clarity_block_when_off(self):
        text = build_response_style_guidance("ultra", auto_clarity=False)
        assert "ultra-brief" in text.lower()
        assert "auto-clarity override" not in text.lower()

    def test_status_summary_reports_current_style_and_rules(self):
        text = build_response_style_guidance("ultra", auto_clarity=True)
        assert "bullets over prose" in text.lower()
        assert "skip preambles" in text.lower()
        assert "minimum extra context needed" in text.lower()

    def test_normal_style_has_no_guidance(self):
        assert build_response_style_guidance("normal") == ""
        assert build_response_style_guidance("bogus") == ""

    def test_invalid_style_summary_defaults_to_normal(self):
        assert build_response_style_guidance("caveman") == ""

    def test_describe_style_returns_human_summary(self):
        from agent.response_style import describe_response_style

        summary = describe_response_style("brief")
        assert summary["style"] == "brief"
        assert summary["label"]
        assert summary["prompt_defaults"]
        assert any("direct" in item.lower() for item in summary["rules"])
        assert summary["auto_clarity"] is True

    def test_describe_style_invalid_value_defaults_to_normal(self):
        from agent.response_style import describe_response_style

        summary = describe_response_style("caveman")
        assert summary["style"] == "normal"
        assert any("full detail" in item.lower() for item in summary["rules"])
        assert summary["auto_clarity"] is True

    def test_describe_style_can_disable_auto_clarity(self):
        from agent.response_style import describe_response_style

        summary = describe_response_style("ultra", auto_clarity=False)
        assert summary["style"] == "ultra"
        assert summary["auto_clarity"] is False
        assert "disabled" in summary["auto_clarity_note"].lower()
        assert any("bullets" in item.lower() for item in summary["rules"])

    def test_format_style_status_contains_readable_lines(self):
        from agent.response_style import format_style_status

        lines = format_style_status("brief", auto_clarity=True)
        rendered = "\n".join(lines).lower()
        assert "current response style: brief" in rendered
        assert "auto-clarity: on" in rendered
        assert "available: normal, brief, ultra" in rendered
        assert any(line.startswith("  - ") for line in lines)

    def test_format_style_status_marks_disabled_auto_clarity(self):
        from agent.response_style import format_style_status

        rendered = "\n".join(format_style_status("ultra", auto_clarity=False)).lower()
        assert "current response style: ultra" in rendered
        assert "auto-clarity: off" in rendered
        assert "minimum extra context" not in rendered
        assert "disabled" in rendered

    def test_format_style_status_normal_mentions_default_behavior(self):
        from agent.response_style import format_style_status

        rendered = "\n".join(format_style_status("normal")).lower()
        assert "current response style: normal" in rendered
        assert "full detail when helpful" in rendered
        assert "usage: /style <normal|brief|ultra>" in rendered

    def test_format_style_status_invalid_value_defaults_to_normal(self):
        from agent.response_style import format_style_status

        rendered = "\n".join(format_style_status("caveman")).lower()
        assert "current response style: normal" in rendered
        assert "available: normal, brief, ultra" in rendered

    def test_format_style_status_with_prefix_preserves_indent(self):
        from agent.response_style import format_style_status

        lines = format_style_status("brief", prefix=">> ")
        assert all(line.startswith(">> ") for line in lines)
        assert any("current response style: brief" in line.lower() for line in lines)
        assert any(line.startswith(">>   - ") for line in lines)

    def test_format_style_status_uses_custom_available_list(self):
        from agent.response_style import format_style_status

        rendered = "\n".join(format_style_status("brief", available_styles=("normal", "brief"))).lower()
        assert "available: normal, brief" in rendered
        assert "ultra" not in rendered

    def test_format_style_status_empty_available_list_falls_back_to_valid_styles(self):
        from agent.response_style import format_style_status

        rendered = "\n".join(format_style_status("brief", available_styles=())).lower()
        assert "available: normal, brief, ultra" in rendered

    def test_describe_and_format_share_same_label(self):
        from agent.response_style import describe_response_style, format_style_status

        summary = describe_response_style("ultra")
        rendered = "\n".join(format_style_status("ultra")).lower()
        assert summary["label"].lower() in rendered

    def test_ultra_guidance_pushes_shortest_useful_answer(self):
        text = build_response_style_guidance("ultra", auto_clarity=True)
        lowered = text.lower()
        assert "shortest useful answer" in lowered
        assert "skip preambles" in lowered
        assert "bullets over prose" in lowered

    def test_brief_guidance_keeps_relevant_details_only(self):
        text = build_response_style_guidance("brief", auto_clarity=True)
        lowered = text.lower()
        assert "most relevant details" in lowered
        assert "avoid long preambles" in lowered
        assert "direct answer" in lowered

    def test_normal_status_does_not_require_clarity_override_line(self):
        from agent.response_style import describe_response_style

        summary = describe_response_style("normal")
        assert "auto-clarity override" not in " ".join(summary["rules"]).lower()
