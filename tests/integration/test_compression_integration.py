"""Integration tests for caveman-llm compression gate in tools.memory_tool.

Tests cover all bypass conditions, error fallback, backup firing, and edge cases.
All external dependencies (caveman-llm, Hindsight) are mocked to keep tests fast.
"""

import os
import pytest
from unittest.mock import MagicMock, patch

# --- conftest-like autouse fixtures to normalize test environment ---

@pytest.fixture(autouse=True)
def clean_hermes_compress():
    """Ensure HERMES_COMPRESS is reset before and after each test."""
    old = os.environ.pop("HERMES_COMPRESS", None)
    yield
    # Restore previous state
    if old is not None:
        os.environ["HERMES_COMPRESS"] = old
    else:
        os.environ.pop("HERMES_COMPRESS", None)


@pytest.fixture(autouse=True)
def patch_caveman_deps(monkeypatch):
    """Patch memory_tool's caveman dependencies to controllable fakes.

    This ensures tests don't depend on caveman-llm being installed.
    """
    # Import the module (ensures it's loaded)
    from tools import memory_tool as mt
    # Mark caveman as available
    monkeypatch.setattr(mt, "_CAVEMAN_AVAILABLE", True)
    # Ensure CompressionOptions is callable (it may be None if import failed originally)
    class _DummyCompressionOptions:
        def __init__(self, *args, **kwargs):
            pass
    monkeypatch.setattr(mt, "CompressionOptions", _DummyCompressionOptions, raising=False)
    # Patch segment to return a MagicMock with configurable prose_ratio
    # Default returns 0.5 (above 0.20 threshold)
    monkeypatch.setattr(mt, "segment", lambda text: MagicMock(prose_ratio=0.5))
    # Patch is_sensitive_content to return (False, [])
    monkeypatch.setattr(mt, "is_sensitive_content", lambda text: (False, []))
    # The actual compress_llm will be patched per-test as needed
    # The _backup_original_async will be patched in tests that care


# --- sample content ---

PROSE = (
    "The quick brown fox jumps over the lazy dog. " * 8
    + "It was the best of times, it was the worst of times. "
    + "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
    + "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
)

TECHNICAL = """def calculate(x, y):
    return x * y

# API endpoint
POST /api/v1/users
Content-Type: application/json
{
  "name": "John"
}
"""

SENSITIVE = "DB_PASSWORD=super_secret_123\nAPI_KEY=sk-CCabB7cKj9tL8mN2pQrStUvWxYz0123456789"

EMPTY = ""

LARGE = "x" * 600_000


# --- fixtures ---

@pytest.fixture
def fake_store():
    s = MagicMock()
    s.add = MagicMock(return_value={"success": True, "entries": 1, "entry_count": 1})
    s.replace = MagicMock(return_value={"success": True, "entries": 1, "entry_count": 1})
    return s


# --- tests ---


