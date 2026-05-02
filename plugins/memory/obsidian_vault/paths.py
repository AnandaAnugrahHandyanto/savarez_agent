"""Path/config helpers for the Obsidian vault memory plugin."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


CONFIG_FILE = "obsidian_vault_provider.json"


def _config_path(hermes_home: str | Path) -> Path:
    return Path(hermes_home).expanduser() / CONFIG_FILE


def load_provider_config(hermes_home: str | Path) -> dict[str, Any]:
    path = _config_path(hermes_home)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def save_provider_config(hermes_home: str | Path, config: Mapping[str, Any]) -> Path:
    path = _config_path(hermes_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(config), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def resolve_relative_path(root: str | Path, rel: str | Path) -> Path:
    root_path = Path(root).expanduser().resolve()
    candidate = (root_path / rel).resolve()
    candidate.relative_to(root_path)
    return candidate


def resolve_vault_root(config: Mapping[str, Any] | None, *, hermes_home: str | Path | None = None) -> Path | None:
    cfg = config or {}
    candidates: list[Any] = []
    candidates.append(cfg.get("vault_path"))

    memory_cfg = cfg.get("memory") if isinstance(cfg.get("memory"), dict) else {}
    candidates.append(memory_cfg.get("vault_path"))

    obsidian_cfg = cfg.get("obsidian_vault") if isinstance(cfg.get("obsidian_vault"), dict) else {}
    candidates.append(obsidian_cfg.get("vault_path"))

    provider_cfg = cfg.get("provider") if isinstance(cfg.get("provider"), dict) else {}
    candidates.append(provider_cfg.get("vault_path"))

    if hermes_home:
        candidates.append(Path(hermes_home).expanduser() / "Hermes Memory Vault")

    for value in candidates:
        if not value:
            continue
        path = Path(value).expanduser().resolve()
        if path.exists() and path.is_dir():
            return path
    return None
