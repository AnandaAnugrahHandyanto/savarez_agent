import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GUARD = REPO_ROOT / "scripts" / "runtime" / "codex_review_guard.py"


def _load_guard_module():
    spec = importlib.util.spec_from_file_location("codex_review_guard_under_test", GUARD)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_fake_codex(path: Path, body: str) -> Path:
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys, time\n"
        + body,
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _run_guard(tmp_path: Path, fake_codex: Path, *extra: str) -> subprocess.CompletedProcess:
    raw_log = tmp_path / "raw.log"
    return subprocess.run(
        [
            sys.executable,
            str(GUARD),
            "--codex-bin",
            str(fake_codex),
            "--prompt",
            "Review current uncommitted changes only.",
            "--workdir",
            str(tmp_path),
            "--raw-log",
            str(raw_log),
            *extra,
        ],
        cwd=str(tmp_path),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )


def test_guard_adds_required_codex_review_flags_and_returns_bounded_result(tmp_path):
    args_file = tmp_path / "args.json"
    fake = _write_fake_codex(
        tmp_path / "fake_codex.py",
        f"""
args_file = {str(args_file)!r}
args = sys.argv[1:]
open(args_file, 'w', encoding='utf-8').write(json.dumps(args))
final_path = args[args.index('--output-last-message') + 1]
open(final_path, 'w', encoding='utf-8').write(json.dumps({{
    'verdict': 'passed',
    'summary': 'No blockers.',
    'must_fix': [],
    'suggested_fixes': [],
    'verification_commands': ['git diff --check'],
    'final_judgment': '可以继续',
}}))
print(json.dumps({{'type': 'message', 'text': 'small progress'}}))
""",
    )

    proc = _run_guard(tmp_path, fake)

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "passed"
    assert result["raw_log_path"].endswith("raw.log")
    assert result["stdout_chars"] < 1000
    assert "small progress" not in proc.stdout

    args = json.loads(args_file.read_text(encoding="utf-8"))
    assert args[0] == "exec"
    sandbox_index = args.index("--sandbox")
    assert args[sandbox_index + 1] == "read-only"
    assert "--json" in args
    assert "--output-schema" in args
    assert "--output-last-message" in args
    color_index = args.index("--color")
    assert args[color_index + 1] == "never"


def test_guard_kills_source_flood_and_does_not_echo_source(tmp_path):
    fake = _write_fake_codex(
        tmp_path / "fake_codex.py",
        """
for i in range(5000):
    print(f'class Flood{{i}}:')
    print('    def method(self):')
    print('        return 1')
    sys.stdout.flush()
    time.sleep(0.0005)
""",
    )

    proc = _run_guard(
        tmp_path,
        fake,
        "--max-stdout-chars",
        "3000",
        "--source-line-threshold",
        "30",
        "--kill-grace-seconds",
        "0.1",
    )

    assert proc.returncode == 2, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "unusable"
    assert result["terminated_by_guard"] is True
    assert result["source_flood_detected"] is True
    assert result["raw_log_path"].endswith("raw.log")
    assert "class Flood" not in proc.stdout


def test_guard_kills_json_aggregated_output_source_flood(tmp_path):
    fake = _write_fake_codex(
        tmp_path / "fake_codex.py",
        """
source_blob = '\\n'.join(
    f'class Flood{i}:\\n    def method(self):\\n        return 1'
    for i in range(2000)
)
print(json.dumps({'type': 'item.completed', 'aggregated_output': source_blob}))
sys.stdout.flush()
time.sleep(5)
""",
    )

    proc = _run_guard(
        tmp_path,
        fake,
        "--max-stdout-chars",
        "1000000",
        "--source-line-threshold",
        "30",
        "--kill-grace-seconds",
        "0.1",
    )

    assert proc.returncode == 2, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "unusable"
    assert result["reason"] == "aggregated_output_flood"
    assert result["terminated_by_guard"] is True
    assert result["json_field_flood_detected"] is True
    assert result["json_flood_field"] == "aggregated_output"
    assert result["json_flood_source_like_lines"] >= 30
    assert "class Flood" not in proc.stdout


