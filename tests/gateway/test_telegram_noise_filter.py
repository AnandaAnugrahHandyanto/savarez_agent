"""Telegram-specific gateway filtering for noisy status/error output."""

from gateway.config import Platform
from gateway.run import (
    _prepare_gateway_status_message,
    _sanitize_gateway_final_response,
)


def test_telegram_status_suppresses_auxiliary_and_retry_noise():
    """Auxiliary failures and retry backoff chatter should not hit Telegram."""
    noisy_messages = [
        "⚠ Auxiliary title generation failed: HTTP 400: Operation contains cybersecurity risk",
        "⚠ Compression summary failed: upstream error. Inserted a fallback context marker.",
        "🗜️ Compacting context — summarizing earlier conversation so I can continue...",
        "ℹ Configured compression model 'small-model' failed (timeout). Recovered using main model — check auxiliary.compression.model in config.yaml.",
        "⏳ Retrying in 4.2s (attempt 1/3)...",
        "⏱️ Rate limited. Waiting 30.0s (attempt 2/3)...",
        "⚠️ Max retries (3) exhausted — trying fallback...",
        "🔄 Primary model failed — switching to fallback: gpt-5.4-mini via openai-api",
    ]

    for message in noisy_messages:
        assert _prepare_gateway_status_message(Platform.TELEGRAM, "warn", message) is None


def test_non_telegram_status_is_unchanged():
    """The Telegram quieting policy must not hide CLI/Discord diagnostics."""
    message = "⏳ Retrying in 4.2s (attempt 1/3)..."

    assert _prepare_gateway_status_message(Platform.DISCORD, "lifecycle", message) == message
    assert _prepare_gateway_status_message("local", "lifecycle", message) == message


def test_telegram_status_sanitizes_raw_provider_security_errors():
    """Provider policy/security bodies should be replaced before chat delivery."""
    raw = (
        "❌ API failed after 3 retries — HTTP 400: request blocked because "
        "Operation contains cybersecurity risk. request_id=req_123"
    )

    sanitized = _prepare_gateway_status_message(Platform.TELEGRAM, "lifecycle", raw)

    assert sanitized is not None
    assert "provider rejected" in sanitized.lower()
    assert "cybersecurity risk" not in sanitized.lower()
    assert "HTTP 400" not in sanitized
    assert "req_123" not in sanitized


def test_telegram_final_response_sanitizes_raw_provider_errors():
    """Final Telegram replies should not expose raw provider/security details."""
    raw = (
        "API call failed after 3 retries: HTTP 400: This request was blocked "
        "under the provider cybersecurity risk policy. request_id=req_abc"
    )

    sanitized = _sanitize_gateway_final_response(Platform.TELEGRAM, raw)

    assert "provider rejected" in sanitized.lower()
    assert "cybersecurity risk" not in sanitized.lower()
    assert "HTTP 400" not in sanitized
    assert "req_abc" not in sanitized


def test_telegram_final_response_sanitizes_codex_incomplete_continuation_error():
    """Codex continuation failures are infrastructure errors, not user-facing prose."""
    raw = "Codex response remained incomplete after 3 continuation attempts"

    sanitized = _sanitize_gateway_final_response(Platform.TELEGRAM, raw)

    assert "model provider failed" in sanitized.lower()
    assert "Codex response" not in sanitized
    assert "continuation attempts" not in sanitized


def test_telegram_status_sanitizes_codex_incomplete_continuation_error():
    """Status callbacks should not leak raw Codex continuation errors to Telegram."""
    raw = "Codex response remained incomplete after 3 continuation attempts"

    sanitized = _prepare_gateway_status_message(Platform.TELEGRAM, "error", raw)

    assert sanitized is not None
    assert "model provider failed" in sanitized.lower()
    assert "Codex response" not in sanitized
    assert "continuation attempts" not in sanitized


