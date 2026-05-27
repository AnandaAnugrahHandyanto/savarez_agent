from gateway.run import _sanitize_gateway_final_response


def test_telegram_provider_quota_exhausted_message_is_actionable():
    raw = (
        "Provider quota exhausted for claude-code-cli/claude-sonnet-4-6: "
        "Claude CLI fail-fast: rate-limit/quota signal detected (usage_limit_reached)"
    )

    reply = _sanitize_gateway_final_response("telegram", raw)

    assert "Provider quota exhausted" in reply
    assert "claude-code-cli/claude-sonnet-4-6" in reply
    assert "billing/usage limits" in reply
    assert "usage_limit_reached" not in reply


def test_non_telegram_keeps_provider_failure_details():
    raw = "Provider quota exhausted for openrouter/gpt-test: quota exhausted"

    assert _sanitize_gateway_final_response("discord", raw) == raw
