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


def test_hermes_continuity_queue_snapshot_script_json_output(monkeypatch, capsys):
    module = _load_script("hermes_continuity_queue_snapshot")
    monkeypatch.setattr(
        module,
        "build_snapshot",
        lambda: {
            "totals": {"ready": 1, "running": 2, "blocked": 1, "handoffs": 1},
            "queue": {"blocked": [{"task_id": "task_b", "blocked_reason": "dependency_blocked:task_a"}]},
        },
    )

    exit_code = module.main(["--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["totals"]["running"] == 2
