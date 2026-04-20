from __future__ import annotations

import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "autorunne_sync.py"


def load_module():
    spec = importlib.util.spec_from_file_location("autorunne_sync", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def init_git_repo(repo_root: Path) -> None:
    git_dir = repo_root / ".git"
    (git_dir / "info").mkdir(parents=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git_dir / "info" / "exclude").write_text("", encoding="utf-8")


def test_bootstrap_creates_core_files_and_snapshot(tmp_path: Path):
    init_git_repo(tmp_path)
    module = load_module()

    result = module.bootstrap_workflow(tmp_path)

    workflow_root = tmp_path / ".autorunne"
    assert workflow_root.exists()
    assert (workflow_root / "README.md").exists()
    assert (workflow_root / "PROJECT_CONTEXT.md").exists()
    assert (workflow_root / "TASKS.md").exists()
    assert (workflow_root / "DECISIONS.md").exists()
    assert (workflow_root / "SESSION_LOG.md").exists()
    assert (workflow_root / "NEXT_ACTION.md").exists()
    assert (workflow_root / "RULES.md").exists()
    assert (workflow_root / "agents" / "common.md").exists()
    assert (workflow_root / "agents" / "hermes.md").exists()
    assert (workflow_root / "agents" / "claude-code.md").exists()
    assert (workflow_root / "agents" / "codex.md").exists()

    snapshot_path = workflow_root / "snapshots" / "latest.json"
    assert snapshot_path.exists()
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["project_name"] == tmp_path.name
    assert snapshot["git_branch"] == "main"
    assert snapshot["workflow_root"] == ".autorunne"
    assert snapshot["paths"]["agents"] == ".autorunne/agents"
    assert ".autorunne/snapshots/latest.json" in snapshot["workflow_files"]
    assert result["snapshot_path"] == snapshot_path


def test_bootstrap_adds_git_exclude_rule_only_once(tmp_path: Path):
    init_git_repo(tmp_path)
    module = load_module()

    module.bootstrap_workflow(tmp_path)
    module.bootstrap_workflow(tmp_path)

    exclude_text = (tmp_path / ".git" / "info" / "exclude").read_text(encoding="utf-8")
    assert exclude_text.count(".autorunne/") == 1


def test_cli_requires_init_flag(tmp_path: Path):
    init_git_repo(tmp_path)
    module = load_module()
    original_parse_args = module.parse_args

    class Args:
        root = str(tmp_path)
        init = False

    module.parse_args = lambda: Args()
    try:
        exit_code = module.main()
    finally:
        module.parse_args = original_parse_args

    assert exit_code == 2
    assert not (tmp_path / ".autorunne").exists()


def test_collect_snapshot_reports_key_repo_state(tmp_path: Path):
    init_git_repo(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# test\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_sample.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    module = load_module()
    module.ensure_workflow_structure(tmp_path)

    snapshot = module.collect_snapshot(tmp_path)

    assert snapshot["project_name"] == tmp_path.name
    assert snapshot["git_branch"] == "main"
    assert snapshot["has_git_repo"] is True
    assert snapshot["paths"]["project_context"] == ".autorunne/PROJECT_CONTEXT.md"
    assert ".autorunne" in snapshot["workflow_files"]
    assert any(cmd.endswith("python -m pytest tests/ -q") for cmd in snapshot["recommended_commands"])
