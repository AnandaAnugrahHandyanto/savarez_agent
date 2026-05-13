"""Tests for the deterministic Hermes Cognitive Core policy layer."""

from agent.cognitive_core import (
    COGNITIVE_CORE_MARKER,
    build_cognitive_core_prompt,
    build_turn_routing_hint,
    detect_mail_readonly_status,
    is_cognitive_core_enabled,
    route_message,
)


def test_flag_gating_env_and_config(monkeypatch):
    monkeypatch.delenv("HERMES_COGNITIVE_CORE", raising=False)
    assert is_cognitive_core_enabled({}) is False
    assert is_cognitive_core_enabled({"agent": {"cognitive_core": {"enabled": True}}}) is True

    monkeypatch.setenv("HERMES_COGNITIVE_CORE", "0")
    assert is_cognitive_core_enabled({"agent": {"cognitive_core": {"enabled": True}}}) is False

    monkeypatch.setenv("HERMES_COGNITIVE_CORE", "1")
    assert is_cognitive_core_enabled({}) is True


def test_router_deterministic_coverage_for_core_modes():
    fixtures = [
        ("debug este bug de docker y corré tests", "technical"),
        ("tensiona esta hipótesis y detecta supuestos", "epistemological"),
        ("analiza mi colesterol y presión en el tiempo", "health"),
        ("recordá lo que vimos antes en Honcho y Obsidian", "contextual"),
        ("mandale un email y agenda un calendario", "external_capability"),
        ("hola", "contextual"),
    ]
    for text, expected in fixtures:
        first = route_message(text).to_dict()
        second = route_message(text).to_dict()
        assert first == second
        assert first["selected_mode"] == expected
        assert first["fallback_status"] in {"matched", "fallback_default"}


def test_external_actions_require_approval():
    route = route_message("mandale un mensaje por telegram")
    assert route.selected_mode == "external_capability"
    assert route.approval_required is True
    assert "explicit approval" in " ".join(route.required_checks)


def test_health_false_positive_routes_to_technical():
    route = route_message("revisá el local health check del runtime")
    assert route.selected_mode == "technical"
    assert "health metaphor suppressed" in route.trigger_evidence


def test_cognitive_core_prompt_is_capability_conservative(monkeypatch):
    monkeypatch.delenv("HERMES_COGNITIVE_CORE", raising=False)
    cfg = {"agent": {"cognitive_core": {"enabled": True, "name": "Darwin Core"}}}
    prompt = build_cognitive_core_prompt(cfg, valid_tool_names={"memory", "session_search"})
    assert COGNITIVE_CORE_MARKER in prompt
    assert "one coherent agent" in prompt
    assert "Mail: read-only capability status" in prompt
    assert "Forbidden without explicit future write gate" in prompt
    assert "NATS/agent.bus: deferred_optional" in prompt
    assert "this policy replaces generic memory guidance" in prompt


def test_mail_readonly_status_is_shape_only(monkeypatch, tmp_path):
    monkeypatch.setattr("agent.cognitive_core.Path.home", lambda: tmp_path)
    monkeypatch.setattr("agent.cognitive_core.shutil.which", lambda name: "/usr/bin/himalaya")

    status = detect_mail_readonly_status({"terminal"})
    assert status["status"] == "blocked_not_configured"
    assert status["himalaya_present"] is True
    assert status["config_present"] is False
    assert status["network_attempted"] is False
    assert status["mail_read_attempted"] is False
    assert status["write_attempted"] is False

    cfg = tmp_path / ".config" / "himalaya" / "config.toml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("# redacted test config")
    status = detect_mail_readonly_status({"terminal"})
    assert status["status"] == "ready_readonly_requires_user_request"
    assert status["config_present"] is True


def test_turn_routing_hint_excludes_raw_user_text():
    route = route_message("debug secreto-api-key-should-not-appear")
    hint = build_turn_routing_hint(route)
    assert "selected_mode=technical" in hint
    assert "secreto-api-key-should-not-appear" not in hint
