"""Hermetic tests for the Proton Pass integration.

Subprocess + urllib are mocked -- no network calls.  The "live" pull
and binary install are exercised manually by `hermes secrets protonpass
setup` outside of pytest.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.secret_sources import protonpass as pp  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_caches():
    pp._reset_cache_for_tests()
    yield
    pp._reset_cache_for_tests()


@pytest.fixture
def hermes_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    import hermes_constants
    if hasattr(hermes_constants, "_HERMES_HOME_CACHE"):
        hermes_constants._HERMES_HOME_CACHE = None  # type: ignore[attr-defined]
    return home


# ---------------------------------------------------------------------------
# find_passcli
# ---------------------------------------------------------------------------


def test_find_passcli_managed_copy(tmp_path, monkeypatch):
    binary = tmp_path / "bin" / "pass-cli"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\necho ok")
    binary.chmod(0o755)
    monkeypatch.setattr(pp, "_hermes_bin_dir", lambda: tmp_path / "bin")
    assert pp.find_passcli() == binary


def test_find_passcli_system_path(monkeypatch, tmp_path):
    monkeypatch.setattr(pp, "_hermes_bin_dir", lambda: tmp_path / "nope")
    fake = tmp_path / "usr" / "bin" / "pass-cli"
    fake.parent.mkdir(parents=True)
    fake.write_text("#!/bin/sh\necho ok")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake.parent))
    assert pp.find_passcli() == fake


def test_find_passcli_not_found(monkeypatch, tmp_path):
    monkeypatch.setattr(pp, "_hermes_bin_dir", lambda: tmp_path / "nope")
    monkeypatch.setenv("PATH", "")
    assert pp.find_passcli() is None


def test_find_passcli_install_on_demand(monkeypatch, tmp_path):
    monkeypatch.setattr(pp, "_hermes_bin_dir", lambda: tmp_path / "nope")
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(pp, "install_passcli", lambda **kw: tmp_path / "bin" / "pass-cli")
    assert pp.find_passcli(install_if_missing=True) == tmp_path / "bin" / "pass-cli"


def test_find_passcli_install_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(pp, "_hermes_bin_dir", lambda: tmp_path / "nope")
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(pp, "install_passcli", lambda **kw: (_ for _ in ()).throw(RuntimeError("fail")))
    assert pp.find_passcli(install_if_missing=True) is None


# ---------------------------------------------------------------------------
# _is_valid_env_name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,expected", [
    ("OPENAI_API_KEY", True), ("_UNDERSCORE", True), ("A1", True),
    ("1BAD", False), ("HAS SPACE", False), ("DASH-KEY", False),
    ("", False), ("valid_NAME_123", True),
])
def test_is_valid_env_name(name, expected):
    assert pp._is_valid_env_name(name) == expected


# ---------------------------------------------------------------------------
# fetch_protonpass_secrets
# ---------------------------------------------------------------------------


def _list_json(items):
    return json.dumps(items)


def _view_json(value):
    return json.dumps({"value": value})


def test_fetch_happy_path(monkeypatch, tmp_path):
    fake = tmp_path / "pass-cli"
    fake.write_text("")
    list_out = _list_json([
        {"title": "OPENAI_API_KEY", "itemId": "i1", "shareId": "s1"},
        {"title": "ANTHROPIC_API_KEY", "itemId": "i2", "shareId": "s1"},
    ])
    values = {"OPENAI_API_KEY": "sk-abc", "ANTHROPIC_API_KEY": "sk-ant-xyz"}

    def fake_run(cmd, **kw):
        if "list" in cmd:
            return mock.Mock(returncode=0, stdout=list_out, stderr="")
        if "view" in cmd:
            t = cmd[cmd.index("--item-title") + 1]
            return mock.Mock(returncode=0, stdout=_view_json(values[t]), stderr="")
        return mock.Mock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    secrets, warnings = pp.fetch_protonpass_secrets(
        access_token="pst_fake", vault_name="Hermes", binary=fake, use_cache=False,
    )
    assert secrets == {"OPENAI_API_KEY": "sk-abc", "ANTHROPIC_API_KEY": "sk-ant-xyz"}
    assert warnings == []


def test_fetch_skips_invalid_env_names(monkeypatch, tmp_path):
    fake = tmp_path / "pass-cli"
    fake.write_text("")
    list_out = _list_json([
        {"title": "GOOD", "itemId": "i1", "shareId": "s1"},
        {"title": "1BAD", "itemId": "i2", "shareId": "s1"},
        {"title": "no spaces", "itemId": "i3", "shareId": "s1"},
    ])

    def fake_run(cmd, **kw):
        if "list" in cmd:
            return mock.Mock(returncode=0, stdout=list_out, stderr="")
        if "view" in cmd:
            return mock.Mock(returncode=0, stdout=_view_json("v"), stderr="")
        return mock.Mock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    secrets, warnings = pp.fetch_protonpass_secrets(
        access_token="pst_t", vault_name="Hermes", binary=fake, use_cache=False,
    )
    assert secrets == {"GOOD": "v"}
    assert len(warnings) == 2


def test_fetch_empty_vault(monkeypatch, tmp_path):
    fake = tmp_path / "pass-cli"
    fake.write_text("")

    def fake_run(cmd, **kw):
        if "list" in cmd:
            return mock.Mock(returncode=0, stdout="[]", stderr="")
        return mock.Mock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    secrets, warnings = pp.fetch_protonpass_secrets(
        access_token="pst_t", vault_name="Hermes", binary=fake, use_cache=False,
    )
    assert secrets == {}
    # Empty vault is not an error -- just no secrets
    assert warnings == []


def test_fetch_auth_failure(monkeypatch, tmp_path):
    fake = tmp_path / "pass-cli"
    fake.write_text("")

    def fake_run(cmd, **kw):
        if "list" in cmd:
            return mock.Mock(returncode=1, stdout="", stderr="Error: unauthorized")
        return mock.Mock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="unauthorized"):
        pp.fetch_protonpass_secrets(
            access_token="pst_bad", vault_name="Hermes", binary=fake, use_cache=False,
        )


def test_fetch_timeout(monkeypatch, tmp_path):
    fake = tmp_path / "pass-cli"
    fake.write_text("")

    def fake_run(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="pass-cli", timeout=30)

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="timed out"):
        pp.fetch_protonpass_secrets(
            access_token="pst_t", vault_name="Hermes", binary=fake, use_cache=False,
        )


def test_fetch_non_json(monkeypatch, tmp_path):
    fake = tmp_path / "pass-cli"
    fake.write_text("")

    def fake_run(cmd, **kw):
        if "list" in cmd:
            return mock.Mock(returncode=0, stdout="not json", stderr="")
        return mock.Mock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="non-JSON"):
        pp.fetch_protonpass_secrets(
            access_token="pst_t", vault_name="Hermes", binary=fake, use_cache=False,
        )


def test_fetch_cache_hit(monkeypatch, tmp_path):
    """Second call with same params returns cached result."""
    fake = tmp_path / "pass-cli"
    fake.write_text("")
    list_out = _list_json([{"title": "K", "itemId": "i1", "shareId": "s1"}])

    call_count = {"n": 0}

    def fake_run(cmd, **kw):
        call_count["n"] += 1
        if "list" in cmd:
            return mock.Mock(returncode=0, stdout=list_out, stderr="")
        if "view" in cmd:
            return mock.Mock(returncode=0, stdout=_view_json("v"), stderr="")
        return mock.Mock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    pp.fetch_protonpass_secrets(
        access_token="pst_t", vault_name="Hermes", binary=fake, cache_ttl_seconds=60,
    )
    first_count = call_count["n"]
    pp.fetch_protonpass_secrets(
        access_token="pst_t", vault_name="Hermes", binary=fake, cache_ttl_seconds=60,
    )
    # Second call should not make additional subprocess calls
    assert call_count["n"] == first_count


def test_fetch_cache_disabled(monkeypatch, tmp_path):
    fake = tmp_path / "pass-cli"
    fake.write_text("")

    call_count = {"n": 0}

    def fake_run(cmd, **kw):
        call_count["n"] += 1
        if "list" in cmd:
            return mock.Mock(returncode=0, stdout="[]", stderr="")
        return mock.Mock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    pp.fetch_protonpass_secrets(
        access_token="pst_t", vault_name="Hermes", binary=fake, use_cache=False,
    )
    pp.fetch_protonpass_secrets(
        access_token="pst_t", vault_name="Hermes", binary=fake, use_cache=False,
    )
    assert call_count["n"] >= 2


# ---------------------------------------------------------------------------
# _run_passcli -- env setup
# ---------------------------------------------------------------------------


def test_run_passcli_sets_env(monkeypatch, tmp_path):
    fake = tmp_path / "pass-cli"
    fake.write_text("")
    captured = {}

    def fake_run(cmd, **kw):
        captured.update(kw.get("env", {}))
        return mock.Mock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    pp._run_passcli(fake, ["info"], access_token="pst_test")
    assert captured["PROTON_PASS_PERSONAL_ACCESS_TOKEN"] == "pst_test"
    assert captured["PROTON_PASS_DISABLE_TELEMETRY"] == "1"
    assert captured["PROTON_PASS_KEY_PROVIDER"] == "fs"


def test_run_passcli_agent_reason(monkeypatch, tmp_path):
    fake = tmp_path / "pass-cli"
    fake.write_text("")
    captured = {}

    def fake_run(cmd, **kw):
        captured.update(kw.get("env", {}))
        return mock.Mock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    pp._run_passcli(fake, ["item", "view"], access_token="t", agent_reason="deploy")
    assert captured["PROTON_PASS_AGENT_REASON"] == "deploy"


# ---------------------------------------------------------------------------
# apply_protonpass_secrets
# ---------------------------------------------------------------------------


def test_apply_disabled():
    result = pp.apply_protonpass_secrets(enabled=False, vault_name="Hermes")
    assert result.ok and not result.applied


def test_apply_missing_token(monkeypatch):
    monkeypatch.delenv("PROTON_PASS_ACCESS_TOKEN", raising=False)
    result = pp.apply_protonpass_secrets(enabled=True, vault_name="Hermes", auto_install=False)
    assert not result.ok
    assert "PROTON_PASS_ACCESS_TOKEN" in (result.error or "")


def test_apply_missing_vault(monkeypatch):
    monkeypatch.setenv("PROTON_PASS_ACCESS_TOKEN", "pst_t")
    result = pp.apply_protonpass_secrets(enabled=True, vault_name="", auto_install=False)
    assert not result.ok
    assert "vault_name" in (result.error or "")


def test_apply_skip_existing(monkeypatch, tmp_path):
    monkeypatch.setenv("PROTON_PASS_ACCESS_TOKEN", "pst_t")
    monkeypatch.setenv("EXISTING", "old")
    fake = tmp_path / "pass-cli"
    fake.write_text("")
    list_out = _list_json([
        {"title": "EXISTING", "itemId": "i1", "shareId": "s1"},
        {"title": "NEW_KEY", "itemId": "i2", "shareId": "s1"},
    ])

    def fake_run(cmd, **kw):
        if "list" in cmd:
            return mock.Mock(returncode=0, stdout=list_out, stderr="")
        if "view" in cmd:
            t = cmd[cmd.index("--item-title") + 1]
            return mock.Mock(returncode=0, stdout=_view_json({"EXISTING": "new", "NEW_KEY": "fresh"}[t]), stderr="")
        return mock.Mock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    monkeypatch.setattr(pp, "find_passcli", lambda **kw: fake)

    result = pp.apply_protonpass_secrets(
        enabled=True, vault_name="Hermes", override_existing=False, auto_install=False,
    )
    assert result.ok
    assert "NEW_KEY" in result.applied
    assert "EXISTING" in result.skipped
    assert os.environ["EXISTING"] == "old"


def test_apply_override_existing(monkeypatch, tmp_path):
    monkeypatch.setenv("PROTON_PASS_ACCESS_TOKEN", "pst_t")
    monkeypatch.setenv("KEY", "stale")
    fake = tmp_path / "pass-cli"
    fake.write_text("")
    list_out = _list_json([{"title": "KEY", "itemId": "i1", "shareId": "s1"}])

    def fake_run(cmd, **kw):
        if "list" in cmd:
            return mock.Mock(returncode=0, stdout=list_out, stderr="")
        if "view" in cmd:
            return mock.Mock(returncode=0, stdout=_view_json("fresh"), stderr="")
        return mock.Mock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    monkeypatch.setattr(pp, "find_passcli", lambda **kw: fake)

    result = pp.apply_protonpass_secrets(
        enabled=True, vault_name="Hermes", override_existing=True, auto_install=False,
    )
    assert result.ok
    assert os.environ["KEY"] == "fresh"


def test_apply_never_overrides_bootstrap(monkeypatch, tmp_path):
    monkeypatch.setenv("PROTON_PASS_ACCESS_TOKEN", "pst_original")
    fake = tmp_path / "pass-cli"
    fake.write_text("")
    list_out = _list_json([{"title": "PROTON_PASS_ACCESS_TOKEN", "itemId": "i1", "shareId": "s1"}])

    def fake_run(cmd, **kw):
        if "list" in cmd:
            return mock.Mock(returncode=0, stdout=list_out, stderr="")
        if "view" in cmd:
            return mock.Mock(returncode=0, stdout=_view_json("pst_evil"), stderr="")
        return mock.Mock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    monkeypatch.setattr(pp, "find_passcli", lambda **kw: fake)

    result = pp.apply_protonpass_secrets(
        enabled=True, vault_name="Hermes", override_existing=True, auto_install=False,
    )
    assert os.environ["PROTON_PASS_ACCESS_TOKEN"] == "pst_original"
    assert "PROTON_PASS_ACCESS_TOKEN" in result.skipped


def test_apply_no_binary(monkeypatch):
    monkeypatch.setenv("PROTON_PASS_ACCESS_TOKEN", "pst_t")
    monkeypatch.setattr(pp, "find_passcli", lambda **kw: None)
    result = pp.apply_protonpass_secrets(enabled=True, vault_name="Hermes", auto_install=False)
    assert not result.ok
    assert "not found" in (result.error or "")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_fetch_empty_password(monkeypatch, tmp_path):
    """Items with empty view result are skipped with a warning."""
    fake = tmp_path / "pass-cli"
    fake.write_text("")
    list_out = _list_json([
        {"title": "GOOD", "itemId": "i1", "shareId": "s1"},
        {"title": "EMPTY", "itemId": "i2", "shareId": "s1"},
    ])

    def fake_run(cmd, **kw):
        if "list" in cmd:
            return mock.Mock(returncode=0, stdout=list_out, stderr="")
        if "view" in cmd:
            t = cmd[cmd.index("--item-title") + 1]
            val = _view_json("ok") if t == "GOOD" else ""
            return mock.Mock(returncode=0, stdout=val, stderr="")
        return mock.Mock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    secrets, warnings = pp.fetch_protonpass_secrets(
        access_token="pst_t", vault_name="Hermes", binary=fake, use_cache=False,
    )
    assert secrets == {"GOOD": "ok"}
    assert any("EMPTY" in w for w in warnings)


def test_fetch_duplicate_titles(monkeypatch, tmp_path):
    """Duplicate titles: last view call wins."""
    fake = tmp_path / "pass-cli"
    fake.write_text("")
    list_out = _list_json([
        {"title": "K", "itemId": "i1", "shareId": "s1"},
        {"title": "K", "itemId": "i2", "shareId": "s1"},
    ])

    call_n = {"n": 0}

    def fake_run(cmd, **kw):
        if "list" in cmd:
            return mock.Mock(returncode=0, stdout=list_out, stderr="")
        if "view" in cmd:
            call_n["n"] += 1
            return mock.Mock(returncode=0, stdout=_view_json("old" if call_n["n"] == 1 else "new"), stderr="")
        return mock.Mock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    secrets, _ = pp.fetch_protonpass_secrets(
        access_token="pst_t", vault_name="Hermes", binary=fake, use_cache=False,
    )
    assert secrets["K"] == "new"
    assert call_n["n"] == 2


def test_view_field_json_with_password_key(monkeypatch, tmp_path):
    fake = tmp_path / "pass-cli"
    fake.write_text("")

    def fake_run(cmd, **kw):
        return mock.Mock(returncode=0, stdout=json.dumps({"password": "pw"}), stderr="")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    assert pp._view_item_field(fake, "t", "v", "i", "password") == "pw"


def test_view_field_json_with_custom_key(monkeypatch, tmp_path):
    fake = tmp_path / "pass-cli"
    fake.write_text("")

    def fake_run(cmd, **kw):
        return mock.Mock(returncode=0, stdout=json.dumps({"api_token": "tok"}), stderr="")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    assert pp._view_item_field(fake, "t", "v", "i", "api_token") == "tok"


def test_view_field_plain_string(monkeypatch, tmp_path):
    fake = tmp_path / "pass-cli"
    fake.write_text("")

    def fake_run(cmd, **kw):
        return mock.Mock(returncode=0, stdout="raw-pw", stderr="")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    assert pp._view_item_field(fake, "t", "v", "i", "password") == "raw-pw"


def test_view_field_failure_returns_none(monkeypatch, tmp_path):
    fake = tmp_path / "pass-cli"
    fake.write_text("")

    def fake_run(cmd, **kw):
        return mock.Mock(returncode=1, stdout="", stderr="not found")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    assert pp._view_item_field(fake, "t", "v", "MISSING", "password") is None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_fetch_empty_token():
    with pytest.raises(RuntimeError, match="access token is empty"):
        pp.fetch_protonpass_secrets(access_token="", vault_name="Hermes", binary=Path("/x"), use_cache=False)


def test_fetch_empty_vault_name():
    with pytest.raises(RuntimeError, match="vault_name is empty"):
        pp.fetch_protonpass_secrets(access_token="pst_t", vault_name="", binary=Path("/x"), use_cache=False)


# ---------------------------------------------------------------------------
# Non-regression
# ---------------------------------------------------------------------------


def test_bitwarden_import_unchanged():
    from agent.secret_sources import bitwarden as bw
    for attr in ("apply_bitwarden_secrets", "fetch_bitwarden_secrets", "find_bws", "FetchResult"):
        assert hasattr(bw, attr)


def test_bitwarden_apply_disabled():
    from agent.secret_sources import bitwarden as bw
    result = bw.apply_bitwarden_secrets(enabled=False, project_id="p")
    assert result.ok and not result.applied


def test_env_loader_protonpass_label():
    from hermes_cli import env_loader
    env_loader._SECRET_SOURCES["T"] = "protonpass"
    try:
        assert env_loader.get_secret_source("T") == "protonpass"
        assert "Proton Pass" in env_loader.format_secret_source_suffix("T")
    finally:
        del env_loader._SECRET_SOURCES["T"]


def test_env_loader_bw_and_pp_coexist():
    from hermes_cli import env_loader
    env_loader._SECRET_SOURCES["A"] = "bitwarden"
    env_loader._SECRET_SOURCES["B"] = "protonpass"
    try:
        assert "Bitwarden" in env_loader.format_secret_source_suffix("A")
        assert "Proton Pass" in env_loader.format_secret_source_suffix("B")
    finally:
        del env_loader._SECRET_SOURCES["A"]
        del env_loader._SECRET_SOURCES["B"]
