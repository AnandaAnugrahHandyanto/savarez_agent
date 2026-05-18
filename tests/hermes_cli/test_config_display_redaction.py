"""Regression tests for secret-safe `hermes config` display output."""

import hashlib


def _safe_secret_status(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"configured (sha256:{digest}, len={len(value)})"


def test_show_config_redacts_api_key_rows(monkeypatch, capsys, tmp_path):
    from hermes_cli import auth as auth_mod
    from hermes_cli import config as config_mod
    import agent.skill_utils as skill_utils

    secret = "tvly-config-secret-0123456789abcdef"
    model_secret = "sk-" + "modelconfig" + "0123456789abcdef"
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("TAVILY_API_KEY", secret)
    monkeypatch.setattr(
        config_mod,
        "load_config",
        lambda: {"model": {"default": "gpt-test", "api_key": model_secret}, "agent": {}},
        raising=False,
    )
    monkeypatch.setattr(auth_mod, "get_anthropic_key", lambda: "", raising=False)
    monkeypatch.setattr(skill_utils, "discover_all_skill_config_vars", lambda: [], raising=False)

    config_mod.show_config()

    output = capsys.readouterr().out
    assert "Tavily" in output
    assert secret not in output
    assert model_secret not in output
    assert "modelconfig" not in output
    assert "tvly-config" not in output
    assert "89abcdef" not in output
    assert _safe_secret_status(secret) in output


def test_show_config_redacts_secret_like_skill_settings(monkeypatch, capsys, tmp_path):
    from hermes_cli import auth as auth_mod
    from hermes_cli import config as config_mod
    import agent.skill_utils as skill_utils

    secret = "sk-testskillsecret0123456789abcdef"
    skill_vars = [{"key": "EXAMPLE_API_TOKEN", "skill": "demo-skill"}]
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setattr(auth_mod, "get_anthropic_key", lambda: "", raising=False)
    monkeypatch.setattr(skill_utils, "discover_all_skill_config_vars", lambda: skill_vars, raising=False)
    monkeypatch.setattr(
        skill_utils,
        "resolve_skill_config_values",
        lambda vars: {"EXAMPLE_API_TOKEN": secret},
        raising=False,
    )

    config_mod.show_config()

    output = capsys.readouterr().out
    assert "EXAMPLE_API_TOKEN" in output
    assert "demo-skill" in output
    assert secret not in output
    assert "sk-testskill" not in output
    assert "89abcdef" not in output
    assert _safe_secret_status(secret) in output
