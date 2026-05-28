from __future__ import annotations

import json

from agent.model_health import (
    get_model_health,
    is_model_in_cooldown,
    load_model_health,
    mark_model_unhealthy,
    model_health_snapshot,
)


def test_mark_model_unhealthy_records_cooldown(tmp_path):
    path = tmp_path / "model-health.json"

    entry = mark_model_unhealthy(
        "deepseek_pro",
        reason="rate_limit",
        provider="deepseek",
        model="deepseek-v4-pro",
        base_url="https://deepseek.test",
        path=path,
        now=100,
    )

    assert entry["cooldown_until"] == 3700
    health = get_model_health("deepseek_pro", path=path, now=160)
    assert health["status"] == "cooldown"
    assert health["cooldown_remaining_seconds"] == 3540
    assert health["reason"] == "rate_limit"
    assert is_model_in_cooldown("deepseek_pro", path=path, now=160)


def test_expired_cooldown_reports_healthy(tmp_path):
    path = tmp_path / "model-health.json"
    mark_model_unhealthy("deepseek_pro", reason="timeout", path=path, now=100)

    health = get_model_health("deepseek_pro", path=path, now=701)

    assert health["status"] == "healthy"
    assert health["cooldown_remaining_seconds"] == 0
    assert not is_model_in_cooldown("deepseek_pro", path=path, now=701)


def test_model_health_snapshot_and_invalid_file(tmp_path):
    invalid_path = tmp_path / "broken.json"
    invalid_path.write_text("{not-json", encoding="utf-8")

    assert load_model_health(invalid_path) == {"models": {}}
    assert get_model_health("", path=invalid_path) == {"status": "unknown"}

    path = tmp_path / "model-health.json"
    mark_model_unhealthy("m1", reason="empty_final_content", path=path, now=10)
    mark_model_unhealthy("m2", reason="unknown", path=path, now=20)
    snapshot = model_health_snapshot(path=path, now=30)

    assert set(snapshot) == {"m1", "m2"}
    assert snapshot["m1"]["status"] == "cooldown"
    assert snapshot["m1"]["cooldown_remaining_seconds"] == 880
    assert json.loads(path.read_text(encoding="utf-8"))["models"]["m2"]["cooldown_seconds"] == 300
