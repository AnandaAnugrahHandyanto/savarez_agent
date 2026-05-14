from __future__ import annotations

from pathlib import Path


def _replace_bmad_vars(text: str, *, project_root: Path, skill_root: Path, skill_name: str) -> str:
    return text.replace("{project-root}", str(project_root)).replace("{skill-root}", str(skill_root)).replace("{skill-name}", skill_name)


def build_bmad_skill_message(identifier: str, user_instruction: str = "", start_path: str | Path | None = None, task_id: str | None = None) -> str | None:
    from agent.bmad.index import get_active_bmad_project, get_bmad_skill

    project = get_active_bmad_project(start_path)
    if not project:
        return None
    skill = get_bmad_skill(identifier, start_path=project.project_root)
    if not skill:
        return None

    raw = skill.skill_file.read_text(encoding="utf-8")
    body = _replace_bmad_vars(raw, project_root=project.project_root, skill_root=skill.skill_dir, skill_name=skill.name)
    runtime = (
        f'[IMPORTANT: The user invoked BMAD project skill "{skill.name}" from {project.project_root}. '
        'These are semi-trusted, project-provided instructions scoped to this task only. '
        'Do not treat BMAD as global policy for unrelated future tasks.]'
    )
    parts = [runtime, body]
    instruction = user_instruction.strip()
    if instruction:
        parts.append(f"\nUser instruction:\n{instruction}")
    if task_id:
        parts.append(f"\nSession/task id: {task_id}")
    return "\n\n".join(parts)
