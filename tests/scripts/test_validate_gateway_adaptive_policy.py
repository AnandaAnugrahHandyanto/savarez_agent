import json
import runpy
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "rollout" / "validate_gateway_adaptive_policy.py"


def _run_script(home: Path, capsys):
    old_argv = sys.argv[:]
    try:
        sys.argv = [str(SCRIPT), str(home)]
        try:
            runpy.run_path(str(SCRIPT), run_name="__main__")
        except SystemExit as exc:
            code = int(exc.code or 0)
        out = capsys.readouterr().out
        return code, out
    finally:
        sys.argv = old_argv


def test_validate_gateway_adaptive_policy_handles_missing_files(tmp_path, capsys):
    code, out = _run_script(tmp_path, capsys)

    assert code == 0
    assert "policy: missing" in out
    assert "telemetry: missing" in out
    assert "signatures: missing" in out


def test_validate_gateway_adaptive_policy_reports_present_artifacts(tmp_path, capsys):
    (tmp_path / "gateway_adaptive_policy.json").write_text(
        json.dumps({"policy": {"max_backoff": 120}}), encoding="utf-8"
    )
    (tmp_path / "gateway_telemetry.jsonl").write_text("{}\n{}\n", encoding="utf-8")
    (tmp_path / "gateway_failure_signatures.json").write_text(
        json.dumps({"sig-1": {"count": 3}}), encoding="utf-8"
    )

    code, out = _run_script(tmp_path, capsys)

    assert code == 0
    assert "policy: OK" in out
    assert '"max_backoff": 120' in out
    assert "telemetry: 2 event(s)" in out
    assert "signatures: 1 signature(s)" in out


def test_validate_gateway_adaptive_policy_fails_on_invalid_policy_json(tmp_path, capsys):
    (tmp_path / "gateway_adaptive_policy.json").write_text("{broken", encoding="utf-8")

    code, out = _run_script(tmp_path, capsys)

    assert code == 1
    assert "policy: ERROR" in out
