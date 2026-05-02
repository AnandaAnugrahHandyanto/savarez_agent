import os


def test_load_config_exports_bankr_wallet_environment_aliases(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        """
bankr:
  walletAddress: "0x000000000000000000000000000000000000ba5e"
  apiKey: "bk_agent_cleartext_secret"
  walletId: "wlt_123"
  withdrawalDestination: "0x000000000000000000000000000000000000feed"
""",
        encoding="utf-8",
    )

    for key in (
        "BANKR_AGENT_WALLET_ADDRESS",
        "BANKR_AGENT_API_KEY",
        "BANKR_AGENT_WALLET_ID",
        "BANKR_AGENT_WITHDRAWAL_DESTINATION",
        "BANKR_API_KEY",
        "BANKR_WALLET_ADDRESS",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    from hermes_cli.config import load_config

    load_config()

    assert os.environ["BANKR_AGENT_WALLET_ADDRESS"] == "0x000000000000000000000000000000000000ba5e"
    assert os.environ["BANKR_AGENT_API_KEY"] == "bk_agent_cleartext_secret"
    assert os.environ["BANKR_AGENT_WALLET_ID"] == "wlt_123"
    assert os.environ["BANKR_AGENT_WITHDRAWAL_DESTINATION"] == "0x000000000000000000000000000000000000feed"
    assert os.environ["BANKR_API_KEY"] == "bk_agent_cleartext_secret"
    assert os.environ["BANKR_WALLET_ADDRESS"] == "0x000000000000000000000000000000000000ba5e"
