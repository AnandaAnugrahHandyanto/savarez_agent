import sys

from hermes_cli.verification.commands import run_command_check


def test_run_command_check_records_passing_command(tmp_path):
    check, artifact = run_command_check(
        name="hello",
        command=f"{sys.executable} -c \"print('hi')\"",
        cwd=tmp_path,
        output_dir=tmp_path / "out",
        timeout_seconds=10,
    )

    assert check.status == "passed"
    assert check.exit_code == 0
    assert "hi" in check.stdout_tail
    assert artifact.path.endswith("hello.log")


def test_run_command_check_records_failing_command(tmp_path):
    check, artifact = run_command_check(
        name="fail",
        command=f"{sys.executable} -c \"import sys; print('bad'); sys.exit(7)\"",
        cwd=tmp_path,
        output_dir=tmp_path / "out",
        timeout_seconds=10,
    )

    assert check.status == "failed"
    assert check.exit_code == 7
    assert "bad" in check.stdout_tail
    assert artifact.kind == "log"


def test_run_command_check_records_timeout(tmp_path):
    check, artifact = run_command_check(
        name="slow",
        command=f"{sys.executable} -c \"import time; time.sleep(2)\"",
        cwd=tmp_path,
        output_dir=tmp_path / "out",
        timeout_seconds=0.1,
    )

    assert check.status == "failed"
    assert check.exit_code is None
    assert "timed out" in check.message.lower()
    assert artifact.path.endswith("slow.log")
