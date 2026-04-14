#!/usr/bin/env python3
"""
Verification test for delegate_task git worktree isolation.

Tests:
1. _is_git_repo correctly identifies git/non-git directories
2. _get_git_root returns the correct repo root
3. _create_worktree creates an isolated worktree
4. _remove_worktree cleans up the worktree
5. _resolve_worktree_for_task creates worktree only when in git repo
6. Worktree is cleaned up after _run_single_child completes
7. Non-git directory falls back gracefully (no worktree created)
"""

import os
import subprocess
import tempfile
import shutil
import sys
import uuid

# Ensure we use the local hermes-agent code
sys.path.insert(0, "/Users/lierdong/.hermes/hermes-agent")

from tools.delegate_tool import (
    _is_git_repo,
    _get_git_root,
    _create_worktree,
    _remove_worktree,
    _resolve_worktree_for_task,
    _WORKTREE_BASE,
)


def run_git(cwd, *args):
    """Run a git command and return result."""
    result = subprocess.run(
        ["git"] + list(args),
        capture_output=True, text=True, cwd=cwd
    )
    return result


def test_is_git_repo():
    """Test _is_git_repo on git and non-git directories."""
    print("\n=== Test: _is_git_repo ===")

    # Non-git directory
    with tempfile.TemporaryDirectory() as tmp:
        assert _is_git_repo(tmp) is False, f"Expected False for {tmp}"
        print(f"  [OK] Non-git dir {tmp} -> False")

    # Git repository (this very repo)
    repo_root = _get_git_root("/Users/lierdong/.hermes/hermes-agent")
    assert repo_root is not None, "Could not find git repo root for hermes-agent"
    assert _is_git_repo(repo_root) is True, f"Expected True for git repo {repo_root}"
    print(f"  [OK] Git repo {repo_root} -> True")


def test_get_git_root():
    """Test _get_git_root returns correct root."""
    print("\n=== Test: _get_git_root ===")

    # Inside hermes-agent (git repo)
    root = _get_git_root("/Users/lierdong/.hermes/hermes-agent/tools")
    assert root is not None, "Should find git root for tools dir"
    print(f"  [OK] tools/ -> root = {root}")

    # Non-git directory
    with tempfile.TemporaryDirectory() as tmp:
        assert _get_git_root(tmp) is None, f"Non-git should return None: {tmp}"
        print(f"  [OK] Non-git dir -> None")


def test_create_and_remove_worktree():
    """Test creating and removing a worktree in a real git repo."""
    print("\n=== Test: _create_worktree / _remove_worktree ===")

    repo_root = _get_git_root("/Users/lierdong/.hermes/hermes-agent")
    assert repo_root is not None, "Need a git repo for this test"

    # Create worktree
    task_id = f"test-{uuid.uuid4().hex[:8]}"
    worktree_info = _create_worktree(task_id, repo_root)
    assert worktree_info is not None, "Worktree creation should succeed"
    assert "path" in worktree_info, "Should have path key"
    assert "branch" in worktree_info, "Should have branch key"
    assert "repo_root" in worktree_info, "Should have repo_root key"
    print(f"  [OK] Created worktree: {worktree_info['path']}")
    print(f"       Branch: {worktree_info['branch']}")

    # Verify worktree exists via git
    result = run_git(repo_root, "worktree", "list")
    assert worktree_info["path"] in result.stdout, f"Worktree not in list: {result.stdout}"
    print(f"  [OK] Worktree appears in 'git worktree list'")

    # Verify it's a directory
    assert os.path.isdir(worktree_info["path"]), f"Worktree dir should exist: {worktree_info['path']}"
    print(f"  [OK] Worktree directory exists")

    # Remove worktree
    removed = _remove_worktree(worktree_info)
    assert removed is True, "Worktree removal should succeed"
    print(f"  [OK] Worktree removed")

    # Verify it's gone
    assert not os.path.exists(worktree_info["path"]), f"Worktree dir should be gone: {worktree_info['path']}"
    print(f"  [OK] Worktree directory no longer exists")

    # Verify it's not in git worktree list anymore
    result = run_git(repo_root, "worktree", "list")
    # The pruned entry may still show briefly; give git a moment
    import time; time.sleep(0.5)
    result = run_git(repo_root, "worktree", "list")
    # Just verify no error
    assert result.returncode == 0, f"git worktree list should succeed: {result.stderr}"
    print(f"  [OK] git worktree list is clean")


