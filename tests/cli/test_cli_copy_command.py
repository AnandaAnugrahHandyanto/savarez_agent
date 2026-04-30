"""Tests for CLI /copy command."""

from unittest.mock import MagicMock, patch

from cli import HermesCLI


def _make_cli() -> HermesCLI:
    cli_obj = HermesCLI.__new__(HermesCLI)
    cli_obj.config = {}
    cli_obj.console = MagicMock()
    cli_obj.agent = None
    cli_obj.conversation_history = []
    cli_obj.session_id = "sess-copy-test"
    cli_obj._pending_input = MagicMock()
    cli_obj._app = None
    return cli_obj


def _patch_clipboard(cli_obj):
    """Patch both clipboard writers to keep tests off the host clipboard."""
    return (
        patch.object(cli_obj, "_write_osc52_clipboard"),
        patch.object(cli_obj, "_write_native_clipboard", return_value=True),
    )


def test_copy_copies_latest_assistant_message():
    cli_obj = _make_cli()
    cli_obj.conversation_history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "first"},
        {"role": "assistant", "content": "latest"},
    ]

    osc_patch, native_patch = _patch_clipboard(cli_obj)
    with osc_patch as mock_osc, native_patch as mock_native:
        result = cli_obj.process_command("/copy")

    assert result is True
    mock_osc.assert_called_once_with("latest")
    mock_native.assert_called_once_with("latest")


def test_copy_with_index_uses_requested_assistant_message():
    cli_obj = _make_cli()
    cli_obj.conversation_history = [
        {"role": "assistant", "content": "one"},
        {"role": "assistant", "content": "two"},
    ]

    osc_patch, native_patch = _patch_clipboard(cli_obj)
    with osc_patch as mock_osc, native_patch:
        cli_obj.process_command("/copy 1")

    mock_osc.assert_called_once_with("one")


def test_copy_strips_reasoning_blocks_before_copy():
    cli_obj = _make_cli()
    cli_obj.conversation_history = [
        {
            "role": "assistant",
            "content": "<REASONING_SCRATCHPAD>internal</REASONING_SCRATCHPAD>\nVisible answer",
        }
    ]

    osc_patch, native_patch = _patch_clipboard(cli_obj)
    with osc_patch as mock_osc, native_patch:
        cli_obj.process_command("/copy")

    mock_osc.assert_called_once_with("Visible answer")


def test_copy_invalid_index_does_not_copy():
    cli_obj = _make_cli()
    cli_obj.conversation_history = [{"role": "assistant", "content": "only"}]

    osc_patch, native_patch = _patch_clipboard(cli_obj)
    with osc_patch as mock_osc, native_patch as mock_native, \
            patch("cli._cprint") as mock_print:
        cli_obj.process_command("/copy 99")

    mock_osc.assert_not_called()
    mock_native.assert_not_called()
    assert any("Invalid response number" in str(call) for call in mock_print.call_args_list)


def test_copy_succeeds_when_native_works_and_osc52_raises():
    """Terminal.app silently swallows OSC 52, but pbcopy works fine —
    if the native helper succeeds we should report success even when
    OSC 52 raises (or, in practice, would no-op)."""
    cli_obj = _make_cli()
    cli_obj.conversation_history = [{"role": "assistant", "content": "hello"}]

    with (
        patch.object(cli_obj, "_write_osc52_clipboard", side_effect=RuntimeError("no tty")),
        patch.object(cli_obj, "_write_native_clipboard", return_value=True),
        patch("cli._cprint") as mock_print,
    ):
        cli_obj.process_command("/copy")

    assert any("Copied assistant response" in str(call) for call in mock_print.call_args_list)
    assert not any("Clipboard copy failed" in str(call) for call in mock_print.call_args_list)


def test_copy_reports_failure_only_when_both_writers_fail():
    cli_obj = _make_cli()
    cli_obj.conversation_history = [{"role": "assistant", "content": "hello"}]

    with (
        patch.object(cli_obj, "_write_osc52_clipboard", side_effect=RuntimeError("no tty")),
        patch.object(cli_obj, "_write_native_clipboard", return_value=False),
        patch("cli._cprint") as mock_print,
    ):
        cli_obj.process_command("/copy")

    assert any("Clipboard copy failed" in str(call) for call in mock_print.call_args_list)


class TestWriteNativeClipboard:
    def test_macos_uses_pbcopy(self, monkeypatch):
        cli_obj = _make_cli()
        monkeypatch.setattr("cli.sys.platform", "darwin")
        monkeypatch.setattr("cli.shutil.which", lambda cmd: "/usr/bin/pbcopy" if cmd == "pbcopy" else None)
        completed = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=completed) as mock_run:
            assert cli_obj._write_native_clipboard("hi") is True
        cmd = mock_run.call_args.args[0]
        assert cmd == ["pbcopy"]
        assert mock_run.call_args.kwargs["input"] == "hi"

    def test_linux_prefers_wl_copy(self, monkeypatch):
        cli_obj = _make_cli()
        monkeypatch.setattr("cli.sys.platform", "linux")
        present = {"wl-copy": "/usr/bin/wl-copy"}
        monkeypatch.setattr("cli.shutil.which", lambda cmd: present.get(cmd))
        completed = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=completed) as mock_run:
            assert cli_obj._write_native_clipboard("hi") is True
        assert mock_run.call_args.args[0] == ["wl-copy"]

    def test_linux_falls_back_to_xclip(self, monkeypatch):
        cli_obj = _make_cli()
        monkeypatch.setattr("cli.sys.platform", "linux")
        present = {"xclip": "/usr/bin/xclip"}
        monkeypatch.setattr("cli.shutil.which", lambda cmd: present.get(cmd))
        completed = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=completed) as mock_run:
            assert cli_obj._write_native_clipboard("hi") is True
        assert mock_run.call_args.args[0] == ["xclip", "-selection", "clipboard"]

    def test_returns_false_when_no_tool_available(self, monkeypatch):
        cli_obj = _make_cli()
        monkeypatch.setattr("cli.sys.platform", "linux")
        monkeypatch.setattr("cli.shutil.which", lambda _cmd: None)
        with patch("subprocess.run") as mock_run:
            assert cli_obj._write_native_clipboard("hi") is False
        mock_run.assert_not_called()

    def test_unknown_platform_returns_false(self, monkeypatch):
        cli_obj = _make_cli()
        monkeypatch.setattr("cli.sys.platform", "freebsd14")
        with patch("subprocess.run") as mock_run:
            assert cli_obj._write_native_clipboard("hi") is False
        mock_run.assert_not_called()
