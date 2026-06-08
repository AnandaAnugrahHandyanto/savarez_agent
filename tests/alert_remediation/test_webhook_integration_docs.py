from pathlib import Path


DOC_PATH = Path("docs/alert-remediation/webhook-integration.md")


def test_webhook_integration_doc_exists_and_covers_secure_route_pattern() -> None:
    text = DOC_PATH.read_text()

    assert "# Alert Remediation Webhook Integration" in text
    assert "HMAC" in text
    assert "secret" in text
    assert "INSECURE_NO_AUTH" in text
    assert "deliver_only" in text
    assert "message_thread_id" in text


def test_webhook_integration_doc_routes_payloads_through_alert_router_not_agent_prompt() -> None:
    text = DOC_PATH.read_text()

    assert "scripts/alert_remediation_router.py" in text
    assert "alert.remediation/v1" in text
    assert "UNTRUSTED" in text
    assert "policy decides" in text
    assert "--dry-run" in text
    assert "--create-kanban" in text


def test_webhook_integration_doc_includes_example_subscription_and_config_route() -> None:
    text = DOC_PATH.read_text()

    assert "hermes webhook subscribe" in text
    assert "platforms:" in text
    assert "webhook:" in text
    assert "/webhooks/alert-remediation" in text
    assert "telegram:-1003939486586:7" in text
