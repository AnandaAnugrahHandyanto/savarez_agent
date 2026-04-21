from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = REPO_ROOT / "docs/plans/orbi-romance-webtoon-20260421"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
MODULE_PATH = SCRIPTS_DIR / "webtoon_contracts.py"


def load_contracts_module(module_name: str = "orbi_romance_contracts"):
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
