import json
import subprocess
from pathlib import Path

import toolsets
from tools import codex_workflow_run_tool as workflow
from tools.registry import registry


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


def _call(**kwargs):
    defaults = {
        "task": "make a small change",
        "allowed_files": ["README.md"],
        "allowed_globs": [],
        "verify_cmd_ids": ["diff-check"],
        "continue_policy": "stop-on-review-needed",
        "dirty_baseline_policy": "require-clean",
        "mode": "execute",
    }
    defaults.update(kwargs)
    return json.loads(workflow.codex_workflow_run(defaults))


def test_clean_repo_calls_staged_implementation(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)
    calls = []

    def fake_staged(args):
        calls.append(args)
        return json.dumps({"status": "ready_for_review", "resolved_workdir": args["workdir"]})

    monkeypatch.setattr(workflow.staged, "codex_staged_implement", fake_staged)

    result = _call(workdir=str(repo))

    assert result["status"] == "staged_called"
    assert result["dirty_recovery"]["strategy"] == "none"
    assert result["codex_staged_result"]["status"] == "ready_for_review"
    assert calls == [
        {
            "workdir": str(repo),
            "task": "make a small change",
            "allowed_files": ["README.md"],
            "allowed_globs": [],
            "verify_cmd_ids": ["diff-check"],
            "continue_policy": "stop-on-review-needed",
            "dirty_baseline_policy": "require-clean",
            "mode": "execute",
        }
    ]


def test_cache_only_dirty_cleanup_then_calls_staged(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)
    cache_path = repo / ".pytest_cache" / "v" / "cache" / "nodeids"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text("cached\n", encoding="utf-8")
    calls = []

    def fake_staged(args):
        calls.append(args)
        return json.dumps({"status": "ready_for_review"})

    monkeypatch.setattr(workflow.staged, "codex_staged_implement", fake_staged)

    result = _call(
        workdir=str(repo),
        standing_authorization=True,
        auto_clean_cache=True,
    )

    assert result["status"] == "staged_called"
    assert result["dirty_recovery"]["strategy"] == "cache_cleanup"
    assert result["dirty_recovery"]["cache_cleaned_paths"] == [".pytest_cache/v/cache/nodeids"]
    assert result["dirty_recovery"]["post_cleanup_dirty_check"]["is_clean"] is True
    assert not cache_path.exists()
    assert len(calls) == 1


def test_source_unknown_dirty_uses_isolated_worktree_when_authorized(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)
    (repo / "tools").mkdir()
    (repo / "tools" / "dirty_tool.py").write_text("dirty\n", encoding="utf-8")
    original_dirty = repo / "scratch.tmp"
    original_dirty.write_text("dirty\n", encoding="utf-8")
    isolated = tmp_path / ".hermes-worktrees" / "repo-phase-abc123"
    calls = []
    worktree_calls = []

    def fake_create(repo_arg, *, stage_id, git_head):
        worktree_calls.append((repo_arg, stage_id, git_head))
        isolated.mkdir(parents=True)
        (isolated / "README.md").write_text("hello\n", encoding="utf-8")
        _git(isolated, "init")
        _git(isolated, "config", "user.email", "test@example.com")
        _git(isolated, "config", "user.name", "Test User")
        _git(isolated, "add", "README.md")
        _git(isolated, "commit", "-m", "isolated base")
        return {"path": str(isolated), "branch": "work/phase-20260606-abc123", "source_head": git_head}

    def fake_staged(args):
        calls.append(args)
        return json.dumps({"status": "ready_for_review", "resolved_workdir": args["workdir"]})

    monkeypatch.setattr(workflow, "_create_isolated_worktree", fake_create)
    monkeypatch.setattr(workflow.staged, "codex_staged_implement", fake_staged)

    result = _call(
        workdir=str(repo),
        standing_authorization=True,
        allow_isolated_worktree=True,
        stage_id="phase",
    )

    assert result["status"] == "staged_called"
    assert result["dirty_recovery"]["strategy"] == "isolated_worktree"
    assert result["dirty_recovery"]["isolated_worktree"]["path"] == str(isolated)
    assert calls[0]["workdir"] == str(isolated)
    assert worktree_calls[0][0] == repo
    assert (repo / "tools" / "dirty_tool.py").exists()
    assert original_dirty.exists()


