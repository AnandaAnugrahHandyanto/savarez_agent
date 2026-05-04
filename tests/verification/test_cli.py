import json
import sys

from hermes_cli.verification.cli import run_verify


def test_run_verify_writes_reports_for_passing_command(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    output = tmp_path / "out"

    code = run_verify(
        repo=repo,
        task_type="cli-test",
        commands=[f"{sys.executable} -c \"print('ok')\""],
        output=output,
        timeout_seconds=10,
        family_map_path=None,
    )

    captured = capsys.readouterr()
    assert code == 0
    assert str(output / "verification.md") in captured.out
    data = json.loads((output / "verification.json").read_text())
    assert data["status"] == "partial"  # non-git repo limitation is honest
    assert data["checks"][0]["status"] == "passed"
    assert (output / "verification.md").exists()


def test_run_verify_returns_nonzero_for_failing_command(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    output = tmp_path / "out"

    code = run_verify(
        repo=repo,
        task_type="cli-test",
        commands=[f"{sys.executable} -c \"import sys; sys.exit(4)\""],
        output=output,
        timeout_seconds=10,
        family_map_path=None,
    )

    data = json.loads((output / "verification.json").read_text())
    assert code == 1
    assert data["status"] == "failed"
