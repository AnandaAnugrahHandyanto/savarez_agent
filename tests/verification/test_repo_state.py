from pathlib import Path

from hermes_cli.verification.repo_state import collect_repo_state


def run(cmd, cwd):
    import subprocess

    subprocess.run(cmd, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def test_collect_repo_state_from_git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test User"], repo)
    (repo / "README.md").write_text("hello\n")
    run(["git", "add", "README.md"], repo)
    run(["git", "commit", "-m", "init"], repo)
    (repo / "README.md").write_text("hello changed\n")

    state = collect_repo_state(repo)

    assert state.repo == str(repo)
    assert state.branch in {"main", "master"}
    assert len(state.sha) >= 7
    assert state.dirty is True
    assert "README.md" in state.changed_files[0]
    assert state.limitations == []


def test_collect_repo_state_handles_non_git_directory(tmp_path):
    state = collect_repo_state(tmp_path)

    assert state.repo == str(tmp_path)
    assert state.branch is None
    assert state.sha is None
    assert state.dirty is None
    assert state.limitations
