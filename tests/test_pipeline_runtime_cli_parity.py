from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_help(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(path), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_romance_live_episode_cli_help_matches_legacy() -> None:
    legacy = _run_help(
        REPO_ROOT / "docs/plans/orbi-romance-webtoon-20260421/webtoon/render_webtoon_fal_live_episode.py"
    )
    canonical = _run_help(REPO_ROOT / "pipeline/runtime/renderers/romance_live_episode.py")
    assert legacy.returncode == 0
    assert canonical.returncode == 0
    assert canonical.stdout == legacy.stdout


def test_balloon_zone_analyzer_cli_help_matches_legacy() -> None:
    legacy = _run_help(
        REPO_ROOT / "docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/analyze_balloon_zones.py"
    )
    canonical = _run_help(REPO_ROOT / "pipeline/runtime/analyzers/balloon_zone_analyzer.py")
    assert legacy.returncode == 0
    assert canonical.returncode == 0
    assert canonical.stdout == legacy.stdout


def test_balloon_overlay_renderer_cli_help_matches_legacy() -> None:
    legacy = _run_help(
        REPO_ROOT / "docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/render_balloons.py"
    )
    canonical = _run_help(REPO_ROOT / "pipeline/runtime/renderers/balloon_overlay_renderer.py")
    assert legacy.returncode == 0
    assert canonical.returncode == 0
    assert canonical.stdout == legacy.stdout


def test_storyboard_cli_outputs_same_episode_manifest_as_legacy() -> None:
    legacy = subprocess.run(
        [sys.executable, str(REPO_ROOT / "docs/plans/orbi-romance-webtoon-20260421/scripts/render_storyboard.py")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    canonical = subprocess.run(
        [sys.executable, str(REPO_ROOT / "pipeline/runtime/cli/render_storyboard.py")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert canonical.stdout == legacy.stdout