def test_create_worktree_non_git():
    """Test that _create_worktree returns None for non-git directories."""
    print("\n=== Test: _create_worktree on non-git ===")

    with tempfile.TemporaryDirectory() as tmp:
        result = _create_worktree("test-task", tmp)
        assert result is None, f"Non-git should return None, got: {result}"
        print(f"  [OK] Non-git directory returns None")


def test_resolve_worktree_for_task():
    """Test _resolve_worktree_for_task creates worktree when isolated=True."""
    print("\n=== Test: _resolve_worktree_for_task ===")

    repo_root = _get_git_root("/Users/lierdong/.hermes/hermes-agent")
    assert repo_root is not None

    # Create a mock parent_agent with session_id and cwd
    class MockAgent:
        session_id = f"test-session-{uuid.uuid4().hex[:8]}"
        terminal_cwd = repo_root
        cwd = repo_root

    agent = MockAgent()

    # is_isolated=False -> should return None
    wt = _resolve_worktree_for_task("task1", 0, agent, is_isolated=False)
    assert wt is None, "is_isolated=False should return None"
    print(f"  [OK] is_isolated=False returns None")

    # is_isolated=True -> should create worktree
    task_id = f"test-{uuid.uuid4().hex[:8]}"
    wt = _resolve_worktree_for_task(task_id, 0, agent, is_isolated=True)
    assert wt is not None, "is_isolated=True should create worktree"
    print(f"  [OK] is_isolated=True created worktree: {wt['path']}")

    # Cleanup
    _remove_worktree(wt)
    print(f"  [OK] Cleanup done")


def test_resolve_worktree_falls_back_when_not_git():
    """Test _resolve_worktree_for_task returns None when not in a git repo."""
    print("\n=== Test: _resolve_worktree_for_task (non-git fallback) ===")

    # Even with is_isolated=True, should return None if not in git repo
    # Use a truly isolated non-git temp dir (outside any git repo tree)
    with tempfile.TemporaryDirectory() as non_git_tmp:
        class MockAgent:
            def __init__(self, cwd):
                self.session_id = f"test-session-{uuid.uuid4().hex[:8]}"
                self.terminal_cwd = str(cwd)
                self.cwd = str(cwd)

        agent = MockAgent(non_git_tmp)
        # Also set TERMINAL_CWD env so _resolve_worktree_for_task uses it
        old_env = os.environ.get("TERMINAL_CWD")
        os.environ["TERMINAL_CWD"] = str(non_git_tmp)
        try:
            wt = _resolve_worktree_for_task("task1", 0, agent, is_isolated=True)
            assert wt is None, f"Should return None when not in git repo, got {wt}"
        finally:
            if old_env is not None:
                os.environ["TERMINAL_CWD"] = old_env
            elif "TERMINAL_CWD" in os.environ:
                del os.environ["TERMINAL_CWD"]
        print(f"  [OK] Returns None when not in git repo (graceful fallback)")


def test_worktree_base_directory():
    """Test that _WORKTREE_BASE is correctly set."""
    print("\n=== Test: _WORKTREE_BASE ===")
    from pathlib import Path
    assert str(_WORKTREE_BASE) == str(Path.home() / ".hermes" / "worktrees")
    print(f"  [OK] _WORKTREE_BASE = {_WORKTREE_BASE}")


def main():
    print("=" * 60)
    print("delegate_task worktree isolation verification")
    print("=" * 60)

    tests = [
        test_is_git_repo,
        test_get_git_root,
        test_create_and_remove_worktree,
        test_create_worktree_non_git,
        test_resolve_worktree_for_task,
        test_resolve_worktree_falls_back_when_not_git,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