class TestCompressionGate:
    """Compression gate logic in memory_tool prior to store dispatch."""

    def test_triggers_on_prose_heavy_add(self, fake_store):
        os.environ["HERMES_COMPRESS"] = "1"
        with patch("tools.memory_tool.compress_llm") as mock_compress:
            mock_compress.return_value = MagicMock(text="[COMPRESSED]", original=PROSE)
            with patch("tools.memory_tool._backup_original_async") as mock_backup:
                from tools.memory_tool import memory_tool
                result = memory_tool(action="add", target="memory", content=PROSE, store=fake_store)
                assert fake_store.add.called
                assert fake_store.add.call_args[0][1] == "[COMPRESSED]"
                mock_backup.assert_called_once_with(PROSE, fake_store.add.return_value, target="memory")

    def test_triggers_on_prose_heavy_replace(self, fake_store):
        os.environ["HERMES_COMPRESS"] = "1"
        with patch("tools.memory_tool.compress_llm") as mock_compress:
            mock_compress.return_value = MagicMock(text="[CMPR]", original=PROSE)
            with patch("tools.memory_tool._backup_original_async") as mock_backup:
                from tools.memory_tool import memory_tool
                result = memory_tool(action="replace", target="memory", old_text="old", content=PROSE, store=fake_store)
                assert fake_store.replace.called
                assert fake_store.replace.call_args[0][2] == "[CMPR]"
                mock_backup.assert_called_once_with(PROSE, fake_store.replace.return_value, target="memory")

    def test_compression_skips_technical_code_raw(self, fake_store):
        os.environ["HERMES_COMPRESS"] = "1"
        with patch("tools.memory_tool.compress_llm") as mock_compress:
            from tools.memory_tool import CompressionError
            mock_compress.side_effect = CompressionError("nope")
            with patch("tools.memory_tool._backup_original_async") as mock_backup:
                from tools.memory_tool import memory_tool
                result = memory_tool(action="add", target="memory", content=TECHNICAL, store=fake_store)
                assert fake_store.add.called
                assert fake_store.add.call_args[0][1] == TECHNICAL
                mock_backup.assert_not_called()

    def test_compression_respects_env_gate_disabled(self, fake_store):
        # HERMES_COMPRESS not set; default bypass
        with patch("tools.memory_tool.compress_llm") as mock_compress:
            mock_compress.return_value = MagicMock(text="[CMPR]")
            from tools.memory_tool import memory_tool
            # env not set (clean_env fixture ensures removal)
            result = memory_tool(action="add", target="memory", content=PROSE, store=fake_store)
            mock_compress.assert_not_called()
            assert fake_store.add.call_args[0][1] == PROSE

    def test_compression_size_limit_enforced(self, fake_store):
        os.environ["HERMES_COMPRESS"] = "1"
        # LARGE > 500k; gate returns False before calling compress_llm
        with patch("tools.memory_tool.compress_llm") as mock_compress:
            from tools.memory_tool import memory_tool
            result = memory_tool(action="add", target="memory", content=LARGE, store=fake_store)
            mock_compress.assert_not_called()
            assert fake_store.add.call_args[0][1] == LARGE

    def test_compression_sensitive_content_blocked(self, fake_store):
        os.environ["HERMES_COMPRESS"] = "1"
        # is_sensitive_content returns True; bypass
        with patch("tools.memory_tool.is_sensitive_content") as mock_sens, \
             patch("tools.memory_tool.compress_llm") as mock_compress:
            mock_sens.return_value = (True, ["API key pattern"])
            from tools.memory_tool import memory_tool
            result = memory_tool(action="add", target="memory", content=SENSITIVE, store=fake_store)
            mock_compress.assert_not_called()
            assert fake_store.add.call_args[0][1] == SENSITIVE

    def test_compression_low_prose_ratio_skipped(self, fake_store):
        os.environ["HERMES_COMPRESS"] = "1"
        # segment returns low prose_ratio
        with patch("tools.memory_tool.segment") as mock_segment, \
             patch("tools.memory_tool.compress_llm") as mock_compress:
            mock_segment.return_value = MagicMock(prose_ratio=0.05)
            from tools.memory_tool import memory_tool
            result = memory_tool(action="add", target="memory", content=PROSE, store=fake_store)
            mock_compress.assert_not_called()
            assert fake_store.add.call_args[0][1] == PROSE

    def test_backup_original_fires_after_success(self, fake_store):
        os.environ["HERMES_COMPRESS"] = "1"
        with patch("tools.memory_tool.compress_llm") as mock_compress:
            mock_compress.return_value = MagicMock(text="[CMPR]")
            with patch("tools.memory_tool._backup_original_async") as mock_backup:
                from tools.memory_tool import memory_tool
                result = memory_tool(action="add", target="memory", content=PROSE, store=fake_store)
                mock_backup.assert_called_once_with(PROSE, fake_store.add.return_value, target="memory")

    def test_backup_original_not_called_on_bypass(self, fake_store):
        # HERMES_COMPRESS unset (clean_env fixture ensures removal)
        with patch("tools.memory_tool._backup_original_async") as mock_backup:
            from tools.memory_tool import memory_tool
            result = memory_tool(action="add", target="memory", content=PROSE, store=fake_store)
            mock_backup.assert_not_called()

    def test_compression_error_falls_back_to_raw(self, fake_store):
        os.environ["HERMES_COMPRESS"] = "1"
        # compress_llm raises unexpected exception → fall back
        with patch("tools.memory_tool.compress_llm") as mock_compress:
            mock_compress.side_effect = Exception("LLM timeout")
            from tools.memory_tool import memory_tool
            result = memory_tool(action="add", target="memory", content=PROSE, store=fake_store)
            assert fake_store.add.called
            assert fake_store.add.call_args[0][1] == PROSE

    def test_compression_empty_content_bypass(self, fake_store):
        os.environ["HERMES_COMPRESS"] = "1"
        # Empty content bypasses before calling compress_llm
        with patch("tools.memory_tool.compress_llm") as mock_compress:
            from tools.memory_tool import memory_tool
            result = memory_tool(action="add", target="memory", content=EMPTY, store=fake_store)
            mock_compress.assert_not_called()
            assert not fake_store.add.called  # store.validate rejects empty

    def test_caveman_not_installed_falls_back_to_raw(self, fake_store):
        # Force _CAVEMAN_AVAILABLE False
        os.environ["HERMES_COMPRESS"] = "1"
        with patch("tools.memory_tool._CAVEMAN_AVAILABLE", False), \
             patch("tools.memory_tool.compress_llm") as mock_compress:
            from tools.memory_tool import memory_tool
            result = memory_tool(action="add", target="memory", content=PROSE, store=fake_store)
            mock_compress.assert_not_called()
            assert fake_store.add.call_args[0][1] == PROSE

    def test_compression_delimiter_collision_protected(self, fake_store):
        os.environ["HERMES_COMPRESS"] = "1"
        collision_text = PROSE + "\n§\n" + PROSE
        with patch("tools.memory_tool.compress_llm") as mock_compress:
            mock_compress.return_value = MagicMock(text="[CMP§OK]", original=collision_text)
            with patch("tools.memory_tool._backup_original_async"):
                from tools.memory_tool import memory_tool
                memory_tool(action="add", target="memory", content=collision_text, store=fake_store)
                assert fake_store.add.called
                stored_content = fake_store.add.call_args[0][1]
                assert "§" in stored_content


