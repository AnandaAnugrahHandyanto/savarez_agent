from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    module_path = REPO_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_hermes_governed_runtime_snapshot_script_json_output(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("model:\n  provider: openai-codex\n  default: gpt-5.4\n", encoding="utf-8")
    module = _load_script("hermes_governed_runtime_snapshot")
    monkeypatch.setattr(
        module,
        "build_governed_runtime_snapshot",
        lambda **_: {
            "overall_status": "healthy",
            "summary": {
                "operator_issue_count": 0,
                "release_block_count": 0,
                "routing_policy_gap_count": 0,
                "blocked_queue_count": 0,
            },
            "recommended_actions": [],
        },
    )

    exit_code = module.main(["--config", str(config_path), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["overall_status"] == "healthy"
