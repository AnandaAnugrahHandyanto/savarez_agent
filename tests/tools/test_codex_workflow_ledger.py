import json
import os
import subprocess
from pathlib import Path

import pytest

from agent import codex_workflow_ledger as ledger


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _clean_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")
    return repo


def _sample_ledger(repo: Path, *, stage_id: str = "phase12a-ledger-resume") -> dict:
    return ledger.new_ledger(
        repo=repo,
        stage_id=stage_id,
        branch=_git(repo, "branch", "--show-current"),
        head_sha=_git(repo, "rev-parse", "HEAD"),
        authorization={"may_write_files": False},
        scope={"allowed_files": ["README.md"], "allowed_globs": []},
        dirty_baseline={"paths": [], "blocking_reasons": [], "resume_strategy": "clean_current"},
    )


def test_ledger_atomic_write_and_read_roundtrip(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)
    hermes_home = tmp_path / "hermes"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    payload = _sample_ledger(repo)

    path = ledger.write_ledger(payload)
    loaded = ledger.read_ledger(path)

    assert loaded["schema_version"] == payload["schema_version"]
    assert loaded["stage_id"] == payload["stage_id"]
    assert loaded["repo"]["head_sha"] == payload["repo"]["head_sha"]
    assert path.exists()
    assert not path.with_suffix(path.suffix + ".tmp").exists()
    assert str(path).startswith(str(hermes_home / "runtime" / "codex_workflows"))


def test_ledger_redacts_home_hermes_home_and_token_like_values(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)
    home = tmp_path / "home"
    hermes_home = tmp_path / "hermes"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    payload = _sample_ledger(repo)
    payload["events"].append(
        {
            "path": str(home / "project" / "file.py"),
            "log": f"cache={hermes_home}/runtime token=sk-testtoken1234567890 ABC_API_KEY=secret-value",
        }
    )

    path = ledger.write_ledger(payload)
    raw = path.read_text(encoding="utf-8")

    assert str(home) not in raw
    assert str(hermes_home) not in raw
    assert "sk-testtoken1234567890" not in raw
    assert "secret-value" not in raw
    assert "<HOME>" in raw
    assert "<HERMES_HOME>" in raw
    assert "<REDACTED>" in raw


def test_ledger_rejects_unsupported_schema(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    payload = _sample_ledger(repo)
    payload["schema_version"] = 99
    path = ledger.ledger_path(repo=repo, branch="master", stage_id="phase12a-ledger-resume")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ledger.LedgerSchemaUnsupported):
        ledger.read_ledger(path)

    status = ledger.resume_status(
        repo=repo,
        branch="master",
        stage_id="phase12a-ledger-resume",
        current_head_sha=_git(repo, "rev-parse", "HEAD"),
        current_dirty_paths=[],
    )
    assert status["resume_status"] == "blocked"
    assert status["reason"] == "ledger_schema_unsupported"


