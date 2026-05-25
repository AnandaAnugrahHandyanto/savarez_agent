from gateway.steering import (
    SteeringConfig,
    load_steering_config,
    render_ack,
    render_interruption_context,
    should_send_ack,
)


def test_steering_defaults_enabled_with_threshold():
    cfg = load_steering_config({})
    assert cfg.enabled is True
    assert cfg.ack_threshold_seconds == 5
    assert cfg.ack_timeout_seconds == 3
    assert cfg.landing_timeout_seconds == 30
    assert cfg.iteration_hard_timeout == 120


def test_render_ack_uses_iteration_variables():
    cfg = SteeringConfig(ack_template="Vu {current}/{total} {current_tool} {user}")
    text = render_ack(
        cfg,
        user="Judy",
        activity={
            "api_call_count": 7,
            "max_iterations": 90,
            "current_tool": "npm test",
        },
    )
    assert text == "Vu 7/90 npm test Judy"


def test_invalid_ack_template_falls_back():
    cfg = SteeringConfig(ack_template="{missing")
    text = render_ack(
        cfg,
        activity={"api_call_count": 7, "max_iterations": 90},
    )
    assert "7/90" in text


def test_render_interruption_context_includes_user_message_and_breakpoint_contract():
    cfg = SteeringConfig()
    text = render_interruption_context(
        cfg,
        message="prends aussi config.ts",
        user="gweeteve",
        activity={"api_call_count": 7, "max_iterations": 90},
    )
    assert "⚠️ Interruption" in text
    assert "itération 7/90" in text
    assert 'Message de gweeteve: "prends aussi config.ts"' in text
    assert "<hermes_steering_breakpoint>" in text


def test_ack_threshold_uses_current_step_elapsed_time():
    cfg = SteeringConfig(ack_threshold_seconds=5)
    assert should_send_ack(cfg, {"seconds_since_activity": 4.9}) is False
    assert should_send_ack(cfg, {"seconds_since_activity": 5.0}) is True
