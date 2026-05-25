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


def test_url_target_rejects_userinfo():
    args = type("Args", (), {"html": None, "url": "https://user:secret@example.com/acta"})()

    with pytest.raises(SystemExit, match="--url must not include userinfo"):
        acta_browser_uat._target_url(args)


def test_run_writes_sanitized_report_url_for_http_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    screenshot = tmp_path / "uat" / "acta-uat.png"

    def fake_run_chrome(url: str, artifact_dir: Path, timeout: int):
        artifact_dir.mkdir(parents=True, exist_ok=True)
        screenshot.write_bytes(b"png")
        return acta_browser_uat.BrowserResult(
            url=url,
            dom="""
            <html><body>
              <h1>Output Streams</h1>
              <h2>Daily life feed</h2>
              <section class="brief-row" data-feed-lane="daily"><span class="lane-chip">Daily</span>Morning newsletter</section>
              <h2>Development sprint cycles</h2>
              <section class="brief-row" data-feed-lane="dev"><span class="lane-chip">Dev</span>Operator sprint review</section>
            </body></html>
            """,
            screenshot=screenshot,
            browser_path=Path("fake-browser"),
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
        },
    )()

    assert acta_browser_uat.run(args) == 0
    report = json.loads((tmp_path / "uat" / "acta-uat-report.json").read_text(encoding="utf-8"))
    assert report["url"] == "https://example.com:8443/acta/dashboard"
