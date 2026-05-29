"""Tests for ``agent.secret_sources.protonpass.session``.

Session establishment (login -> info, with a logout/relogin recovery), the
minimal/scrubbed child env (no inherited secrets, A3), the token-fingerprinted
isolated session dir (A7), the ANSI/CSI stream cleaner, and token redaction.
The token is NEVER logged, stored, or surfaced in a warning/raised message.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests._protonpass_helpers import (  # noqa: F401
    _fail,
    _ok,
    _reset_caches,
    _session_runner,
    hermes_home,
    pp_session,
)


# ---------------------------------------------------------------------------
# Session establishment helpers (login → info; logout+retry; redaction)
# ---------------------------------------------------------------------------


def test_session_login_then_info_success(hermes_home, monkeypatch, tmp_path):
    binary = tmp_path / "pass-cli"
    binary.write_text("", encoding="utf-8")
    calls = []
    _session_runner(monkeypatch, {"login": [_ok()], "info": [_ok()]}, calls=calls)

    warnings = pp_session._establish_session("svc-token", binary)
    assert warnings == []
    verbs = [c[0][1] for c in calls]
    assert verbs == ["login", "info"]
    # Child env carries the token + isolated session dir, never logs it.
    env = calls[0][1]
    assert env["PROTON_PASS_PERSONAL_ACCESS_TOKEN"] == "svc-token"
    # A7: the session dir is suffixed with the token fingerprint, so the path is
    # ``.../protonpass-session-<fp>`` (NOT the bare base name).
    assert "protonpass-session" in env["PROTON_PASS_SESSION_DIR"]
    # The raw token must never leak into the session-dir path.
    assert "svc-token" not in env["PROTON_PASS_SESSION_DIR"]


def test_session_recovery_logout_retry(hermes_home, monkeypatch, tmp_path):
    binary = tmp_path / "pass-cli"
    binary.write_text("", encoding="utf-8")
    calls = []
    # First login fails; after logout, second login + info succeed.
    _session_runner(
        monkeypatch,
        {
            "login": [_fail("auth bad"), _ok()],
            "info": [_ok()],
            "logout": [_ok()],
        },
        calls=calls,
    )

    warnings = pp_session._establish_session("svc-token", binary)
    assert any("recovered" in w for w in warnings)
    verbs = [c[0][1] for c in calls]
    assert "logout" in verbs


def test_session_failure_redacts_token(hermes_home, monkeypatch, tmp_path):
    binary = tmp_path / "pass-cli"
    binary.write_text("", encoding="utf-8")
    token = "super-secret-token-value"
    _session_runner(
        monkeypatch,
        {"login": [_fail(token), _fail(token)], "logout": [_ok()]},
    )

    with pytest.raises(RuntimeError) as exc:
        pp_session._establish_session(token, binary)
    # The token value must never appear in the raised message.
    assert token not in str(exc.value)


def test_session_failure_surfaces_redacted_stderr(hermes_home, monkeypatch, tmp_path):
    """A8: the final RuntimeError carries a redacted, ANSI-stripped login stderr
    (the token is scrubbed) to aid debugging."""
    binary = tmp_path / "pass-cli"
    binary.write_text("", encoding="utf-8")
    token = "tok-value"
    _session_runner(
        monkeypatch,
        {
            "login": [_fail("\x1b[31minvalid credentials\x1b[0m"),
                      _fail("\x1b[31minvalid credentials\x1b[0m")],
            "logout": [_ok()],
        },
    )

    with pytest.raises(RuntimeError) as exc:
        pp_session._establish_session(token, binary)
    msg = str(exc.value)
    assert "invalid credentials" in msg  # surfaced
    assert "\x1b[" not in msg  # ANSI stripped
    assert token not in msg  # token never present


def test_session_login_failure_detail_uses_stderr_only(hermes_home, monkeypatch, tmp_path):
    """C7: ``_try_login_and_verify`` surfaces ONLY login stderr on failure (the
    ``or login.stdout`` fallback was dropped for consistency with the
    stderr-only secret-command rule)."""
    binary = tmp_path / "pass-cli"
    binary.write_text("", encoding="utf-8")
    # login fails with content ONLY on stdout; stderr is empty.
    login_fail = __import__("unittest").mock.Mock(
        returncode=1, stdout="DETAIL-ON-STDOUT", stderr=""
    )

    def fake_run(cmd, env):
        verb = cmd[1] if len(cmd) > 1 else cmd[-1]
        if verb == "login":
            return login_fail
        return _ok()

    monkeypatch.setattr(pp_session, "_run_pass_cli", fake_run)

    ok, detail = pp_session._try_login_and_verify(binary, {"E": "1"})
    assert ok is False
    # stdout is NOT used as the detail fallback.
    assert detail == ""
    assert "DETAIL-ON-STDOUT" not in detail


def test_run_pass_cli_uses_errors_replace(monkeypatch):
    """C7: ``_run_pass_cli`` passes ``errors='replace'`` so invalid UTF-8 in a
    pass-cli stream can't raise a decode error."""
    captured = {}

    def fake_run(cmd, *, env, capture_output, text, errors, timeout):
        captured["errors"] = errors
        captured["text"] = text
        return __import__("unittest").mock.Mock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pp_session.subprocess, "run", fake_run)
    pp_session._run_pass_cli(["pass-cli", "info"], {"E": "1"})
    assert captured["errors"] == "replace"
    assert captured["text"] is True


