from __future__ import annotations


def test_gateway_discord_cron_helper_accepts_thread_target_and_sanitizes_mentions():
    from cron.discord_delivery import sanitize_cron_output_for_discord, validate_cron_delivery_target

    assert validate_cron_delivery_target("discord:123456789012345678:987654321098765432").ok
    sanitized = sanitize_cron_output_for_discord("cron done @everyone <#123456789012345678>")
    assert "@everyone" not in sanitized
    assert "<#123456789012345678>" not in sanitized


def test_cron_delivery_formatter_preserves_legacy_wrapper_by_default():
    from cron.scheduler import _format_cron_delivery_content

    rendered = _format_cron_delivery_content(
        {"id": "job_1", "name": "Daily report"},
        "done",
    )

    assert rendered.startswith("Cronjob Response: Daily report")
    assert "(job_id: job_1)" in rendered
    assert "done" in rendered
    assert "To stop or manage this job" in rendered


def test_cron_delivery_formatter_uses_event_renderer_when_enabled():
    from cron.scheduler import _format_cron_delivery_content
    from gateway.event_routing import create_cron_delivery_event

    event = create_cron_delivery_event(
        job_id="job_1",
        job_name="Daily report",
        success=True,
        content="done @everyone",
        run_id="run_abcdef123456",
    )

    rendered = _format_cron_delivery_content(
        {"id": "job_1", "name": "Daily report"},
        "done @everyone",
        delivery_event=event,
        use_event_renderer=True,
    )

    assert rendered.startswith("🛠️ Agent ops")
    assert "cron.completed" in rendered
    assert "run_abcdef12" in rendered
    assert "@everyone" not in rendered
    assert "Cronjob Response" not in rendered


def test_cron_delivery_formatter_uses_incident_format_for_failures():
    from cron.scheduler import _format_cron_delivery_content
    from gateway.event_routing import create_cron_delivery_event

    event = create_cron_delivery_event(
        job_id="job_broken",
        job_name="Broken job",
        success=False,
        content="failed",
        error="boom",
        run_id="run_fail123456",
    )

    rendered = _format_cron_delivery_content(
        {"id": "job_broken", "name": "Broken job"},
        "failed",
        delivery_event=event,
        use_event_renderer=True,
    )

    assert rendered.startswith("🚨 Agent incident")
    assert "cron.failed" in rendered
    assert "run_fail123" in rendered
    assert "failed" in rendered


def test_cron_delivery_renderer_is_selected_only_for_discord_targets():
    from cron.scheduler import _select_cron_delivery_content_for_platform

    assert _select_cron_delivery_content_for_platform(
        "discord",
        legacy_content="legacy",
        rendered_content="rendered",
        use_event_renderer=True,
    ) == "rendered"
    assert _select_cron_delivery_content_for_platform(
        "telegram",
        legacy_content="legacy",
        rendered_content="rendered",
        use_event_renderer=True,
    ) == "legacy"
    assert _select_cron_delivery_content_for_platform(
        "discord",
        legacy_content="legacy",
        rendered_content="rendered",
        use_event_renderer=False,
    ) == "legacy"
