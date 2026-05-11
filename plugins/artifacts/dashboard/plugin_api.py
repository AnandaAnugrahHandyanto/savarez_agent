"""Artifacts dashboard plugin backend routes.

Mounted at /api/plugins/artifacts/ by the Dashboard plugin loader.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse

try:
    from plugins.artifacts import store
except Exception:  # pragma: no cover - supports direct file loading in tests
    import importlib.util
    import sys

    _store_path = Path(__file__).resolve().parents[1] / "store.py"
    _spec = importlib.util.spec_from_file_location("hermes_artifacts_store_runtime", _store_path)
    if _spec is None or _spec.loader is None:
        raise
    store = importlib.util.module_from_spec(_spec)  # type: ignore[assignment]
    sys.modules[_spec.name] = store
    _spec.loader.exec_module(store)


router = APIRouter()


def _security_headers(content_type: str | None = None) -> dict[str, str]:
    headers = {
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": store.DEFAULT_CSP,
        "Cache-Control": "private, max-age=60",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


@router.get("/list")
def list_artifacts() -> dict[str, object]:
    artifacts = store.list_artifacts()
    return {"artifacts": artifacts, "count": len(artifacts)}


@router.get("/{artifact_id}")
def get_artifact(artifact_id: str) -> dict[str, object]:
    try:
        artifact = store.get_artifact(artifact_id)
    except store.ArtifactStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="artifact not found") from exc
    return {"artifact": artifact}


@router.head("/preview/{artifact_id}/versions/{version}/{file_path:path}")
def head_preview(artifact_id: str, version: int, file_path: str) -> Response:
    try:
        path = store.resolve_preview_path(artifact_id, version, file_path)
    except store.ArtifactStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="preview file not found") from exc
    return Response(headers=_security_headers(store.content_type_for(path)))


@router.get("/preview/{artifact_id}/versions/{version}/{file_path:path}")
def get_preview(artifact_id: str, version: int, file_path: str) -> FileResponse:
    try:
        path = store.resolve_preview_path(artifact_id, version, file_path)
    except store.ArtifactStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="preview file not found") from exc
    return FileResponse(path, media_type=store.content_type_for(path), headers=_security_headers())
