"""Tests for resume-time provider/model hydration in hermes_cli.main."""

from argparse import Namespace
from types import SimpleNamespace


def _make_chat_args(**overrides):
    return Namespace(
        continue_last=overrides.get("continue_last", None),
        resume=overrides.get("resume", None),
        model=overrides.get("model", None),
        provider=overrides.get("provider", None),
        base_url=overrides.get("base_url", None),
        toolsets=overrides.get("toolsets", None),
        verbose=overrides.get("verbose", False),
        query=overrides.get("query", None),
        worktree=overrides.get("worktree", False),
        yolo=overrides.get("yolo", False),
        pass_session_id=overrides.get("pass_session_id", False),
        quiet=overrides.get("quiet", False),
        checkpoints=overrides.get("checkpoints", False),
        skills=overrides.get("skills", None),
    )


def test_cmd_chat_hydrates_resume_runtime(monkeypatch):
    import hermes_cli.main as main_mod

    args = _make_chat_args(resume="sess_123")
    captured = {}

    monkeypatch.setattr(main_mod, "_has_any_provider_configured", lambda: True)
    monkeypatch.setattr(main_mod, "_resolve_session_by_name_or_id", lambda value: value)
    monkeypatch.setattr(
        main_mod,
        "_load_session_resume_runtime",
        lambda session_id: {
            "provider": "claude-code-cli",
            "model": "claude-sonnet-4-6",
            "base_url": "acp://claude-code-cli",
        },
    )

    def fake_cli_main(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("cli.main", fake_cli_main)

    main_mod.cmd_chat(args)

    assert captured["resume"] == "sess_123"
    assert captured["provider"] == "claude-code-cli"
    assert captured["model"] == "claude-sonnet-4-6"
    assert captured["base_url"] == "acp://claude-code-cli"


def test_cmd_chat_preserves_explicit_resume_runtime(monkeypatch):
    import hermes_cli.main as main_mod

    args = _make_chat_args(
        resume="sess_123",
        provider="anthropic",
        model="claude-opus-4-6",
        base_url="https://api.anthropic.com",
    )
    captured = {}

    monkeypatch.setattr(main_mod, "_has_any_provider_configured", lambda: True)
    monkeypatch.setattr(main_mod, "_resolve_session_by_name_or_id", lambda value: value)
    monkeypatch.setattr(
        main_mod,
        "_load_session_resume_runtime",
        lambda session_id: {
            "provider": "claude-code-cli",
            "model": "claude-sonnet-4-6",
            "base_url": "acp://claude-code-cli",
        },
    )

    def fake_cli_main(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("cli.main", fake_cli_main)

    main_mod.cmd_chat(args)

    assert captured["provider"] == "anthropic"
    assert captured["model"] == "claude-opus-4-6"
    assert captured["base_url"] == "https://api.anthropic.com"


def test_load_session_resume_runtime_uses_model_config_fallback(monkeypatch):
    import json
    import sys
    import hermes_cli.main as main_mod

    class FakeDB:
        def get_session(self, session_id):
            assert session_id == "sess_123"
            return {
                "model": "claude-sonnet-4-6",
                "billing_provider": "",
                "billing_base_url": "",
                "model_config": json.dumps(
                    {
                        "provider": "claude-code-cli",
                        "base_url": "acp://claude-code-cli",
                    }
                ),
            }

        def close(self):
            return None

    monkeypatch.setitem(sys.modules, "hermes_state", SimpleNamespace(SessionDB=FakeDB))

    runtime = main_mod._load_session_resume_runtime("sess_123")

    assert runtime == {
        "model": "claude-sonnet-4-6",
        "provider": "claude-code-cli",
        "base_url": "acp://claude-code-cli",
    }


def test_load_session_resume_runtime_infers_provider_from_marker_base_url(monkeypatch):
    import sys
    import hermes_cli.main as main_mod

    class FakeDB:
        def get_session(self, session_id):
            assert session_id == "sess_123"
            return {
                "model": "claude-sonnet-4-6",
                "billing_provider": "",
                "billing_base_url": "acp://claude-code-cli",
                "model_config": None,
            }

        def close(self):
            return None

    monkeypatch.setitem(sys.modules, "hermes_state", SimpleNamespace(SessionDB=FakeDB))

    runtime = main_mod._load_session_resume_runtime("sess_123")

    assert runtime == {
        "model": "claude-sonnet-4-6",
        "provider": "claude-code-cli",
        "base_url": "acp://claude-code-cli",
    }


def test_has_any_provider_configured_counts_external_process(monkeypatch, tmp_path):
    import sys
    import hermes_cli.main as main_mod
    import hermes_cli.auth as auth_mod

    monkeypatch.setattr(main_mod.os, "getenv", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(
        "hermes_cli.config.get_env_path",
        lambda: SimpleNamespace(exists=lambda: False),
    )
    monkeypatch.setattr(
        "hermes_cli.config.get_hermes_home",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        auth_mod,
        "PROVIDER_REGISTRY",
        {
            "claude-code-cli": SimpleNamespace(auth_type="external_process"),
        },
    )
    monkeypatch.setattr(
        auth_mod,
        "get_auth_status",
        lambda provider_id: {"logged_in": provider_id == "claude-code-cli"},
    )
    monkeypatch.setitem(
        sys.modules,
        "agent.anthropic_adapter",
        SimpleNamespace(
            read_claude_code_credentials=lambda: None,
            is_claude_code_token_valid=lambda creds: False,
        ),
    )

    assert main_mod._has_any_provider_configured() is True
