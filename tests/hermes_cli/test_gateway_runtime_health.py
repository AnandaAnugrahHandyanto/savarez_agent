from hermes_cli.gateway import _runtime_health_lines


def test_runtime_health_lines_include_fatal_platform_and_startup_reason(monkeypatch):
    monkeypatch.setattr(
        "gateway.status.read_runtime_status",
        lambda: {
            "gateway_state": "startup_failed",
            "exit_reason": "telegram conflict",
            "platforms": {
                "telegram": {
                    "state": "fatal",
                    "error_message": "another poller is active",
                }
            },
        },
    )

    lines = _runtime_health_lines()

    assert "⚠ telegram: another poller is active" in lines
    assert "⚠ Last startup issue: telegram conflict" in lines


def test_runtime_health_lines_include_validation_and_evidence_summary(monkeypatch):
    monkeypatch.setattr(
        "gateway.status.read_runtime_status",
        lambda: {
            "schema_version": 1,
            "gateway_state": "running",
            "updated_at": "2026-04-14T01:00:00+00:00",
            "platforms": {},
        },
    )
    monkeypatch.setattr(
        "gateway.status.validate_runtime_artifacts",
        lambda: {
            "runtime_status": {"valid": False, "errors": ["gateway_state invalid"]},
            "pid": {"valid": True, "errors": []},
            "evidence": {"exists": True, "line_count": 3, "last_event": "gateway_started"},
        },
    )
    monkeypatch.setattr(
        "agent.routing_governance.read_rollout_state",
        lambda: {
            "current_route": {"provider": "openrouter", "model": "google/gemini-2.5-flash"},
            "rollback": {
                "available": True,
                "from_route": {"provider": "openrouter", "model": "anthropic/claude-sonnet-4"},
            },
        },
    )

    lines = _runtime_health_lines()

    assert "⚠ Runtime state validation: gateway_state invalid" in lines
    assert "ℹ Runtime evidence: 3 event(s), last=gateway_started" in lines
    assert "ℹ Routing rollout: google/gemini-2.5-flash via openrouter" in lines
    assert "ℹ Rollback ready: anthropic/claude-sonnet-4 via openrouter" in lines