# ---------------------------------------------------------------------------
# minimal/scrubbed child env (A3): no inherited secrets
# ---------------------------------------------------------------------------


def test_minimal_env_has_no_token_or_secrets(monkeypatch):
    monkeypatch.setenv("PROTON_PASS_PERSONAL_ACCESS_TOKEN", "leak-me")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-leak")
    monkeypatch.setenv("PATH", "/usr/bin")

    env = pp_session._minimal_env()
    assert "PROTON_PASS_PERSONAL_ACCESS_TOKEN" not in env
    assert "OPENAI_API_KEY" not in env
    assert env.get("NO_COLOR") == "1"
    assert env.get("PATH") == "/usr/bin"  # ambient PATH is carried


def test_child_env_adds_only_protonpass_vars(hermes_home, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-leak")
    env = pp_session._child_env("svc-token")
    assert env["PROTON_PASS_PERSONAL_ACCESS_TOKEN"] == "svc-token"
    assert env["PROTON_PASS_SESSION_DIR"]
    assert env["PROTON_PASS_AGENT_REASON"]
    # No other secret made it into the child env.
    assert "OPENAI_API_KEY" not in env


# ---------------------------------------------------------------------------
# A7: session-dir creation/chmod failure -> skip Proton Pass (RuntimeError)
# ---------------------------------------------------------------------------


def test_child_env_raises_when_session_dir_cannot_be_secured(hermes_home, monkeypatch):
    """A7: if the isolated session dir can't be created/locked to 0o700, we
    RAISE (don't continue with unverifiable session storage)."""
    def boom_chmod(path, mode):
        raise OSError("cannot chmod")

    monkeypatch.setattr(pp_session.os, "chmod", boom_chmod)

    with pytest.raises(RuntimeError, match="session directory"):
        pp_session._child_env("svc-token")


def test_session_dir_is_token_fingerprinted(hermes_home):
    """A7 (nice): two different tokens map to different session dirs.

    C7: the token-fingerprint suffix is now UNCONDITIONAL (the dead bare-path
    branch was removed), so every session dir carries a ``protonpass-session-<fp>``
    suffix and never the raw token."""
    a = pp_session._session_dir("token-A")
    b = pp_session._session_dir("token-B")
    assert a != b
    # The fingerprint, never the token, appears in the path.
    assert "token-A" not in str(a)
    assert pp_session._token_fingerprint("token-A") in str(a)
    assert a.name == f"protonpass-session-{pp_session._token_fingerprint('token-A')}"


def test_session_dir_suffix_unconditional(hermes_home):
    """C7: even a bare ``_session_dir()`` (empty token, not used by any real
    caller) carries the fingerprint suffix — the unsuffixed base path branch is
    gone, so the 'session isolation' claim always holds."""
    bare = pp_session._session_dir()
    assert bare.name == (
        f"protonpass-session-{pp_session._token_fingerprint('')}"
    )


def test_session_dir_created_0700(hermes_home):
    """A7: the per-token session dir is created and locked to 0o700."""
    env = pp_session._child_env("svc-token")
    session_dir = Path(env["PROTON_PASS_SESSION_DIR"])
    assert session_dir.exists()
    assert (os.stat(session_dir).st_mode & 0o777) == 0o700


# ---------------------------------------------------------------------------
# token fingerprint + stream cleaning + redaction
# ---------------------------------------------------------------------------


def test_token_fingerprint_is_stable_and_not_the_token():
    fp = pp_session._token_fingerprint("svc-token")
    assert fp == pp_session._token_fingerprint("svc-token")  # stable
    assert "svc-token" not in fp
    assert len(fp) == 16


def test_clean_stream_full_csi_strip():
    # A full CSI sequence (colour codes) must be stripped, not just the ESC byte.
    raw = "\x1b[31merror\x1b[0m: \x1b[1;33mboom\x1b[0m"
    assert pp_session._clean_stream(raw) == "error: boom"


def test_clean_stream_handles_empty():
    assert pp_session._clean_stream("") == ""
    assert pp_session._clean_stream(None) == ""


def test_redact_token_replaces_all_occurrences():
    out = pp_session._redact_token("a tok b tok c", "tok")
    assert "tok" not in out.replace("***REDACTED***", "")
    assert pp_session._redact_token("anything", "") == "anything"
