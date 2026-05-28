import json
from pathlib import Path

from hermes_cli.project_autopilot import bootstrap_project_home, verify_project_home


def test_bootstrap_project_home_writes_required_files(tmp_path):
    project_home = tmp_path / "active" / "demo"

    doc = bootstrap_project_home(
        slug="demo",
        title="Demo",
        goal="Make demo restartable",
        board_slug="demo",
        root_task_id="t_root",
        project_home=project_home,
        repo_org="summation",
        repo_name="Code",
        canonical_checkout=Path("/Users/vsletten/src/summation/Code/main"),
        final_branch="feat/demo-pr",
        source_plan=None,
    )

    for rel in [
        "PROJECT.md",
        "STATUS.md",
        "SESSION-HANDOFF.md",
        "SESSION-LOG.md",
        "PARKING-LOT.md",
        "TASKS.md",
        "project.json",
        "status",
        "refs",
        "scratch",
        "artifacts",
    ]:
        assert (project_home / rel).exists(), rel

    saved = json.loads((project_home / "project.json").read_text())
    assert saved["slug"] == "demo"
    assert saved["root_task_id"] == "t_root"
    assert "## Next action" in (project_home / "STATUS.md").read_text()
    verify_project_home(project_home)
