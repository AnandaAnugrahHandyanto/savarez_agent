"""Tests for tools.env_passthrough — skill and config env var passthrough."""

import os
import pytest
import yaml

import tools.env_passthrough as _ep_mod
from tools.env_passthrough import (
    clear_env_passthrough,
    get_all_passthrough,
    is_env_passthrough,
    register_env_passthrough,
)


@pytest.fixture(autouse=True)
def _clean_passthrough():
    """Ensure a clean passthrough state for every test."""
    clear_env_passthrough()
    _ep_mod._config_passthrough = None
    yield
    clear_env_passthrough()
    _ep_mod._config_passthrough = None


class TestSkillScopedPassthrough:
    def test_register_and_check(self):
        assert not is_env_passthrough("TENOR_API_KEY")
        register_env_passthrough(["TENOR_API_KEY"])
        assert is_env_passthrough("TENOR_API_KEY")

    def test_register_multiple(self):
        register_env_passthrough(["FOO_TOKEN", "BAR_SECRET"])
        assert is_env_passthrough("FOO_TOKEN")
        assert is_env_passthrough("BAR_SECRET")
        assert not is_env_passthrough("OTHER_KEY")

    def test_clear(self):
        register_env_passthrough(["TENOR_API_KEY"])
        assert is_env_passthrough("TENOR_API_KEY")
        clear_env_passthrough()
        assert not is_env_passthrough("TENOR_API_KEY")

    def test_get_all(self):
        register_env_passthrough(["A_KEY", "B_TOKEN"])
        result = get_all_passthrough()
        assert "A_KEY" in result
        assert "B_TOKEN" in result

    def test_strips_whitespace(self):
        register_env_passthrough(["  SPACED_KEY  "])
        assert is_env_passthrough("SPACED_KEY")

    def test_skips_empty(self):
        register_env_passthrough(["", "  ", "VALID_KEY"])
        assert is_env_passthrough("VALID_KEY")
        assert not is_env_passthrough("")


class TestConfigPassthrough:
    def test_reads_from_config(self, tmp_path, monkeypatch):
        config = {"terminal": {"env_passthrough": [
            "MY_CUSTOM_KEY", "ANOTHER_TOKEN",
        ]}}
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(config))
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _ep_mod._config_passthrough = None

        assert is_env_passthrough("MY_CUSTOM_KEY")
        assert is_env_passthrough("ANOTHER_TOKEN")
        assert not is_env_passthrough("UNRELATED_VAR")

    def test_empty_config(self, tmp_path, monkeypatch):
        config = {"terminal": {"env_passthrough": []}}
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(config))
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _ep_mod._config_passthrough = None

        assert not is_env_passthrough("ANYTHING")

    def test_missing_config_key(self, tmp_path, monkeypatch):
        config = {"terminal": {"backend": "local"}}
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(config))
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _ep_mod._config_passthrough = None

        assert not is_env_passthrough("ANYTHING")

    def test_no_config_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _ep_mod._config_passthrough = None

        assert not is_env_passthrough("ANYTHING")

    def test_union_of_skill_and_config(self, tmp_path, monkeypatch):
        config = {"terminal": {"env_passthrough": ["CONFIG_KEY"]}}
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(config))
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _ep_mod._config_passthrough = None

        register_env_passthrough(["SKILL_KEY"])
        all_pt = get_all_passthrough()
        assert "CONFIG_KEY" in all_pt
        assert "SKILL_KEY" in all_pt