def test_dirty_without_authorization_requires_recovery_and_does_not_call_staged(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)
    (repo / "scratch.tmp").write_text("dirty\n", encoding="utf-8")
    calls = []

    def fake_staged(args):
        calls.append(args)
        raise AssertionError("staged implementation should not be called")

    monkeypatch.setattr(workflow.staged, "codex_staged_implement", fake_staged)

    result = _call(workdir=str(repo))

    assert result["status"] == "dirty_recovery_required"
    assert result["dirty_recovery"]["initial_dirty_check"]["is_clean"] is False
    assert result["dirty_recovery"]["requires_user_decision"] is True
    assert result["codex_staged_result"] is None
    assert calls == []


def test_registration_and_core_toolset_exposure():
    schema = registry.get_schema("codex_workflow_run")

    assert schema is not None
    assert registry.get_toolset_for_tool("codex_workflow_run") == "codex_staged_implement"
    assert "codex_workflow_run" in toolsets._HERMES_CORE_TOOLS
    assert "codex_workflow_run" in toolsets.resolve_toolset("codex_staged_implement")
    assert "codex_staged_implement" in toolsets.resolve_toolset("codex_staged_implement")
    assert "codex_workflow_run" in toolsets.resolve_toolset("codex_workflow_run")


def test_schema_has_no_executable_command_suggestions():
    encoded = json.dumps(registry.get_schema("codex_workflow_run"))

    assert "git worktree add" not in encoded
    assert "codex exec" not in encoded
    assert "codex-yuna exec" not in encoded
    assert "stash" not in encoded
    assert "reset" not in encoded


def test_cache_cleanup_never_deletes_original_dirty_source(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)
    source_path = repo / "tools" / "dirty_tool.py"
    source_path.parent.mkdir()
    source_path.write_text("dirty\n", encoding="utf-8")
    cache_path = repo / ".pytest_cache" / "v" / "cache" / "nodeids"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text("cached\n", encoding="utf-8")
    calls = []

    def fake_staged(args):
        calls.append(args)
        raise AssertionError("staged implementation should not be called")

    monkeypatch.setattr(workflow.staged, "codex_staged_implement", fake_staged)

    result = _call(
        workdir=str(repo),
        standing_authorization=True,
        auto_clean_cache=True,
    )

    assert result["status"] == "dirty_recovery_required"
    assert source_path.exists()
    assert cache_path.exists()
    assert calls == []


def _verified_evidence(repo: Path, *, touched_files: list[str] | None = None, dirty_state_id: str | None = None) -> dict:
    dirty = workflow.staged._dirty_check(repo)
    return {
        "stage_id": "phase-4",
        "allowed_files": ["README.md"],
        "allowed_globs": [],
        "touched_files": touched_files if touched_files is not None else dirty["dirty_paths"],
        "dirty_state_id": dirty_state_id if dirty_state_id is not None else dirty["dirty_state_id"],
        "codex_implementation_status": "completed",
        "codex_review_status": "packet_only_passed",
        "hermes_verification_commands": [{"id": "diff-check", "status": "passed"}],
        "verified_at": "2026-06-06T00:00:00Z",
    }


def test_checkpoint_valid_evidence_commits_touched_files(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)
    evidence = {}

    def fake_staged(args):
        (Path(args["workdir"]) / "README.md").write_text("hello\nchanged\n", encoding="utf-8")
        evidence.update(_verified_evidence(repo))
        return json.dumps({"status": "ready_for_review", "candidate_id": "cand-1"})

    monkeypatch.setattr(workflow.staged, "codex_staged_implement", fake_staged)

    result = _call(
        workdir=str(repo),
        standing_authorization=True,
        checkpoint_verified_diff=True,
        verification_evidence=evidence,
        checkpoint_message="checkpoint phase 4",
        stage_id="phase-4",
    )

    assert result["status"] == "staged_called"
    assert result["checkpoint"]["status"] == "committed"
    assert result["checkpoint"]["message"] == "checkpoint phase 4"
    assert result["checkpoint"]["touched_files"] == ["README.md"]
    assert _git(repo, "status", "--porcelain=v1", "--untracked-files=all") == ""
    assert _git(repo, "log", "-1", "--pretty=%s") == "checkpoint phase 4"


