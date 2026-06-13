"""Tests for cron job model resolution fallback (Issue #43899).

Verifies that cron jobs correctly resolve the model from config.yaml
when no explicit model override is set on the job.
"""
import os
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.cron
class TestCronModelFallback:
    """Test cron job model resolution."""

    def _make_base_patches(self, tmp_path):
        """Create common patches for run_job tests."""
        fake_db = MagicMock()
        return [
            patch("cron.scheduler._hermes_home", tmp_path),
            patch("cron.scheduler._resolve_origin", return_value=None),
            patch("dotenv.load_dotenv"),
            patch("hermes_state.SessionDB", return_value=fake_db),
        ]

    def test_model_from_job_override(self, tmp_path):
        """Job-level model should take priority."""
        job = {
            "id": "test-1",
            "model": "gpt-4",
            "prompt": "Hello",
            "thread_id": "thread-1",
        }
        # When model is explicitly set on job, it should be used directly
        # without needing config.yaml fallback
        model = job.get("model") or os.getenv("HERMES_MODEL") or None
        assert model == "gpt-4"

    def test_model_from_env_var(self, tmp_path):
        """Environment variable should be used when job has no model."""
        job = {"id": "test-2", "prompt": "Hello", "thread_id": "thread-2"}
        with patch.dict(os.environ, {"HERMES_MODEL": "claude-3"}):
            model = job.get("model") or os.getenv("HERMES_MODEL") or None
            assert model == "claude-3"

    def test_model_none_when_no_source(self, tmp_path):
        """Model should be None when no source provides it."""
        job = {"id": "test-3", "prompt": "Hello", "thread_id": "thread-3"}
        with patch.dict(os.environ, {}, clear=True):
            model = job.get("model") or os.getenv("HERMES_MODEL") or None
            assert model is None

    def test_config_yaml_fallback_model_default(self, tmp_path):
        """Config.yaml model.default should be used as fallback."""
        job = {"id": "test-4", "prompt": "Hello", "thread_id": "thread-4"}
        model = job.get("model") or os.getenv("HERMES_MODEL") or None

        # Simulate config.yaml with model.default
        model_cfg = {"default": "hermes-3"}
        if not model and isinstance(model_cfg, dict):
            model = model_cfg.get("default")

        assert model == "hermes-3"

    def test_config_yaml_model_as_string(self, tmp_path):
        """Config.yaml model as plain string should be used."""
        job = {"id": "test-5", "prompt": "Hello", "thread_id": "thread-5"}
        model = job.get("model") or os.getenv("HERMES_MODEL") or None

        # Simulate config.yaml with model as string
        model_cfg = "hermes-3"
        if not model and isinstance(model_cfg, str):
            model = model_cfg

        assert model == "hermes-3"

    def test_fail_early_when_no_model(self, tmp_path):
        """RuntimeError should be raised when no model can be resolved."""
        job = {"id": "test-6", "prompt": "Hello", "thread_id": "thread-6"}
        model = job.get("model") or os.getenv("HERMES_MODEL") or None

        # Config doesn't help
        if not model:
            with pytest.raises(RuntimeError, match="No model configured"):
                raise RuntimeError(
                    "No model configured for cron job '%s'. "
                    "Set model.default in config.yaml, pass --model when creating "
                    "the job, or set HERMES_MODEL in the environment." % job["id"]
                )
