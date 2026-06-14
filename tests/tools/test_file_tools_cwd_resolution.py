"""Regression tests for file-tool path resolution base correctness.

The bug (observed in a worktree dev session, May 2026): when the resolution
base for a relative path is itself RELATIVE — e.g. ``TERMINAL_CWD="."`` from a
stale config — ``_resolve_path_for_task`` resolved the path against the agent's
PROCESS cwd instead of the intended workspace. In a git-worktree session this
silently routed ``patch``/``write_file`` edits into the *main* checkout: the
write landed, self-verified, and reported success — against the wrong file.
The agent then grepped the worktree, saw nothing, and concluded the patch tool
had silently no-op'd. It hadn't; it wrote to the wrong place.

Core invariant these tests pin:
  The resolution base for a relative path MUST always be absolute. A relative
  ``TERMINAL_CWD`` (``.``, ``./sub``, ``..``) must be anchored deterministically,
  never left to resolve against whatever the process cwd happens to be.
"""

import os
from pathlib import Path

import pytest

import tools.file_tools as ft


@pytest.fixture
def _isolated_cwd(tmp_path, monkeypatch):
    """Two checkouts: workspace (intended) + decoy (process cwd)."""
    workspace = tmp_path / "workspace"
    decoy = tmp_path / "decoy"
    workspace.mkdir()
    decoy.mkdir()
    (workspace / "target.py").write_text("WORKSPACE_ORIGINAL\n")
    (decoy / "target.py").write_text("DECOY_ORIGINAL\n")
    # Process cwd = decoy, analogous to "main repo" while the terminal is in
    # the worktree.
    monkeypatch.chdir(decoy)
    # No live-terminal-cwd tracking recorded yet (fresh-session condition).
    monkeypatch.setattr(ft, "_get_live_tracking_cwd", lambda task_id="default": None)
    return workspace, decoy


def test_relative_terminal_cwd_anchors_to_absolute_not_process_cwd(_isolated_cwd, monkeypatch):
    """TERMINAL_CWD='.' must NOT silently mean 'the agent process cwd'.

    A relative base is meaningless as a resolution anchor. The resolver must
    make it absolute deterministically. We assert the resolved path is
    absolute and stable regardless of where os.getcwd() points.
    """
    workspace, decoy = _isolated_cwd
    # Poison config: literal relative '.'
    monkeypatch.setenv("TERMINAL_CWD", ".")

    resolved = ft._resolve_path_for_task("target.py", task_id="default")

    assert resolved.is_absolute(), f"resolution base leaked a relative path: {resolved}"
    # The exact anchor for a bare '.' is the process cwd resolved to absolute —
    # that is acceptable as long as it is ABSOLUTE and stable. The bug was that
    # a relative base produced surprising results; the fix is that the base is
    # always absolutised. (We do not require it to point at the workspace here —
    # that's what live-cwd tracking is for; see the next test.)
    assert str(resolved) == str((Path(os.getcwd()) / "target.py").resolve())


def test_live_tracking_cwd_wins_over_relative_terminal_cwd(_isolated_cwd, monkeypatch):
    """When the terminal reports its absolute cwd, that is authoritative.

    This is the real-world fix: the terminal's tracked absolute cwd (the
    worktree) must override a stale relative TERMINAL_CWD so edits land where
    the agent is actually working.
    """
    workspace, decoy = _isolated_cwd
    monkeypatch.setenv("TERMINAL_CWD", ".")
    monkeypatch.setattr(ft, "_get_live_tracking_cwd", lambda task_id="default": str(workspace))

    resolved = ft._resolve_path_for_task("target.py", task_id="default")

    assert resolved == (workspace / "target.py")


def test_absolute_terminal_cwd_used_verbatim(_isolated_cwd, monkeypatch):
    """An absolute TERMINAL_CWD is the resolution base (no live tracking)."""
    workspace, decoy = _isolated_cwd
    monkeypatch.setenv("TERMINAL_CWD", str(workspace))

    resolved = ft._resolve_path_for_task("target.py", task_id="default")

    assert resolved == (workspace / "target.py")


def test_absolute_input_path_ignores_base(_isolated_cwd, monkeypatch):
    """An absolute input path is never re-anchored."""
    workspace, decoy = _isolated_cwd
    monkeypatch.setenv("TERMINAL_CWD", ".")
    abs_target = str(workspace / "target.py")

    resolved = ft._resolve_path_for_task(abs_target, task_id="default")

    assert resolved == Path(abs_target).resolve()


