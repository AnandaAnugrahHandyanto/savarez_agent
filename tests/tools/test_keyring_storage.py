"""Tests for keyring-backed secret storage."""
import pytest
from unittest.mock import patch, MagicMock
import hermes_cli.config as config


class TestKeyringHelpers:
    def test_save_returns_false_when_keyring_unavailable(self):
        with patch.object(config, "_KEYRING_AVAILABLE", False):
            assert config.save_secret_keyring("k", "v") is False

    def test_save_returns_true_on_success(self):
        mock_kr = MagicMock()
        with patch.object(config, "_KEYRING_AVAILABLE", True):
            with patch.object(config, "_keyring", mock_kr):
                result = config.save_secret_keyring("mykey", "myval")
        assert result is True
        mock_kr.set_password.assert_called_once_with("hermes-agent", "mykey", "myval")

    def test_save_returns_false_on_exception(self):
        mock_kr = MagicMock()
        mock_kr.set_password.side_effect = Exception("no daemon")
        with patch.object(config, "_KEYRING_AVAILABLE", True):
            with patch.object(config, "_keyring", mock_kr):
                result = config.save_secret_keyring("k", "v")
        assert result is False

    def test_get_returns_none_when_unavailable(self):
        with patch.object(config, "_KEYRING_AVAILABLE", False):
            assert config.get_secret_keyring("k") is None

    def test_get_returns_value_on_success(self):
        mock_kr = MagicMock()
        mock_kr.get_password.return_value = "secretval"
        with patch.object(config, "_KEYRING_AVAILABLE", True):
            with patch.object(config, "_keyring", mock_kr):
                result = config.get_secret_keyring("mykey")
        assert result == "secretval"

    def test_get_returns_none_on_exception(self):
        mock_kr = MagicMock()
        mock_kr.get_password.side_effect = Exception("locked")
        with patch.object(config, "_KEYRING_AVAILABLE", True):
            with patch.object(config, "_keyring", mock_kr):
                assert config.get_secret_keyring("k") is None

    def test_delete_returns_false_when_unavailable(self):
        with patch.object(config, "_KEYRING_AVAILABLE", False):
            assert config.delete_secret_keyring("k") is False

    def test_delete_returns_true_on_success(self):
        mock_kr = MagicMock()
        with patch.object(config, "_KEYRING_AVAILABLE", True):
            with patch.object(config, "_keyring", mock_kr):
                assert config.delete_secret_keyring("k") is True
        mock_kr.delete_password.assert_called_once_with("hermes-agent", "k")


class TestKeyringIntegration:
    """Keyring wired into save_env_value_secure and get_env_value."""

    def test_save_env_value_secure_uses_keyring_first(self):
        with patch.object(config, "save_secret_keyring", return_value=True) as mock_save:
            with patch.object(config, "save_env_value") as mock_file:
                result = config.save_env_value_secure("ANTHROPIC_API_KEY", "sk-test")
        mock_save.assert_called_once_with("ANTHROPIC_API_KEY", "sk-test")
        mock_file.assert_not_called()  # keyring succeeded, no file write
        assert result["backend"] == "keyring"

    def test_save_env_value_secure_falls_back_to_file(self):
        with patch.object(config, "save_secret_keyring", return_value=False):
            with patch.object(config, "save_env_value") as mock_file:
                result = config.save_env_value_secure("SOME_KEY", "val")
        mock_file.assert_called_once_with("SOME_KEY", "val")
        assert result["backend"] == "file"

    def test_get_env_value_checks_keyring_first(self):
        with patch.object(config, "get_secret_keyring", return_value="from_keyring"):
            result = config.get_env_value("MY_KEY")
        assert result == "from_keyring"

    def test_get_env_value_falls_back_to_env(self):
        import os
        with patch.object(config, "get_secret_keyring", return_value=None):
            with patch.dict(os.environ, {"MY_KEY": "from_env"}):
                result = config.get_env_value("MY_KEY")
        assert result == "from_env"

    def test_get_env_value_falls_back_to_file(self):
        with patch.object(config, "get_secret_keyring", return_value=None):
            with patch.object(config, "load_env", return_value={"SOME_KEY": "from_file"}):
                import os
                with patch.dict(os.environ, {}, clear=False):
                    # Make sure SOME_KEY is not in env
                    os.environ.pop("SOME_KEY", None)
                    result = config.get_env_value("SOME_KEY")
        assert result == "from_file"
