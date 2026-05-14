from __future__ import annotations

from pathlib import Path

from agent.bmad.models import BmadSkill
from agent.skill_utils import parse_frontmatter


def _description_from_frontmatter(frontmatter: dict) -> str:
    description = frontmatter.get("description")
    if isinstance(description, str):
        return description.strip()
    return ""


def load_bmad_skill(skill_dir: str | Path, module: str, category: str | None = None) -> BmadSkill | None:
    root = Path(skill_dir)
    skill_file = root / "SKILL.md"
    if not skill_file.is_file() or skill_file.is_symlink():
        return None
    try:
        skill_file.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    raw = skill_file.read_text(encoding="utf-8")
    frontmatter, _body = parse_frontmatter(raw)
    if not frontmatter:
        return None
    name = str(frontmatter.get("name") or "").strip()
    description = _description_from_frontmatter(frontmatter)
    if not name or not description:
        return None
    return BmadSkill(
        name=name,
        description=description,
        skill_dir=root,
        skill_file=skill_file,
        module=module,
        category=category or module,
        frontmatter=frontmatter,
    )


_ALLOWED_RESOURCE_DIRS = {"references", "templates", "scripts", "assets"}


def _has_symlink_component(path: Path, stop_at: Path) -> bool:
    current = path
    parts: list[Path] = []
    while current != stop_at and current != current.parent:
        parts.append(current)
        current = current.parent
    return any(part.is_symlink() for part in parts)


def resolve_bmad_resource(skill: BmadSkill, relative_path: str) -> Path | None:
    rel = Path(relative_path)
    if rel.is_absolute() or ".." in rel.parts:
        return None
    if not rel.parts or rel.parts[0] not in _ALLOWED_RESOURCE_DIRS:
        return None

    skill_root = skill.skill_dir.resolve()
    requested_unresolved = skill.skill_dir / rel
    if _has_symlink_component(requested_unresolved, skill.skill_dir):
        return None
    requested = requested_unresolved.resolve()
    try:
        requested.relative_to(skill_root)
    except ValueError:
        return None
    return requested if requested.is_file() else None
