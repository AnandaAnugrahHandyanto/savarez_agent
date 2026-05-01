from argparse import Namespace

from hermes_cli import status as status_mod


def test_status_surfaces_masked_secret_warning(monkeypatch, tmp_path, capsys):
    home = tmp_path / ".hermes"
    home.mkdir(parents=True, exist_ok=True)
    env_path = home / ".env"
    env_path.write_text("FEISHU_APP_SECRET=masked\n", encoding="utf-8")

    monkeypatch.setattr(status_mod, "get_env_path", lambda: env_path)
    monkeypatch.setattr(status_mod, "load_config", lambda: {})
    monkeypatch.setattr(status_mod, "_configured_model_label", lambda config: "(not set)")
    monkeypatch.setattr(status_mod, "_effective_provider_label", lambda: "custom")
    monkeypatch.setattr(status_mod, "get_env_value", lambda key: "")
    monkeypatch.setattr(status_mod, "managed_nous_tools_enabled", lambda: False)

    monkeypatch.setattr(
        "hermes_cli.auth.get_nous_auth_status",
        lambda: {},
        raising=False,
    )
    monkeypatch.setattr(
        "hermes_cli.auth.get_codex_auth_status",
        lambda: {},
        raising=False,
    )
    monkeypatch.setattr(
        "hermes_cli.auth.get_qwen_auth_status",
        lambda: {},
        raising=False,
    )

    status_mod.show_status(Namespace(all=False, deep=False))
    out = capsys.readouterr().out
    assert "Secret Warnings" in out
    assert "FEISHU_APP_SECRET" in out
    assert "握手失败" in out