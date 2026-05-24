from cron.scheduler import _cron_persist_sessions_enabled


def test_cron_persist_sessions_defaults_to_legacy_enabled(monkeypatch):
    monkeypatch.delenv("HERMES_CRON_PERSIST_SESSIONS", raising=False)

    assert _cron_persist_sessions_enabled({}) is True


def test_cron_persist_sessions_can_be_disabled_by_config(monkeypatch):
    monkeypatch.delenv("HERMES_CRON_PERSIST_SESSIONS", raising=False)

    assert _cron_persist_sessions_enabled({"cron": {"persist_sessions": False}}) is False
    assert _cron_persist_sessions_enabled({"cron": {"persist_sessions": "no"}}) is False
    assert _cron_persist_sessions_enabled({"cron": {"persist_sessions": "0"}}) is False


def test_cron_persist_sessions_env_overrides_config(monkeypatch):
    monkeypatch.setenv("HERMES_CRON_PERSIST_SESSIONS", "0")
    assert _cron_persist_sessions_enabled({"cron": {"persist_sessions": True}}) is False

    monkeypatch.setenv("HERMES_CRON_PERSIST_SESSIONS", "1")
    assert _cron_persist_sessions_enabled({"cron": {"persist_sessions": False}}) is True
