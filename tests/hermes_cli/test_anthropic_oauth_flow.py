"""Tests for the ``_run_anthropic_oauth_flow`` menu in ``hermes_cli.main``.

The flow now presents a 4-choice menu:

  1. Hermes browser login (pure PKCE — default)
  2. Paste an existing Claude Code setup-token
  3. Run 'claude setup-token' via the npm CLI (legacy)
  4. Cancel

These tests cover the three non-cancel branches.  Option 1 is covered in
depth because it's the new default — it calls
``run_hermes_oauth_login_pure``, persists via ``_HERMES_OAUTH_FILE`` and
the credential pool, and signals use-credential-file via ``.env``.
"""

from __future__ import annotations

import json
from pathlib import Path

from hermes_cli.config import load_env, save_env_value


def _iter_inputs(*responses: str):
    it = iter(responses)
    def _next(_prompt: str = "") -> str:
        try:
            return next(it)
        except StopIteration:  # pragma: no cover
            return ""
    return _next


def test_oauth_flow_default_choice_runs_pure_pkce(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    from agent import anthropic_adapter as ant
    monkeypatch.setattr(
        ant,
        "_HERMES_OAUTH_FILE",
        tmp_path / ".anthropic_oauth.json",
    )
    monkeypatch.setattr(
        ant,
        "run_hermes_oauth_login_pure",
        lambda: {
            "access_token": "sk-ant-oat01-pkce-new",
            "refresh_token": "sk-ant-ort01-pkce-new",
            "expires_at_ms": 9_999_999_999_000,
        },
    )

    # Bare Enter defaults to choice 1 (Hermes PKCE).
    monkeypatch.setattr("builtins.input", _iter_inputs(""))

    from hermes_cli.main import _run_anthropic_oauth_flow

    assert _run_anthropic_oauth_flow(save_env_value) is True

    oauth_file = tmp_path / ".anthropic_oauth.json"
    assert oauth_file.exists()
    saved = json.loads(oauth_file.read_text(encoding="utf-8"))
    assert saved["accessToken"] == "sk-ant-oat01-pkce-new"
    assert saved["refreshToken"] == "sk-ant-ort01-pkce-new"
    assert saved["expiresAt"] == 9_999_999_999_000

    # ``.env`` should signal use-credential-file (both Anthropic env vars
    # cleared so the file becomes the source of truth).
    env_vars = load_env()
    assert env_vars.get("ANTHROPIC_TOKEN", "") == ""
    assert env_vars.get("ANTHROPIC_API_KEY", "") == ""

    output = capsys.readouterr().out
    assert "Hermes browser login" in output


def test_oauth_flow_manual_setup_token_choice_persists(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    # Choice 2 + setup-token.
    monkeypatch.setattr("builtins.input", _iter_inputs("2"))
    monkeypatch.setattr("getpass.getpass", lambda _prompt="": "sk-ant-oat01-manual")

    from hermes_cli.main import _run_anthropic_oauth_flow

    assert _run_anthropic_oauth_flow(save_env_value) is True

    env_vars = load_env()
    assert env_vars["ANTHROPIC_TOKEN"] == "sk-ant-oat01-manual"
    out = capsys.readouterr().out
    assert "Setup-token saved" in out or "saved" in out.lower()


def test_oauth_flow_legacy_npm_choice_uses_setup_token_subprocess(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    from agent import anthropic_adapter as ant
    monkeypatch.setattr(
        ant,
        "run_oauth_setup_token",
        lambda: "sk-ant-oat01-from-claude-setup",
    )
    # Simulate the Claude Code credentials file appearing after subprocess.
    monkeypatch.setattr(
        ant,
        "read_claude_code_credentials",
        lambda: {
            "accessToken": "cc-access-token",
            "refreshToken": "cc-refresh-token",
            "expiresAt": 9999999999999,
            "source": "file",
        },
    )
    monkeypatch.setattr(ant, "is_claude_code_token_valid", lambda creds: True)

    # Choice 3 = legacy npm ``claude setup-token``.
    monkeypatch.setattr("builtins.input", _iter_inputs("3"))

    from hermes_cli.main import _run_anthropic_oauth_flow

    # Stale env var — the legacy flow should clear it because Claude Code's
    # refreshable credential file is preferred when available.
    save_env_value("ANTHROPIC_TOKEN", "stale-env-token")

    assert _run_anthropic_oauth_flow(save_env_value) is True

    env_vars = load_env()
    assert env_vars["ANTHROPIC_TOKEN"] == ""
    assert env_vars["ANTHROPIC_API_KEY"] == ""
    out = capsys.readouterr().out
    assert "Claude Code credentials linked" in out


def test_oauth_flow_cancel_returns_false(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setattr("builtins.input", _iter_inputs("4"))
    from hermes_cli.main import _run_anthropic_oauth_flow
    assert _run_anthropic_oauth_flow(save_env_value) is False
