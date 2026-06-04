import json
import os
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = REPO_ROOT / "scripts" / "runtime" / "codex_stage_runner.py"
REAL_IMPL_GUARD = REPO_ROOT / "scripts" / "runtime" / "codex_impl_guard.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "demo.py").write_text("VALUE = 'old'\n", encoding="utf-8")
    _git(repo, "add", "demo.py")
    _git(repo, "commit", "-m", "init")


def _write_fake_guard(path: Path) -> Path:
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "args = sys.argv[1:]\n"
        "prompt = args[args.index('--prompt-file') + 1]\n"
        "raw_log = args[args.index('--raw-log') + 1] if '--raw-log' in args else '/tmp/raw-' + os.path.basename(prompt)\n"
        "final_file = args[args.index('--final-file') + 1] if '--final-file' in args else '/tmp/final-' + os.path.basename(prompt)\n"
        "status = open(prompt, encoding='utf-8').read().strip()\n"
        "calls = os.environ.get('FAKE_GUARD_CALLS')\n"
        "if calls:\n"
        "    with open(calls, 'a', encoding='utf-8') as handle:\n"
        "        handle.write(os.path.basename(prompt) + '\\n')\n"
        "result = {\n"
        "    'status': status,\n"
        "    'reason': 'fake_' + status,\n"
        "    'raw_log_path': raw_log,\n"
        "    'final_file': final_file,\n"
        "    'verification': [{'status': 'passed', 'id': 'fake'}] if status == 'passed' else [],\n"
        "}\n"
        "print(json.dumps(result))\n"
        "sys.exit(0 if status in {'passed', 'review_needed'} else 1)\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _write_plan(repo: Path, path: Path, slices: list[dict], **extra) -> Path:
    plan = {"repo": str(repo), "slices": slices, **extra}
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def _slice(repo: Path, name: str, status: str) -> dict:
    prompt = repo / f"{name}.md"
    prompt.write_text(status, encoding="utf-8")
    return {
        "id": name,
        "prompt_file": str(prompt),
        "allowed_files": ["demo.py"],
        "allowed_globs": [],
        "verify_cmd_ids": ["none"],
    }


def _run_runner(
    plan: Path | None,
    fake_guard: Path | None = None,
    calls: Path | None = None,
    raw_dir: Path | None = None,
    fake_codex: Path | None = None,
    timeout_seconds: float | None = None,
) -> subprocess.CompletedProcess:
    argv = [sys.executable, str(RUNNER)]
    if plan is not None:
        argv.extend(["--plan-file", str(plan)])
    if fake_guard is not None:
        argv.extend(["--impl-guard-file", str(fake_guard)])
    if raw_dir is not None:
        argv.extend(["--raw-dir", str(raw_dir)])
    if timeout_seconds is not None:
        argv.extend(["--timeout-seconds", str(timeout_seconds)])
    env = os.environ.copy()
    if calls is not None:
        env["FAKE_GUARD_CALLS"] = str(calls)
    if fake_codex is not None:
        env["CODEX_BIN"] = str(fake_codex)
        env["HERMES_CODEX_IMPL_GUARD_ALLOW_FAKE_CODEX"] = "1"
    return subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20, env=env)


def _write_fake_codex(path: Path) -> Path:
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys, time\n"
        "prompt = sys.argv[-1]\n"
        "if 'SCENARIO:allowed-change' in prompt:\n"
        "    open('demo.py', 'w', encoding='utf-8').write(\"VALUE = 'new'\\n\")\n"
        "elif 'SCENARIO:nonzero-no-diff' in prompt:\n"
        "    sys.exit(9)\n"
        "elif 'SCENARIO:outside-allowlist' in prompt:\n"
        "    open('outside.py', 'w', encoding='utf-8').write('bad = True\\n')\n"
        "elif 'SCENARIO:timeout-safe-diff' in prompt:\n"
        "    open('demo.py', 'w', encoding='utf-8').write(\"VALUE = 'timeout'\\n\")\n"
        "    sys.stdout.flush()\n"
        "    time.sleep(5)\n"
        "elif 'SCENARIO:passed-currently-review-needed' in prompt:\n"
        "    open('demo.py', 'w', encoding='utf-8').write(\"VALUE = 'safe'\\n\")\n"
        "    open('slice2-ran.txt', 'w', encoding='utf-8').write('ran')\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _smoke_slice(repo: Path, name: str, scenario: str) -> dict:
    prompt = repo.parent / f"{name}.md"
    prompt.write_text(f"SCENARIO:{scenario}\n", encoding="utf-8")
    return {
        "id": name,
        "prompt_file": str(prompt),
        "allowed_files": ["demo.py"],
        "allowed_globs": [],
        "verify_cmd_ids": ["none"],
    }