class TestExecuteCodeIntegration:
    """Verify the passthrough is checked in execute_code's env filtering."""

    def test_secret_substring_blocked_by_default(self):
        """TENOR_API_KEY should be blocked without passthrough."""
        _SAFE_ENV_PREFIXES = (
            "PATH", "HOME", "USER", "LANG", "LC_", "TERM",
            "TMPDIR", "TMP", "TEMP", "SHELL", "LOGNAME",
            "XDG_", "PYTHONPATH", "VIRTUAL_ENV", "CONDA",
        )
        _SECRET_SUBSTRINGS = (
            "KEY", "TOKEN", "SECRET", "PASSWORD",
            "CREDENTIAL", "PASSWD", "AUTH",
        )

        test_env = {
            "PATH": "/usr/bin",
            "TENOR_API_KEY": "test123",
            "HOME": "/home/user",
        }
        child_env = {}
        for k, v in test_env.items():
            if is_env_passthrough(k):
                child_env[k] = v
                continue
            if any(s in k.upper() for s in _SECRET_SUBSTRINGS):
                continue
            if any(k.startswith(p) for p in _SAFE_ENV_PREFIXES):
                child_env[k] = v

        assert "PATH" in child_env
        assert "HOME" in child_env
        assert "TENOR_API_KEY" not in child_env

    def test_passthrough_allows_secret_through(self):
        """TENOR_API_KEY should pass through when registered."""
        _SAFE_ENV_PREFIXES = (
            "PATH", "HOME", "USER", "LANG", "LC_", "TERM",
            "TMPDIR", "TMP", "TEMP", "SHELL", "LOGNAME",
            "XDG_", "PYTHONPATH", "VIRTUAL_ENV", "CONDA",
        )
        _SECRET_SUBSTRINGS = (
            "KEY", "TOKEN", "SECRET", "PASSWORD",
            "CREDENTIAL", "PASSWD", "AUTH",
        )

        register_env_passthrough(["TENOR_API_KEY"])

        test_env = {
            "PATH": "/usr/bin",
            "TENOR_API_KEY": "test123",
            "HOME": "/home/user",
        }
        child_env = {}
        for k, v in test_env.items():
            if is_env_passthrough(k):
                child_env[k] = v
                continue
            if any(s in k.upper() for s in _SECRET_SUBSTRINGS):
                continue
            if any(k.startswith(p) for p in _SAFE_ENV_PREFIXES):
                child_env[k] = v

        assert "PATH" in child_env
        assert "HOME" in child_env
        assert "TENOR_API_KEY" in child_env
        assert child_env["TENOR_API_KEY"] == "test123"


class TestTerminalIntegration:
    """Verify that the passthrough is checked in terminal's env sanitizers."""

    def test_blocklisted_var_blocked_by_default(self):
        from tools.environments.local import (
            _sanitize_subprocess_env,
            _HERMES_PROVIDER_ENV_BLOCKLIST,
        )

        # Pick a var we know is in the blocklist
        blocked_var = next(iter(_HERMES_PROVIDER_ENV_BLOCKLIST))
        env = {blocked_var: "secret_value", "PATH": "/usr/bin"}
        result = _sanitize_subprocess_env(env)
        assert blocked_var not in result
        assert "PATH" in result

    def test_passthrough_cannot_override_provider_blocklist(self):
        """GHSA-rhgp-j443-p4rf: register_env_passthrough must NOT accept
        Hermes provider credentials — that was the bypass where a skill
        could declare ANTHROPIC_TOKEN / OPENAI_API_KEY as passthrough and
        defeat the execute_code sandbox scrubbing."""
        from tools.environments.local import (
            _sanitize_subprocess_env,
            _HERMES_PROVIDER_ENV_BLOCKLIST,
        )

        blocked_var = next(iter(_HERMES_PROVIDER_ENV_BLOCKLIST))
        # Attempt to register — must be silently refused (logged warning).
        register_env_passthrough([blocked_var])

        # is_env_passthrough must NOT report it as allowed
        assert not is_env_passthrough(blocked_var)

        # Sanitizer still strips the var from subprocess env
        env = {blocked_var: "secret_value", "PATH": "/usr/bin"}
        result = _sanitize_subprocess_env(env)
        assert blocked_var not in result
        assert "PATH" in result

    def test_make_run_env_blocklist_override_rejected(self):
        """_make_run_env must NOT expose a blocklisted var to subprocess env
        even after a skill attempts to register it via passthrough."""
        from tools.environments.local import (
            _make_run_env,
            _HERMES_PROVIDER_ENV_BLOCKLIST,
        )

        blocked_var = next(iter(_HERMES_PROVIDER_ENV_BLOCKLIST))
        os.environ[blocked_var] = "secret_value"
        try:
            # Without passthrough — blocked
            result_before = _make_run_env({})
            assert blocked_var not in result_before

            # Skill tries to register it — must be refused, so still blocked
            register_env_passthrough([blocked_var])
            result_after = _make_run_env({})
            assert blocked_var not in result_after
        finally:
            os.environ.pop(blocked_var, None)

    def test_non_hermes_api_key_still_registerable(self):
        """Third-party API keys (TENOR_API_KEY, NOTION_TOKEN, etc.) are NOT
        Hermes provider credentials and must still pass through — skills
        that legitimately wrap third-party APIs must keep working."""
        # TENOR_API_KEY is a real example — used by the gif-search skill
        register_env_passthrough(["TENOR_API_KEY"])
        assert is_env_passthrough("TENOR_API_KEY")

        # Arbitrary skill-specific var
        register_env_passthrough(["MY_SKILL_CUSTOM_CONFIG"])
        assert is_env_passthrough("MY_SKILL_CUSTOM_CONFIG")


