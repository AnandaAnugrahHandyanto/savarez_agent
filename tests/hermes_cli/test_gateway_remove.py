"""Tests for ``hermes gateway remove <platform>`` (issue #9842)."""

from __future__ import annotations

import pytest

from hermes_cli import config as cli_config
from hermes_cli import gateway as gw


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _env_path():
    return cli_config.get_env_path()


def _read_env_text() -> str:
    p = _env_path()
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8-sig")


def _silence_prompts(monkeypatch, *, yes: bool = True, choice: int = 0) -> None:
    monkeypatch.setattr(gw, "prompt_yes_no", lambda *a, **kw: yes)
    monkeypatch.setattr(gw, "prompt_choice", lambda *a, **kw: choice)


def _seed_telegram_env(monkeypatch):
    """Populate .env with the standard Telegram setup secrets."""
    cli_config.save_env_value("TELEGRAM_BOT_TOKEN", "fake-bot-token")
    cli_config.save_env_value("TELEGRAM_ALLOWED_USERS", "123,456")
    cli_config.save_env_value("TELEGRAM_HOME_CHANNEL", "123")


# ---------------------------------------------------------------------------
# _platform_env_var_names
# ---------------------------------------------------------------------------


def test_platform_env_vars_for_telegram_includes_setup_schema():
    plat = gw._resolve_platform_for_removal("telegram")
    assert plat is not None
    names = gw._platform_env_var_names(plat)
    assert "TELEGRAM_BOT_TOKEN" in names
    assert "TELEGRAM_ALLOWED_USERS" in names
    assert "TELEGRAM_HOME_CHANNEL" in names
    # Order: vars-schema entries appear before token_var/_extras.
    assert names.index("TELEGRAM_BOT_TOKEN") < names.index("TELEGRAM_HOME_CHANNEL")
    # No duplicates even when token_var also appears in the vars schema.
    assert len(names) == len(set(names))


def test_platform_env_vars_pulls_extras_for_matrix():
    plat = gw._resolve_platform_for_removal("matrix")
    if plat is None:  # matrix is hidden on Windows; skip there
        pytest.skip("matrix platform not available on this host")
    names = gw._platform_env_var_names(plat)
    assert "MATRIX_ACCESS_TOKEN" in names
    assert "MATRIX_PASSWORD" in names  # from _PLATFORM_EXTRA_ENV_VARS


# ---------------------------------------------------------------------------
# _resolve_platform_for_removal
# ---------------------------------------------------------------------------


def test_resolve_platform_is_case_insensitive():
    assert gw._resolve_platform_for_removal("Telegram")["key"] == "telegram"
    assert gw._resolve_platform_for_removal("TELEGRAM")["key"] == "telegram"
    assert gw._resolve_platform_for_removal("  telegram ")["key"] == "telegram"


def test_resolve_platform_unknown_returns_none():
    assert gw._resolve_platform_for_removal("notarealplatform") is None
    assert gw._resolve_platform_for_removal("") is None


# ---------------------------------------------------------------------------
# unknown platform
# ---------------------------------------------------------------------------


def test_remove_unknown_platform_exits_with_help(monkeypatch, capsys):
    _silence_prompts(monkeypatch)
    with pytest.raises(SystemExit) as exc_info:
        gw._gateway_remove_platform("not-a-real-platform", force=True)
    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "Unknown platform" in out
    assert "telegram" in out  # the known-platform list is printed


# ---------------------------------------------------------------------------
# happy path — env-var deletion
# ---------------------------------------------------------------------------


def test_remove_telegram_deletes_env_vars(monkeypatch, capsys):
    _silence_prompts(monkeypatch)
    _seed_telegram_env(monkeypatch)
    assert "TELEGRAM_BOT_TOKEN=fake-bot-token" in _read_env_text()

    gw._gateway_remove_platform("telegram", force=True)

    text = _read_env_text()
    assert "TELEGRAM_BOT_TOKEN" not in text
    assert "TELEGRAM_ALLOWED_USERS" not in text
    assert "TELEGRAM_HOME_CHANNEL" not in text

    out = capsys.readouterr().out
    assert "Telegram removed" in out


def test_remove_force_skips_confirmation(monkeypatch, capsys):
    """With --force, the y/N prompt must not run.

    We assert this by raising from the prompt: if it gets called, the test
    fails with a clear traceback instead of hanging or false-passing.
    """
    def _fail(*args, **kwargs):
        raise AssertionError("prompt_yes_no should not be called when force=True")
    monkeypatch.setattr(gw, "prompt_yes_no", _fail)

    _seed_telegram_env(monkeypatch)
    gw._gateway_remove_platform("telegram", force=True)
    assert "TELEGRAM_BOT_TOKEN" not in _read_env_text()


def test_remove_user_declines_keeps_env(monkeypatch, capsys):
    """When the user answers 'no' at the confirmation, env vars stay put."""
    monkeypatch.setattr(gw, "prompt_yes_no", lambda *a, **kw: False)
    monkeypatch.setattr(gw, "prompt_choice", lambda *a, **kw: 0)
    _seed_telegram_env(monkeypatch)

    gw._gateway_remove_platform("telegram", force=False)

    assert "TELEGRAM_BOT_TOKEN=fake-bot-token" in _read_env_text()
    assert "Cancelled" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# --keep-env (comment out instead of delete)
# ---------------------------------------------------------------------------


def test_keep_env_comments_out_instead_of_deleting(monkeypatch, capsys):
    _silence_prompts(monkeypatch)
    _seed_telegram_env(monkeypatch)

    gw._gateway_remove_platform("telegram", force=True, keep_env=True)

    text = _read_env_text()
    # Lines preserved but commented — the token is still recoverable.
    assert "# TELEGRAM_BOT_TOKEN=fake-bot-token" in text
    assert "# TELEGRAM_ALLOWED_USERS=" in text
    # No uncommented copies left.
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("TELEGRAM_BOT_TOKEN="):
            pytest.fail(f"unexpected active line: {line!r}")

    out = capsys.readouterr().out
    assert "commented out" in out.lower()


