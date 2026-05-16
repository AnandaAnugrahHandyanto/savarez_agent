import subprocess
from pathlib import Path
from shutil import copy2


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_validate(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "scripts/validate_pr.sh", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def make_temp_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    copy2(REPO_ROOT / "scripts" / "validate_pr.sh", scripts / "validate_pr.sh")
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return repo


def run_temp_validate(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "scripts/validate_pr.sh", "--scope", "auto", "--base", "HEAD", "--dry-run"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )


def test_docs_scope_is_shell_syntax_only():
    result = run_validate("--scope", "docs", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert "Validation scope: docs" in result.stdout
    assert "+ bash -n scripts/validate_pr.sh" in result.stdout
    assert "scripts/run_tests.sh" not in result.stdout


def test_scripts_scope_delegates_pytest_to_canonical_runner():
    result = run_validate("--scope", "scripts", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert "Validation scope: scripts" in result.stdout
    assert "+ bash -n scripts/validate_pr.sh" in result.stdout
    assert "+ bash -n scripts/run_tests.sh" in result.stdout
    assert "+ scripts/run_tests.sh tests/test_validation_contract.py" in result.stdout


def test_full_scope_uses_canonical_runner_without_direct_pytest():
    result = run_validate("--scope", "full", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert "Validation scope: full" in result.stdout
    assert "+ scripts/run_tests.sh" in result.stdout
    assert "python -m pytest" not in result.stdout


def test_unknown_scope_fails_with_usage():
    result = run_validate("--scope", "unknown", "--dry-run")

    assert result.returncode == 2
    assert "error: unknown scope: unknown" in result.stderr
    assert "Usage: scripts/validate_pr.sh" in result.stderr


def test_auto_scope_escalates_mixed_runtime_and_script_changes(tmp_path):
    repo = make_temp_repo(tmp_path)
    (repo / "scripts" / "validate_pr.sh").write_text(
        (repo / "scripts" / "validate_pr.sh").read_text(encoding="utf-8") + "\n# local edit\n",
        encoding="utf-8",
    )
    (repo / "runtime.py").write_text("print('runtime')\n", encoding="utf-8")

    result = run_temp_validate(repo)

    assert result.returncode == 0, result.stderr
    assert "Validation scope: full" in result.stdout
    assert "+ scripts/run_tests.sh" in result.stdout


def test_auto_scope_does_not_treat_all_tests_as_contract_tests(tmp_path):
    repo = make_temp_repo(tmp_path)
    test_dir = repo / "tests" / "agent"
    test_dir.mkdir(parents=True)
    (test_dir / "test_runtime_behavior.py").write_text("def test_example(): pass\n", encoding="utf-8")

    result = run_temp_validate(repo)

    assert result.returncode == 0, result.stderr
    assert "Validation scope: full" in result.stdout


def test_auto_scope_contract_test_only_uses_tests_scope(tmp_path):
    repo = make_temp_repo(tmp_path)
    test_dir = repo / "tests"
    test_dir.mkdir()
    (test_dir / "test_validation_contract.py").write_text("def test_example(): pass\n", encoding="utf-8")

    result = run_temp_validate(repo)

    assert result.returncode == 0, result.stderr
    assert "Validation scope: tests" in result.stdout
    assert "+ scripts/run_tests.sh tests/test_validation_contract.py" in result.stdout
