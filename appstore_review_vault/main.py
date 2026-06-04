from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .web import PACKAGE_DIR, DEFAULT_APPS_YAML, DEFAULT_DB_PATH, create_router, initialize_storage


def create_app(db_path: str | Path = DEFAULT_DB_PATH, apps_yaml: str | Path = DEFAULT_APPS_YAML) -> FastAPI:
    db_path = Path(db_path)
    apps_yaml = Path(apps_yaml)
    initialize_storage(db_path, apps_yaml)
    app = FastAPI(title="App Store Review Vault")
    app.state.db_path = db_path
    app.state.apps_yaml = apps_yaml
    app.include_router(create_router())
    app.mount("/static", StaticFiles(directory=str(PACKAGE_DIR / "static")), name="static")
    return app


app = create_app()
