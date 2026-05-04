from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

DEFAULT_FAMILY_MAP = Path("/Users/cal/dev/orca/hermes/repo-families.yaml")


@dataclass(frozen=True)
class DiscoveredCommand:
    name: str
    command: str
    source: str


def _resolve(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _matches_repo(repo: Path, family: dict) -> bool:
    candidates: list[str] = []
    reference_repo = family.get("reference_repo")
    if reference_repo:
        candidates.append(str(reference_repo))
    candidates.extend(str(item) for item in family.get("similar_repos") or [])
    return any(_resolve(candidate) == repo for candidate in candidates)


def discover_commands(
    *,
    repo: str | Path,
    explicit_commands: Iterable[str] | None = None,
    family_map_path: str | Path | None = DEFAULT_FAMILY_MAP,
) -> list[DiscoveredCommand]:
    explicit = [command for command in (explicit_commands or []) if command]
    if explicit:
        return [
            DiscoveredCommand(name=f"command {index}", command=command, source="explicit")
            for index, command in enumerate(explicit, start=1)
        ]

    if family_map_path is None:
        return []

    map_path = Path(family_map_path).expanduser()
    if not map_path.exists():
        return []

    data = yaml.safe_load(map_path.read_text(encoding="utf-8")) or {}
    families = data.get("families") or {}
    repo_path = _resolve(repo)
    for family_name, family in families.items():
        if not isinstance(family, dict) or not _matches_repo(repo_path, family):
            continue
        commands = ((family.get("command_surface") or {}).get("fast_verify") or [])
        return [
            DiscoveredCommand(
                name=f"fast verify {index}",
                command=str(command),
                source=f"repo-family:{family_name}",
            )
            for index, command in enumerate(commands, start=1)
        ]
    return []
