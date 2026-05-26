from datetime import datetime, timedelta, timezone

from gateway.calls.tokens import CallTokenService


def test_token_round_trips_when_scope_matches():
    now = datetime(2026, 5, 26, tzinfo=timezone.utc)
    service = CallTokenService(secret="test-secret")

    token = service.mint(
        platform="telegram",
        chat_id="123",
        user_id="456",
        call_id="call_abc",
        now=now,
        ttl_seconds=600,
    )

    payload = service.verify(
        token,
        platform="telegram",
        chat_id="123",
        user_id="456",
        call_id="call_abc",
        now=now + timedelta(seconds=30),
    )

    assert payload["call_id"] == "call_abc"
    assert payload["platform"] == "telegram"


def test_token_rejects_wrong_user():
    now = datetime(2026, 5, 26, tzinfo=timezone.utc)
    service = CallTokenService(secret="test-secret")
    token = service.mint("telegram", "123", "456", "call_abc", now=now, ttl_seconds=600)

    assert service.verify(token, "telegram", "123", "wrong", "call_abc", now=now) is None


def test_token_rejects_expired_token():
    now = datetime(2026, 5, 26, tzinfo=timezone.utc)
    service = CallTokenService(secret="test-secret")
    token = service.mint("telegram", "123", "456", "call_abc", now=now, ttl_seconds=10)

    assert service.verify(token, "telegram", "123", "456", "call_abc", now=now + timedelta(seconds=11)) is None
