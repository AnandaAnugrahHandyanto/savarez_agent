import json
import os
import subprocess
import sys
import time
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "clawpatch_weekly_evidence_gate.py"


def test_clawpatch_verify_only_completes_with_fresh_report(tmp_path):
    report = tmp_path / "REPORT.md"
    report.write_text("# Weekly\n\nVerified.\n", encoding="utf-8")
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

    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["status"] == "COMPLETED"
    assert payload["success"] is True
    assert "Status: COMPLETED" in result_path.read_text(encoding="utf-8")
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_payload["checks"][1]["type"] == "file_fresh"
    assert "command" not in manifest_payload["checks"][1]


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


def test_clawpatch_verify_only_refuses_stale_report(tmp_path):
    report = tmp_path / "REPORT.md"
    report.write_text("# Weekly\n\nOld.\n", encoding="utf-8")
    stale = time.time() - 7200
    os.utime(report, (stale, stale))
    result_path = tmp_path / "RESULT.md"
    manifest = tmp_path / "manifest.json"

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
            "--max-age-hours",
            "1",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode != 0
    payload = json.loads(proc.stdout)
    assert payload["status"] == "FAILED"
    assert payload["checks"][0]["passed"] is True
    assert payload["checks"][1]["type"] == "file_fresh"
    assert payload["checks"][1]["passed"] is False
