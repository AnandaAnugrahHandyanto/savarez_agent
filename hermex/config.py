from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from hermex.core.store import CoreStore, SQLiteStoreConfig, build_sqlite_core_store


@dataclass(frozen=True)
class Config:
    store_backend: str = "sqlite"
    sqlite_path: Path = Path(".hermex/hermex.sqlite3")
    upstream_base: str = "https://api.anthropic.com"
    api_key: str = ""


def load_config() -> Config:
    return Config(
        store_backend=os.getenv("HERMEX_STORE", "sqlite"),
        sqlite_path=Path(os.getenv("HERMEX_SQLITE_PATH", ".hermex/hermex.sqlite3")),
        upstream_base=os.getenv("UPSTREAM_BASE", "https://api.anthropic.com"),
        api_key=os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENROUTER_API_KEY") or "",
    )


def build_core_store(config: Config) -> CoreStore:
    if config.store_backend == "redis":
        raise NotImplementedError("HERMEX_STORE=redis is reserved for phase 2; use HERMEX_STORE=sqlite for MVP.")
    if config.store_backend != "sqlite":
        raise ValueError(f"Unsupported HERMEX_STORE value: {config.store_backend}")
    return build_sqlite_core_store(SQLiteStoreConfig(path=config.sqlite_path))
