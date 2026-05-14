from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BmadAgent:
    code: str
    name: str
    title: str = ""
    icon: str = ""
    team: str = ""
    description: str = ""
    module: str = ""


@dataclass(frozen=True)
class BmadSkill:
    name: str
    description: str
    skill_dir: Path
    skill_file: Path
    module: str
    category: str
    frontmatter: dict[str, Any] = field(default_factory=dict)

    @property
    def identifier(self) -> str:
        return f"bmad:{self.name}"

    @property
    def slash_command(self) -> str:
        return f"/{self.name}"


@dataclass(frozen=True)
class BmadProject:
    project_root: Path
    bmad_root: Path
    manifest_path: Path | None
    config: dict[str, Any]
    agents: list[BmadAgent]
    skills: list[BmadSkill]
