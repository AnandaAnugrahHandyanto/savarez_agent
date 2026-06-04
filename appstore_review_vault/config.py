from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass(frozen=True)
class AppSeed:
    app_id: str
    name: str | None = None


def load_apps_yaml(path: str | Path) -> list[AppSeed]:
    path = Path(path)
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    seen: set[str] = set()
    apps: list[AppSeed] = []
    for item in data.get("apps", []):
        app_id = str(item.get("app_id", "")).strip()
        if not app_id or not app_id.isdigit() or app_id in seen:
            continue
        seen.add(app_id)
        name = item.get("name")
        apps.append(AppSeed(app_id=app_id, name=str(name) if name else None))
    return apps
