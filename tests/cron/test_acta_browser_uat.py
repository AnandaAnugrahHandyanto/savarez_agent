import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from cron.acta_dashboard import collect_situation_items, render_dashboard


ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "scripts" / "acta_browser_uat.py"

_spec = importlib.util.spec_from_file_location("acta_browser_uat", HARNESS)
assert _spec is not None and _spec.loader is not None
acta_browser_uat = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = acta_browser_uat
_spec.loader.exec_module(acta_browser_uat)


def _browser_cli_available() -> bool:
    return bool(os.environ.get("ACTA_UAT_AGENT_BROWSER") or shutil.which("agent-browser") or shutil.which("npx"))


def _valid_feed_dom() -> str:
    return """
    <html><body>
      <h1>Output Streams</h1>
      <h2>Daily life feed</h2>
      <section class="brief-row" data-feed-lane="daily"><span class="lane-chip">Daily</span>Morning newsletter</section>
      <h2>Development sprint cycles</h2>
      <section class="brief-row" data-feed-lane="dev"><span class="lane-chip">Dev</span>Operator sprint review</section>
    </body></html>
    """


def test_acta_browser_uat_harness_validates_feed_lane_contract(tmp_path: Path):
    if not _browser_cli_available():
        pytest.skip("agent-browser/npx unavailable; pure validation tests still cover feed contract")

    jobs = [
        {"id": "daily", "name": "Morning newsletter digest", "schedule": "daily", "deliver": "telegram"},
        {"id": "weather", "name": "Daily weather and outfit", "schedule": "daily", "deliver": "telegram"},
        {"id": "dev", "name": "Vesta Startup Sprint CEO loop", "schedule": "every 120m", "deliver": "telegram"},
    ]
    for job in jobs:
        (tmp_path / "cron" / "output" / job["id"]).mkdir(parents=True)
    (tmp_path / "cron" / "jobs.json").write_text(json.dumps(jobs))
    (tmp_path / "cron" / "output" / "daily" / "2026-05-19_09-00-00.md").write_text("## Response\n\nDaily signal")
    (tmp_path / "cron" / "output" / "weather" / "2026-05-19_08-55-00.md").write_text("## Response\n\nWeather signal")
    (tmp_path / "cron" / "output" / "dev" / "2026-05-19_09-10-00.md").write_text("## Response\n\nSprint signal")
    html_path = tmp_path / "acta.html"
    html_path.write_text(render_dashboard(collect_situation_items(tmp_path)), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(HARNESS), "--html", str(html_path), "--artifact-dir", str(tmp_path / "uat")],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=45,
    )

    assert result.returncode == 0, result.stdout
    assert "PASS Acta browser UAT" in result.stdout
    assert (tmp_path / "uat" / "acta-uat.png").exists()


def test_validate_feed_contract_fails_exactly_when_dev_rows_are_commingled():
    dom = """
    <!doctype html><html><body>
      <div class="panel-title"><b>Output Streams</b></div>
      <div class="feed-section lane-section-daily">
        <div class="feed-section-title"><b>Daily life feed</b></div>
        <section class="feed" data-feed-lane="daily">
          <section class="brief-row" data-feed-lane="daily">
            <span class="lane-chip">Daily</span><h2>Morning newsletter digest</h2>
          </section>
          <section class="brief-row" data-feed-lane="daily">
            <span class="lane-chip">Daily</span><h2>QA pipeline canary</h2>
          </section>
        </section>
      </div>
      <div class="feed-section lane-section-dev">
        <div class="feed-section-title"><b>Development sprint cycles</b></div>
        <section class="feed" data-feed-lane="dev">
          <section class="brief-row" data-feed-lane="dev">
            <span class="lane-chip">Dev</span><h2>Operator sprint review</h2>
          </section>
        </section>
      </div>
    </body></html>
    """

    assert acta_browser_uat._validate_feed_contract(dom) == [
        "Development sprint output is commingled into Daily life feed"
    ]


def test_validate_feed_contract_detects_qa_pipeline_canary_in_daily_lane():
    dom = """
    <html><body>
      <h1>Output Streams</h1>
      <h2>Daily life feed</h2>
      <section class="brief-row" data-feed-lane="daily"><span class="lane-chip">Daily</span>QA pipeline canary</section>
      <h2>Development sprint cycles</h2>
      <section class="brief-row" data-feed-lane="dev"><span class="lane-chip">Dev</span>User testing sweep</section>
    </body></html>
    """

    assert "Development sprint output is commingled into Daily life feed" in acta_browser_uat._validate_feed_contract(dom)


def test_validate_feed_contract_counts_lane_tagged_lead_as_daily_row():
    dom = """
    <html><body>
      <h1>Output Streams</h1>
      <article class="lead" data-feed-lane="daily"><span class="lane-chip">Daily</span>Morning newsletter</article>
      <h2>Daily life feed</h2>
      <p class="empty-feed">No additional outputs in this lane yet.</p>
      <h2>Development sprint cycles</h2>
      <section class="brief-row" data-feed-lane="dev"><span class="lane-chip">Dev</span>User testing sweep</section>
    </body></html>
    """

    assert acta_browser_uat._validate_feed_contract(dom) == []


def test_url_target_rejects_userinfo():
    args = type("Args", (), {"html": None, "url": "https://user:secret@example.com/acta"})()

    with pytest.raises(SystemExit, match="--url must not include userinfo"):
        acta_browser_uat._target_url(args)


