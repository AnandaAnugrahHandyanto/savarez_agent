from pathlib import Path
import subprocess
import tomllib
import zipfile

from hermes_constants import get_bundled_skills_dir, get_optional_skills_dir


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_faster_whisper_is_not_a_base_dependency():
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    deps = data["project"]["dependencies"]

    assert not any(dep.startswith("faster-whisper") for dep in deps)

    voice_extra = data["project"]["optional-dependencies"]["voice"]
    assert any(dep.startswith("faster-whisper") for dep in voice_extra)


def test_manifest_includes_bundled_skills():
    manifest = (REPO_ROOT / "MANIFEST.in").read_text(encoding="utf-8")

    assert "graft skills" in manifest
    assert "graft optional-skills" in manifest


def test_wheel_includes_bundled_skills(tmp_path):
    dist_dir = tmp_path / "dist"
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(dist_dir)],
        cwd=REPO_ROOT,
        check=True,
    )

    wheels = sorted(dist_dir.glob("*.whl"))
    assert wheels, "expected a built wheel artifact"

    with zipfile.ZipFile(wheels[-1]) as wheel:
        names = set(wheel.namelist())

    assert any(name.startswith("hermes_agent-0.13.0.data/data/skills/") for name in names)
    assert any(
        name.startswith("hermes_agent-0.13.0.data/data/skills/devops/kanban-worker/")
        for name in names
    )
    assert any(name.startswith("hermes_agent-0.13.0.data/data/optional-skills/") for name in names)


def test_packaged_data_dirs_are_discoverable(tmp_path, monkeypatch):
    packaged_root = tmp_path / "venv"
    (packaged_root / "skills" / "devops" / "kanban-worker").mkdir(parents=True)
    (packaged_root / "optional-skills" / "creative").mkdir(parents=True)

    monkeypatch.delenv("HERMES_BUNDLED_SKILLS", raising=False)
    monkeypatch.delenv("HERMES_OPTIONAL_SKILLS", raising=False)
    monkeypatch.setattr(
        "hermes_constants.sysconfig.get_path",
        lambda scheme: str(packaged_root) if scheme == "data" else "",
    )

    bundled = get_bundled_skills_dir(Path("/fallback/skills"))
    optional_dir = get_optional_skills_dir(Path("/fallback/optional-skills"))

    assert bundled == packaged_root / "skills"
    assert optional_dir == packaged_root / "optional-skills"
