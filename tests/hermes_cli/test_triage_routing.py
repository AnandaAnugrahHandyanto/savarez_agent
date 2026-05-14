"""Tests for the triage routing engine.

Covers first-match-wins semantics, subset matching, LLM fallback,
malformed-rule validation, and the ``load_routing_rules`` config loader.
No network or DB — pure function tests plus YAML file I/O against a
``tmp_path``.
"""

from __future__ import annotations

import textwrap

import pytest
import yaml

from hermes_cli import triage_routing as tr


# ---------------------------------------------------------------------------
# route() — matching semantics
# ---------------------------------------------------------------------------

class TestRouteMatching:
    """Core matching behavior for ``route()``."""

    def test_first_match_wins(self):
        """Earlier rules must take precedence over later matching ones."""
        rules = [
            {"labels": ["bug"], "assignee": "alice"},
            {"labels": ["bug"], "assignee": "bob"},
        ]
        assert tr.route(["bug"], None, rules) == "alice"

    def test_first_match_wins_with_different_label_sets(self):
        """First rule whose labels are subset of card's labels wins,
        even when a later, more-specific rule also matches."""
        rules = [
            {"labels": ["bug"], "assignee": "first"},
            {"labels": ["bug", "p0"], "assignee": "second"},
        ]
        assert tr.route(["bug", "p0"], None, rules) == "first"

    def test_subset_match_single_label(self):
        """A rule requiring one label matches a card that has that label
        among others."""
        rules = [{"labels": ["security"], "assignee": "sec-team"}]
        assert tr.route(["security", "bug", "p1"], None, rules) == "sec-team"

    def test_subset_match_multiple_required_labels(self):
        """A rule with multiple labels requires ALL of them on the card."""
        rules = [
            {"labels": ["bug", "p0"], "assignee": "oncall"},
        ]
        assert tr.route(["bug", "p0", "frontend"], None, rules) == "oncall"

    def test_no_match_when_rule_label_missing(self):
        """A rule whose labels are NOT a subset of the card's labels
        must not match."""
        rules = [{"labels": ["bug", "p0"], "assignee": "oncall"}]
        # Card has 'bug' but not 'p0' — rule should not fire.
        assert tr.route(["bug", "p1"], None, rules) is None

    def test_empty_rule_labels_matches_any_card(self):
        """A rule with empty label set is vacuously a subset of any
        card's labels — matches everything (acts as a catch-all)."""
        rules = [{"labels": [], "assignee": "catch-all"}]
        assert tr.route(["whatever"], None, rules) == "catch-all"
        assert tr.route([], None, rules) == "catch-all"


# ---------------------------------------------------------------------------
# route() — fallback to LLM suggestion
# ---------------------------------------------------------------------------

class TestRouteFallback:
    """LLM suggestion is used only when no rule matches."""

    def test_fallback_to_llm_when_no_rule_matches(self):
        rules = [{"labels": ["security"], "assignee": "sec-team"}]
        assert tr.route(["bug"], "llm-pick", rules) == "llm-pick"

    def test_fallback_to_llm_when_no_rules_configured(self):
        assert tr.route(["anything"], "model-suggestion", []) == "model-suggestion"

    def test_returns_none_when_no_rule_and_no_suggestion(self):
        """The None/None case — used when the LLM had no preference
        either, and the card should fall through to manual triage."""
        assert tr.route(["bug"], None, []) is None
        assert tr.route(["bug"], None, [{"labels": ["other"], "assignee": "x"}]) is None

    def test_rule_match_overrides_llm_suggestion(self):
        """An explicit user rule must trump the LLM's guess."""
        rules = [{"labels": ["bug"], "assignee": "user-pick"}]
        assert tr.route(["bug"], "llm-pick", rules) == "user-pick"

    def test_empty_labels_falls_through_to_llm(self):
        """A card with no labels matches no rule with required labels
        and should fall back to the LLM suggestion."""
        rules = [{"labels": ["bug"], "assignee": "buggy"}]
        assert tr.route([], "llm-pick", rules) == "llm-pick"


# ---------------------------------------------------------------------------
# route() — validation
# ---------------------------------------------------------------------------

class TestRouteValidation:
    """``route()`` must reject malformed rule lists with a clear error."""

    def test_malformed_rule_not_a_dict_raises(self):
        rules = ["not-a-dict"]
        with pytest.raises(ValueError, match="must be a dict"):
            tr.route(["bug"], None, rules)

    def test_malformed_rule_missing_labels_raises(self):
        rules = [{"assignee": "bob"}]
        with pytest.raises(ValueError, match="missing required key 'labels'"):
            tr.route(["bug"], None, rules)

    def test_malformed_rule_missing_assignee_raises(self):
        rules = [{"labels": ["bug"]}]
        with pytest.raises(ValueError, match="missing required key 'assignee'"):
            tr.route(["bug"], None, rules)

    def test_malformed_rule_labels_not_list_raises(self):
        rules = [{"labels": "bug", "assignee": "bob"}]
        with pytest.raises(ValueError, match="'labels' must be a list"):
            tr.route(["bug"], None, rules)

    def test_malformed_rule_label_element_not_string_raises(self):
        rules = [{"labels": ["bug", 42], "assignee": "bob"}]
        with pytest.raises(ValueError, match="must be a string"):
            tr.route(["bug"], None, rules)

    def test_malformed_rule_assignee_not_string_raises(self):
        rules = [{"labels": ["bug"], "assignee": 123}]
        with pytest.raises(ValueError, match="'assignee' must be a string"):
            tr.route(["bug"], None, rules)

    def test_routing_rules_not_a_list_raises(self):
        with pytest.raises(ValueError, match="routing_rules must be a list"):
            tr.route(["bug"], None, "not-a-list")  # type: ignore[arg-type]

    def test_error_message_names_rule_index(self):
        """The index of the offending rule is in the error message so
        users can find it in config.yaml."""
        rules = [
            {"labels": ["a"], "assignee": "x"},
            {"labels": ["b"], "assignee": "y"},
            "broken",
        ]
        # The first rule matches "a" so we never reach the broken one.
        # Use card labels that miss the first two rules so we walk to
        # the malformed third.
        with pytest.raises(ValueError, match="at index 2"):
            tr.route(["c"], None, rules)