def test_checkpoint_without_evidence_does_not_commit(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)

    def fake_staged(args):
        (Path(args["workdir"]) / "README.md").write_text("hello\nchanged\n", encoding="utf-8")
        return json.dumps({"status": "ready_for_review"})

    monkeypatch.setattr(workflow.staged, "codex_staged_implement", fake_staged)

    result = _call(
        workdir=str(repo),
        standing_authorization=True,
        checkpoint_verified_diff=True,
    )

    assert result["status"] == "checkpoint_blocked"
    assert result["checkpoint"]["status"] == "blocked"
    assert result["checkpoint"]["reason"] == "missing_verification_evidence"
    assert _git(repo, "log", "--oneline").count("\n") == 0
    assert "README.md" in _git(repo, "status", "--porcelain=v1", "--untracked-files=all")


def test_checkpoint_dirty_state_id_mismatch_blocks(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)
    evidence = {}

    def fake_staged(args):
        (Path(args["workdir"]) / "README.md").write_text("hello\nchanged\n", encoding="utf-8")
        evidence.update(_verified_evidence(repo, dirty_state_id="stale"))
        return json.dumps({"status": "ready_for_review"})

    monkeypatch.setattr(workflow.staged, "codex_staged_implement", fake_staged)

    result = _call(
        workdir=str(repo),
        standing_authorization=True,
        checkpoint_verified_diff=True,
        verification_evidence=evidence,
    )

    assert result["status"] == "checkpoint_blocked"
    assert result["checkpoint"]["reason"] == "dirty_state_id_mismatch"
    assert "README.md" in _git(repo, "status", "--porcelain=v1", "--untracked-files=all")


def test_checkpoint_without_standing_authorization_blocks(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)
    evidence = {}

    def fake_staged(args):
        (Path(args["workdir"]) / "README.md").write_text("hello\nchanged\n", encoding="utf-8")
        evidence.update(_verified_evidence(repo))
        return json.dumps({"status": "ready_for_review"})

    monkeypatch.setattr(workflow.staged, "codex_staged_implement", fake_staged)

    result = _call(
        workdir=str(repo),
        checkpoint_verified_diff=True,
        verification_evidence=evidence,
    )

    assert result["status"] == "checkpoint_blocked"
    assert result["checkpoint"]["reason"] == "authorization_required"
    assert result["checkpoint"]["authorization_required"] is True
    assert "README.md" in _git(repo, "status", "--porcelain=v1", "--untracked-files=all")


def test_leftover_candidate_reported_after_staged_leaves_dirty(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)

    def fake_staged(args):
        (Path(args["workdir"]) / "README.md").write_text("hello\ncandidate\n", encoding="utf-8")
        return json.dumps(
            {
                "status": "ready_for_review",
                "candidate_id": "cand-left",
                "candidate_disposition": "pending_review",
                "completion_trusted": False,
            }
        )

    monkeypatch.setattr(workflow.staged, "codex_staged_implement", fake_staged)
    monkeypatch.setattr(
        workflow,
        "_run_packet_only_review",
        lambda **kwargs: _packet_review("packet_only_unusable", must_fix_count=None),
        raising=False,
    )

    result = _call(workdir=str(repo))

    assert result["status"] == "staged_review_unavailable"
    assert result["leftover_candidate"]["requires_review"] is True
    assert result["leftover_candidate"]["requires_hermes_verification"] is True
    assert result["leftover_candidate"]["candidate_id"] == "cand-left"
    assert result["leftover_candidate"]["candidate_disposition"] == "pending_review"
    assert result["leftover_candidate"]["completion_trusted"] is False
    assert result["leftover_candidate"]["touched_files"] == ["README.md"]