class TestFallbackBlocklistOnImportError:
    """Verify fail-closed behaviour when tools.environments.local is unavailable.

    Simulates an ImportError from the blocklist module and checks that
    _is_hermes_provider_credential() falls back to the hardcoded minimum
    blocklist rather than returning False (the old fail-open bug).
    """

    def _make_import_error_patcher(self, monkeypatch):
        """Return a side_effect callable that raises ImportError for local.py."""
        import builtins
        real_import = builtins.__import__

        def _patched_import(name, *args, **kwargs):
            if name == "tools.environments.local":
                raise ImportError("simulated missing module")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _patched_import)

    def test_anthropic_credential_blocked_on_import_error(self, monkeypatch):
        """ANTHROPIC_TOKEN must be blocked even if local.py fails to import."""
        self._make_import_error_patcher(monkeypatch)
        from tools.env_passthrough import _is_hermes_provider_credential
        assert _is_hermes_provider_credential("ANTHROPIC_TOKEN") is True
        assert _is_hermes_provider_credential("ANTHROPIC_API_KEY") is True

    def test_openai_credential_blocked_on_import_error(self, monkeypatch):
        """OPENAI_API_KEY must be blocked even if local.py fails to import."""
        self._make_import_error_patcher(monkeypatch)
        from tools.env_passthrough import _is_hermes_provider_credential
        assert _is_hermes_provider_credential("OPENAI_API_KEY") is True
        assert _is_hermes_provider_credential("OPENAI_BASE_URL") is True

    def test_exact_match_credentials_blocked_on_import_error(self, monkeypatch):
        """Exact-match entries in the fallback list must be blocked."""
        self._make_import_error_patcher(monkeypatch)
        from tools.env_passthrough import _is_hermes_provider_credential
        for var in ("GH_TOKEN", "HASS_TOKEN", "EMAIL_PASSWORD",
                    "LLM_MODEL", "FIRECRAWL_API_KEY", "DAYTONA_API_KEY"):
            assert _is_hermes_provider_credential(var) is True, (
                f"{var} should be blocked by fallback exact list"
            )

    def test_third_party_key_not_blocked_on_import_error(self, monkeypatch):
        """TENOR_API_KEY is not a Hermes provider credential and must NOT be
        blocked by the fallback list — skill third-party API keys must still work."""
        self._make_import_error_patcher(monkeypatch)
        from tools.env_passthrough import _is_hermes_provider_credential
        assert _is_hermes_provider_credential("TENOR_API_KEY") is False
        assert _is_hermes_provider_credential("NOTION_TOKEN") is False
        assert _is_hermes_provider_credential("MY_SKILL_VAR") is False

    def test_register_env_passthrough_blocked_on_import_error(self, monkeypatch):
        """register_env_passthrough must refuse Hermes credentials even when
        the blocklist module import fails (end-to-end fail-closed check)."""
        self._make_import_error_patcher(monkeypatch)
        register_env_passthrough(["ANTHROPIC_TOKEN", "OPENAI_API_KEY"])
        assert not is_env_passthrough("ANTHROPIC_TOKEN")
        assert not is_env_passthrough("OPENAI_API_KEY")

    def test_third_party_still_registers_on_import_error(self, monkeypatch):
        """Non-Hermes keys must still register successfully via passthrough
        even when the blocklist module import fails."""
        self._make_import_error_patcher(monkeypatch)
        register_env_passthrough(["TENOR_API_KEY"])
        assert is_env_passthrough("TENOR_API_KEY")