class TestBackupHelper:
    """_backup_original_async helper thread behaviour."""

    def test_backup_writes_jsonl_file(self):
        from tools.memory_tool import _backup_original_async
        _backup_original_async("original text", {"success": True, "entry_count": 1}, target="memory")

    def test_backup_never_raises_on_write_error(self):
        from tools.memory_tool import _backup_original_async
        with patch("pathlib.Path.mkdir", side_effect=PermissionError("nope")):
            with patch("threading.Thread.start"):
                _backup_original_async("text", {}, target="memory")


class TestBackupEncryption:
    """Fernet-encrypted backup storage (HERMES_BACKUP_KEY)."""

    def test_backup_creates_encrypted_jsonl_file(self, tmp_path, monkeypatch):
        """When HERMES_BACKUP_KEY is set, backup file is created and contains decryptable data."""
        import json
        import datetime
        from cryptography.fernet import Fernet
        from tools.memory_tool import _backup_original_async

        key = Fernet.generate_key()
        monkeypatch.setenv("HERMES_BACKUP_KEY", key.decode())
        backup_base = tmp_path / "backups" / "compression"
        monkeypatch.setattr("hermes_constants.get_hermes_home", lambda: str(tmp_path))

        _backup_original_async(
            "secret original text",
            {"success": True, "entry_count": 1, "action": "add", "entry_index": 0},
            target="memory",
        )
        import time; time.sleep(0.5)

        backup_file = backup_base / f"{datetime.date.today()}.jsonl"
        assert backup_file.exists(), f"Backup file not created: {backup_file}"

        lines_content = backup_file.read_text().strip().splitlines()
        record = json.loads(lines_content[-1])
        assert "original_enc" in record
        f = Fernet(key)
        recovered = f.decrypt(record["original_enc"].encode()).decode()
        assert recovered == "secret original text"
        assert record["action"] == "add"
        assert record["entry_index"] == 0
        assert record["target"] == "memory"
        assert record["original_length"] == 20

    def test_backup_skipped_when_key_missing(self, tmp_path, monkeypatch):
        """If HERMES_BACKUP_KEY is unset, no backup file is written."""
        from tools.memory_tool import _backup_original_async

        monkeypatch.delenv("HERMES_BACKUP_KEY", raising=False)
        backup_base = tmp_path / "backups" / "compression"
        monkeypatch.setattr("hermes_constants.get_hermes_home", lambda: str(tmp_path))

        _backup_original_async("some text", {"success": True}, target="memory")
        import time; time.sleep(0.5)

        assert not backup_base.exists(), "Backup dir should not be created when key missing"

    def test_backup_handles_invalid_key_gracefully(self, tmp_path, monkeypatch, capsys):
        """Invalid HERMES_BACKUP_KEY logs warning but does not raise."""
        from tools.memory_tool import _backup_original_async

        monkeypatch.setenv("HERMES_BACKUP_KEY", "not-a-valid-fernkey")
        backup_base = tmp_path / "backups" / "compression"
        monkeypatch.setattr("hermes_constants.get_hermes_home", lambda: str(tmp_path))

        _backup_original_async("text", {"success": True}, target="memory")
        import time; time.sleep(0.5)

        captured = capsys.readouterr()
        assert "encryption failed" in captured.err.lower()
    def test_backup_appends_multiple_records(self, tmp_path, monkeypatch):
        """Two sequential backups produce two lines in the same daily file."""
        import datetime
        import json
        import time
        from tools.memory_tool import _backup_original_async
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        monkeypatch.setenv("HERMES_BACKUP_KEY", key)
        monkeypatch.setattr("hermes_constants.get_hermes_home", lambda: str(tmp_path))

        fernet = Fernet(key.encode())
        target = "test::target"

        # First backup
        _backup_original_async("original text", {"action": "add", "entry_index": 0, "compressed": "a", "metadata": {}}, target=target)
        time.sleep(0.3)  # let daemon thread finish

        backup_dir = tmp_path / "backups" / "compression"
        backup_file = backup_dir / f"{datetime.datetime.now(datetime.timezone.utc):%Y-%m-%d}.jsonl"
        assert backup_file.exists(), f"Backup file not created: {backup_file}"

        # Second backup
        _backup_original_async("original text", {"action": "add", "entry_index": 1, "compressed": "b", "metadata": {}}, target=target)
        time.sleep(0.3)  # let daemon thread finish again

        lines = backup_file.read_text().splitlines()
        assert len(lines) == 2, f"Expected 2 lines, got {len(lines)}: {lines}"

        # Both decrypt correctly and have correct indices
        for i, line in enumerate(lines):
            rec = json.loads(line)
            original = fernet.decrypt(rec["original_enc"]).decode()
            assert original == "original text"
            assert rec["entry_index"] == i
            assert rec["target"] == target