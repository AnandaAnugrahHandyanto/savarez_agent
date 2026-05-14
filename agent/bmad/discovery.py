from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from agent.bmad.models import BmadSkill
from agent.bmad.skill_loader import load_bmad_skill


def _normalize_start(start_path: str | Path | None) -> Path:
    if start_path is None:
        return Path.cwd().resolve()
    path = Path(start_path).expanduser().resolve()
    return path if path.is_dir() else path.parent


def _is_git_root(path: Path) -> bool:
    return (path / ".git").exists()


def find_bmad_root(start_path: str | Path | None = None, *, stop_at_git_root: bool = True) -> Path | None:
    current = _normalize_start(start_path)
    for candidate in (current, *current.parents):
        bmad_root = candidate / "_bmad"
        if bmad_root.is_dir() and not bmad_root.is_symlink():
            return bmad_root
        if stop_at_git_root and _is_git_root(candidate):
            return None
    return None


def find_project_root(start_path: str | Path | None = None) -> Path | None:
    bmad_root = find_bmad_root(start_path)
    return bmad_root.parent if bmad_root else None


def _skill_manifest_rows(root: Path) -> list[dict[str, str]]:
    manifest = root / "_config" / "skill-manifest.csv"
    if not manifest.is_file() or manifest.is_symlink():
        return []
    try:
        manifest.resolve().relative_to(root.resolve())
        with manifest.open(newline="", encoding="utf-8") as f:
            return [row for row in csv.DictReader(f)]
    except Exception:
        return []


def _manifest_module_names(root: Path) -> list[str]:
    manifest = root / "_config" / "manifest.yaml"
    if not manifest.is_file() or manifest.is_symlink():
        return []
    try:
        manifest.resolve().relative_to(root.resolve())
        import yaml
        data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    except Exception:
        return []
    modules = data.get("modules") if isinstance(data, dict) else None
    if not isinstance(modules, list):
        return []
    names: list[str] = []
    for item in modules:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
        else:
            name = str(item or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _manifest_skill_paths(root: Path) -> list[tuple[Path, str, str | None]]:
    paths: list[tuple[Path, str, str | None]] = []
    for row in _skill_manifest_rows(root):
        if str(row.get("install_to_bmad", "true")).lower() not in {"true", "1", "yes", ""}:
            continue
        raw_path = str(row.get("path") or "").strip()
        module = str(row.get("module") or "").strip() or "bmad"
        if not raw_path:
            continue
        rel = Path(raw_path)
        path = root.parent / rel if rel.parts and rel.parts[0] == "_bmad" else root / rel
        paths.append((path, module, str(row.get("name") or "").strip() or None))
    return paths


def discover_bmad_skills(bmad_root: str | Path) -> list[BmadSkill]:
    root = Path(bmad_root)
    discovered: list[BmadSkill] = []
    seen: set[str] = set()

    manifest_paths = _manifest_skill_paths(root)
    if manifest_paths:
        for skill_file, module, _name in manifest_paths:
            try:
                skill_file.resolve().relative_to(root.resolve())
            except ValueError:
                continue
            skill = load_bmad_skill(skill_file.parent, module=module)
            if skill and skill.name not in seen:
                discovered.append(skill)
                seen.add(skill.name)
        return discovered

    modules = _manifest_module_names(root) or ["core", "bmm"]
    for module in modules:
        module_root = root / module
        if not module_root.is_dir() or module_root.is_symlink():
            continue
        for skill_file in sorted(module_root.rglob("SKILL.md")):
            try:
                skill_file.resolve().relative_to(root.resolve())
            except ValueError:
                continue
            skill = load_bmad_skill(skill_file.parent, module=module)
            if skill and skill.name not in seen:
                discovered.append(skill)
                seen.add(skill.name)
    return discovered


def build_bmad_fingerprint(bmad_root: str | Path) -> tuple[tuple[str, int, int, str], ...]:
    root = Path(bmad_root)
    patterns = [
        "**/SKILL.md",
        "config*.toml",
        "custom/config*.toml",
        "*/config.yaml",
        "_config/manifest.yaml",
        "_config/skill-manifest.csv",
    ]
    entries: dict[str, tuple[str, int, int, str]] = {}
    for pattern in patterns:
        for path in root.glob(pattern):
            if not path.is_file() or path.is_symlink():
                continue
            try:
                path.resolve().relative_to(root.resolve())
                stat = path.stat()
                rel = path.relative_to(root).as_posix()
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
            except (OSError, ValueError):
                continue
            entries[rel] = (rel, stat.st_mtime_ns, stat.st_size, digest)
    return tuple(entries[key] for key in sorted(entries))