def test_default_whatsapp_final_response_keeps_admin_diagnostics(monkeypatch):
    """Default/admin WhatsApp gateways keep existing diagnostic behaviour."""
    monkeypatch.setenv("HERMES_PROFILE", "default")
    monkeypatch.setenv("HERMES_HOME", "/home/test/.hermes")
    raw = "Codex response remained incomplete after 3 continuation attempts"

    assert _sanitize_gateway_final_response(Platform.WHATSAPP, raw) == raw


def test_ochied_whatsapp_final_response_uses_guest_safe_provider_wording(monkeypatch):
    """Ochied WhatsApp chats should never see technical provider wording."""
    monkeypatch.setenv("HERMES_PROFILE", "ochied")
    monkeypatch.setenv("HERMES_HOME", "/home/test/.hermes/profiles/ochied")
    raw = "Codex response remained incomplete after 3 continuation attempts"

    sanitized = _sanitize_gateway_final_response(Platform.WHATSAPP, raw)

    assert "Ochied" in sanitized
    assert "gangguan sebentar" in sanitized
    assert "Codex response" not in sanitized
    assert "provider" not in sanitized.lower()
    assert "continuation attempts" not in sanitized


def test_ochied_whatsapp_final_response_sanitizes_quota_errors(monkeypatch):
    """Ochied WhatsApp chats should not see raw quota/billing provider errors."""
    monkeypatch.setenv("HERMES_PROFILE", "ochied")
    monkeypatch.setenv("HERMES_HOME", "/home/test/.hermes/profiles/ochied")
    raw = (
        "You exceeded your current quota, please check your plan and billing details. "
        "For more information, read https://platform.openai.com/docs/guides/error-codes/api-errors."
    )

    sanitized = _sanitize_gateway_final_response(Platform.WHATSAPP, raw)

    assert "Ochied" in sanitized
    assert "gangguan sebentar" in sanitized
    assert "quota" not in sanitized.lower()
    assert "billing" not in sanitized.lower()
    assert "platform.openai.com" not in sanitized
    assert "provider" not in sanitized.lower()


def test_ochied_whatsapp_status_suppresses_fallback_switch_notice(monkeypatch):
    """Ochied WhatsApp chats should not see internal fallback-routing notices."""
    monkeypatch.setenv("HERMES_PROFILE", "ochied")
    monkeypatch.setenv("HERMES_HOME", "/home/test/.hermes/profiles/ochied")
    raw = "Primary model failed — switching to fallback: gpt-5.4-mini via openai-api"

    sanitized = _prepare_gateway_status_message(Platform.WHATSAPP, "warn", raw)

    assert sanitized is None


def test_ochied_whatsapp_status_uses_guest_safe_provider_wording(monkeypatch):
    """Ochied WhatsApp status callbacks should not leak raw provider errors."""
    monkeypatch.setenv("HERMES_PROFILE", "ochied")
    monkeypatch.setenv("HERMES_HOME", "/home/test/.hermes/profiles/ochied")
    raw = "❌ API failed after 3 retries — HTTP 500: upstream unavailable"

    sanitized = _prepare_gateway_status_message(Platform.WHATSAPP, "lifecycle", raw)

    assert sanitized is not None
    assert "Ochied" in sanitized
    assert "gangguan sebentar" in sanitized
    assert "HTTP 500" not in sanitized
    assert "upstream" not in sanitized.lower()
    assert "provider" not in sanitized.lower()


def test_telegram_final_response_redacts_auth_secrets():
    """Authentication errors should be useful without leaking key material."""
    raw = (
        "⚠️ Provider authentication failed: Incorrect API key provided: "
        "sk-live_abcdefghijklmnopqrstuvwxyz1234567890"
    )

    sanitized = _sanitize_gateway_final_response(Platform.TELEGRAM, raw)

    assert "authentication failed" in sanitized.lower()
    assert "check the configured credentials" in sanitized.lower()
    assert "sk-live" not in sanitized


def test_telegram_final_response_keeps_normal_answers():
    """Normal assistant content should not be rewritten."""
    answer = "Here is the clean summary you asked for."

    assert _sanitize_gateway_final_response(Platform.TELEGRAM, answer) == answer
