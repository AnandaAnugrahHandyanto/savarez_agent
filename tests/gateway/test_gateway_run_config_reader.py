from unittest.mock import patch

import gateway.run as run_mod


def test_load_gateway_config_uses_shared_reader(monkeypatch):
    called = {}

    def fake_read_user_config(*, expand_env=True, merge_defaults=False, config_path=None):
        called["args"] = (expand_env, merge_defaults, config_path)
        return {"model": {"default": "x"}}

    monkeypatch.setattr("hermes_cli.config.read_user_config", fake_read_user_config)
    monkeypatch.setattr(run_mod, "_hermes_home", run_mod.Path("/tmp/hermes-test-home"))

    data = run_mod._load_gateway_config()

    assert data == {"model": {"default": "x"}}
    assert called["args"] == (True, False, run_mod.Path("/tmp/hermes-test-home/config.yaml"))


def test_main_reads_explicit_config_with_shared_raw_reader(tmp_path, monkeypatch):
    config_path = tmp_path / "gateway-config.yaml"
    config_path.write_text("model:\n  default: old\n", encoding="utf-8")
    called = {}

    def fake_read_user_config_raw(*, config_path=None):
        called["config_path"] = config_path
        return {"model": {"default": "gpt-5.4"}}

    async def fake_start_gateway(config):
        called["gateway_config"] = config
        return True

    monkeypatch.setattr(
        "hermes_cli.config.read_user_config_raw",
        fake_read_user_config_raw,
    )
    monkeypatch.setattr(run_mod, "start_gateway", fake_start_gateway)
    monkeypatch.setattr(run_mod.sys, "argv", ["gateway.run", "--config", str(config_path)])

    with patch("gateway.run.GatewayConfig.from_dict", return_value="parsed-config") as from_dict:
        run_mod.main()

    assert called["config_path"] == config_path
    from_dict.assert_called_once_with({"model": {"default": "gpt-5.4"}})
    assert called["gateway_config"] == "parsed-config"


def test_main_raises_on_invalid_explicit_config(tmp_path, monkeypatch):
    config_path = tmp_path / "gateway-config.yaml"
    config_path.write_text("model:\n  default: [unterminated\n", encoding="utf-8")

    monkeypatch.setattr(run_mod.sys, "argv", ["gateway.run", "--config", str(config_path)])

    try:
        run_mod.main()
        raise AssertionError("expected invalid explicit config to raise")
    except Exception as exc:
        import yaml

        assert isinstance(exc, yaml.YAMLError)


def test_main_raises_on_non_mapping_explicit_config(tmp_path, monkeypatch):
    config_path = tmp_path / "gateway-config.yaml"
    config_path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    monkeypatch.setattr(run_mod.sys, "argv", ["gateway.run", "--config", str(config_path)])

    try:
        run_mod.main()
        raise AssertionError("expected non-mapping explicit config to raise")
    except Exception as exc:
        assert isinstance(exc, TypeError)


def test_main_raises_on_falsy_non_mapping_explicit_config(tmp_path, monkeypatch):
    config_path = tmp_path / "gateway-config.yaml"
    config_path.write_text("[]\n", encoding="utf-8")

    monkeypatch.setattr(run_mod.sys, "argv", ["gateway.run", "--config", str(config_path)])

    try:
        run_mod.main()
        raise AssertionError("expected falsy non-mapping explicit config to raise")
    except Exception as exc:
        assert isinstance(exc, TypeError)
