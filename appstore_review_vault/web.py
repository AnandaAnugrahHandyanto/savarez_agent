from __future__ import annotations

from pathlib import Path
import threading
from typing import Any

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from .config import load_apps_yaml
from .csv_export import reviews_to_csv
from .db import (
    archive_app,
    dashboard_stats,
    get_connection,
    init_db,
    list_apps,
    list_errors,
    list_runs,
    restore_app,
    search_reviews,
    upsert_app,
)
from .jobs import refresh_all, refresh_app

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = Path.cwd() / "data"
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "appstore_reviews.sqlite"
DEFAULT_APPS_YAML = DEFAULT_DATA_DIR / "apps.yaml"

templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))
router = APIRouter()
_job_lock = threading.Lock()


def get_db_path(request: Request) -> Path:
    return Path(getattr(request.app.state, "db_path", DEFAULT_DB_PATH))


def get_conn(request: Request):
    conn = get_connection(get_db_path(request))
    try:
        yield conn
    finally:
        conn.close()


def redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


def _sync_yaml_apps(db_path: Path, apps_yaml: Path) -> None:
    if not apps_yaml.exists():
        apps_yaml.parent.mkdir(parents=True, exist_ok=True)
        apps_yaml.write_text("apps: []\n", encoding="utf-8")
    conn = get_connection(db_path)
    try:
        for seed in load_apps_yaml(apps_yaml):
            upsert_app(conn, seed.app_id, seed.name)
    finally:
        conn.close()


def create_router() -> APIRouter:
    return router


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, conn=Depends(get_conn)):
    return templates.TemplateResponse(request, "dashboard.html", {"stats": dashboard_stats(conn)})


@router.get("/apps", response_class=HTMLResponse)
def apps_page(request: Request, include_archived: bool = Query(False), conn=Depends(get_conn)):
    return templates.TemplateResponse(
        request,
        "apps.html",
        {"apps": list_apps(conn, include_archived=include_archived), "include_archived": include_archived},
    )


@router.post("/apps")
def add_app(app_id: str = Form(...), name: str = Form(""), conn=Depends(get_conn)):
    app_id = app_id.strip()
    if app_id.isdigit():
        upsert_app(conn, app_id, name.strip() or None)
    return redirect("/apps")


@router.post("/apps/{app_id}/archive")
def archive_app_route(app_id: str, conn=Depends(get_conn)):
    archive_app(conn, app_id)
    return redirect("/apps")


@router.post("/apps/{app_id}/restore")
def restore_app_route(app_id: str, conn=Depends(get_conn)):
    restore_app(conn, app_id)
    return redirect("/apps?include_archived=true")


def _run_refresh(db_path: Path, app_id: str | None = None) -> None:
    if not _job_lock.acquire(blocking=False):
        return
    conn = get_connection(db_path)
    try:
        if app_id:
            refresh_app(conn, app_id)
        else:
            refresh_all(conn)
    finally:
        conn.close()
        _job_lock.release()


@router.post("/apps/{app_id}/refresh")
def refresh_app_route(request: Request, app_id: str):
    threading.Thread(target=_run_refresh, args=(get_db_path(request), app_id), daemon=True).start()
    return redirect("/runs")


@router.post("/refresh-all")
def refresh_all_route(request: Request):
    threading.Thread(target=_run_refresh, args=(get_db_path(request), None), daemon=True).start()
    return redirect("/runs")


def _review_filters(
    app_id: str | None,
    country: str | None,
    rating: int | None,
    version: str | None,
    q: str | None,
    sort_source: str | None,
    include_archived: bool,
) -> dict[str, Any]:
    return {
        "app_id": app_id or None,
        "country": country or None,
        "rating": rating,
        "version": version or None,
        "q": q or None,
        "sort_source": sort_source or None,
        "include_archived": include_archived,
    }


@router.get("/reviews", response_class=HTMLResponse)
def reviews_page(
    request: Request,
    app_id: str | None = None,
    country: str | None = None,
    rating: int | None = None,
    version: str | None = None,
    q: str | None = None,
    sort_source: str | None = None,
    include_archived: bool = False,
    conn=Depends(get_conn),
):
    filters = _review_filters(app_id, country, rating, version, q, sort_source, include_archived)
    rows = search_reviews(conn, **filters, limit=100)
    return templates.TemplateResponse(
        request,
        "reviews.html",
        {"reviews": rows, "apps": list_apps(conn, include_archived=True), "filters": filters},
    )


@router.get("/reviews.csv")
def reviews_csv(
    app_id: str | None = None,
    country: str | None = None,
    rating: int | None = None,
    version: str | None = None,
    q: str | None = None,
    sort_source: str | None = None,
    include_archived: bool = False,
    conn=Depends(get_conn),
):
    filters = _review_filters(app_id, country, rating, version, q, sort_source, include_archived)
    rows = search_reviews(conn, **filters, limit=100000)
    return Response(
        reviews_to_csv(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=appstore_reviews.csv"},
    )


@router.get("/runs", response_class=HTMLResponse)
def runs_page(request: Request, conn=Depends(get_conn)):
    return templates.TemplateResponse(request, "runs.html", {"runs": list_runs(conn)})


@router.get("/errors", response_class=HTMLResponse)
def errors_page(request: Request, conn=Depends(get_conn)):
    return templates.TemplateResponse(request, "errors.html", {"errors": list_errors(conn)})


def initialize_storage(db_path: Path = DEFAULT_DB_PATH, apps_yaml: Path = DEFAULT_APPS_YAML) -> None:
    init_db(db_path)
    _sync_yaml_apps(db_path, apps_yaml)
