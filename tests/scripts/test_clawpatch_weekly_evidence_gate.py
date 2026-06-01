import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "clawpatch_weekly_evidence_gate.py"


def test_clawpatch_verify_only_refuses_completion_without_fresh_report(tmp_path):
    report = tmp_path / "missing-report.md"
    result_path = tmp_path / "RESULT.md"
    manifest = tmp_path / "manifest.json"
    log_path = tmp_path / "evidence-gate.log"

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--verify-only",
            "--report",
            str(report),
            "--result",
            str(result_path),
            "--manifest",
            str(manifest),
            "--log-path",
            str(log_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode != 0
    payload = json.loads(proc.stdout)
    assert payload["status"] == "FAILED"
    assert payload["requested_status"] == "COMPLETED"
    assert "Status: FAILED" in result_path.read_text(encoding="utf-8")
    log_text = log_path.read_text(encoding="utf-8")
    assert "evidence_gate_refused" in log_text
    assert "completion_refused" in log_text
