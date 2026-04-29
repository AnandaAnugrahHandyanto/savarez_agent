"""
Skill Discovery Module - Auto-discovery and Loading of Skills

Scans ~/.hermes/skills/ directory and loads skills dynamically based on
task context. Skills are loaded without requiring a new session.

Skills are structured directories containing:
    - skill.yaml or skill.json: Skill metadata
    - prompts/: Prompt templates
    - scripts/: Optional helper scripts
"""

import importlib
import importlib.util
import json
import logging
import os
import re
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class Skill:
    """Represents a discovered skill."""

    def __init__(
        self,
        name: str,
        path: Path,
        description: str = "",
        domain: str = "",
        keywords: Optional[List[str]] = None,
        tools: Optional[List[str]] = None,
        prompts: Optional[Dict[str, str]] = None,
        enabled: bool = True,
        metadata: Optional[Dict] = None,
    ):
        self.name = name
        self.path = path
        self.description = description
        self.domain = domain
        self.keywords = keywords or []
        self.tools = tools or []
        self.prompts = prompts or {}
        self.enabled = enabled
        self.metadata = metadata or {}

    def matches_context(self, context: str) -> bool:
        """
        Check if this skill matches the given context.

        Args:
            context: Task context (e.g., user message, conversation topic)

        Returns:
            True if skill is relevant to the context
        """
        context_lower = context.lower()

        # Check keywords
        for keyword in self.keywords:
            if keyword.lower() in context_lower:
                return True

        # Check description
        if self.description and self.description.lower() in context_lower:
            return True

        # Check domain
        if self.domain and self.domain.lower() in context_lower:
            return True

        return False

    def to_dict(self) -> Dict:
        """Convert skill to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
            "keywords": self.keywords,
            "tools": self.tools,
            "prompts": list(self.prompts.keys()),
            "enabled": self.enabled,
            "path": str(self.path),
        }


class SkillDiscovery:
    """
    Discovers and manages skills from ~/.hermes/skills/.

    Scans the skills directory, loads skill metadata, and provides
    context-based skill recommendations.
    """

    def __init__(self, skills_dir: Optional[Path] = None):
        self._lock = threading.RLock()
        self._skills_dir = skills_dir or self._get_default_skills_dir()
        self._skills: Dict[str, Skill] = {}
        self._loaded = False
        self._active_skills: Set[str] = set()
        self._skill_hooks: Dict[str, Any] = {}

    def _get_default_skills_dir(self) -> Path:
        """Get the default skills directory."""
        from hermes_constants import get_hermes_home
        return get_hermes_home() / "skills"

    @property
    def skills_dir(self) -> Path:
        """Return the skills directory path."""
        return self._skills_dir

    def _load_skill_metadata(self, skill_path: Path) -> Optional[Dict]:
        """
        Load skill metadata from skill.yaml or skill.json.

        Args:
            skill_path: Path to the skill directory

        Returns:
            Metadata dict or None if not found
        """
        for filename in ["skill.yaml", "skill.yml", "skill.json"]:
            metadata_file = skill_path / filename
            if metadata_file.exists():
                try:
                    if filename.endswith(".json"):
                        with open(metadata_file, "r", encoding="utf-8") as f:
                            return json.load(f)
                    else:
                        # Simple YAML parse (avoiding pyyaml dependency)
                        with open(metadata_file, "r", encoding="utf-8") as f:
                            content = f.read()
                        return self._parse_simple_yaml(content)
                except Exception as e:
                    logger.warning("Failed to load %s: %s", metadata_file, e)
        return None

    def _parse_simple_yaml(self, content: str) -> Dict:
        """Parse a simple YAML-like structure without pyyaml."""
        result = {}
        current_key = None
        current_list = []
        in_list = False

        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if ": " in line and not line.startswith("-"):
                # Key-value pair
                if in_list and current_key:
                    result[current_key] = current_list
                    current_list = []
                    in_list = False

                key, value = line.split(": ", 1)
                current_key = key.strip()
                result[current_key] = value.strip().strip('"').strip("'")
            elif line.startswith("- "):
                # List item
                in_list = True
                current_list.append(line[1:].strip().strip('"').strip("'"))

        if in_list and current_key:
            result[current_key] = current_list

        return result

    def _load_prompts(self, skill_path: Path) -> Dict[str, str]:
        """
        Load prompt templates from the prompts/ subdirectory.

        Args:
            skill_path: Path to the skill directory

        Returns:
            Dict mapping prompt name to prompt content
        """
        prompts = {}
        prompts_dir = skill_path / "prompts"

        if prompts_dir.exists() and prompts_dir.is_dir():
            for prompt_file in prompts_dir.glob("*.txt"):
                try:
                    prompts[prompt_file.stem] = prompt_file.read_text(encoding="utf-8")
                except Exception as e:
                    logger.warning("Failed to load prompt %s: %s", prompt_file, e)

        return prompts

    def _discover_skill(self, skill_path: Path) -> Optional[Skill]:
        """
        Discover a single skill from its directory.

        Args:
            skill_path: Path to the skill directory

        Returns:
            Skill object or None if not valid
        """
        if not skill_path.is_dir():
            return None

        name = skill_path.name
        metadata = self._load_skill_metadata(skill_path)

        if metadata is None:
            logger.debug("No metadata found for skill: %s", name)
            return None

        return Skill(
            name=name,
            path=skill_path,
            description=metadata.get("description", ""),
            domain=metadata.get("domain", ""),
            keywords=metadata.get("keywords", []),
            tools=metadata.get("tools", []),
            prompts=self._load_prompts(skill_path),
            enabled=metadata.get("enabled", True),
            metadata=metadata,
        )

    def discover(self, force: bool = False) -> List[Skill]:
        """
        Discover all skills in the skills directory.

        Args:
            force: Force re-discovery even if already loaded

        Returns:
            List of discovered skills
        """
        with self._lock:
            if self._loaded and not force:
                return list(self._skills.values())

            self._skills.clear()

            if not self._skills_dir.exists():
                logger.warning("Skills directory does not exist: %s", self._skills_dir)
                return []

            for entry in self._skills_dir.iterdir():
                if entry.is_dir() and not entry.name.startswith("."):
                    skill = self._discover_skill(entry)
                    if skill is not None:
                        self._skills[skill.name] = skill
                        logger.debug("Discovered skill: %s", skill.name)

            self._loaded = True
            logger.info("Discovered %d skills in %s", len(self._skills), self._skills_dir)
            return list(self._skills.values())

    def get_skill(self, name: str) -> Optional[Skill]:
        """
        Get a skill by name.

        Args:
            name: Skill name

        Returns:
            Skill object or None
        """
        with self._lock:
            if not self._loaded:
                self.discover()
            return self._skills.get(name)

    def get_all_skills(self) -> List[Skill]:
        """Get all discovered skills."""
        with self._lock:
            if not self._loaded:
                self.discover()
            return list(self._skills.values())

    def get_enabled_skills(self) -> List[Skill]:
        """Get all enabled skills."""
        return [s for s in self.get_all_skills() if s.enabled]

    def recommend_skills(self, context: str, max_results: int = 5) -> List[Skill]:
        """
        Recommend skills based on task context.

        Args:
            context: Task context (e.g., user message)
            max_results: Maximum number of recommendations

        Returns:
            List of recommended skills, sorted by relevance
        """
        skills = self.get_enabled_skills()

        # Score each skill
        scored = []
        for skill in skills:
            score = 0

            # Exact keyword match = highest score
            context_lower = context.lower()
            for keyword in skill.keywords:
                if keyword.lower() == context_lower:
                    score += 100
                elif keyword.lower() in context_lower:
                    score += 10

            # Domain match
            if skill.domain and skill.domain.lower() in context_lower:
                score += 5

            # Description match
            if skill.description:
                desc_words = skill.description.lower().split()
                for word in desc_words:
                    if len(word) > 3 and word in context_lower:
                        score += 1

            if score > 0:
                scored.append((score, skill))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        return [s for _, s in scored[:max_results]]

    def enable_skill(self, name: str) -> bool:
        """
        Enable a skill.

        Args:
            name: Skill name

        Returns:
            True if skill was found and enabled
        """
        with self._lock:
            skill = self._skills.get(name)
            if skill is None:
                return False
            skill.enabled = True
            self._active_skills.add(name)
            return True

    def disable_skill(self, name: str) -> bool:
        """
        Disable a skill.

        Args:
            name: Skill name

        Returns:
            True if skill was found and disabled
        """
        with self._lock:
            skill = self._skills.get(name)
            if skill is None:
                return False
            skill.enabled = False
            self._active_skills.discard(name)
            return True

    def get_active_skills(self) -> List[Skill]:
        """Get all currently active (enabled) skills."""
        return [self._skills[name] for name in self._active_skills if name in self._skills]

    def load_skill_prompt(self, skill_name: str, prompt_name: str = "system") -> Optional[str]:
        """
        Load a specific prompt from a skill.

        Args:
            skill_name: Name of the skill
            prompt_name: Name of the prompt (default: "system")

        Returns:
            Prompt content or None
        """
        skill = self.get_skill(skill_name)
        if skill is None:
            return None
        return skill.prompts.get(prompt_name)

    def inject_skill_context(self, context: str) -> str:
        """
        Inject relevant skill context into a user message.

        This adds skill prompts to the context for the current task.

        Args:
            context: Original user message

        Returns:
            Enhanced context with skill information
        """
        recommendations = self.recommend_skills(context, max_results=3)

        if not recommendations:
            return context

        injected = [context, "", "## Relevant Skills", ""]

        for skill in recommendations:
            injected.append(f"### {skill.name}")
            if skill.description:
                injected.append(f"{skill.description}")
            if skill.prompts:
                injected.append(f"Available prompts: {', '.join(skill.prompts.keys())}")
            injected.append("")

        return "\n".join(injected)

    def register_skill_hook(self, skill_name: str, hook_type: str, callback: Any) -> None:
        """
        Register a hook callback for a skill event.

        Args:
            skill_name: Name of the skill
            hook_type: Type of hook (e.g., "on_activate", "on_message")
            callback: Callback function
        """
        key = f"{skill_name}:{hook_type}"
        self._skill_hooks[key] = callback

    def trigger_skill_hook(
        self, skill_name: str, hook_type: str, *args, **kwargs
    ) -> Optional[Any]:
        """
        Trigger a registered skill hook.

        Args:
            skill_name: Name of the skill
            hook_type: Type of hook
            *args, **kwargs: Arguments to pass to the callback

        Returns:
            Hook result or None
        """
        key = f"{skill_name}:{hook_type}"
        callback = self._skill_hooks.get(key)
        if callback is None:
            return None

        try:
            return callback(*args, **kwargs)
        except Exception as e:
            logger.exception("Skill hook %s failed: %s", key, e)
            return None


# Global singleton instance
_skill_discovery = None


def get_skill_discovery() -> SkillDiscovery:
    """Get the global SkillDiscovery singleton instance."""
    global _skill_discovery
    if _skill_discovery is None:
        _skill_discovery = SkillDiscovery()
    return _skill_discovery
