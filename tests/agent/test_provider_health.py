import time

from agent import provider_health as ph


def test_record_provider_degradation_writes_state(tmp_path, monkeypatch):
    monkeypatch.setattr("hermes_constants.get_hermes_home", lambda: tmp_path)

    state = ph.record_provider_degradation(
        "gemini",
        reason="rate_limit",
        base_cooldown_seconds=60,
    )

    assert state["provider"] == "gemini"
    assert state["reason"] == "rate_limit"
    assert state["degraded_until"] > time.time()
    assert ph.provider_degraded_remaining("gemini") is not None
    assert (tmp_path / "provider_health" / "gemini.json").exists()


def test_record_provider_degradation_exponentially_backoff(tmp_path, monkeypatch):
    monkeypatch.setattr("hermes_constants.get_hermes_home", lambda: tmp_path)

    first = ph.record_provider_degradation(
        "gemini",
        reason="rate_limit",
        base_cooldown_seconds=60,
    )
    second = ph.record_provider_degradation(
        "gemini",
        reason="rate_limit",
        base_cooldown_seconds=60,
    )

    assert second["failure_count"] == first["failure_count"] + 1
    assert second["cooldown_seconds"] >= first["cooldown_seconds"]
    assert ph.provider_degraded_remaining("gemini") is not None


def test_clear_provider_degradation_removes_state(tmp_path, monkeypatch):
    monkeypatch.setattr("hermes_constants.get_hermes_home", lambda: tmp_path)

    ph.record_provider_degradation(
        "gemini",
        reason="rate_limit",
        base_cooldown_seconds=60,
    )
    assert ph.provider_degraded_remaining("gemini") is not None

    ph.clear_provider_degradation("gemini")
    assert ph.provider_degraded_remaining("gemini") is None
