import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WRITE_GATE = REPO_ROOT / "scripts" / "write_gate.py"
VALIDATE_GATE = REPO_ROOT / "scripts" / "validate_gate.py"
INSTALL_HOOK = REPO_ROOT / "scripts" / "install_local_gate_hook.py"


def run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, env=merged_env)


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-b", "main"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    run(["git", "add", "README.md"], cwd=repo)
    commit = run(["git", "commit", "-m", "init"], cwd=repo)
    assert commit.returncode == 0, commit.stderr
    return repo


def write_reports(repo: Path, head_sha: str) -> None:
    gate_dir = repo / ".hermes-gate"
    gate_dir.mkdir(exist_ok=True)
    (gate_dir / "review.md").write_text(
        "\n".join(
            [
                "# Review Report",
                f"- Head SHA: {head_sha}",
                "- Reviewer: hermes-subagent-review",
                "- Verdict: PASS",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (gate_dir / "test.md").write_text(
        "\n".join(
            [
                "# Test Report",
                f"- Head SHA: {head_sha}",
                "- Tester: hermes-subagent-test",
                "- Verdict: PASS",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def git_head(repo: Path) -> str:
    result = run(["git", "rev-parse", "HEAD"], cwd=repo)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_write_gate_writes_current_head_and_relative_paths(tmp_path):
    repo = init_repo(tmp_path)
    head_sha = git_head(repo)
    write_reports(repo, head_sha)

    result = run(
        [
            sys.executable,
            str(WRITE_GATE),
            "--review-status",
            "PASS",
            "--reviewer",
            "hermes-subagent-review",
            "--review-summary",
            "clean",
            "--review-report",
            ".hermes-gate/review.md",
            "--test-status",
            "PASS",
            "--tester",
            "hermes-subagent-test",
            "--test-summary",
            "clean",
            "--test-report",
            ".hermes-gate/test.md",
        ],
        cwd=repo,
    )

    assert result.returncode == 0, result.stderr
    gate_path = repo / ".hermes-gate" / "gate.json"
    payload = json.loads(gate_path.read_text(encoding="utf-8"))
    assert payload["head_sha"] == head_sha
    assert payload["review"]["head_sha"] == head_sha
    assert payload["test"]["head_sha"] == head_sha
    assert payload["review"]["report_path"] == ".hermes-gate/review.md"
    assert payload["test"]["report_path"] == ".hermes-gate/test.md"


def test_validate_gate_rejects_report_sha_mismatch(tmp_path):
    repo = init_repo(tmp_path)
    head_sha = git_head(repo)
    write_reports(repo, head_sha)

    write_result = run(
        [
            sys.executable,
            str(WRITE_GATE),
            "--review-status",
            "PASS",
            "--reviewer",
            "hermes-subagent-review",
            "--review-summary",
            "clean",
            "--review-report",
            ".hermes-gate/review.md",
            "--test-status",
            "PASS",
            "--tester",
            "hermes-subagent-test",
            "--test-summary",
            "clean",
            "--test-report",
            ".hermes-gate/test.md",
        ],
        cwd=repo,
    )
    assert write_result.returncode == 0, write_result.stderr

    (repo / ".hermes-gate" / "review.md").write_text(
        "# Review Report\n- Head SHA: deadbeef\n- Reviewer: hermes-subagent-review\n- Verdict: PASS\n",
        encoding="utf-8",
    )

    validate_result = run([sys.executable, str(VALIDATE_GATE)], cwd=repo)
    assert validate_result.returncode == 1
    assert "review report Head SHA mismatch" in validate_result.stderr


def test_validate_gate_rejects_report_verdict_fail(tmp_path):
    repo = init_repo(tmp_path)
    head_sha = git_head(repo)
    write_reports(repo, head_sha)
    write_result = run(
        [
            sys.executable,
            str(WRITE_GATE),
            "--review-status",
            "PASS",
            "--reviewer",
            "hermes-subagent-review",
            "--review-summary",
            "clean",
            "--review-report",
            ".hermes-gate/review.md",
            "--test-status",
            "PASS",
            "--tester",
            "hermes-subagent-test",
            "--test-summary",
            "clean",
            "--test-report",
            ".hermes-gate/test.md",
        ],
        cwd=repo,
    )
    assert write_result.returncode == 0, write_result.stderr

    (repo / ".hermes-gate" / "test.md").write_text(
        f"# Test Report\n- Head SHA: {head_sha}\n- Tester: hermes-subagent-test\n- Verdict: FAIL\n",
        encoding="utf-8",
    )

    validate_result = run([sys.executable, str(VALIDATE_GATE)], cwd=repo)
    assert validate_result.returncode == 1
    assert "test report Verdict is not PASS" in validate_result.stderr


def test_validate_gate_rejects_report_path_escape(tmp_path):
    repo = init_repo(tmp_path)
    head_sha = git_head(repo)
    outside = tmp_path / "outside.md"
    outside.write_text(
        f"# Report\n- Head SHA: {head_sha}\n- Verdict: PASS\n",
        encoding="utf-8",
    )
    gate_dir = repo / ".hermes-gate"
    gate_dir.mkdir(exist_ok=True)
    (gate_dir / "gate.json").write_text(
        json.dumps(
            {
                "head_sha": head_sha,
                "review": {
                    "status": "PASS",
                    "head_sha": head_sha,
                    "report_path": "../outside.md",
                },
                "test": {
                    "status": "PASS",
                    "head_sha": head_sha,
                    "report_path": "../outside.md",
                },
            }
        ),
        encoding="utf-8",
    )

    validate_result = run([sys.executable, str(VALIDATE_GATE)], cwd=repo)
    assert validate_result.returncode == 1
    assert "outside repo root" in validate_result.stderr


def test_install_hook_uses_repo_root_for_relative_core_hookspath(tmp_path):
    repo = init_repo(tmp_path)
    config_result = run(["git", "config", "core.hooksPath", ".githooks"], cwd=repo)
    assert config_result.returncode == 0, config_result.stderr

    nested = repo / "nested"
    nested.mkdir()
    install_result = run([sys.executable, str(INSTALL_HOOK), "--force"], cwd=nested)
    assert install_result.returncode == 0, install_result.stderr
    assert (repo / ".githooks" / "pre-push").exists()
    assert not (nested / ".githooks" / "pre-push").exists()


def test_installed_hook_noops_without_validate_script(tmp_path):
    repo = init_repo(tmp_path)
    hooks_dir = tmp_path / "hooks"
    install_result = run(
        [sys.executable, str(INSTALL_HOOK), "--hooks-dir", str(hooks_dir), "--force"],
        cwd=repo,
    )
    assert install_result.returncode == 0, install_result.stderr

    (repo / ".hermes-gate").mkdir(exist_ok=True)
    hook_result = run([str(hooks_dir / "pre-push")], cwd=repo)
    assert hook_result.returncode == 0, hook_result.stderr
    assert hook_result.stdout == ""


def test_install_hook_uses_git_path_hooks_in_worktree(tmp_path):
    repo = init_repo(tmp_path)
    worktree = tmp_path / "wt"
    worktree_result = run(["git", "worktree", "add", str(worktree), "-d"], cwd=repo)
    assert worktree_result.returncode == 0, worktree_result.stderr

    isolated_git_env = {
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": str(tmp_path / "empty-gitconfig"),
    }
    (tmp_path / "empty-gitconfig").write_text("", encoding="utf-8")

    install_result = run(
        [sys.executable, str(INSTALL_HOOK), "--force"],
        cwd=worktree,
        env=isolated_git_env,
    )
    assert install_result.returncode == 0, install_result.stderr

    hooks_path_result = run(
        ["git", "rev-parse", "--git-path", "hooks"],
        cwd=worktree,
        env=isolated_git_env,
    )
    assert hooks_path_result.returncode == 0, hooks_path_result.stderr
    hook_dir = Path(hooks_path_result.stdout.strip())
    if not hook_dir.is_absolute():
        hook_dir = worktree / hook_dir
    assert (hook_dir.resolve() / "pre-push").exists()


def test_install_hook_and_run_pre_push_smoke(tmp_path):
    repo = init_repo(tmp_path)
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "write_gate.py").write_text(WRITE_GATE.read_text(encoding="utf-8"), encoding="utf-8")
    (scripts_dir / "validate_gate.py").write_text(VALIDATE_GATE.read_text(encoding="utf-8"), encoding="utf-8")

    head_sha = git_head(repo)
    write_reports(repo, head_sha)
    write_result = run(
        [
            sys.executable,
            str(scripts_dir / "write_gate.py"),
            "--review-status",
            "PASS",
            "--reviewer",
            "hermes-subagent-review",
            "--review-summary",
            "clean",
            "--review-report",
            ".hermes-gate/review.md",
            "--test-status",
            "PASS",
            "--tester",
            "hermes-subagent-test",
            "--test-summary",
            "clean",
            "--test-report",
            ".hermes-gate/test.md",
        ],
        cwd=repo,
    )
    assert write_result.returncode == 0, write_result.stderr

    hooks_dir = tmp_path / "hooks"
    install_result = run(
        [sys.executable, str(INSTALL_HOOK), "--hooks-dir", str(hooks_dir), "--force"],
        cwd=repo,
    )
    assert install_result.returncode == 0, install_result.stderr

    hook_path = hooks_dir / "pre-push"
    hook_result = run([str(hook_path)], cwd=repo)
    assert hook_result.returncode == 0, hook_result.stderr
    assert "pre-push gate passed" in hook_result.stdout
