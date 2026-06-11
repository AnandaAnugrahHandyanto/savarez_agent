from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from plugins.questframe_fh6vr import core


def test_run_launcher_parses_json(monkeypatch, tmp_path):
    launcher = tmp_path / "FH6VR.Launcher.exe"
    launcher.write_text("", encoding="utf-8")

    def fake_run(argv, **kwargs):
        assert argv == [str(launcher), "preflight", "--json"]
        assert kwargs["timeout"] == 60
        return SimpleNamespace(
            returncode=0,
            stdout='{"Overall":"Pass","Product":"FH6VR Launcher"}',
            stderr="",
        )

    monkeypatch.setattr(core, "resolve_launcher_path", lambda explicit=None: launcher)
    monkeypatch.setattr(core.subprocess, "run", fake_run)

    result = core.run_launcher("preflight", extra_args=["--json"])

    assert result["ok"] is True
    assert result["json"]["Overall"] == "Pass"


def test_unity_scan_detects_vrchat_packages(tmp_path):
    project = tmp_path / "AvatarProject"
    (project / "Assets").mkdir(parents=True)
    (project / "Packages").mkdir()
    (project / "ProjectSettings").mkdir()
    (project / "ProjectSettings" / "ProjectVersion.txt").write_text(
        "m_EditorVersion: 2022.3.22f1\n", encoding="utf-8"
    )
    (project / "Packages" / "manifest.json").write_text(
        json.dumps(
            {
                "dependencies": {
                    "com.vrchat.avatars": "3.10.3",
                    "nadena.dev.modular-avatar": "1.13.0",
                    "jp.lilxyzw.liltoon": "1.8.7",
                }
            }
        ),
        encoding="utf-8",
    )

    result = core.scan_unity_projects(project_path=str(project))

    assert result["ok"] is True
    assert result["project_count"] == 1
    first = result["projects"][0]
    detected = {pkg["id"] for pkg in first["detected_packages"]}
    assert "com.vrchat.avatars" in detected
    assert "nadena.dev.modular-avatar" in detected
    assert first["unity_version"] == "2022.3.22f1"
    assert "VRChat SDK package not detected" not in first["risks"]