def test_guard_kills_json_content_diff_flood(tmp_path):
    fake = _write_fake_codex(
        tmp_path / "fake_codex.py",
        """
diff_blob = '\\n'.join(
    f'+changed line {i}'
    for i in range(80)
)
print(json.dumps({'type': 'command_execution', 'content': {'text': diff_blob}}))
sys.stdout.flush()
time.sleep(5)
""",
    )

    proc = _run_guard(
        tmp_path,
        fake,
        "--max-stdout-chars",
        "1000000",
        "--diff-line-threshold",
        "20",
        "--kill-grace-seconds",
        "0.1",
    )

    assert proc.returncode == 2, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "unusable"
    assert result["reason"] == "json_field_flood"
    assert result["terminated_by_guard"] is True
    assert result["json_field_flood_detected"] is True
    assert result["json_flood_field"] == "text"
    assert result["json_flood_diff_like_lines"] >= 20
    assert "+changed line" not in proc.stdout


def test_guard_detects_json_field_flood_without_trailing_newline_after_exit(tmp_path):
    fake = _write_fake_codex(
        tmp_path / "fake_codex.py",
        """
diff_blob = '\\n'.join(
    f'+changed line {i}'
    for i in range(80)
)
sys.stdout.write(json.dumps({'type': 'command_execution', 'content': {'text': diff_blob}}))
sys.stdout.flush()
""",
    )

    proc = _run_guard(
        tmp_path,
        fake,
        "--max-stdout-chars",
        "1000000",
        "--diff-line-threshold",
        "20",
        "--kill-grace-seconds",
        "0.1",
    )

    assert proc.returncode == 2, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "unusable"
    assert result["reason"] == "json_field_flood"
    assert result["terminated_by_guard"] is False
    assert result["process_exited_before_guard"] is True
    assert result["json_field_flood_detected"] is True
    assert result["json_flood_field"] == "text"
    assert result["json_flood_diff_like_lines"] >= 20
    assert "+changed line" not in proc.stdout


def test_guard_injects_bounded_review_packet_and_isolates_codex_workdir(tmp_path):
    args_file = tmp_path / "args.json"
    cwd_file = tmp_path / "cwd.txt"
    packet = tmp_path / "review_packet.md"
    packet.write_text("# Bounded Codex review packet\nPACKET_SENTINEL\n", encoding="utf-8")
    fake = _write_fake_codex(
        tmp_path / "fake_codex.py",
        f"""
args_file = {str(args_file)!r}
cwd_file = {str(cwd_file)!r}
args = sys.argv[1:]
open(args_file, 'w', encoding='utf-8').write(json.dumps(args))
open(cwd_file, 'w', encoding='utf-8').write(os.getcwd())
final_path = args[args.index('--output-last-message') + 1]
open(final_path, 'w', encoding='utf-8').write(json.dumps({{
    'verdict': 'passed',
    'summary': 'Packet-only review passed.',
    'must_fix': [],
    'suggested_fixes': [],
    'verification_commands': ['python -m pytest tests/scripts/test_codex_review_guard.py -q -o addopts='],
    'final_judgment': '可以继续',
}}))
""",
    )

    proc = _run_guard(tmp_path, fake, "--review-packet-file", str(packet))

    assert proc.returncode == 0, proc.stdout + proc.stderr
    args = json.loads(args_file.read_text(encoding="utf-8"))
    prompt = args[-1]
    assert "PACKET_SENTINEL" in prompt
    assert "Do not run shell commands" in prompt
    assert "Review only the bounded packet" in prompt
    assert "--skip-git-repo-check" in args
    assert Path(cwd_file.read_text(encoding="utf-8")).resolve() != tmp_path.resolve()


