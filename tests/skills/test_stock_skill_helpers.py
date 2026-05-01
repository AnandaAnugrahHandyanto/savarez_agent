from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DUCK_QUERY_SCRIPT = (
    REPO_ROOT
    / "skills"
    / "research"
    / "duckduckgo-search"
    / "scripts"
    / "build_a_share_queries.py"
)
BLOGWATCHER_SCRIPT = (
    REPO_ROOT
    / "optional-skills"
    / "research"
    / "blogwatcher"
    / "scripts"
    / "build_a_share_watchlist.py"
)
SCRAPLING_SUPPLEMENT_SCRIPT = (
    REPO_ROOT
    / "optional-skills"
    / "research"
    / "blogwatcher-a-share"
    / "scripts"
    / "build_scrapling_supplement.py"
)


def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_a_share_watchlist_writes_expected_payload(tmp_path: Path):
    output_path = tmp_path / "watchlist.json"

    result = subprocess.run(
        [sys.executable, str(BLOGWATCHER_SCRIPT), "--output", str(output_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(result.stdout)

    assert payload["purpose"] == "A股短线情报监控"
    assert stdout_payload["ok"] is True
    assert stdout_payload["feed_count"] >= 5
    feed_names = {feed["name"] for feed in payload["feeds"]}
    assert "上交所上市公司公告" in feed_names
    assert "财联社" in feed_names
    assert any(feed.get("notes") for feed in payload["feeds"])
    assert any("scrapling" in action for action in payload["next_actions"])


def test_build_a_share_watchlist_module_payload_shape():
    module = _load_module(BLOGWATCHER_SCRIPT, "build_a_share_watchlist")
    payload = module.build_payload()

    assert payload["purpose"] == "A股短线情报监控"
    assert len(payload["feeds"]) >= 5
    assert {feed["category"] for feed in payload["feeds"]} >= {"exchange-announcement", "market-news"}


def test_build_a_share_queries_writes_expected_payload(tmp_path: Path):
    output_path = tmp_path / "queries.json"

    result = subprocess.run(
        [sys.executable, str(DUCK_QUERY_SCRIPT), "--output", str(output_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(result.stdout)

    assert payload["purpose"] == "A股短线 DuckDuckGo 检索模板"
    assert stdout_payload["ok"] is True
    assert stdout_payload["template_count"] >= 5
    template_names = {item["name"] for item in payload["templates"]}
    assert "盘前公告催化" in template_names
    assert "公司传闻补证" in template_names
    assert any("ticker_or_name" in item["query"] for item in payload["templates"])


def test_build_a_share_queries_module_payload_shape():
    module = _load_module(DUCK_QUERY_SCRIPT, "build_a_share_queries")
    payload = module.build_payload()

    assert payload["purpose"] == "A股短线 DuckDuckGo 检索模板"
    assert len(payload["templates"]) >= 5
    assert any("公告" in item["name"] for item in payload["templates"])


def test_build_cron_closure_writes_expected_payload(tmp_path: Path):
    cron_script = (
        REPO_ROOT
        / "optional-skills"
        / "research"
        / "blogwatcher-a-share"
        / "scripts"
        / "build_cron_closure.py"
    )
    output_path = tmp_path / "cron-closure.json"

    result = subprocess.run(
        [sys.executable, str(cron_script), "--output", str(output_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(result.stdout)

    assert payload["purpose"] == "A股短线 blogwatcher + duckduckgo cron 闭环模板"
    assert stdout_payload["ok"] is True
    assert stdout_payload["job_count"] == 4
    assert set(payload["jobs"].keys()) == {"pre_market", "midday", "intraday", "post_market"}
    assert any("duckduckgo-search" in note or "DuckDuckGo" in note for note in payload["notes"])


def test_build_cron_closure_module_payload_shape():
    cron_script = (
        REPO_ROOT
        / "optional-skills"
        / "research"
        / "blogwatcher-a-share"
        / "scripts"
        / "build_cron_closure.py"
    )
    module = _load_module(cron_script, "build_cron_closure")
    payload = module.build_payload()

    assert payload["purpose"] == "A股短线 blogwatcher + duckduckgo cron 闭环模板"
    assert len(payload["jobs"]) == 4
    assert payload["jobs"]["pre_market"]["schedule"] == "0 30 8 * * 1-5"
    assert "blogwatcher-a-share" in payload["skills"]


def test_build_a_share_bootstrap_writes_expected_payload(tmp_path: Path):
    bootstrap_script = (
        REPO_ROOT
        / "optional-skills"
        / "research"
        / "qmd-a-share"
        / "scripts"
        / "build_a_share_bootstrap.py"
    )
    output_path = tmp_path / "qmd-bootstrap.json"

    result = subprocess.run(
        [sys.executable, str(bootstrap_script), "--output", str(output_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(result.stdout)

    assert payload["purpose"] == "A股短线 QMD 知识库 bootstrap"
    assert stdout_payload["ok"] is True
    assert stdout_payload["collection_count"] == 6
    assert len(payload["collections"]) == 6
    assert payload["collections"][0]["name"] == "a-review-daily"
    assert any("qmd embed" == step for step in payload["next_steps"])
    assert any("竞价" in item for item in payload["acceptance"])


def test_build_a_share_bootstrap_module_payload_shape():
    bootstrap_script = (
        REPO_ROOT
        / "optional-skills"
        / "research"
        / "qmd-a-share"
        / "scripts"
        / "build_a_share_bootstrap.py"
    )
    module = _load_module(bootstrap_script, "build_a_share_bootstrap")
    payload = module.build_payload()

    assert payload["purpose"] == "A股短线 QMD 知识库 bootstrap"
    assert len(payload["collections"]) == 6
    assert all(item["path"].startswith("research/a_share_kb/") for item in payload["collections"])
    assert any(step.startswith("mkdir -p research/a_share_kb/") for step in payload["next_steps"])


def test_build_scrapling_supplement_writes_expected_payload(tmp_path: Path):
    output_path = tmp_path / "scrapling-supplement.json"

    result = subprocess.run(
        [sys.executable, str(SCRAPLING_SUPPLEMENT_SCRIPT), "--output", str(output_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(result.stdout)

    assert payload["purpose"] == "A股非RSS信源 Scrapling 补链模板"
    assert stdout_payload["ok"] is True
    assert stdout_payload["job_count"] == 3
    assert {job["name"] for job in payload["jobs"]} == {"szse-announcements", "cninfo-announcements", "csrc-news"}
    assert all("scrapling extract" in job["scrapling_extract_get"] for job in payload["jobs"])


def test_build_scrapling_supplement_module_payload_shape():
    module = _load_module(SCRAPLING_SUPPLEMENT_SCRIPT, "build_scrapling_supplement")
    payload = module.build_payload()

    assert payload["purpose"] == "A股非RSS信源 Scrapling 补链模板"
    assert len(payload["jobs"]) == 3
    assert all(job["recommended_flow"][:2] == ["duckduckgo-search", "scrapling"] for job in payload["jobs"])
    assert any("非RSS页面" in item for item in payload["acceptance"])


def test_duckduckgo_helper_requires_query():
    helper_script = (
        REPO_ROOT
        / "skills"
        / "research"
        / "duckduckgo-search"
        / "scripts"
        / "duckduckgo.sh"
    )

    result = subprocess.run(
        ["bash", str(helper_script)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Usage:" in result.stdout
    assert "Requires: pip install ddgs" in result.stdout