def test_run_writes_sanitized_report_url_for_http_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    screenshot = tmp_path / "uat" / "acta-uat.png"

    def fake_run_chrome(url: str, artifact_dir: Path, timeout: int, viewport_width: int, viewport_height: int):
        artifact_dir.mkdir(parents=True, exist_ok=True)
        screenshot.write_bytes(b"png")
        return acta_browser_uat.BrowserResult(
            url=url,
            dom=_valid_feed_dom(),
            screenshot=screenshot,
            browser_path=Path("fake-browser"),
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            layout_metrics={"innerWidth": viewport_width, "innerHeight": viewport_height, "scrollWidth": viewport_width},
        )

    monkeypatch.setattr(acta_browser_uat, "_run_chrome", fake_run_chrome)
    args = type(
        "Args",
        (),
        {
            "html": None,
            "url": "https://example.com:8443/acta/dashboard?token=secret#frag",
            "artifact_dir": str(tmp_path / "uat"),
            "timeout": 1,
            "viewport_width": 390,
            "viewport_height": 844,
        },
    )()

    assert acta_browser_uat.run(args) == 0
    report = json.loads((tmp_path / "uat" / "acta-uat-report.json").read_text(encoding="utf-8"))
    assert report["url"] == "https://example.com:8443/acta/dashboard"
    assert report["persona"] == "mobile Acta operator checking dashboard feed lanes"
    assert "mobile" in report["scenario"].lower()
    assert report["viewport"] == {"width": 390, "height": 844}
    assert report["layout_metrics"]["innerWidth"] == 390


def test_run_chrome_sets_mobile_viewport_clears_and_collects_console_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    commands: list[list[str]] = []

    def fake_agent_browser_command() -> list[str]:
        return ["agent-browser"]

    def fake_run_agent_browser(command: list[str], args: list[str], timeout: int):
        commands.append(args)
        stdout = ""
        if args == ["eval", "document.documentElement.outerHTML"]:
            stdout = json.dumps(_valid_feed_dom())
        elif args and args[0] == "eval":
            stdout = json.dumps({"innerWidth": 390, "innerHeight": 844, "scrollWidth": 390, "bodyScrollWidth": 390, "mobilebarVisible": True})
        elif args and args[0] == "screenshot":
            Path(args[1]).write_bytes(b"png")
        return subprocess.CompletedProcess([*command, *args], 0, stdout)

    monkeypatch.setattr(acta_browser_uat, "_agent_browser_command", fake_agent_browser_command)
    monkeypatch.setattr(acta_browser_uat, "_run_agent_browser", fake_run_agent_browser)

    result = acta_browser_uat._run_chrome("file:///tmp/acta.html", tmp_path, 1, 390, 844)

    assert commands[:4] == [
        ["set", "viewport", "390", "844"],
        ["console", "--clear"],
        ["errors", "--clear"],
        ["open", "file:///tmp/acta.html"],
    ]
    assert ["console"] in commands
    assert ["errors"] in commands
    assert commands[-1] == ["close", "--all"]
    assert result.viewport_width == 390
    assert result.viewport_height == 844
    assert result.layout_metrics["innerWidth"] == 390
    assert result.horizontal_overflow is False


def test_validate_feed_contract_fails_on_mobile_overflow_console_and_page_errors():
    failures = acta_browser_uat._validate_feed_contract(
        _valid_feed_dom(),
        horizontal_overflow=True,
        console_output="Uncaught Error: boom",
        errors_output="TypeError: failed during render",
    )

    assert "Horizontal overflow detected at mobile viewport" in failures
    assert "Browser console contains error/exception output" in failures
    assert "Browser page errors were reported" in failures


def test_validate_feed_contract_ignores_empty_console_and_no_page_errors():
    failures = acta_browser_uat._validate_feed_contract(
        _valid_feed_dom(),
        console_output="No console messages",
        errors_output="No page errors",
    )

    assert failures == []


def test_sanitize_diagnostic_output_redacts_tokens_and_truncates():
    output = "GET https://acta.imperatr.com/r/detail.html?token=abc123secret&api_key=apikeysecret&sig=deadbeef Bearer sk-test-secret-token-1234567890 X-Api-Key: xapikey-secret-123456 public-diagnostic " + "x" * 4100

    sanitized = acta_browser_uat._sanitize_diagnostic_output(output, limit=160)

    assert "abc123secret" not in sanitized
    assert "apikeysecret" not in sanitized
    assert "deadbeef" not in sanitized
    assert "sk-test-secret-token" not in sanitized
    assert "xapikey-secret" not in sanitized
    assert "token=[REDACTED]" in sanitized
    assert "api_key=[REDACTED]" in sanitized
    assert "sig=[REDACTED]" in sanitized
    assert "Bearer [REDACTED]" in sanitized
    assert "X-Api-Key: [REDACTED]" in sanitized
    assert "truncated" in sanitized


def test_run_agent_browser_timeout_redacts_command_and_output(monkeypatch: pytest.MonkeyPatch):
    def fake_subprocess_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=["agent-browser", "open", "https://acta.imperatr.com/r/detail.html?token=abc123secret&sig=deadbeef"],
            timeout=1,
            output="X-Api-Key: xapikey-secret-123456",
        )

    monkeypatch.setattr(acta_browser_uat.subprocess, "run", fake_subprocess_run)

    with pytest.raises(RuntimeError) as excinfo:
        acta_browser_uat._run_agent_browser(
            ["agent-browser"],
            ["open", "https://acta.imperatr.com/r/detail.html?token=abc123secret&sig=deadbeef"],
            1,
        )

    message = str(excinfo.value)
    assert "abc123secret" not in message
    assert "deadbeef" not in message
    assert "xapikey-secret" not in message
    assert "token=[REDACTED]" in message
    assert "sig=[REDACTED]" in message
    assert "X-Api-Key: [REDACTED]" in message
