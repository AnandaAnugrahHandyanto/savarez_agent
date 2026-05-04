from hermes_cli.verification.report import (
    VerificationArtifact,
    VerificationCheck,
    VerificationReport,
)


def test_report_serializes_json_and_markdown():
    report = VerificationReport(
        repo="/tmp/repo",
        task_type="web-ui",
        branch="main",
        sha="abc123",
    )
    report.add_check(
        VerificationCheck(
            name="unit tests",
            kind="command",
            status="passed",
            command="pytest -q",
            exit_code=0,
            duration_seconds=1.23,
        )
    )
    report.add_artifact(
        VerificationArtifact(kind="log", path="/tmp/repo/test.log", description="pytest output")
    )

    data = report.to_dict()

    assert data["status"] == "passed"
    assert data["repo"] == "/tmp/repo"
    assert data["task_type"] == "web-ui"
    assert data["checks"][0]["name"] == "unit tests"
    assert data["artifacts"][0]["path"] == "/tmp/repo/test.log"

    markdown = report.to_markdown()
    assert "# Verification Report" in markdown
    assert "Status: passed" in markdown
    assert "unit tests" in markdown


def test_report_failed_check_sets_failed_status():
    report = VerificationReport(repo="/tmp/repo")
    report.add_check(
        VerificationCheck(
            name="lint",
            kind="command",
            status="failed",
            command="npm run lint",
            exit_code=1,
        )
    )

    assert report.status == "failed"


def test_report_not_run_without_failures_is_partial():
    report = VerificationReport(repo="/tmp/repo")
    report.add_check(
        VerificationCheck(
            name="screenshot",
            kind="web_ui",
            status="not_run",
            message="No URL supplied",
        )
    )

    assert report.status == "partial"