# ---------------------------------------------------------------------------
# config.yaml block removal
# ---------------------------------------------------------------------------


def test_remove_drops_config_yaml_block(monkeypatch):
    _silence_prompts(monkeypatch)
    _seed_telegram_env(monkeypatch)
    cli_config.save_config({
        "gateway": {
            "platforms": {
                "telegram": {"enabled": True, "extra": {"reply_to_mode": "first"}},
                "slack": {"enabled": True},
            },
        },
    })

    gw._gateway_remove_platform("telegram", force=True)

    after = cli_config.read_raw_config()
    platforms = after.get("gateway", {}).get("platforms", {})
    assert "telegram" not in platforms
    assert "slack" in platforms  # other platforms untouched


def test_remove_prunes_empty_gateway_section(monkeypatch):
    """When the platform we remove is the only one in gateway.platforms,
    drop the now-empty gateway block too. Avoids leaving a dangling
    ``gateway: {platforms: {}}`` skeleton in config.yaml.
    """
    _silence_prompts(monkeypatch)
    _seed_telegram_env(monkeypatch)
    cli_config.save_config({
        "gateway": {"platforms": {"telegram": {"enabled": True}}},
    })

    gw._gateway_remove_platform("telegram", force=True)

    after = cli_config.read_raw_config()
    assert "gateway" not in after


def test_no_config_flag_leaves_yaml_untouched(monkeypatch):
    _silence_prompts(monkeypatch)
    _seed_telegram_env(monkeypatch)
    cli_config.save_config({
        "gateway": {"platforms": {"telegram": {"enabled": True}}},
    })

    gw._gateway_remove_platform("telegram", force=True, no_config=True)

    after = cli_config.read_raw_config()
    assert "telegram" in after["gateway"]["platforms"]
    # …but env vars are still cleared.
    assert "TELEGRAM_BOT_TOKEN" not in _read_env_text()


# ---------------------------------------------------------------------------
# idempotency
# ---------------------------------------------------------------------------


def test_remove_already_absent_is_noop(monkeypatch, capsys):
    _silence_prompts(monkeypatch)
    # Nothing seeded.
    gw._gateway_remove_platform("telegram", force=True)
    out = capsys.readouterr().out
    assert "not currently configured" in out


def test_remove_twice_is_idempotent(monkeypatch, capsys):
    _silence_prompts(monkeypatch)
    _seed_telegram_env(monkeypatch)
    gw._gateway_remove_platform("telegram", force=True)
    capsys.readouterr()  # discard

    gw._gateway_remove_platform("telegram", force=True)
    out = capsys.readouterr().out
    assert "not currently configured" in out


# ---------------------------------------------------------------------------
# interactive picker (no positional arg)
# ---------------------------------------------------------------------------


def test_interactive_picker_lists_configured_platforms(monkeypatch, capsys):
    _seed_telegram_env(monkeypatch)
    monkeypatch.setattr(gw, "prompt_yes_no", lambda *a, **kw: True)
    captured = {}

    def fake_choice(question, choices, default):
        captured["choices"] = choices
        return 0  # pick the first one (Telegram)

    monkeypatch.setattr(gw, "prompt_choice", fake_choice)
    gw._gateway_remove_platform(None, force=True)

    labels = captured["choices"]
    assert any("Telegram" in c for c in labels)
    # Cancel option is appended at the end.
    assert labels[-1] == "Cancel"
    assert "TELEGRAM_BOT_TOKEN" not in _read_env_text()


def test_interactive_picker_cancel_does_not_remove(monkeypatch, capsys):
    _seed_telegram_env(monkeypatch)
    monkeypatch.setattr(gw, "prompt_yes_no", lambda *a, **kw: True)
    monkeypatch.setattr(gw, "prompt_choice", lambda q, choices, d: len(choices) - 1)

    gw._gateway_remove_platform(None)

    assert "TELEGRAM_BOT_TOKEN=fake-bot-token" in _read_env_text()
    assert "Cancelled" in capsys.readouterr().out


def test_interactive_picker_no_configured_platforms(monkeypatch, capsys):
    _silence_prompts(monkeypatch)
    gw._gateway_remove_platform(None)
    out = capsys.readouterr().out
    assert "No platforms are currently configured" in out


# ---------------------------------------------------------------------------
# config.comment_env_value helper
# ---------------------------------------------------------------------------


def test_comment_env_value_prefixes_lines():
    cli_config.save_env_value("TEST_VAR_FOO", "hello")
    assert cli_config.comment_env_value("TEST_VAR_FOO") is True

    text = _read_env_text()
    assert "# TEST_VAR_FOO=hello" in text
    assert "\nTEST_VAR_FOO=" not in text


def test_comment_env_value_missing_key_returns_false():
    # File doesn't exist yet.
    assert cli_config.comment_env_value("NEVER_SET_VAR") is False
    # File exists but doesn't contain the key.
    cli_config.save_env_value("KEPT", "1")
    assert cli_config.comment_env_value("NEVER_SET_VAR") is False
    assert "KEPT=1" in _read_env_text()


def test_comment_env_value_idempotent_on_commented_line():
    cli_config.save_env_value("TEST_VAR_FOO", "hello")
    cli_config.comment_env_value("TEST_VAR_FOO")
    text_first = _read_env_text()
    # Run again — already commented, must not double-prefix.
    cli_config.comment_env_value("TEST_VAR_FOO")
    assert _read_env_text() == text_first
