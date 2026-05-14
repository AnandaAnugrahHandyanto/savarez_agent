from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.bmad.config import resolve_bmad_config
from agent.bmad.discovery import discover_bmad_skills, find_bmad_root, find_project_root
from agent.bmad.models import BmadAgent, BmadProject, BmadSkill


def _agents_from_config(config: dict[str, Any]) -> list[BmadAgent]:
    agents = config.get("agents") or []
    result: list[BmadAgent] = []
    for item in agents:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip()
        name = str(item.get("name") or "").strip()
        if not code or not name:
            continue
        result.append(BmadAgent(code=code, name=name, title=str(item.get("title") or ""), icon=str(item.get("icon") or ""), team=str(item.get("team") or ""), description=str(item.get("description") or ""), module=str(item.get("module") or "")))
    return result


def _bmad_adapter_config() -> dict[str, Any]:
    try:
        from hermes_cli.config import load_config
        return (load_config() or {}).get("bmad") or {}
    except Exception:
        return {}


def _path_allowed(project_root: Path, allowed_roots: list[str]) -> bool:
    if not allowed_roots:
        return True
    resolved = project_root.resolve()
    for root in allowed_roots:
        try:
            resolved.relative_to(Path(root).expanduser().resolve())
            return True
        except ValueError:
            continue
    return False


def get_active_bmad_project(start_path: str | Path | None = None) -> BmadProject | None:
    adapter_config = _bmad_adapter_config()
    if adapter_config.get("enabled", True) is not True:
        return None
    if adapter_config.get("auto_detect", True) is not True and start_path is None:
        return None

    bmad_root = find_bmad_root(start_path)
    project_root = find_project_root(start_path)
    if not bmad_root or not project_root:
        return None
    if not _path_allowed(project_root, list(adapter_config.get("allowed_roots") or [])):
        return None

    config = resolve_bmad_config(bmad_root)
    manifest = bmad_root / "_config" / "manifest.yaml"
    return BmadProject(project_root=project_root, bmad_root=bmad_root, manifest_path=manifest if manifest.exists() else None, config=config, agents=_agents_from_config(config), skills=discover_bmad_skills(bmad_root))


def list_bmad_skills(start_path: str | Path | None = None) -> list[BmadSkill]:
    project = get_active_bmad_project(start_path)
    if not project:
        return []
    adapter_config = _bmad_adapter_config()
    disabled = {str(item) for item in (adapter_config.get("disabled_skills") or [])}
    max_indexed = int(adapter_config.get("max_indexed_skills") or 80)
    skills = [skill for skill in project.skills if skill.name not in disabled and skill.identifier not in disabled]
    return skills[:max_indexed]


def get_bmad_skill(identifier: str, start_path: str | Path | None = None) -> BmadSkill | None:
    normalized = identifier.removeprefix("bmad:").lstrip("/")
    for skill in list_bmad_skills(start_path):
        if skill.name == normalized or skill.identifier == identifier:
            return skill
    return None


def build_bmad_skill_message(identifier: str, user_instruction: str = "", start_path: str | Path | None = None, task_id: str | None = None) -> str | None:
    from agent.bmad.invocation import build_bmad_skill_message as _build
    return _build(identifier, user_instruction, start_path=start_path, task_id=task_id)
