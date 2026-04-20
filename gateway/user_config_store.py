"""Shared raw config.yaml read/write helpers for gateway runtime code."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import hermes_cli.config as hermes_config
import yaml
from utils import atomic_yaml_write


def gateway_user_config_path(hermes_home: Path) -> Path:
    return hermes_home / "config.yaml"


def load_raw_config_mapping(
    config_path: Path,
    *,
    allow_missing: bool,
    require_mapping: bool = False,
) -> dict[str, Any]:
    cfg = hermes_config.read_user_config_raw(config_path=config_path)
    if isinstance(cfg, dict) and cfg:
        return cfg

    if not config_path.exists():
        if allow_missing:
            return {}
        raise FileNotFoundError(config_path)

    with open(config_path, encoding="utf-8") as f:
        raw_validated = yaml.safe_load(f)
    if require_mapping and not isinstance(raw_validated, dict):
        raise TypeError(f"Expected mapping at {config_path}, got {type(raw_validated).__name__}")
    validated = raw_validated or {}
    return validated if isinstance(validated, dict) else {}


def load_gateway_user_config_raw(hermes_home: Path) -> dict[str, Any]:
    return load_raw_config_mapping(gateway_user_config_path(hermes_home), allow_missing=True)


def save_gateway_user_config_raw(hermes_home: Path, config: dict[str, Any]) -> None:
    config_path = gateway_user_config_path(hermes_home)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_yaml_write(config_path, config)


def set_gateway_config_key(config: dict[str, Any], key_path: str, value: Any) -> None:
    current = config
    keys = key_path.split(".")
    for key in keys[:-1]:
        child = current.get(key)
        if not isinstance(child, dict):
            child = {}
            current[key] = child
        current = child
    current[keys[-1]] = value


def delete_gateway_config_key(config: dict[str, Any], key_path: str) -> None:
    keys = key_path.split(".")
    current: dict[str, Any] | None = config
    parents: list[tuple[dict[str, Any], str]] = []
    for key in keys[:-1]:
        if not isinstance(current, dict):
            return
        child = current.get(key)
        if not isinstance(child, dict):
            return
        parents.append((current, key))
        current = child
    if not isinstance(current, dict):
        return
    current.pop(keys[-1], None)
    for parent, key in reversed(parents):
        child = parent.get(key)
        if isinstance(child, dict) and not child:
            parent.pop(key, None)
        else:
            break


def save_gateway_config_key(hermes_home: Path, key_path: str, value: Any) -> None:
    config = load_gateway_user_config_raw(hermes_home)
    set_gateway_config_key(config, key_path, value)
    save_gateway_user_config_raw(hermes_home, config)


def save_gateway_config_updates(
    hermes_home: Path,
    updates: dict[str, Any],
    *,
    delete_paths: list[str] | None = None,
) -> None:
    config = load_gateway_user_config_raw(hermes_home)
    for key_path, value in updates.items():
        set_gateway_config_key(config, key_path, value)
    for key_path in delete_paths or []:
        delete_gateway_config_key(config, key_path)
    save_gateway_user_config_raw(hermes_home, config)


__all__ = [
    "gateway_user_config_path",
    "load_raw_config_mapping",
    "load_gateway_user_config_raw",
    "save_gateway_user_config_raw",
    "set_gateway_config_key",
    "delete_gateway_config_key",
    "save_gateway_config_key",
    "save_gateway_config_updates",
]