def test_guard_recovers_structured_review_from_raw_log_before_json_field_flood(tmp_path):
    review = {
        "verdict": "failed",
        "summary": "Recovered blocker before flood.",
        "must_fix": ["json fallback must preserve blocker"],
        "suggested_fixes": [],
        "verification_commands": ["git diff --check"],
        "final_judgment": "需要先修",
    }
    fake = _write_fake_codex(
        tmp_path / "fake_codex.py",
        f"""
review = {json.dumps(review, ensure_ascii=False)!r}
print(json.dumps({{'type': 'message', 'text': review}}, ensure_ascii=False))
diff_blob = '\\n'.join(f'+changed line {{i}}' for i in range(80))
print(json.dumps({{'type': 'item.completed', 'aggregated_output': diff_blob}}, ensure_ascii=False))
sys.stdout.flush()
time.sleep(5)
""",
    )

    proc = _run_guard(
        tmp_path,
        fake,
        "--max-stdout-chars",
        "1000000",
        "--diff-line-threshold",
        "20",
        "--kill-grace-seconds",
        "0.1",
    )

    assert proc.returncode == 1, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "failed"
    assert result["reason"] == "recovered_after_aggregated_output_flood"
    assert result["review_recovered_from_flood"] is True
    assert result["flood_reason"] == "aggregated_output_flood"
    assert result["review"]["must_fix"] == ["json fallback must preserve blocker"]
    assert "+changed line" not in proc.stdout


def test_guard_does_not_pass_recovered_passed_review_after_json_field_flood(tmp_path):
    review = {
        "verdict": "passed",
        "summary": "Recovered pass before flood.",
        "must_fix": [],
        "suggested_fixes": [],
        "verification_commands": ["git diff --check"],
        "final_judgment": "可以继续",
    }
    fake = _write_fake_codex(
        tmp_path / "fake_codex.py",
        f"""
review = {json.dumps(review, ensure_ascii=False)!r}
print(json.dumps({{'type': 'message', 'text': review}}, ensure_ascii=False))
diff_blob = '\\n'.join(f'+changed line {{i}}' for i in range(80))
print(json.dumps({{'type': 'item.completed', 'aggregated_output': diff_blob}}, ensure_ascii=False))
sys.stdout.flush()
time.sleep(5)
""",
    )

    proc = _run_guard(
        tmp_path,
        fake,
        "--max-stdout-chars",
        "1000000",
        "--diff-line-threshold",
        "20",
        "--kill-grace-seconds",
        "0.1",
    )

    assert proc.returncode != 0, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "unusable"
    assert result["reason"] == "recovered_after_aggregated_output_flood"
    assert result["review_recovered_from_flood"] is True
    assert result["review"]["verdict"] == "passed"
    assert "+changed line" not in proc.stdout


def test_guard_recovers_structured_review_even_when_later_output_exceeds_raw_tail(tmp_path):
    review = {
        "verdict": "failed",
        "summary": "Recovered old blocker before long progress.",
        "must_fix": ["streaming recovery must not depend on raw tail"],
        "suggested_fixes": [],
        "verification_commands": ["git diff --check"],
        "final_judgment": "需要先修",
    }
    fake = _write_fake_codex(
        tmp_path / "fake_codex.py",
        f"""
review = {json.dumps(review, ensure_ascii=False)!r}
print(json.dumps({{'type': 'message', 'text': review}}, ensure_ascii=False))
for i in range(5000):
    print(json.dumps({{'type': 'message', 'text': 'progress ' + ('x' * 40)}}))
diff_blob = '\\n'.join(f'+changed line {{i}}' for i in range(80))
print(json.dumps({{'type': 'item.completed', 'aggregated_output': diff_blob}}, ensure_ascii=False))
sys.stdout.flush()
time.sleep(5)
""",
    )

    proc = _run_guard(
        tmp_path,
        fake,
        "--max-stdout-chars",
        "1000000",
        "--max-stdout-lines",
        "10000",
        "--diff-line-threshold",
        "20",
        "--kill-grace-seconds",
        "0.1",
    )

    assert proc.returncode == 1, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "failed"
    assert result["reason"] == "recovered_after_aggregated_output_flood"
    assert result["review"]["must_fix"] == ["streaming recovery must not depend on raw tail"]
    assert "progress x" not in proc.stdout
    assert "+changed line" not in proc.stdout


