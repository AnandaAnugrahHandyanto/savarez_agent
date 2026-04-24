from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.task_contracts import TaskContract, validate_task_contract

MAX_HERMES_CONTEXT_LAYERS = 3


@dataclass(frozen=True)
class ContextLayer:
    kind: str
    path: Path
    precedence: int

    @property
    def display_path(self) -> str:
        return self.path.name


@dataclass(frozen=True)
class BoundedHierarchicalContext:
    task_contract: dict[str, Any]
    layers: tuple[ContextLayer, ...]
    precedence: tuple[str, ...]


_HERMES_NAMES = (".hermes.md", "HERMES.md")


def _find_git_root(start: Path) -> Path | None:
    current = start.resolve()
    for parent in (current, *current.parents):
        if (parent / ".git").exists():
            return parent
    return None


def discover_hermes_context_layers(cwd: str | Path, *, max_layers: int = MAX_HERMES_CONTEXT_LAYERS) -> tuple[ContextLayer, ...]:
    cwd_path = Path(cwd).resolve()
    stop_at = _find_git_root(cwd_path)
    lineage = [cwd_path, *cwd_path.parents]
    if stop_at is not None:
        lineage = lineage[: lineage.index(stop_at) + 1]
    lineage = list(reversed(lineage))

    discovered: list[ContextLayer] = []
    for directory in lineage:
        chosen = None
        for name in _HERMES_NAMES:
            candidate = directory / name
            if candidate.is_file():
                chosen = candidate
                break
        if chosen is None:
            continue
        discovered.append(ContextLayer(kind="hermes", path=chosen, precedence=len(discovered) + 1))

    if len(discovered) <= max_layers:
        return tuple(discovered)

    bounded = [discovered[0], *discovered[-(max_layers - 1):]] if max_layers > 1 else [discovered[-1]]
    return tuple(
        ContextLayer(kind=layer.kind, path=layer.path, precedence=index + 1)
        for index, layer in enumerate(bounded)
    )


def apply_bounded_hierarchical_context(
    task_contract: dict[str, Any] | TaskContract,
    layers: list[ContextLayer] | tuple[ContextLayer, ...],
) -> BoundedHierarchicalContext:
    validated = validate_task_contract(task_contract).model_dump()
    preserved_context = validated.get("context")
    if preserved_context != validate_task_contract(task_contract).model_dump().get("context"):
        raise AssertionError("task contract context must remain unchanged")
    precedence = ("task_contract",) + tuple(f"{layer.kind}:{layer.display_path}" for layer in layers)
    return BoundedHierarchicalContext(
        task_contract=validated,
        layers=tuple(layers),
        precedence=precedence,
    )


__all__ = [
    "BoundedHierarchicalContext",
    "ContextLayer",
    "MAX_HERMES_CONTEXT_LAYERS",
    "apply_bounded_hierarchical_context",
    "discover_hermes_context_layers",
]
