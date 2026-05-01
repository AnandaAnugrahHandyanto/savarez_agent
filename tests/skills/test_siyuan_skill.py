from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "optional-skills"
    / "productivity"
    / "siyuan"
    / "scripts"
    / "check_siyuan.py"
)
WORKSPACE_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "optional-skills"
    / "productivity"
    / "siyuan"
    / "scripts"
    / "build_a_share_workspace.py"
)


def test_check_siyuan_requires_token():
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
        env={**os.environ, "SIYUAN_TOKEN": "", "SIYUAN_URL": "http://127.0.0.1:6806"},
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["ok"] is False
    assert payload["error"] == "missing_siyuan_token"


def test_check_siyuan_success_path(monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("check_siyuan", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    monkeypatch.setenv("SIYUAN_TOKEN", "token-123")
    monkeypatch.setenv("SIYUAN_URL", "http://example.local:6806")
    monkeypatch.setattr(
        module,
        "_check",
        lambda url, token: {"code": 0, "msg": "", "data": {"notebooks": [{"id": "nb1"}, {"id": "nb2"}]}},
    )

    rc = module.main()
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["ok"] is True
    assert payload["url"] == "http://example.local:6806"
    assert payload["notebook_count"] == 2


def test_build_a_share_workspace_writes_expected_payload(tmp_path: Path):
    output_path = tmp_path / "siyuan-a-share.json"

    result = subprocess.run(
        [sys.executable, str(WORKSPACE_SCRIPT_PATH), "--output", str(output_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(result.stdout)

    assert payload["purpose"] == "A股短线 SiYuan 知识库模板"
    assert stdout_payload["ok"] is True
    assert stdout_payload["notebook_count"] == 3
    assert len(payload["notebooks"]) == 3
    assert "盘后复盘.md" in payload["templates"]
    assert any("竞价" in item for item in payload["acceptance"])


def test_build_a_share_workspace_module_payload_shape():
    spec = importlib.util.spec_from_file_location("build_a_share_workspace", WORKSPACE_SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    payload = module.build_payload()

    assert payload["purpose"] == "A股短线 SiYuan 知识库模板"
    assert len(payload["notebooks"]) == 3
    assert {item["name"] for item in payload["notebooks"]} == {"A股-日复盘", "A股-题材库", "A股-风险与风控"}
    assert payload["templates"]["盘前计划.md"].startswith("# 盘前计划")