# ---------------------------------------------------------------------------
# load_routing_rules()
# ---------------------------------------------------------------------------

class TestLoadRoutingRules:
    """``load_routing_rules`` reads rules from config.yaml, tolerating
    missing files and missing config keys."""

    def test_missing_config_file_returns_empty(self, tmp_path):
        missing = tmp_path / "does-not-exist.yaml"
        assert tr.load_routing_rules(str(missing)) == []

    def test_missing_triage_section_returns_empty(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("model:\n  default: gpt-4\n")
        assert tr.load_routing_rules(str(cfg)) == []

    def test_missing_routing_rules_key_returns_empty(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(textwrap.dedent("""\
            triage:
              other_setting: foo
        """))
        assert tr.load_routing_rules(str(cfg)) == []

    def test_empty_routing_rules_returns_empty(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(textwrap.dedent("""\
            triage:
              routing_rules: []
        """))
        assert tr.load_routing_rules(str(cfg)) == []

    def test_loads_rules_in_order(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        payload = {
            "triage": {
                "routing_rules": [
                    {"labels": ["security"], "assignee": "sec-team"},
                    {"labels": ["bug", "p0"], "assignee": "oncall"},
                    {"labels": ["docs"], "assignee": "writer"},
                ]
            }
        }
        cfg.write_text(yaml.safe_dump(payload))

        rules = tr.load_routing_rules(str(cfg))
        assert len(rules) == 3
        assert rules[0] == {"labels": ["security"], "assignee": "sec-team"}
        assert rules[1] == {"labels": ["bug", "p0"], "assignee": "oncall"}
        assert rules[2] == {"labels": ["docs"], "assignee": "writer"}

    def test_loaded_rules_drive_route(self, tmp_path):
        """End-to-end: rules loaded from disk feed straight into route()."""
        cfg = tmp_path / "config.yaml"
        payload = {
            "triage": {
                "routing_rules": [
                    {"labels": ["security"], "assignee": "sec-team"},
                    {"labels": ["bug"], "assignee": "bug-team"},
                ]
            }
        }
        cfg.write_text(yaml.safe_dump(payload))

        rules = tr.load_routing_rules(str(cfg))
        assert tr.route(["security", "bug"], None, rules) == "sec-team"
        assert tr.route(["bug"], None, rules) == "bug-team"
        assert tr.route(["other"], "fallback", rules) == "fallback"

    def test_malformed_routing_rules_not_list_raises(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(textwrap.dedent("""\
            triage:
              routing_rules:
                labels: [bug]
                assignee: bob
        """))
        with pytest.raises(ValueError, match="routing_rules must be a list"):
            tr.load_routing_rules(str(cfg))

    def test_malformed_individual_rule_raises_at_load(self, tmp_path):
        """A broken rule in the YAML should fail load immediately, with
        the index in the message."""
        cfg = tmp_path / "config.yaml"
        payload = {
            "triage": {
                "routing_rules": [
                    {"labels": ["ok"], "assignee": "fine"},
                    {"labels": "not-a-list", "assignee": "bob"},
                ]
            }
        }
        cfg.write_text(yaml.safe_dump(payload))

        with pytest.raises(ValueError, match="at index 1"):
            tr.load_routing_rules(str(cfg))

    def test_unparseable_yaml_returns_empty(self, tmp_path):
        """Garbled YAML should NOT crash routing — we surface a warning
        and act as if no rules were configured."""
        cfg = tmp_path / "config.yaml"
        cfg.write_text(":\n  invalid: : :\n\t- bad")
        assert tr.load_routing_rules(str(cfg)) == []

    def test_non_dict_root_returns_empty(self, tmp_path):
        """A YAML file whose root is a list (instead of a mapping)
        should be treated as 'no config'."""
        cfg = tmp_path / "config.yaml"
        cfg.write_text("- just\n- a\n- list\n")
        assert tr.load_routing_rules(str(cfg)) == []

    def test_default_path_via_hermes_home(self, tmp_path, monkeypatch):
        """When ``config_path`` is None, the module reads from
        ``$HERMES_HOME/config.yaml``."""
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        (tmp_path / "config.yaml").write_text(yaml.safe_dump({
            "triage": {
                "routing_rules": [
                    {"labels": ["x"], "assignee": "y"}
                ]
            }
        }))
        rules = tr.load_routing_rules()
        assert rules == [{"labels": ["x"], "assignee": "y"}]
