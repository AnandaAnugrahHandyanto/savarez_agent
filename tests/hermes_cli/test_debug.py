"""Tests for ``hermes debug`` CLI command and debug utilities."""

import os
import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def hermes_home(tmp_path, monkeypatch):
    """Set up an isolated HERMES_HOME with minimal logs."""
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))

    # Create log files
    logs_dir = home / "logs"
    logs_dir.mkdir()
    (logs_dir / "agent.log").write_text(
        "2026-04-12 17:00:00 INFO agent: session started\n"
        "2026-04-12 17:00:01 INFO tools.terminal: running ls\n"
        "2026-04-12 17:00:02 WARNING agent: high token usage\n"
    )
    (logs_dir / "errors.log").write_text(
        "2026-04-12 17:00:05 ERROR gateway.run: connection lost\n"
    )
    (logs_dir / "gateway.log").write_text(
        "2026-04-12 17:00:10 INFO gateway.run: started\n"
    )

    return home


# ---------------------------------------------------------------------------
# Unit tests for upload helpers
# ---------------------------------------------------------------------------

class TestUploadPasteRs:
    """Test paste.rs upload path."""

    def test_upload_paste_rs_success(self):
        """Successful paste.rs upload returns the paste URL."""
        from hermes_cli.debug import _upload_paste_rs

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"https://paste.rs/abc123\n"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("hermes_cli.debug.urllib.request.urlopen", return_value=mock_resp):
            url = _upload_paste_rs("hello world")

        assert url == "https://paste.rs/abc123"

    def test_upload_paste_rs_bad_response(self):
        """paste.rs non-URL response raises ValueError."""
        from hermes_cli.debug import _upload_paste_rs

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"<html>error</html>"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("hermes_cli.debug.urllib.request.urlopen", return_value=mock_resp):
            with pytest.raises(ValueError, match="Unexpected response"):
                _upload_paste_rs("test")

    def test_upload_paste_rs_network_error(self):
        """paste.rs upload raises on network failure."""
        from hermes_cli.debug import _upload_paste_rs

        with patch(
            "hermes_cli.debug.urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            with pytest.raises(urllib.error.URLError):
                _upload_paste_rs("test")


class TestUploadDpasteCom:
    """Test dpaste.com fallback upload path."""

    def test_upload_dpaste_com_success(self):
        """Successful dpaste.com upload returns the paste URL."""
        from hermes_cli.debug import _upload_dpaste_com

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"https://dpaste.com/ABCDEFG\n"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("hermes_cli.debug.urllib.request.urlopen", return_value=mock_resp):
            url = _upload_dpaste_com("hello world", expiry_days=7)

        assert url == "https://dpaste.com/ABCDEFG"


class TestUploadToPastebin:
    """Test the combined upload with fallback."""

    def test_tries_paste_rs_first(self):
        """upload_to_pastebin tries paste.rs before dpaste.com."""
        from hermes_cli.debug import upload_to_pastebin

        with patch("hermes_cli.debug._upload_paste_rs",
                    return_value="https://paste.rs/test") as prs:
            url = upload_to_pastebin("content")

        assert url == "https://paste.rs/test"
        prs.assert_called_once()

    def test_falls_back_to_dpaste_com(self):
        """Falls back to dpaste.com when paste.rs fails."""
        from hermes_cli.debug import upload_to_pastebin

        with patch("hermes_cli.debug._upload_paste_rs",
                    side_effect=Exception("down")), \
             patch("hermes_cli.debug._upload_dpaste_com",
                    return_value="https://dpaste.com/TEST") as dp:
            url = upload_to_pastebin("content")

        assert url == "https://dpaste.com/TEST"
        dp.assert_called_once()

    def test_raises_when_both_fail(self):
        """RuntimeError when all services fail."""
        from hermes_cli.debug import upload_to_pastebin

        with patch("hermes_cli.debug._upload_paste_rs",
                    side_effect=Exception("err1")), \
             patch("hermes_cli.debug._upload_dpaste_com",
                    side_effect=Exception("err2")):
            with pytest.raises(RuntimeError, match="Failed to upload"):
                upload_to_pastebin("content")


# ---------------------------------------------------------------------------
# Debug report collection
# ---------------------------------------------------------------------------

class TestCollectDebugReport:
    """Test the debug report builder."""

    def test_report_includes_dump_output(self, hermes_home):
        """Report includes the hermes dump section."""
        from hermes_cli.debug import collect_debug_report

        with patch("hermes_cli.dump.run_dump") as mock_dump:
            mock_dump.side_effect = lambda args: print(
                "--- hermes dump ---\nversion: 0.8.0\n--- end dump ---"
            )
            report = collect_debug_report(log_lines=50)

        assert "--- hermes dump ---" in report
        assert "version: 0.8.0" in report

    def test_report_includes_agent_log(self, hermes_home):
        """Report includes agent.log tail."""
        from hermes_cli.debug import collect_debug_report

        with patch("hermes_cli.dump.run_dump"):
            report = collect_debug_report(log_lines=50)

        assert "--- agent.log" in report
        assert "session started" in report

    def test_report_includes_errors_log(self, hermes_home):
        """Report includes errors.log tail."""
        from hermes_cli.debug import collect_debug_report

        with patch("hermes_cli.dump.run_dump"):
            report = collect_debug_report(log_lines=50)

        assert "--- errors.log" in report
        assert "connection lost" in report

    def test_report_includes_gateway_log(self, hermes_home):
        """Report includes gateway.log tail."""
        from hermes_cli.debug import collect_debug_report

        with patch("hermes_cli.dump.run_dump"):
            report = collect_debug_report(log_lines=50)

        assert "--- gateway.log" in report

    def test_missing_logs_handled(self, tmp_path, monkeypatch):
        """Report handles missing log files gracefully."""
        home = tmp_path / ".hermes"
        home.mkdir()
        monkeypatch.setenv("HERMES_HOME", str(home))

        from hermes_cli.debug import collect_debug_report

        with patch("hermes_cli.dump.run_dump"):
            report = collect_debug_report(log_lines=50)

        assert "(file not found)" in report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

class TestRunDebugShare:
    """Test the run_debug_share CLI handler."""

    def test_local_flag_prints_report(self, hermes_home, capsys):
        """--local prints the report without uploading."""
        from hermes_cli.debug import run_debug_share

        args = MagicMock()
        args.lines = 50
        args.expire = 7
        args.local = True

        with patch("hermes_cli.dump.run_dump"):
            run_debug_share(args)

        out = capsys.readouterr().out
        assert "--- agent.log" in out

    def test_share_prints_url_on_success(self, hermes_home, capsys):
        """Successful upload prints the paste URL."""
        from hermes_cli.debug import run_debug_share

        args = MagicMock()
        args.lines = 50
        args.expire = 7
        args.local = False

        with patch("hermes_cli.dump.run_dump"), \
             patch("hermes_cli.debug.upload_to_pastebin",
                    return_value="https://paste.rs/xyz"):
            run_debug_share(args)

        out = capsys.readouterr().out
        assert "https://paste.rs/xyz" in out
        assert "Share this link" in out

    def test_share_falls_back_on_upload_failure(self, hermes_home, capsys):
        """Upload failure prints report locally and exits with code 1."""
        from hermes_cli.debug import run_debug_share

        args = MagicMock()
        args.lines = 50
        args.expire = 7
        args.local = False

        with patch("hermes_cli.dump.run_dump"), \
             patch("hermes_cli.debug.upload_to_pastebin",
                    side_effect=RuntimeError("all failed")):
            with pytest.raises(SystemExit) as exc_info:
                run_debug_share(args)

        assert exc_info.value.code == 1
        out = capsys.readouterr()
        assert "all failed" in out.err


class TestRunDebug:
    """Test the top-level run_debug router."""

    def test_no_subcommand_shows_usage(self, capsys):
        """No subcommand prints usage help."""
        from hermes_cli.debug import run_debug

        args = MagicMock()
        args.debug_command = None

        run_debug(args)

        out = capsys.readouterr().out
        assert "hermes debug share" in out

    def test_share_subcommand_routes(self, hermes_home):
        """'share' subcommand routes to run_debug_share."""
        from hermes_cli.debug import run_debug

        args = MagicMock()
        args.debug_command = "share"
        args.lines = 200
        args.expire = 7
        args.local = True

        with patch("hermes_cli.dump.run_dump"):
            run_debug(args)  # Should not raise


# ---------------------------------------------------------------------------
# Argparse integration
# ---------------------------------------------------------------------------

class TestArgparseIntegration:
    """Verify the debug subparser is correctly wired in main.py."""

    def test_module_imports_clean(self):
        """debug module functions are importable."""
        from hermes_cli.debug import run_debug, run_debug_share
        assert callable(run_debug)
        assert callable(run_debug_share)

    def test_cmd_debug_dispatches(self):
        """cmd_debug in main.py correctly calls run_debug."""
        from hermes_cli.main import cmd_debug

        args = MagicMock()
        args.debug_command = None

        # Should print usage without error
        cmd_debug(args)
