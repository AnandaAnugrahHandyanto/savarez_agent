"""Reusable helpers for verifying declared artifact paths.

The helpers in this module intentionally check path existence only. They do not
validate artifact contents because content schemas are workflow-specific.

This is a dedicated artifact-verification module rather than a general-purpose
``utils`` addition. Keeping it separate makes the API importable and testable
without growing the existing top-level ``utils.py`` catch-all module.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class ArtifactPathPolicy:
    """Controls how artifact path declarations are resolved."""

    base_dir: Path
    workspace_root: Path | None = None
    workspace_relative_prefixes: tuple[str, ...] = ()
    allow_absolute: bool = True
    require_file: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.base_dir, Path):
            raise TypeError("base_dir must be a pathlib.Path")
        if self.workspace_root is not None and not isinstance(self.workspace_root, Path):
            raise TypeError("workspace_root must be a pathlib.Path or None")
        if not isinstance(self.workspace_relative_prefixes, tuple):
            raise TypeError("workspace_relative_prefixes must be a tuple of strings")
        if not all(isinstance(prefix, str) for prefix in self.workspace_relative_prefixes):
            raise TypeError("workspace_relative_prefixes must contain only strings")


@dataclass(frozen=True)
class ArtifactCheckItem:
    """Single artifact path check result."""

    path: str
    exists: bool
    is_file: bool | None = None
    resolved: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "exists": self.exists,
            "is_file": self.is_file,
            "resolved": self.resolved,
        }


@dataclass(frozen=True)
class ArtifactCheckResult:
    """Aggregate result for a required-artifact check."""

    ok: bool
    expected_count: int
    present: list[str]
    missing: list[str]
    checked: list[ArtifactCheckItem]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "expected_count": self.expected_count,
            "present": list(self.present),
            "missing": list(self.missing),
            "checked": [item.to_dict() for item in self.checked],
        }


def artifact_path_from_spec(spec: str | Mapping[str, Any]) -> str | None:
    """Extract a path string from a string or ``{"path": ...}`` artifact spec."""

    if isinstance(spec, str):
        return spec if spec else None
    if isinstance(spec, Mapping):
        path = spec.get("path")
        return path if isinstance(path, str) and path else None
    return None


def required_artifact_paths(
    spec_owner: Mapping[str, Any],
    *,
    field: str = "required_artifacts",
) -> list[str]:
    """Return valid required artifact path declarations from ``spec_owner``.

    Non-list values for ``field`` are treated as empty, meaning no artifacts
    are declared.
    """

    raw_specs = spec_owner.get(field, [])
    if not isinstance(raw_specs, list):
        return []

    paths: list[str] = []
    for spec in raw_specs:
        path = artifact_path_from_spec(spec)
        if path is not None:
            paths.append(path)
    return paths


def resolve_artifact_path(path_text: str, policy: ArtifactPathPolicy) -> Path:
    """Resolve one artifact path according to an explicit path policy."""

    path = Path(path_text).expanduser()
    if path.is_absolute():
        if not policy.allow_absolute:
            raise ValueError("Absolute artifact paths are not allowed")
        return path

    if policy.workspace_root is not None:
        normalized = path_text.replace("\\", "/")
        for prefix in policy.workspace_relative_prefixes:
            if prefix and normalized.startswith(prefix):
                return policy.workspace_root / path

    return policy.base_dir / path


def _is_satisfied(path: Path, policy: ArtifactPathPolicy) -> tuple[bool, bool | None]:
    exists = path.exists()
    if not exists:
        return False, None
    is_file = path.is_file()
    if policy.require_file and not is_file:
        return False, is_file
    return True, is_file


def check_required_artifacts(
    spec_owner: Mapping[str, Any],
    *,
    policy: ArtifactPathPolicy,
    extra_paths: Iterable[str | Mapping[str, Any]] = (),
    field: str = "required_artifacts",
) -> ArtifactCheckResult:
    """Check declared artifact paths for existence.

    By default, a satisfying artifact must be an existing regular file. Set
    ``policy.require_file=False`` when directory artifacts should count as
    present. Content validation is intentionally left to callers.
    """

    paths = required_artifact_paths(spec_owner, field=field)
    for spec in extra_paths:
        path = artifact_path_from_spec(spec)
        if path is not None:
            paths.append(path)

    checked: list[ArtifactCheckItem] = []
    present: list[str] = []
    missing: list[str] = []

    for path_text in paths:
        resolved_path = resolve_artifact_path(path_text, policy)
        satisfied, is_file = _is_satisfied(resolved_path, policy)
        checked.append(
            ArtifactCheckItem(
                path=path_text,
                exists=resolved_path.exists(),
                is_file=is_file,
                resolved=str(resolved_path),
            )
        )
        if satisfied:
            present.append(path_text)
        else:
            missing.append(path_text)

    return ArtifactCheckResult(
        ok=not missing,
        expected_count=len(paths),
        present=present,
        missing=missing,
        checked=checked,
    )