def test_checkpoint_touched_files_outside_current_dirty_blocks(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)
    evidence = {}

    def fake_staged(args):
        (Path(args["workdir"]) / "README.md").write_text("hello\nchanged\n", encoding="utf-8")
        evidence.update(_verified_evidence(repo, touched_files=["README.md", "missing.txt"]))
        return json.dumps({"status": "ready_for_review"})

    monkeypatch.setattr(workflow.staged, "codex_staged_implement", fake_staged)

    result = _call(
        workdir=str(repo),
        standing_authorization=True,
        checkpoint_verified_diff=True,
        verification_evidence=evidence,
    )

    assert result["status"] == "checkpoint_blocked"
    assert result["checkpoint"]["reason"] == "touched_files_do_not_match_dirty_paths"
    assert "README.md" in _git(repo, "status", "--porcelain=v1", "--untracked-files=all")


def test_checkpoint_touched_files_outside_allowlist_blocks(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)
    (repo / "other.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "other.txt")
    _git(repo, "commit", "-m", "add other")
    evidence = {}

    def fake_staged(args):
        (Path(args["workdir"]) / "README.md").write_text("hello\nchanged\n", encoding="utf-8")
        (Path(args["workdir"]) / "other.txt").write_text("base\nchanged\n", encoding="utf-8")
        evidence.update(_verified_evidence(repo, touched_files=["README.md", "other.txt"]))
        return json.dumps({"status": "ready_for_review"})

    monkeypatch.setattr(workflow.staged, "codex_staged_implement", fake_staged)

    result = _call(
        workdir=str(repo),
        standing_authorization=True,
        checkpoint_verified_diff=True,
        verification_evidence=evidence,
    )

    assert result["status"] == "checkpoint_blocked"
    assert result["checkpoint"]["reason"] == "touched_files_outside_allowlist"
    assert "README.md" in _git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    assert "other.txt" in _git(repo, "status", "--porcelain=v1", "--untracked-files=all")


def test_dry_run_clean_repo_does_not_call_staged_or_checkpoint(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)
    calls = []

    def fake_staged(args):
        calls.append(args)
        raise AssertionError("dry_run must not call staged implementation")

    monkeypatch.setattr(workflow.staged, "codex_staged_implement", fake_staged)

    result = _call(
        workdir=str(repo),
        mode="dry_run",
        standing_authorization=True,
        checkpoint_verified_diff=True,
        verification_evidence={"stage_id": "phase-4"},
    )

    assert result["status"] == "dry_run"
    assert result["would_call_staged"] is True
    assert result["codex_staged_result"] is None
    assert "checkpoint" not in result
    assert calls == []
    assert _git(repo, "status", "--porcelain=v1", "--untracked-files=all") == ""


def test_dry_run_cache_dirty_does_not_clean_cache_or_call_staged(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)
    cache_path = repo / ".pytest_cache" / "v" / "cache" / "nodeids"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text("cached\n", encoding="utf-8")
    calls = []

    def fake_staged(args):
        calls.append(args)
        raise AssertionError("dry_run must not call staged implementation")

    monkeypatch.setattr(workflow.staged, "codex_staged_implement", fake_staged)

    result = _call(
        workdir=str(repo),
        mode="dry_run",
        standing_authorization=True,
        auto_clean_cache=True,
    )

    assert result["status"] == "dry_run"
    assert result["would_call_staged"] is False
    assert cache_path.exists()
    assert result["dirty_recovery"]["initial_dirty_check"]["dirty_path_classes"]["cache"] == [
        ".pytest_cache/v/cache/nodeids"
    ]
    assert calls == []


def test_dry_run_source_dirty_does_not_create_isolated_worktree(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)
    source_path = repo / "tools" / "dirty_tool.py"
    source_path.parent.mkdir()
    source_path.write_text("dirty\n", encoding="utf-8")
    staged_calls = []
    worktree_calls = []

    def fake_staged(args):
        staged_calls.append(args)
        raise AssertionError("dry_run must not call staged implementation")

    def fake_create(*args, **kwargs):
        worktree_calls.append((args, kwargs))
        raise AssertionError("dry_run must not create isolated worktrees")

    monkeypatch.setattr(workflow.staged, "codex_staged_implement", fake_staged)
    monkeypatch.setattr(workflow, "_create_isolated_worktree", fake_create)

    result = _call(
        workdir=str(repo),
        mode="dry_run",
        standing_authorization=True,
        allow_isolated_worktree=True,
    )

    assert result["status"] == "dry_run"
    assert result["would_call_staged"] is False
    assert source_path.exists()
    assert staged_calls == []
    assert worktree_calls == []


def _packet_review(status: str, *, must_fix_count: int | None = 0, summary: str = "review summary") -> dict:
    return {
        "status": status,
        "reason": None,
        "must_fix_count": must_fix_count,
        "final_judgment": "可以继续" if status == "packet_only_passed" else "需要先修",
        "summary": summary,
        "raw_log_path": "/tmp/codex-review.raw.log",
        "final_file": "/tmp/codex-review.final.txt",
    }


def test_auto_packet_review_passes_ready_candidate(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)
    review_calls = []

    def fake_staged(args):
        (Path(args["workdir"]) / "README.md").write_text("hello\nreviewed\n", encoding="utf-8")
        return json.dumps(
            {
                "status": "ready_for_review",
                "candidate_id": "cand-p0",
                "candidate_disposition": "pending_review",
                "completion_trusted": True,
            }
        )

    def fake_review(**kwargs):
        review_calls.append(kwargs)
        return _packet_review("packet_only_passed", must_fix_count=0)

    monkeypatch.setattr(workflow.staged, "codex_staged_implement", fake_staged)
    monkeypatch.setattr(workflow, "_run_packet_only_review", fake_review, raising=False)

    result = _call(workdir=str(repo))

    assert result["status"] == "staged_reviewed"
    assert result["codex_packet_review"]["status"] == "packet_only_passed"
    assert result["codex_packet_review"]["must_fix_count"] == 0
    assert result["leftover_candidate"]["requires_review"] is False
    assert result["leftover_candidate"]["requires_fixes"] is False
    assert result["leftover_candidate"]["requires_hermes_verification"] is True
    assert result["leftover_candidate"]["packet_review_status"] == "packet_only_passed"
    assert review_calls[0]["repo"] == repo
    assert review_calls[0]["touched_files"] == ["README.md"]
    assert review_calls[0]["dirty_baseline_paths"] == []
    assert "dirty" not in review_calls[0]


def test_auto_packet_review_blocks_on_must_fix(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)

    def fake_staged(args):
        (Path(args["workdir"]) / "README.md").write_text("hello\nblocked\n", encoding="utf-8")
        return json.dumps({"status": "review_needed", "candidate_id": "cand-blocked"})

    monkeypatch.setattr(workflow.staged, "codex_staged_implement", fake_staged)
    monkeypatch.setattr(
        workflow,
        "_run_packet_only_review",
        lambda **kwargs: _packet_review("packet_only_failed", must_fix_count=1),
        raising=False,
    )

    result = _call(workdir=str(repo))

    assert result["status"] == "staged_review_blocked"
    assert result["codex_packet_review"]["status"] == "packet_only_failed"
    assert result["codex_packet_review"]["must_fix_count"] == 1
    assert result["leftover_candidate"]["requires_review"] is False
    assert result["leftover_candidate"]["requires_fixes"] is True
    assert result["leftover_candidate"]["requires_hermes_verification"] is True


def test_auto_packet_review_unusable_fail_closed(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)

    def fake_staged(args):
        (Path(args["workdir"]) / "README.md").write_text("hello\nunusable\n", encoding="utf-8")
        return json.dumps({"status": "ready_for_review", "candidate_id": "cand-unusable"})

    monkeypatch.setattr(workflow.staged, "codex_staged_implement", fake_staged)
    monkeypatch.setattr(
        workflow,
        "_run_packet_only_review",
        lambda **kwargs: _packet_review("packet_only_unusable", must_fix_count=None),
        raising=False,
    )

    result = _call(workdir=str(repo))

    assert result["status"] == "staged_review_unavailable"
    assert result["codex_packet_review"]["status"] == "packet_only_unusable"
    assert result["leftover_candidate"]["requires_review"] is True
    assert result["leftover_candidate"]["requires_fixes"] is False
    assert result["leftover_candidate"]["requires_hermes_verification"] is True


def test_takeover_candidate_review_pass_does_not_become_trusted_completion(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)

    def fake_staged(args):
        (Path(args["workdir"]) / "README.md").write_text("hello\ntakeover\n", encoding="utf-8")
        return json.dumps(
            {
                "status": "takeover_candidate",
                "candidate_id": "cand-takeover",
                "candidate_disposition": "takeover_required",
                "completion_trusted": False,
            }
        )

    monkeypatch.setattr(workflow.staged, "codex_staged_implement", fake_staged)
    monkeypatch.setattr(
        workflow,
        "_run_packet_only_review",
        lambda **kwargs: _packet_review("packet_only_passed", must_fix_count=0),
        raising=False,
    )

    result = _call(workdir=str(repo))

    assert result["status"] == "staged_reviewed"
    assert result["codex_staged_result"]["status"] == "takeover_candidate"
    assert result["leftover_candidate"]["completion_trusted"] is False
    assert result["leftover_candidate"]["candidate_disposition"] == "takeover_required"
    assert result["leftover_candidate"]["requires_hermes_verification"] is True
    assert "approved" not in json.dumps(result)


def test_blocked_staged_status_does_not_run_packet_review(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)

    def fake_staged(args):
        (Path(args["workdir"]) / "README.md").write_text("hello\nblocked by allowlist\n", encoding="utf-8")
        return json.dumps({"status": "blocked_by_allowlist", "candidate_id": "cand-blocked"})

    def fake_review(**kwargs):
        raise AssertionError("blocked staged status must not run packet review")

    monkeypatch.setattr(workflow.staged, "codex_staged_implement", fake_staged)
    monkeypatch.setattr(workflow, "_run_packet_only_review", fake_review, raising=False)

    result = _call(workdir=str(repo))

    assert result["status"] == "staged_called"
    assert result["codex_packet_review"]["status"] == "not_run"
    assert result["codex_packet_review"]["reason"] == "staged_status_blocked_by_allowlist"
    assert result["leftover_candidate"]["requires_review"] is True


def test_checkpoint_path_does_not_auto_review_or_commit_without_evidence(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)

    def fake_staged(args):
        (Path(args["workdir"]) / "README.md").write_text("hello\ncheckpoint\n", encoding="utf-8")
        return json.dumps({"status": "ready_for_review", "candidate_id": "cand-checkpoint"})

    def fake_review(**kwargs):
        raise AssertionError("checkpoint path must not run packet review")

    monkeypatch.setattr(workflow.staged, "codex_staged_implement", fake_staged)
    monkeypatch.setattr(workflow, "_run_packet_only_review", fake_review, raising=False)

    result = _call(workdir=str(repo), standing_authorization=True, checkpoint_verified_diff=True)

    assert result["status"] == "checkpoint_blocked"
    assert result["checkpoint"]["reason"] == "missing_verification_evidence"


def test_dry_run_never_runs_packet_review(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)

    def fake_review(**kwargs):
        raise AssertionError("dry_run must not run packet review")

    monkeypatch.setattr(workflow, "_run_packet_only_review", fake_review, raising=False)

    result = _call(workdir=str(repo), mode="dry_run")

    assert result["status"] == "dry_run"
    assert result["codex_packet_review"] is None


def test_review_output_is_bounded(tmp_path, monkeypatch):
    repo = _clean_repo(tmp_path)

    def fake_staged(args):
        (Path(args["workdir"]) / "README.md").write_text("hello\nbounded\n", encoding="utf-8")
        return json.dumps({"status": "ready_for_review", "candidate_id": "cand-bounded"})

    def fake_review(**kwargs):
        result = _packet_review("packet_only_passed", must_fix_count=0)
        result["raw_review_text"] = "diff --git a/README.md b/README.md\n" + "source line\n" * 100
        result["full_diff"] = "@@ should not be returned @@"
        return result

    monkeypatch.setattr(workflow.staged, "codex_staged_implement", fake_staged)
    monkeypatch.setattr(workflow, "_run_packet_only_review", fake_review, raising=False)

    result = _call(workdir=str(repo))
    encoded = json.dumps(result)

    assert result["codex_packet_review"]["status"] == "packet_only_passed"
    assert "diff --git" not in encoded
    assert "@@ should not be returned @@" not in encoded


def test_malformed_structured_review_fails_closed():
    malformed_reviews = [
        {"status": "passed", "review": {}},
        {
            "status": "passed",
            "review": {
                "verdict": "passed",
                "must_fix": "not-a-list",
                "final_judgment": "可以继续",
                "summary": "bad must_fix type",
            },
        },
        {
            "status": "passed",
            "review": {
                "verdict": "unknown",
                "must_fix": [],
                "final_judgment": "可以继续",
                "summary": "bad verdict",
            },
        },
        {
            "status": "passed",
            "review": {
                "verdict": "passed",
                "must_fix": [],
                "summary": "missing final judgment",
            },
        },
        {
            "status": "passed",
            "review": {
                "verdict": "passed",
                "must_fix": [],
                "final_judgment": "不能继续",
                "summary": "contradictory final judgment",
            },
        },
        {
            "status": "passed",
            "review": {
                "verdict": "failed",
                "must_fix": [],
                "final_judgment": "可以继续",
                "summary": "contradictory failed verdict",
            },
        },
        {
            "status": "passed",
            "review": {
                "verdict": "failed",
                "must_fix": [],
                "final_judgment": "需要先修",
                "summary": "failed verdict without actionable blockers",
            },
        },
    ]

    for raw in malformed_reviews:
        normalized = workflow._normalize_packet_review_result(raw)

        assert normalized["status"] == "packet_only_unusable"
        assert normalized["reason"] == "review_guard_schema_invalid"


def test_direct_packet_review_passed_shape_is_validated():
    malformed_passes = [
        {"status": "packet_only_passed"},
        {
            "status": "packet_only_passed",
            "must_fix_count": 1,
            "final_judgment": "可以继续",
            "summary": "contradictory pass",
        },
        {
            "status": "packet_only_passed",
            "must_fix_count": 0,
            "final_judgment": "需要先修",
            "summary": "contradictory judgment",
        },
        {
            "status": "packet_only_passed",
            "must_fix_count": 0,
            "final_judgment": "可以继续",
            "summary": "",
        },
    ]

    for raw in malformed_passes:
        normalized = workflow._normalize_packet_review_result(raw)

        assert normalized["status"] == "packet_only_unusable"
        assert normalized["reason"] == "review_guard_schema_invalid"


def test_direct_packet_review_failed_requires_must_fix_count():
    normalized = workflow._normalize_packet_review_result(
        {
            "status": "packet_only_failed",
            "must_fix_count": 0,
            "final_judgment": "需要先修",
            "summary": "failed without blockers",
        }
    )

    assert normalized["status"] == "packet_only_unusable"
    assert normalized["reason"] == "review_guard_schema_invalid"


def test_packet_review_summary_omits_diff_like_content():
    summarized = workflow._summarize_packet_review(
        {
            "status": "packet_only_passed",
            "must_fix_count": 0,
            "final_judgment": "可以继续",
            "summary": "diff --git a/file.py b/file.py\n@@ giant source excerpt @@",
            "raw_log_path": "/tmp/raw.log",
            "final_file": "/tmp/final.txt",
        }
    )

    assert summarized["status"] == "packet_only_passed"
    assert "diff --git" not in summarized["summary"]
    assert "@@" not in summarized["summary"]


def test_packet_review_reason_omits_diff_like_content():
    summarized = workflow._summarize_packet_review(
        {
            "status": "packet_only_unusable",
            "reason": "diff --git a/file.py b/file.py\n@@ giant source excerpt @@",
            "summary": "review unavailable",
            "raw_log_path": "/tmp/raw.log",
            "final_file": "/tmp/final.txt",
        }
    )
    encoded = json.dumps(summarized)

    assert summarized["status"] == "packet_only_unusable"
    assert "diff --git" not in encoded
    assert "@@" not in encoded
