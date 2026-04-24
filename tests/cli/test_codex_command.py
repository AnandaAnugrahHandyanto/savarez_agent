from unittest.mock import MagicMock, patch

from cli import HermesCLI
from hermes_cli.commands import COMMAND_REGISTRY, resolve_command


def _make_cli():
    cli_obj = HermesCLI.__new__(HermesCLI)
    cli_obj.config = {}
    cli_obj.console = MagicMock()
    cli_obj.agent = None
    cli_obj.conversation_history = []
    cli_obj.session_id = "session-123"
    cli_obj._pending_input = MagicMock()
    cli_obj._status_bar_visible = True
    cli_obj.model = "openai/gpt-5.4"
    cli_obj.provider = "openai"
    cli_obj._agent_running = False
    cli_obj._session_db = MagicMock()
    cli_obj._session_db.get_session.return_value = None
    return cli_obj


def test_codex_command_is_registered_as_cli_only():
    cmd = next(c for c in COMMAND_REGISTRY if c.name == "codex")
    assert cmd.cli_only is True
    assert "add" in cmd.subcommands
    assert "probe" in cmd.subcommands
    assert "doctor" in cmd.subcommands
    assert "管理 Codex 多账号" in cmd.description


def test_codex_alias_resolves_to_canonical_command():
    assert resolve_command("codex-accounts").name == "codex"


def test_process_command_dispatches_codex_handler():
    cli_obj = _make_cli()

    with patch.object(cli_obj, "_handle_codex_command", create=True) as mock_handler:
        assert cli_obj.process_command("/codex list") is True

    mock_handler.assert_called_once_with("/codex list")


def test_add_account_prefers_email_claim_as_default_label(monkeypatch):
    import codex_account_manager as cam

    class DummyPool:
        def entries(self):
            return []

        def add_entry(self, entry):
            self.entry = entry
            return entry

    pool = DummyPool()
    monkeypatch.setattr(cam, "load_codex_pool", lambda: pool)
    monkeypatch.setattr(
        cam,
        "_codex_device_code_login",
        lambda: {
            "tokens": {
                "access_token": "***",
                "refresh_token": "***",
            },
            "base_url": cam.DEFAULT_BASE_URL,
            "last_refresh": None,
        },
    )
    monkeypatch.setattr(cam, "label_from_token", lambda token, fallback: "li@example.com")

    entry = cam.add_account()

    assert entry.label == "li@example.com"


def test_codex_parser_help_contains_chinese_subcommand_descriptions():
    import codex_account_manager as cam

    parser = cam.build_parser()
    help_text = parser.format_help()

    assert "新增账号：通过设备码登录一个 Codex 账号" in help_text
    assert "查看账号列表：展示邮箱、套餐、当前账号额度快照" in help_text
    assert "诊断状态：检查活动账号与 Hermes/Codex CLI 登录态是否一致" in help_text

    command_action = next(action for action in parser._actions if getattr(action, "dest", None) == "command")
    list_subparser = command_action.choices["list"]
    assert "--refresh-all" in list_subparser.format_help()

    doctor_parser = cam.build_parser()
    doctor_action = next(action for action in doctor_parser._actions if getattr(action, "dest", None) == "command")
    doctor_subparser = doctor_action.choices["doctor"]
    assert "--fix" in doctor_subparser.format_help()