def test_resolution_base_always_absolute_no_terminal_cwd(_isolated_cwd, monkeypatch):
    """With TERMINAL_CWD unset, the base falls back to an ABSOLUTE process cwd."""
    workspace, decoy = _isolated_cwd
    monkeypatch.delenv("TERMINAL_CWD", raising=False)

    resolved = ft._resolve_path_for_task("target.py", task_id="default")

    assert resolved.is_absolute()
    assert str(resolved) == str((Path(os.getcwd()) / "target.py").resolve())


# ── B-(ii): workspace-divergence warning ────────────────────────────────────


def test_warning_fires_when_relative_path_escapes_workspace(_isolated_cwd, monkeypatch):
    """Relative path resolving outside the live workspace must warn."""
    workspace, decoy = _isolated_cwd
    # Live cwd = workspace, but the relative path resolves to decoy (process cwd)
    # because TERMINAL_CWD is the poison '.'.  Simulate by pointing live tracking
    # at workspace while the resolved path is under decoy.
    monkeypatch.setattr(ft, "_get_live_tracking_cwd", lambda task_id="default": str(workspace))
    resolved_in_decoy = decoy / "target.py"

    warn = ft._path_resolution_warning("target.py", resolved_in_decoy, task_id="default")

    assert warn is not None
    assert "OUTSIDE the active workspace" in warn
    assert str(decoy) in warn
    assert str(workspace) in warn


def test_no_warning_when_relative_path_inside_workspace(_isolated_cwd, monkeypatch):
    workspace, decoy = _isolated_cwd
    monkeypatch.setattr(ft, "_get_live_tracking_cwd", lambda task_id="default": str(workspace))
    resolved_in_workspace = workspace / "target.py"

    warn = ft._path_resolution_warning("target.py", resolved_in_workspace, task_id="default")

    assert warn is None


def test_no_warning_for_absolute_input(_isolated_cwd, monkeypatch):
    workspace, decoy = _isolated_cwd
    monkeypatch.setattr(ft, "_get_live_tracking_cwd", lambda task_id="default": str(workspace))

    warn = ft._path_resolution_warning(str(decoy / "target.py"), decoy / "target.py", task_id="default")

    assert warn is None


def test_no_warning_when_no_live_cwd(_isolated_cwd, monkeypatch):
    workspace, decoy = _isolated_cwd
    monkeypatch.setattr(ft, "_get_live_tracking_cwd", lambda task_id="default": None)
    monkeypatch.delenv("TERMINAL_CWD", raising=False)

    warn = ft._path_resolution_warning("target.py", decoy / "target.py", task_id="default")

    assert warn is None


# ── Fix C: sentinel TERMINAL_CWD + empty-registry worktree anchoring ─────────
# (May 2026 follow-up: PR #35399 made misroutes visible via resolved_path but
# the divergence warning only fired when the live terminal cwd was known. A
# worktree session whose terminal registry is still empty — no `cd` run yet —
# got neither a worktree anchor nor a warning, so a relative edit silently
# landed in main. These tests pin the sentinel handling + empty-registry
# anchoring + early warning.)


@pytest.mark.parametrize("sentinel", ["", ".", "./", "auto", "cwd", "CWD", "Auto"])
def test_sentinel_terminal_cwd_is_treated_as_unset(_isolated_cwd, monkeypatch, sentinel):
    """Sentinel TERMINAL_CWD values are NOT used as a directory anchor.

    They fall through to the (absolute) process cwd, exactly as if unset —
    never resolved as a literal relative directory.
    """
    workspace, decoy = _isolated_cwd
    monkeypatch.setattr(ft, "_get_live_tracking_cwd", lambda task_id="default": None)
    monkeypatch.setenv("TERMINAL_CWD", sentinel)

    assert ft._configured_terminal_cwd() is None
    resolved = ft._resolve_path_for_task("target.py", task_id="default")
    assert resolved.is_absolute()
    assert resolved == (decoy / "target.py").resolve()


def test_relative_nonsentinel_terminal_cwd_rejected(_isolated_cwd, monkeypatch):
    """A relative (but non-sentinel) TERMINAL_CWD is still rejected as an anchor.

    A relative anchor is ambiguous (relative to which cwd?), which is the exact
    ambiguity that misroutes edits. It must fall through to the process cwd, not
    be joined onto it as a literal subdir.
    """
    workspace, decoy = _isolated_cwd
    monkeypatch.setattr(ft, "_get_live_tracking_cwd", lambda task_id="default": None)
    monkeypatch.setenv("TERMINAL_CWD", "some/rel/path")

    assert ft._configured_terminal_cwd() is None
    resolved = ft._resolve_path_for_task("target.py", task_id="default")
    assert resolved == (decoy / "target.py").resolve()


