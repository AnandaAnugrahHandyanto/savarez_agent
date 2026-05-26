"""Tests for startup reconciliation of orphan sandboxes (#28807).

The idle reaper in ``tools.terminal_tool`` only knows about envs in this
process's ``_active_environments`` dict.  ``reconcile_orphan_sandboxes``
sweeps the actual backend listings on gateway startup and reaps any
``hermes-*`` sandbox that isn't tracked here.
"""

from __future__ import annotations

import subprocess
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

from tools import terminal_tool


def _completed(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


def test_reconcile_docker_reaps_unknown_containers():
    """Docker containers not tracked in-process should be removed."""
    calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        if "ps" in cmd:
            return _completed(stdout="hermes-abc12345\nhermes-def67890\n")
        return _completed()

    with patch.object(terminal_tool, "_active_environments", {}), \
         patch("tools.environments.docker.find_docker", return_value="/usr/bin/docker"), \
         patch.object(terminal_tool.subprocess, "run", side_effect=fake_run):
        reaped = terminal_tool.reconcile_orphan_sandboxes()

    assert reaped.get("docker") == 2
    # Both names should have been `docker rm -f`'d
    rm_targets = [c[-1] for c in calls if "rm" in c]
    assert "hermes-abc12345" in rm_targets
    assert "hermes-def67890" in rm_targets


def test_reconcile_docker_skips_in_process_containers():
    """A container whose id matches an in-process env must NOT be reaped."""

    # The tracked env reports a container id; reconcile lists it by name. We
    # also list a separately-named orphan that must be reaped.
    tracked_env = SimpleNamespace(_container_id="hermes-live9999")

    def fake_run(cmd, **kw):
        if "ps" in cmd:
            # docker ps prints names — our tracked container surfaces as
            # "hermes-live9999" (we stuff that into _container_id for the test).
            return _completed(stdout="hermes-live9999\nhermes-orphan01\n")
        return _completed()

    with patch.object(terminal_tool, "_active_environments", {"t1": tracked_env}), \
         patch("tools.environments.docker.find_docker", return_value="/usr/bin/docker"), \
         patch.object(terminal_tool.subprocess, "run", side_effect=fake_run) as m:
        reaped = terminal_tool.reconcile_orphan_sandboxes()

    assert reaped.get("docker") == 1
    rm_targets = [list(c.args[0])[-1] for c in m.call_args_list
                  if "rm" in list(c.args[0])]
    assert rm_targets == ["hermes-orphan01"]


def test_reconcile_docker_no_op_when_docker_missing():
    """No docker binary → docker branch is skipped silently."""
    with patch.object(terminal_tool, "_active_environments", {}), \
         patch("tools.environments.docker.find_docker", return_value=None), \
         patch.object(terminal_tool.subprocess, "run") as m:
        reaped = terminal_tool.reconcile_orphan_sandboxes()
    assert "docker" not in reaped
    m.assert_not_called()


def test_reconcile_daytona_reaps_orphans(monkeypatch):
    """Daytona sandboxes whose ids aren't tracked must be deleted."""
    monkeypatch.setenv("DAYTONA_API_KEY", "test-key")

    sb_orphan = SimpleNamespace(id="sb-orphan", name="hermes-task-x")
    sb_live = SimpleNamespace(id="sb-live", name="hermes-task-y")
    sb_other = SimpleNamespace(id="sb-other", name="not-hermes")

    fake_client = MagicMock()
    fake_client.list.return_value = [sb_orphan, sb_live, sb_other]

    fake_daytona_mod = SimpleNamespace(Daytona=MagicMock(return_value=fake_client))

    tracked = SimpleNamespace(_sandbox=SimpleNamespace(id="sb-live"))

    monkeypatch.setitem(__import__("sys").modules, "daytona", fake_daytona_mod)

    # Make the docker sweep a no-op so we isolate daytona behavior.
    with patch("tools.environments.docker.find_docker", return_value=None), \
         patch.object(terminal_tool, "_active_environments", {"t": tracked}):
        reaped = terminal_tool.reconcile_orphan_sandboxes()

    assert reaped.get("daytona") == 1
    fake_client.delete.assert_called_once_with(sb_orphan)


def test_reconcile_swallows_backend_errors():
    """A crashing backend sweep must not bubble out of reconcile."""

    def boom(cmd, **kw):
        raise RuntimeError("docker daemon down")

    with patch.object(terminal_tool, "_active_environments", {}), \
         patch("tools.environments.docker.find_docker", return_value="/usr/bin/docker"), \
         patch.object(terminal_tool.subprocess, "run", side_effect=boom):
        # Must not raise.
        reaped = terminal_tool.reconcile_orphan_sandboxes()
    assert reaped == {} or "docker" not in reaped
