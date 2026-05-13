#!/usr/bin/env python3
"""
Knowledge Local Source — SkillSource adapter for ~/github/knowledge/skills/

This adapter lets Hermes discover and install skills from the local knowledge
repo without requiring a GitHub API call. It reads SKILL.md files directly
from the filesystem.

Trust level: "trusted" (because it's local to this machine)
"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

logger = logging.getLogger(__name__)

# The local knowledge repo skills directory
KNOWLEDGE_SKILLS_DIR = Path.home() / "github" / "knowledge" / "skills"


# ----------------------------------------------------------------------
# Minimal SkillSource types (duplicated from skills_hub to avoid circular import)
# ----------------------------------------------------------------------

@dataclass
class SkillMeta:
    """Minimal metadata for a skill."""
    name: str
    description: str
    source: str
    identifier: str
    trust_level: str
    repo: Optional[str] = None
    path: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillBundle:
    """A skill directory with its file contents."""
    name: str
    files: Dict[str, Union[str, bytes]]
    source: str
    identifier: str
    trust_level: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class SkillSource(ABC):
    """Abstract base for skill registry adapters."""

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> List[SkillMeta]:
        ...

    @abstractmethod
    def fetch(self, identifier: str) -> Optional[SkillBundle]:
        ...

    @abstractmethod
    def inspect(self, identifier: str) -> Optional[SkillMeta]:
        ...

    @abstractmethod
    def source_id(self) -> str:
        ...


# ----------------------------------------------------------------------
# KnowledgeLocalSource implementation
# ----------------------------------------------------------------------

class KnowledgeLocalSource(SkillSource):
    """
    SkillSource that reads skills from the local ~/github/knowledge/skills/ directory.

    This is the primary source for all shared team skills — it's always available
    (no network required), fast (local filesystem), and trusted.
    """

    def __init__(self, skills_dir: Path = KNOWLEDGE_SKILLS_DIR):
        self.skills_dir = skills_dir

    def source_id(self) -> str:
        return "knowledge-local"

    def trust_level_for(self, identifier: str) -> str:
        return "trusted"

    def search(self, query: str, limit: int = 10) -> List[SkillMeta]:
        """Search skills by name and description in the local knowledge repo."""
        results: List[SkillMeta] = []
        query_lower = query.lower()

        if not self.skills_dir.exists():
            return results

        for skill_path in self.skills_dir.iterdir():
            if not skill_path.is_dir() or skill_path.name.startswith("."):
                continue

            skill_md = skill_path / "SKILL.md"
            if not skill_md.exists():
                continue

            try:
                content = skill_md.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            fm = self._parse_frontmatter(content)
            name = fm.get("name", skill_path.name)
            description = fm.get("description", "")

            tags = []
            meta = fm.get("metadata", {})
            if isinstance(meta, dict):
                hermes_meta = meta.get("hermes", {})
                if isinstance(hermes_meta, dict):
                    tags = hermes_meta.get("tags", [])
            if not tags:
                raw_tags = fm.get("tags", [])
                tags = raw_tags if isinstance(raw_tags, list) else []

            searchable = f"{name} {description} {' '.join(tags)}".lower()
            if query_lower in searchable:
                results.append(SkillMeta(
                    name=name,
                    description=str(description)[:200],
                    source="knowledge-local",
                    identifier=f"knowledge-local/{skill_path.name}",
                    trust_level="trusted",
                    repo=None,
                    path=str(skill_path.relative_to(self.skills_dir)),
                    tags=[str(t) for t in tags],
                ))

            if len(results) >= limit:
                break

        return results

    def fetch(self, identifier: str) -> Optional[SkillBundle]:
        """
        Read a skill from the local knowledge repo.

        identifier format: "knowledge-local/<skill-name>"
        """
        if not identifier.startswith("knowledge-local/"):
            return None

        skill_name = identifier.split("/", 1)[-1]
        skill_path = self.skills_dir / skill_name

        if not skill_path.exists() or not skill_path.is_dir():
            return None

        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            return None

        files: dict = {}
        for fpath in skill_path.rglob("*"):
            if fpath.is_file() and not fpath.name.startswith("."):
                rel_path = str(fpath.relative_to(skill_path))
                try:
                    files[rel_path] = fpath.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    pass

        if not files:
            return None

        return SkillBundle(
            name=skill_name,
            files=files,
            source="knowledge-local",
            identifier=identifier,
            trust_level="trusted",
        )

    def inspect(self, identifier: str) -> Optional[SkillMeta]:
        """Get metadata for a skill without downloading all files."""
        if not identifier.startswith("knowledge-local/"):
            return None

        skill_name = identifier.split("/", 1)[-1]
        skill_path = self.skills_dir / skill_name

        if not skill_path.exists():
            return None

        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            return None

        try:
            content = skill_md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

        fm = self._parse_frontmatter(content)
        name = fm.get("name", skill_name)
        description = fm.get("description", "")

        tags = []
        meta = fm.get("metadata", {})
        if isinstance(meta, dict):
            hermes_meta = meta.get("hermes", {})
            if isinstance(hermes_meta, dict):
                tags = hermes_meta.get("tags", [])
        if not tags:
            raw_tags = fm.get("tags", [])
            tags = raw_tags if isinstance(raw_tags, list) else []

        return SkillMeta(
            name=name,
            description=str(description)[:200],
            source="knowledge-local",
            identifier=identifier,
            trust_level="trusted",
            repo=None,
            path=skill_name,
            tags=[str(t) for t in tags],
        )

    @staticmethod
    def _parse_frontmatter(content: str) -> dict:
        """Parse YAML frontmatter from SKILL.md content."""
        if not content.startswith("---"):
            return {}
        match = re.search(r"\n---\s*\n", content[3:])
        if not match:
            return {}
        yaml_text = content[3:match.start() + 3]
        try:
            parsed = yaml.safe_load(yaml_text)
            return parsed if isinstance(parsed, dict) else {}
        except yaml.YAMLError:
            return {}