def test_absolute_terminal_cwd_anchors_with_empty_registry(_isolated_cwd, monkeypatch):
    """The incident-preventing case: worktree session, registry still empty.

    With no live terminal cwd recorded yet but an absolute TERMINAL_CWD (the
    worktree path cli.py/main.py set for `-w`), a relative edit must land in the
    worktree — not the process cwd (main repo).
    """
    workspace, decoy = _isolated_cwd
    monkeypatch.setattr(ft, "_get_live_tracking_cwd", lambda task_id="default": None)
    monkeypatch.setenv("TERMINAL_CWD", str(workspace))

    resolved = ft._resolve_path_for_task("target.py", task_id="default")

    assert resolved == (workspace / "target.py")
    assert not str(resolved).startswith(str(decoy))


def test_warning_fires_from_terminal_cwd_when_registry_empty(_isolated_cwd, monkeypatch):
    """Divergence warning must fire even before any terminal command runs.

    PR #35399's warning required a live terminal cwd; a fresh worktree session
    (empty registry) silently misrouted with no warning. Now the warning falls
    back to the absolute TERMINAL_CWD anchor, so an edit aimed outside the
    worktree is flagged on the very first write.
    """
    workspace, decoy = _isolated_cwd
    monkeypatch.setattr(ft, "_get_live_tracking_cwd", lambda task_id="default": None)
    monkeypatch.setenv("TERMINAL_CWD", str(workspace))

    # Relative path that escapes the worktree into the decoy/main checkout.
    escaping = os.path.relpath(str(decoy / "target.py"), str(workspace))
    resolved = ft._resolve_path_for_task(escaping, task_id="default")

    warn = ft._path_resolution_warning(escaping, resolved, task_id="default")

    assert warn is not None
    assert "OUTSIDE the active workspace" in warn
    assert str(workspace) in warn


def test_live_cwd_still_wins_over_absolute_terminal_cwd(_isolated_cwd, monkeypatch):
    """When both are present, the live terminal cwd remains authoritative."""
    workspace, decoy = _isolated_cwd
    other = decoy.parent / "other"
    other.mkdir()
    # Live cwd = workspace; TERMINAL_CWD points elsewhere — live must win.
    monkeypatch.setattr(ft, "_get_live_tracking_cwd", lambda task_id="default": str(workspace))
    monkeypatch.setenv("TERMINAL_CWD", str(other))

    resolved = ft._resolve_path_for_task("target.py", task_id="default")

    assert resolved == (workspace / "target.py")


# ── Fix A: write_file / patch report the resolved ABSOLUTE path ──────────────


def test_write_file_reports_resolved_absolute_path(_isolated_cwd, monkeypatch):
    """write_file_tool must put the absolute on-disk path in files_modified."""
    workspace, decoy = _isolated_cwd
    monkeypatch.setattr(ft, "_get_live_tracking_cwd", lambda task_id="default": str(workspace))

    import json
    out = json.loads(ft.write_file_tool("newfile.txt", "hello\n", task_id="t1"))

    expected = str((workspace / "newfile.txt").resolve())
    assert out.get("resolved_path") == expected
    assert out.get("files_modified") == [expected]
    assert (workspace / "newfile.txt").read_text() == "hello\n"


def test_patch_reports_resolved_absolute_path(_isolated_cwd, monkeypatch):
    """patch_tool (replace mode) must put the absolute on-disk path in files_modified."""
    workspace, decoy = _isolated_cwd
    monkeypatch.setattr(ft, "_get_live_tracking_cwd", lambda task_id="default": str(workspace))

    import json
    out = json.loads(ft.patch_tool(
        mode="replace", path="target.py",
        old_string="WORKSPACE_ORIGINAL", new_string="WORKSPACE_PATCHED",
        task_id="t1",
    ))

    expected = str((workspace / "target.py").resolve())
    assert not out.get("error"), out
    assert out.get("resolved_path") == expected
    assert out.get("files_modified") == [expected]
    assert "WORKSPACE_PATCHED" in (workspace / "target.py").read_text()
    # And the decoy copy is untouched.
    assert (decoy / "target.py").read_text() == "DECOY_ORIGINAL\n"