def test_resume_blocks_on_head_change_with_overlapping_dirty(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    payload = _sample_ledger(repo)
    payload["dirty_baseline"]["paths"] = ["README.md"]
    ledger.write_ledger(payload)
    (repo / "next.txt").write_text("next\n", encoding="utf-8")
    _git(repo, "add", "next.txt")
    _git(repo, "commit", "-m", "next")

    status = ledger.resume_status(
        repo=repo,
        branch="master",
        stage_id="phase12a-ledger-resume",
        current_head_sha=_git(repo, "rev-parse", "HEAD"),
        current_dirty_paths=["README.md"],
    )

    assert status["resume_status"] == "blocked"
    assert status["reason"] == "head_changed_with_overlapping_dirty"
    assert status["overlapping_dirty_paths"] == ["README.md"]


def test_resume_marks_interrupted_running_without_process_as_recoverable_dry_run_only(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    payload = _sample_ledger(repo)
    payload["status"] = "running"
    payload["active_pid"] = 99999999
    ledger.write_ledger(payload)

    status = ledger.resume_status(
        repo=repo,
        branch="master",
        stage_id="phase12a-ledger-resume",
        current_head_sha=_git(repo, "rev-parse", "HEAD"),
        current_dirty_paths=[],
    )

    assert status["resume_status"] == "interrupted_recoverable"
    assert status["dry_run_only"] is True


def test_lock_blocks_second_active_run_for_same_repo_branch_stage(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    lock = ledger.acquire_lock(repo=repo, branch="master", stage_id="phase12a-ledger-resume", pid=os.getpid())
    try:
        second = ledger.acquire_lock(repo=repo, branch="master", stage_id="phase12a-ledger-resume", pid=os.getpid())
    finally:
        ledger.release_lock(lock)

    assert lock["acquired"] is True
    assert second["acquired"] is False
    assert second["reason"] == "active_elsewhere"


def test_ledger_redacts_repo_path_outside_home_and_hermes_home(tmp_path, monkeypatch):
    workspace = tmp_path / "work space [punct]"
    workspace.mkdir()
    repo = _clean_repo(workspace)
    home = tmp_path / "home"
    hermes_home = tmp_path / "hermes"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    payload = _sample_ledger(repo)
    payload["events"].append({"log": f"repo at {repo.resolve()}/nested file.py token=sk-token...7890"})
    payload["events"].append({"log": f"status path {repo.resolve()}/nested file.py, status ok"})
    payload["events"].append({"log": f"{repo.resolve()}/start file.py ABC_API_KEY=sample-value"})

    path = ledger.write_ledger(payload)
    raw = path.read_text(encoding="utf-8")

    assert str(repo.resolve()) not in raw
    assert "work space [punct]" not in raw
    assert "sk-token...7890" not in raw
    assert "sample-value" not in raw
    assert raw.count("<REDACTED>") >= 2
    assert "status ok" in raw
    assert "<PATH>" in raw


def test_resume_status_not_found_needs_replan_ready_and_active_elsewhere(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    branch = _git(repo, "branch", "--show-current")
    head = _git(repo, "rev-parse", "HEAD")

    assert ledger.resume_status(
        repo=repo,
        branch=branch,
        stage_id="phase12a-ledger-resume",
        current_head_sha=head,
        current_dirty_paths=[],
    )["resume_status"] == "not_found"

    payload = _sample_ledger(repo)
    payload["status"] = "completed"
    ledger.write_ledger(payload)
    assert ledger.resume_status(
        repo=repo,
        branch=branch,
        stage_id="phase12a-ledger-resume",
        current_head_sha=head,
        current_dirty_paths=[],
    )["resume_status"] == "ready"
    assert ledger.resume_status(
        repo=repo,
        branch=branch,
        stage_id="phase12a-ledger-resume",
        current_head_sha="different-head",
        current_dirty_paths=[],
    )["resume_status"] == "needs_replan"

    lock = ledger.acquire_lock(repo=repo, branch=branch, stage_id="phase12a-ledger-resume", pid=os.getpid())
    try:
        assert ledger.resume_status(
            repo=repo,
            branch=branch,
            stage_id="phase12a-ledger-resume",
            current_head_sha=head,
            current_dirty_paths=[],
        )["resume_status"] == "active_elsewhere"
    finally:
        ledger.release_lock(lock)


def test_release_lock_does_not_remove_replaced_lock(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    branch = _git(repo, "branch", "--show-current")
    first = ledger.acquire_lock(repo=repo, branch=branch, stage_id="phase12a-ledger-resume", pid=os.getpid())
    lock_path = Path(first["path"])
    replacement = {
        "pid": os.getpid(),
        "repo_id": first["repo_id"],
        "branch": first["branch"],
        "stage_id": first["stage_id"],
        "token": "replacement-token",
    }
    lock_path.write_text(json.dumps(replacement), encoding="utf-8")

    ledger.release_lock(first)

    assert lock_path.exists()
    assert json.loads(lock_path.read_text(encoding="utf-8"))["token"] == "replacement-token"
    ledger.release_lock({**first, "token": "replacement-token"})
    assert not lock_path.exists()