def test_raw_log_recovery_scans_before_large_later_output(tmp_path):
    guard = _load_guard_module()
    review = {
        "verdict": "failed",
        "summary": "Recovered from full raw log.",
        "must_fix": ["full raw scan must find older review"],
        "suggested_fixes": [],
        "verification_commands": ["git diff --check"],
        "final_judgment": "需要先修",
    }
    raw_log = tmp_path / "raw.log"
    raw_log.write_text(
        json.dumps({"type": "message", "text": json.dumps(review, ensure_ascii=False)}, ensure_ascii=False)
        + "\n"
        + "\n".join(json.dumps({"type": "message", "text": "x" * 80}) for _ in range(5000)),
        encoding="utf-8",
    )

    recovered = guard._recover_review_from_raw_log(raw_log)

    assert recovered["must_fix"] == ["full raw scan must find older review"]


def test_guard_marks_missing_final_file_unusable(tmp_path):
    fake = _write_fake_codex(
        tmp_path / "fake_codex.py",
        """
print(json.dumps({'type': 'message', 'text': 'done without final'}))
""",
    )

    proc = _run_guard(tmp_path, fake)

    assert proc.returncode == 2, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "unusable"
    assert result["reason"] == "final_file_missing"
    assert result["raw_log_path"].endswith("raw.log")


def test_guard_marks_malformed_final_review_schema_unusable(tmp_path):
    fake = _write_fake_codex(
        tmp_path / "fake_codex.py",
        """
args = sys.argv[1:]
final_path = args[args.index('--output-last-message') + 1]
open(final_path, 'w', encoding='utf-8').write(json.dumps({'summary': 'partial only'}))
""",
    )

    proc = _run_guard(tmp_path, fake)

    assert proc.returncode == 2, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "unusable"
    assert result["reason"] == "review_schema_invalid"
    assert result["review_schema_error"] == "missing_verdict"


def test_guard_marks_partial_recovered_review_schema_unusable(tmp_path):
    fake = _write_fake_codex(
        tmp_path / "fake_codex.py",
        """
print(json.dumps({'type': 'message', 'text': json.dumps({'final_judgment': '可以继续'})}, ensure_ascii=False))
diff_blob = '\\n'.join(f'+changed line {i}' for i in range(80))
print(json.dumps({'type': 'item.completed', 'aggregated_output': diff_blob}, ensure_ascii=False))
sys.stdout.flush()
time.sleep(5)
""",
    )

    proc = _run_guard(
        tmp_path,
        fake,
        "--max-stdout-chars",
        "1000000",
        "--diff-line-threshold",
        "20",
        "--kill-grace-seconds",
        "0.1",
    )

    assert proc.returncode == 2, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "unusable"
    assert result["reason"] == "recovered_review_schema_invalid_after_aggregated_output_flood"
    assert result["review_recovered_from_flood"] is True
    assert result["review_schema_error"] == "missing_verdict"
    assert "+changed line" not in proc.stdout


def test_guard_does_not_pass_when_recovered_review_passed_before_flood(tmp_path):
    review = {
        "verdict": "passed",
        "summary": "Recovered pass before flood.",
        "must_fix": [],
        "suggested_fixes": [],
        "verification_commands": ["git diff --check"],
        "final_judgment": "可以继续",
    }
    fake = _write_fake_codex(
        tmp_path / "fake_codex.py",
        f"""
review = {json.dumps(review, ensure_ascii=False)!r}
print(json.dumps({{'type': 'message', 'text': review}}, ensure_ascii=False))
diff_blob = '\\n'.join(f'+changed line {{i}}' for i in range(80))
print(json.dumps({{'type': 'item.completed', 'aggregated_output': diff_blob}}, ensure_ascii=False))
sys.stdout.flush()
time.sleep(5)
""",
    )

    proc = _run_guard(
        tmp_path,
        fake,
        "--max-stdout-chars",
        "1000000",
        "--diff-line-threshold",
        "20",
        "--kill-grace-seconds",
        "0.1",
    )

    assert proc.returncode == 2, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "unusable"
    assert result["reason"] == "recovered_after_aggregated_output_flood"
    assert result["review_recovered_from_flood"] is True
    assert result["review"]["verdict"] == "passed"
    assert "+changed line" not in proc.stdout
