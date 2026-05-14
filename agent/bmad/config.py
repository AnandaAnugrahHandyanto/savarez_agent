from __future__ import annotations

import copy
import tomllib
from pathlib import Path
from typing import Any


def _array_key(items: list[Any]) -> str | None:
    if not items or not all(isinstance(item, dict) for item in items):
        return None
    for key in ("code", "id"):
        if all(key in item for item in items):
            return key
    return None


def merge_bmad_values(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        result = copy.deepcopy(base)
        for key, value in override.items():
            result[key] = merge_bmad_values(result[key], value) if key in result else copy.deepcopy(value)
        return result

    if isinstance(base, list) and isinstance(override, list):
        key = _array_key(base)
        if not key or key != _array_key(override):
            return copy.deepcopy(base) + copy.deepcopy(override)
        result = [copy.deepcopy(item) for item in base]
        index = {item[key]: idx for idx, item in enumerate(result)}
        for item in override:
            item_key = item[key]
            if item_key in index:
                result[index[item_key]] = merge_bmad_values(result[index[item_key]], item)
            else:
                index[item_key] = len(result)
                result.append(copy.deepcopy(item))
        return result

    return copy.deepcopy(override)


def _safe_project_file(path: Path, root: Path) -> bool:
    if not path.exists() or path.is_symlink():
        return False
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return path.is_file()


def _read_toml(path: Path, root: Path) -> dict[str, Any]:
    if not _safe_project_file(path, root):
        return {}
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _read_yaml(path: Path, root: Path) -> dict[str, Any]:
    if not _safe_project_file(path, root):
        return {}
    try:
        import yaml
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def resolve_bmad_config(bmad_root: str | Path) -> dict[str, Any]:
    root = Path(bmad_root)
    resolved: dict[str, Any] = {}

    # Real BMAD installs (v6.x) write module-local config.yaml files. Merge these
    # first in module-directory order, then apply root/custom TOML layers for
    # compatibility with older/planned layouts and user overrides.
    module_configs = sorted(
        root.glob("*/config.yaml"),
        key=lambda path: (0 if path.parent.name == "core" else 1 if path.parent.name == "bmm" else 2, path.parent.name),
    )
    for layer in module_configs:
        resolved = merge_bmad_values(resolved, _read_yaml(layer, root))

    layers = [
        root / "config.toml",
        root / "config.user.toml",
        root / "custom" / "config.toml",
        root / "custom" / "config.user.toml",
    ]
    for layer in layers:
        resolved = merge_bmad_values(resolved, _read_toml(layer, root))
    return resolved