def test_missing_plan_outputs_json():
    proc = _run_runner(None)

    assert proc.returncode == 1
    result = json.loads(proc.stdout)
    assert result["status"] == "unusable"
    assert result["reason"] == "missing_plan"
    assert proc.stderr == ""


def test_plan_file_not_found_outputs_json(tmp_path):
    proc = _run_runner(tmp_path / "missing-plan.json")

    assert proc.returncode == 1
    result = json.loads(proc.stdout)
    assert result["status"] == "unusable"
    assert result["reason"] == "missing_plan"


def test_invalid_json_outputs_json(tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text("{not json", encoding="utf-8")

    proc = _run_runner(plan)

    result = json.loads(proc.stdout)
    assert result["status"] == "unusable"
    assert result["reason"] == "invalid_json"


def test_duplicate_id_is_rejected(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    s1 = _slice(repo, "slice1", "passed")
    s2 = _slice(repo, "slice1", "passed")
    plan = _write_plan(repo, tmp_path / "plan.json", [s1, s2])

    proc = _run_runner(plan)

    result = json.loads(proc.stdout)
    assert result["status"] == "unusable"
    assert result["reason"] == "duplicate_slice_id"


def test_empty_slices_is_rejected(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    plan = _write_plan(repo, tmp_path / "plan.json", [])

    proc = _run_runner(plan)

    result = json.loads(proc.stdout)
    assert result["status"] == "unusable"
    assert result["reason"] == "empty_slices"


def test_invalid_allowed_glob_is_rejected_by_runner_before_impl_guard(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    fake = _write_fake_guard(tmp_path / "fake_guard.py")
    item = _slice(repo, "slice1", "passed")
    item["allowed_globs"] = ["src/../*.py"]
    plan = _write_plan(repo, tmp_path / "plan.json", [item])

    proc = _run_runner(plan, fake)

    result = json.loads(proc.stdout)
    assert result["status"] == "unusable"
    assert result["reason"] == "invalid_allowlist"


def test_raw_dir_inside_repo_is_rejected_before_directory_creation(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    fake = _write_fake_guard(tmp_path / "fake_guard.py")
    raw_dir = repo / "runner-raw"
    plan = _write_plan(repo, tmp_path / "plan.json", [_slice(repo, "slice1", "review_needed")])

    proc = _run_runner(plan, fake, raw_dir=raw_dir)

    result = json.loads(proc.stdout)
    assert result["status"] == "unusable"
    assert result["reason"] == "unsafe_raw_dir"
    assert not raw_dir.exists()


def test_review_needed_stops_before_slice2(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    fake = _write_fake_guard(tmp_path / "fake_guard.py")
    calls = tmp_path / "calls.txt"
    plan = _write_plan(repo, tmp_path / "plan.json", [_slice(repo, "slice1", "review_needed"), _slice(repo, "slice2", "passed")])

    proc = _run_runner(plan, fake, calls)

    result = json.loads(proc.stdout)
    assert result["status"] == "stopped"
    assert result["reason"] == "slice_review_needed"
    assert result["completed_slices"] == []
    assert result["stopped_slice"] == "slice1"
    assert calls.read_text(encoding="utf-8").splitlines() == ["slice1.md"]


def test_failed_blocked_and_takeover_stop_before_slice2(tmp_path):
    for status in ["failed", "blocked_by_allowlist", "takeover_candidate"]:
        repo = tmp_path / status / "repo"
        _init_repo(repo)
        fake = _write_fake_guard(tmp_path / status / "fake_guard.py")
        calls = tmp_path / status / "calls.txt"
        plan = _write_plan(repo, tmp_path / status / "plan.json", [_slice(repo, "slice1", status), _slice(repo, "slice2", "passed")])

        proc = _run_runner(plan, fake, calls)

        result = json.loads(proc.stdout)
        assert result["status"] == "stopped"
        assert result["reason"] == f"slice_{status}"
        assert result["stopped_slice"] == "slice1"
        assert calls.read_text(encoding="utf-8").splitlines() == ["slice1.md"]


def test_passed_default_policy_stops_before_slice2(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    fake = _write_fake_guard(tmp_path / "fake_guard.py")
    calls = tmp_path / "calls.txt"
    plan = _write_plan(repo, tmp_path / "plan.json", [_slice(repo, "slice1", "passed"), _slice(repo, "slice2", "review_needed")])

    proc = _run_runner(plan, fake, calls)

    result = json.loads(proc.stdout)
    assert result["status"] == "stopped"
    assert result["reason"] == "slice_passed"
    assert result["completed_slices"] == []
    assert result["stopped_slice"] == "slice1"
    assert calls.read_text(encoding="utf-8").splitlines() == ["slice1.md"]


def test_passed_continue_on_passed_runs_slice2(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    fake = _write_fake_guard(tmp_path / "fake_guard.py")
    calls = tmp_path / "calls.txt"
    plan = _write_plan(
        repo,
        tmp_path / "plan.json",
        [_slice(repo, "slice1", "passed"), _slice(repo, "slice2", "passed")],
        continue_policy="continue-on-passed",
    )

    proc = _run_runner(plan, fake, calls)

    result = json.loads(proc.stdout)
    assert result["status"] == "completed"
    assert result["completed_slices"] == ["slice1", "slice2"]
    assert result["stopped_slice"] is None
    assert calls.read_text(encoding="utf-8").splitlines() == ["slice1.md", "slice2.md"]


def test_unknown_status_stops(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    fake = _write_fake_guard(tmp_path / "fake_guard.py")
    plan = _write_plan(repo, tmp_path / "plan.json", [_slice(repo, "slice1", "surprise"), _slice(repo, "slice2", "passed")])

    proc = _run_runner(plan, fake)

    result = json.loads(proc.stdout)
    assert result["status"] == "stopped"
    assert result["reason"] == "unknown_slice_status"
    assert result["stopped_slice"] == "slice1"
    assert len(result["slice_results"]) == 1


def test_continue_on_passed_rejects_malformed_verification(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    guard = tmp_path / "malformed_verification_guard.py"
    guard.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "print(json.dumps({'status': 'passed', 'reason': 'fake_passed', 'verification': ['bad']}))\n",
        encoding="utf-8",
    )
    guard.chmod(0o755)
    calls = tmp_path / "calls.txt"
    plan = _write_plan(
        repo,
        tmp_path / "plan.json",
        [_slice(repo, "slice1", "passed"), _slice(repo, "slice2", "review_needed")],
        continue_policy="continue-on-passed",
    )

    proc = _run_runner(plan, guard, calls)

    result = json.loads(proc.stdout)
    assert result["status"] == "stopped"
    assert result["reason"] == "slice_passed"
    assert result["stopped_slice"] == "slice1"
    assert result["completed_slices"] == []
    assert not calls.exists()


def test_stdout_bounded_json(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    prompt = repo / "slice1.md"
    prompt.write_text("passed", encoding="utf-8")
    huge_files = [f"file_{index}.py" for index in range(500)]
    plan = _write_plan(
        repo,
        tmp_path / "plan.json",
        [{
            "id": "slice1",
            "prompt_file": str(prompt),
            "allowed_files": huge_files,
            "allowed_globs": [],
            "verify_cmd_ids": ["none"],
        }],
        continue_policy="continue-on-passed",
    )
    fake = _write_fake_guard(tmp_path / "fake_guard.py")

    proc = _run_runner(plan, fake)

    json.loads(proc.stdout)
    assert len(proc.stdout) < 20000


def test_impl_guard_stdout_is_capped_before_json_parsing(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    noisy_guard = tmp_path / "noisy_guard.py"
    noisy_guard.write_text(
        "#!/usr/bin/env python3\n"
        "print('x' * 250000)\n",
        encoding="utf-8",
    )
    noisy_guard.chmod(0o755)
    plan = _write_plan(repo, tmp_path / "plan.json", [_slice(repo, "slice1", "passed")])

    proc = _run_runner(plan, noisy_guard)

    assert proc.returncode == 1
    assert len(proc.stdout) < 20000
    result = json.loads(proc.stdout)
    assert result["status"] == "stopped"
    assert result["reason"] == "slice_unusable"
    assert result["slice_results"][0]["reason"] == "impl_guard_stdout_limit_exceeded"


def test_impl_guard_stderr_is_capped_before_json_parsing(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    noisy_guard = tmp_path / "noisy_stderr_guard.py"
    noisy_guard.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "sys.stderr.write('x' * 250000)\n",
        encoding="utf-8",
    )
    noisy_guard.chmod(0o755)
    plan = _write_plan(repo, tmp_path / "plan.json", [_slice(repo, "slice1", "passed")])

    proc = _run_runner(plan, noisy_guard)

    assert proc.returncode == 1
    assert proc.stderr == ""
    assert len(proc.stdout) < 20000
    result = json.loads(proc.stdout)
    assert result["status"] == "stopped"
    assert result["reason"] == "slice_unusable"
    assert result["slice_results"][0]["reason"] == "impl_guard_stderr_limit_exceeded"


def test_impl_guard_nonzero_exit_with_passed_json_stops_before_slice2(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    guard = tmp_path / "nonzero_guard.py"
    guard.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "print(json.dumps({'status': 'passed', 'reason': 'fake_passed', 'verification': [{'status': 'passed'}]}))\n"
        "sys.exit(1)\n",
        encoding="utf-8",
    )
    guard.chmod(0o755)
    calls = tmp_path / "calls.txt"
    plan = _write_plan(repo, tmp_path / "plan.json", [_slice(repo, "slice1", "passed"), _slice(repo, "slice2", "review_needed")])

    proc = _run_runner(plan, guard, calls)

    result = json.loads(proc.stdout)
    assert result["status"] == "stopped"
    assert result["reason"] == "slice_unusable"
    assert result["stopped_slice"] == "slice1"
    assert result["slice_results"][0]["reason"] == "impl_guard_nonzero_exit"
    assert not calls.exists()


def test_impl_guard_file_change_stops_before_next_slice(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    guard = tmp_path / "self_mutating_guard.py"
    guard.write_text(
        "#!/usr/bin/env python3\n"
        "import json, pathlib, sys\n"
        "pathlib.Path(__file__).write_text(pathlib.Path(__file__).read_text(encoding='utf-8') + '# changed\\n', encoding='utf-8')\n"
        "print(json.dumps({'status': 'passed', 'reason': 'fake_passed', 'verification': [{'status': 'passed'}]}))\n",
        encoding="utf-8",
    )
    guard.chmod(0o755)
    calls = tmp_path / "calls.txt"
    plan = _write_plan(
        repo,
        tmp_path / "plan.json",
        [_slice(repo, "slice1", "passed"), _slice(repo, "slice2", "review_needed")],
        continue_policy="continue-on-passed",
    )

    proc = _run_runner(plan, guard, calls)

    result = json.loads(proc.stdout)
    assert result["status"] == "stopped"
    assert result["reason"] == "slice_unusable"
    assert result["stopped_slice"] == "slice1"
    assert result["slice_results"][0]["reason"] == "impl_guard_file_changed"
    assert not calls.exists()


def test_impl_guard_timeout_kills_child_process_group(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    marker = repo / "child-wrote.txt"
    guard = tmp_path / "spawning_guard.py"
    guard.write_text(
        "#!/usr/bin/env python3\n"
        "import subprocess, sys, time\n"
        "subprocess.Popen([sys.executable, '-c', "
        + repr("import pathlib, time; time.sleep(11); pathlib.Path(%r).write_text('child alive', encoding='utf-8')" % str(marker))
        + "])\n"
        "time.sleep(12)\n",
        encoding="utf-8",
    )
    guard.chmod(0o755)
    plan = _write_plan(repo, tmp_path / "plan.json", [_slice(repo, "slice1", "passed")])

    proc = _run_runner(plan, guard, timeout_seconds=0.1)
    time.sleep(1.4)

    result = json.loads(proc.stdout)
    assert result["status"] == "stopped"
    assert result["reason"] == "slice_unusable"
    assert result["slice_results"][0]["reason"] == "impl_guard_timeout"
    assert not marker.exists()


def test_raw_and_final_paths_present_in_slice_result(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    fake = _write_fake_guard(tmp_path / "fake_guard.py")
    raw_dir = tmp_path / "runner-raw"
    plan = _write_plan(repo, tmp_path / "plan.json", [_slice(repo, "slice1", "review_needed")])

    proc = _run_runner(plan, fake, raw_dir=raw_dir)

    result = json.loads(proc.stdout)
    slice_result = result["slice_results"][0]
    assert slice_result["raw_log_path"] == str(raw_dir / "slice1.raw.log")
    assert slice_result["final_file"] == str(raw_dir / "slice1.final.json")


def test_smoke_real_impl_guard_allowed_change_stops_before_slice2(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    fake_codex = _write_fake_codex(tmp_path / "codex-yuna")
    raw_dir = tmp_path / "runner-raw"
    plan = _write_plan(
        repo,
        tmp_path / "plan.json",
        [
            _smoke_slice(repo, "slice1", "allowed-change"),
            _smoke_slice(repo, "slice2", "passed-currently-review-needed"),
        ],
    )

    proc = _run_runner(plan, REAL_IMPL_GUARD, raw_dir=raw_dir, fake_codex=fake_codex)

    assert proc.returncode == 1, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "stopped"
    assert result["reason"] == "slice_review_needed"
    assert result["completed_slices"] == []
    assert result["stopped_slice"] == "slice1"
    assert len(result["slice_results"]) == 1
    guard_result = result["slice_results"][0]["impl_guard_result"]
    assert guard_result["status"] == "review_needed"
    assert guard_result["changed_files"] == ["demo.py"]
    assert guard_result["allowlist_violations"] == []
    assert guard_result["verification"][0]["status"] == "skipped"
    assert not (repo / "slice2-ran.txt").exists()


def test_smoke_real_impl_guard_continue_on_passed_still_stops_on_review_needed(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    fake_codex = _write_fake_codex(tmp_path / "codex-yuna")
    plan = _write_plan(
        repo,
        tmp_path / "plan.json",
        [
            _smoke_slice(repo, "slice1", "allowed-change"),
            _smoke_slice(repo, "slice2", "passed-currently-review-needed"),
        ],
        continue_policy="continue-on-passed",
    )

    proc = _run_runner(plan, REAL_IMPL_GUARD, fake_codex=fake_codex)

    assert proc.returncode == 1, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "stopped"
    assert result["reason"] == "slice_review_needed"
    assert result["completed_slices"] == []
    assert result["stopped_slice"] == "slice1"
    assert len(result["slice_results"]) == 1
    guard_result = result["slice_results"][0]["impl_guard_result"]
    assert guard_result["status"] == "review_needed"
    assert guard_result["reason"] == "codex_exit_zero_safe_diff"
    assert not (repo / "slice2-ran.txt").exists()


def test_smoke_real_impl_guard_nonzero_no_diff_stops_failed(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    fake_codex = _write_fake_codex(tmp_path / "codex-yuna")
    plan = _write_plan(
        repo,
        tmp_path / "plan.json",
        [
            _smoke_slice(repo, "slice1", "nonzero-no-diff"),
            _smoke_slice(repo, "slice2", "allowed-change"),
        ],
    )

    proc = _run_runner(plan, REAL_IMPL_GUARD, fake_codex=fake_codex)

    assert proc.returncode == 1, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "stopped"
    assert result["reason"] == "slice_failed"
    assert result["stopped_slice"] == "slice1"
    assert len(result["slice_results"]) == 1
    guard_result = result["slice_results"][0]["impl_guard_result"]
    assert guard_result["status"] == "failed"
    assert guard_result["reason"] == "codex_nonzero_without_diff"
    assert guard_result["changed_files"] == []
    assert guard_result["untracked_files"] == []


def test_smoke_real_impl_guard_allowlist_violation_stops_blocked(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    fake_codex = _write_fake_codex(tmp_path / "codex-yuna")
    plan = _write_plan(
        repo,
        tmp_path / "plan.json",
        [
            _smoke_slice(repo, "slice1", "outside-allowlist"),
            _smoke_slice(repo, "slice2", "allowed-change"),
        ],
    )

    proc = _run_runner(plan, REAL_IMPL_GUARD, fake_codex=fake_codex)

    assert proc.returncode == 1, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "stopped"
    assert result["reason"] == "slice_blocked_by_allowlist"
    assert result["stopped_slice"] == "slice1"
    assert len(result["slice_results"]) == 1
    guard_result = result["slice_results"][0]["impl_guard_result"]
    assert guard_result["status"] == "blocked_by_allowlist"
    assert guard_result["allowlist_violations"] == ["outside.py"]
    assert guard_result["untracked_files"] == ["outside.py"]
    assert (repo / "outside.py").exists()


def test_smoke_real_impl_guard_timeout_safe_diff_stops_takeover(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    fake_codex = _write_fake_codex(tmp_path / "codex-yuna")
    plan = _write_plan(
        repo,
        tmp_path / "plan.json",
        [
            _smoke_slice(repo, "slice1", "timeout-safe-diff"),
            _smoke_slice(repo, "slice2", "allowed-change"),
        ],
    )

    proc = _run_runner(plan, REAL_IMPL_GUARD, fake_codex=fake_codex, timeout_seconds=0.2)

    assert proc.returncode == 1, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "stopped"
    assert result["reason"] == "slice_takeover_candidate"
    assert result["stopped_slice"] == "slice1"
    assert len(result["slice_results"]) == 1
    guard_result = result["slice_results"][0]["impl_guard_result"]
    assert guard_result["status"] == "takeover_candidate"
    assert guard_result["reason"] == "codex_terminated_with_safe_diff"
    assert guard_result["codex_reason"] == "timeout"
    assert guard_result["changed_files"] == ["demo.py"]
