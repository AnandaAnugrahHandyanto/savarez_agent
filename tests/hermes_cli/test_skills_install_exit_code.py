"""
Regression coverage for issue #30631.

`hermes skills install <unresolvable>` used to print a friendly "no match"
message to stdout and then exit 0 — silently breaking shell chains like
``hermes skills install foo && hermes skills run foo`` and bulk-install
loops that rely on the exit code to detect typos.

These tests pin three behaviours:

* ``do_install`` returns a non-zero int when the identifier cannot be
  resolved or fetched.
* The CLI argparse path (``cmd_skills``) propagates that int to the process
  exit via ``sys.exit``.
* Successful and "already-installed" paths still exit 0.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from hermes_cli.skills_hub import do_install


class _FakeSource:
    """Minimal source-router stand-in: no skills exist."""

    is_rate_limited = False

    def __init__(self):
        self.github = None

    def inspect(self, identifier):  # noqa: ARG002
        return None

    def fetch(self, identifier):  # noqa: ARG002
        return None


@patch("tools.skills_hub.create_source_router", return_value=[_FakeSource()])
@patch("tools.skills_hub.GitHubAuth", return_value=MagicMock())
@patch("tools.skills_hub.ensure_hub_dirs")
@patch("tools.skills_hub.unified_search", return_value=[])
def test_do_install_returns_nonzero_when_identifier_unresolvable(
    _unified, _ensure, _auth, _router
):
    """Short name with no search hits → exit code 1."""
    rc = do_install("definitely-not-a-real-skill-zzz", skip_confirm=True)
    assert rc == 1


@patch("tools.skills_hub.create_source_router", return_value=[_FakeSource()])
@patch("tools.skills_hub.GitHubAuth", return_value=MagicMock())
@patch("tools.skills_hub.ensure_hub_dirs")
def test_do_install_returns_nonzero_when_fetch_fails(_ensure, _auth, _router):
    """Fully-qualified identifier that no source can fetch → exit code 1."""
    rc = do_install("official/email/does-not-exist", skip_confirm=True)
    assert rc == 1


def test_cli_skills_install_exits_nonzero_on_resolution_failure(monkeypatch):
    """End-to-end: the CLI surfaces the non-zero exit code to the process."""
    from hermes_cli.main import main

    # Stub the inner command so we don't hit the real network / GitHub API.
    def fake_skills_command(args):  # noqa: ARG001
        return 1

    monkeypatch.setattr("hermes_cli.skills_hub.skills_command", fake_skills_command)
    monkeypatch.setattr(
        sys,
        "argv",
        ["hermes", "skills", "install", "definitely-not-a-real-skill-zzz", "--yes"],
    )

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1


def test_cli_skills_install_exits_zero_on_success(monkeypatch):
    """A successful install must not blow up with SystemExit(0) noise."""
    from hermes_cli.main import main

    def fake_skills_command(args):  # noqa: ARG001
        return 0

    monkeypatch.setattr("hermes_cli.skills_hub.skills_command", fake_skills_command)
    monkeypatch.setattr(
        sys,
        "argv",
        ["hermes", "skills", "install", "official/email/agentmail", "--yes"],
    )

    # Should not raise SystemExit.
    main()


def test_cli_skills_install_handles_none_return(monkeypatch):
    """Defensive: legacy stubs returning None still treated as success."""
    from hermes_cli.main import main

    def fake_skills_command(args):  # noqa: ARG001
        return None

    monkeypatch.setattr("hermes_cli.skills_hub.skills_command", fake_skills_command)
    monkeypatch.setattr(
        sys,
        "argv",
        ["hermes", "skills", "install", "test/skill"],
    )

    # Should not raise SystemExit.
    main()