# ── Fix C: Windows MSYS / cygdrive / WSL absolute-path translation ───────────
#
# Bug: on Windows, Path("/c/dev/x") is drive-less rooted (is_absolute() ==
# False), so the resolver joined it onto the active drive and produced the
# literal C:\c\dev\x. _normalize_windows_msys_path translates the cygdrive /
# /mnt / /cygdrive conventions to native drive form, but ONLY on Windows with
# the LOCAL terminal backend. These tests run on any OS by forcing os.name and
# the backend via monkeypatch so behaviour is pinned cross-platform.


@pytest.fixture
def _force_windows_local(monkeypatch):
    """Force os.name == 'nt' and a LOCAL terminal backend for normalization."""
    monkeypatch.setattr(ft.os, "name", "nt")
    monkeypatch.setattr(ft, "_terminal_backend_is_local", lambda task_id="default": True)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("/c/dev/x.ts", "C:/dev/x.ts"),
        ("/mnt/c/dev/x.ts", "C:/dev/x.ts"),
        ("/cygdrive/c/dev/x.ts", "C:/dev/x.ts"),
        ("/d/projects/a", "D:/projects/a"),
        ("/c", "C:/"),
        ("/mnt/c", "C:/"),
        ("/cygdrive/c", "C:/"),
    ],
)
def test_msys_paths_translate_on_windows_local(_force_windows_local, raw, expected):
    assert ft._normalize_windows_msys_path(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "/tmp/x",          # multi-letter POSIX root — not a drive
        "/home/x",         # multi-letter POSIX root
        "/root/x",         # multi-letter POSIX root
        "/usr/lib/x",
        "/var/log/x",
        "C:\\dev\\x",      # real Windows path
        "C:/dev/x",        # real Windows path (forward slashes)
        "src/x.ts",        # genuine relative path
        "./x",             # genuine relative path
        "x",               # bare relative
        "~",               # home, left for expanduser
        "~/foo",
        "",                # empty
    ],
)
def test_non_msys_paths_unchanged_on_windows_local(_force_windows_local, raw):
    assert ft._normalize_windows_msys_path(raw) == raw


def test_msys_translation_noop_when_not_windows(monkeypatch):
    """On a non-Windows OS, /c/dev/x must pass through untouched."""
    monkeypatch.setattr(ft.os, "name", "posix")
    monkeypatch.setattr(ft, "_terminal_backend_is_local", lambda task_id="default": True)
    assert ft._normalize_windows_msys_path("/c/dev/x.ts") == "/c/dev/x.ts"


def test_msys_translation_noop_when_backend_not_local(monkeypatch):
    """On Windows but a Docker/non-local backend, /c/... must NOT be rewritten.

    In a container, /c/... or /root/... can be a real path; rewriting it to
    C:/... would corrupt the target.
    """
    monkeypatch.setattr(ft.os, "name", "nt")
    monkeypatch.setattr(ft, "_terminal_backend_is_local", lambda task_id="default": False)
    assert ft._normalize_windows_msys_path("/c/dev/x.ts") == "/c/dev/x.ts"
    assert ft._normalize_windows_msys_path("/root/x") == "/root/x"


def test_backend_local_detection_reads_env_config(monkeypatch):
    """_terminal_backend_is_local reflects _get_env_config()['env_type']."""
    import tools.terminal_tool as tt

    monkeypatch.setattr(tt, "_get_env_config", lambda: {"env_type": "local"})
    assert ft._terminal_backend_is_local() is True
    monkeypatch.setattr(tt, "_get_env_config", lambda: {"env_type": "docker"})
    assert ft._terminal_backend_is_local() is False


def test_resolve_path_for_task_translates_msys_absolute(monkeypatch, tmp_path):
    """End-to-end: /c/... absolute input resolves to a real C: path, not C:\\c\\...

    Gated to Windows: the drive-less-rooted bug only exists on nt, and
    Path semantics differ on POSIX. On non-Windows we assert the no-op
    instead (the function returns the path unchanged before Path()).
    """
    monkeypatch.setattr(ft, "_terminal_backend_is_local", lambda task_id="default": True)
    if os.name == "nt":
        monkeypatch.setattr(ft, "_get_live_tracking_cwd", lambda task_id="default": None)
        resolved = ft._resolve_path_for_task("/c/dev/_unit_probe.ts", task_id="default")
        # Must be C:\dev\_unit_probe.ts — NOT the literal C:\c\dev\...
        assert resolved == Path("C:/dev/_unit_probe.ts")
        assert "\\c\\dev" not in str(resolved).lower().replace("c:", "", 1)
    else:
        # Non-Windows: normalization is a no-op, path stays POSIX-absolute.
        monkeypatch.setattr(ft.os, "name", "posix")
        assert ft._normalize_windows_msys_path("/c/dev/x") == "/c/dev/x"

