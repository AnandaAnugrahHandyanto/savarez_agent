"""Regression test for issue #21275.

`gateway.run._load_gateway_config()` previously returned the raw YAML
verbatim, so `${VAR}` placeholders inside `custom_providers.base_url`,
model entries, etc. were never expanded. Callers down-stream
(`get_compatible_custom_providers`, hygiene worker, context-length
detection) then rejected the templated URLs as invalid.

The fix runs `hermes_cli.config._expand_env_vars` on the loaded dict
before returning.
"""

from pathlib import Path

import pytest

import gateway.run as gateway_run


@pytest.fixture
def fake_hermes_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point gateway.run at a throwaway HERMES_HOME with a config.yaml."""
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    return tmp_path


def _write_config(home: Path, body: str) -> None:
    (home / "config.yaml").write_text(body, encoding="utf-8")


def test_env_vars_expanded_in_custom_providers_base_url(
    fake_hermes_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARC_BASE_URL", "https://arc.example.com/v1")
    _write_config(
        fake_hermes_home,
        """
custom_providers:
  - name: arc
    base_url: ${ARC_BASE_URL}
""",
    )

    cfg = gateway_run._load_gateway_config()

    providers = cfg.get("custom_providers")
    assert isinstance(providers, list) and providers
    assert providers[0]["base_url"] == "https://arc.example.com/v1"


def test_env_vars_expanded_in_model_base_url(
    fake_hermes_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARC_BASE_URL", "https://arc.example.com/v1")
    _write_config(
        fake_hermes_home,
        """
model:
  default: glm-5.1
  base_url: ${ARC_BASE_URL}
""",
    )

    cfg = gateway_run._load_gateway_config()

    assert cfg["model"]["base_url"] == "https://arc.example.com/v1"


def test_undefined_env_var_left_as_template(
    fake_hermes_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the env var is unset, the placeholder must survive untouched
    so downstream validation can emit a clear "missing env" error rather
    than silently coercing it to an empty string."""
    monkeypatch.delenv("UNDEFINED_VAR_FOR_TEST", raising=False)
    _write_config(
        fake_hermes_home,
        """
custom_providers:
  - name: arc
    base_url: ${UNDEFINED_VAR_FOR_TEST}
""",
    )

    cfg = gateway_run._load_gateway_config()

    assert cfg["custom_providers"][0]["base_url"] == "${UNDEFINED_VAR_FOR_TEST}"


def test_missing_config_returns_empty_dict(fake_hermes_home: Path) -> None:
    cfg = gateway_run._load_gateway_config()
    assert cfg == {}
