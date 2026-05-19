"""
Workflow Engine plugin — FastAPI router.

Phase 3: real handlers delegating to WorkflowEngine.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine bootstrap
# ---------------------------------------------------------------------------

_PLUGIN_DIR = Path(__file__).resolve().parent.parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

from engine import WorkflowEngine, create_engine  # noqa: E402

_engine: WorkflowEngine = create_engine()

router = APIRouter()

_VERSION = "0.1.0"

# Validation patterns (mirror TS)
_ID_RE = re.compile(r"^[A-Za-z0-9_:.\-]{1,128}$")
_MAX_YAML_BYTES = 1024 * 1024


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _json(body: Any, status: int = 200) -> JSONResponse:
    return JSONResponse(content=body, status_code=status)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get("/health")
async def health() -> dict:
    return {"ok": True, "version": _VERSION}


# ---------------------------------------------------------------------------
# Definitions — GET /definitions
# ---------------------------------------------------------------------------


@router.get("/definitions")
async def list_definitions() -> JSONResponse:
    defs = await _engine.list_definitions()
    return _json({"definitions": defs})


# ---------------------------------------------------------------------------
# Definitions — POST /definitions
# ---------------------------------------------------------------------------


@router.post("/definitions")
async def create_definition(request: Request) -> JSONResponse:
    try:
        body: Dict[str, Any] = await request.json()
    except Exception:
        return _json({"error": "Invalid JSON body"}, 400)

    # Validate id
    if not isinstance(body.get("id"), str) or not _ID_RE.match(body["id"]):
        return _json({"error": "id must be 1-128 chars of [A-Za-z0-9_:.-]"}, 400)
    # Validate name
    name = body.get("name")
    if not isinstance(name, str) or len(name) < 1 or len(name) > 256:
        return _json({"error": "name must be a string 1-256 chars"}, 400)
    # Validate yaml
    yaml_text = body.get("yaml")
    if not isinstance(yaml_text, str) or len(yaml_text) == 0:
        return _json({"error": "yaml must be a non-empty string"}, 400)
    if len(yaml_text.encode("utf-8")) > _MAX_YAML_BYTES:
        return _json({"error": f"yaml exceeds {_MAX_YAML_BYTES} bytes"}, 413)
    # Validate source
    source = body.get("source", "project")
    if source not in ("project", "user", "bundled"):
        return _json({"error": "source must be 'project' | 'user' | 'bundled'"}, 400)
    if source == "bundled":
        return _json({"error": "source='bundled' is read-only"}, 403)
    # Validate scope_path
    scope_path = body.get("scope_path")
    if scope_path is not None:
        if not isinstance(scope_path, str) or not scope_path.startswith("/") or ".." in scope_path:
            return _json({"error": "scope_path must be absolute and contain no .. segments"}, 400)
    # Validate optional fields
    if "description" in body and not isinstance(body["description"], str):
        return _json({"error": "description must be a string when provided"}, 400)
    if "version" in body and not isinstance(body["version"], str):
        return _json({"error": "version must be a string when provided"}, 400)
    tags = body.get("tags")
    if tags is not None:
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            return _json({"error": "tags must be a string[] when provided"}, 400)

    try:
        defn = await _engine.upsert_definition(yaml_text=yaml_text, source_path=scope_path)
    except ValueError as exc:
        return _json({"error": str(exc)}, 422)

    return _json({"definition": defn}, 201)


# ---------------------------------------------------------------------------
# Definitions — GET /definitions/{id}
# ---------------------------------------------------------------------------


@router.get("/definitions/{def_id}")
async def get_definition(def_id: str) -> JSONResponse:
    defn = await _engine.get_definition(def_id)
    if defn is None:
        return _json({"error": "not found"}, 404)
    return _json({"definition": defn})


# ---------------------------------------------------------------------------
# Definitions — GET /definitions/{id}/parsed
# ---------------------------------------------------------------------------


@router.get("/definitions/{def_id}/parsed")
async def get_definition_parsed(def_id: str) -> JSONResponse:
    result = await _engine.parse_definition(def_id)
    if result is None:
        return _json({"error": "not found"}, 404)
    if "error" in result:
        return _json({"error": result["error"]}, 422)
    return _json({"parsed": result})


# ---------------------------------------------------------------------------
# Runs — GET /runs
# ---------------------------------------------------------------------------


@router.get("/runs")
async def list_runs(request: Request) -> JSONResponse:
    params = request.query_params
    workflow_id: Optional[str] = params.get("workflow_id") or None
    status_csv: Optional[str] = params.get("status") or None
    statuses: Optional[List[str]] = status_csv.split(",") if status_csv else None

    rows = await _engine.list_runs(workflow_id=workflow_id)
    if statuses:
        rows = [r for r in rows if r.get("status") in statuses]
    return _json({"runs": rows})


# ---------------------------------------------------------------------------
# Runs — POST /runs
# ---------------------------------------------------------------------------


@router.post("/runs")
async def create_run(request: Request) -> JSONResponse:
    try:
        body: Dict[str, Any] = await request.json()
    except Exception:
        return _json({"error": "Invalid JSON body"}, 400)

    # Required fields
    if not body.get("workflow_id") or not body.get("conversation_id") or not body.get("user_message"):
        return _json({"error": "workflow_id, conversation_id, user_message required"}, 400)

    workflow_id = body["workflow_id"]
    conversation_id = body["conversation_id"]
    user_message = body["user_message"]

    if not isinstance(workflow_id, str) or not _ID_RE.match(workflow_id):
        return _json({"error": "workflow_id must be 1-128 chars of [A-Za-z0-9_:.-]"}, 400)
    if not isinstance(conversation_id, str) or len(conversation_id) < 1 or len(conversation_id) > 256:
        return _json({"error": "conversation_id must be 1-256 chars"}, 400)
    if not isinstance(user_message, str) or len(user_message) == 0:
        return _json({"error": "user_message must be a non-empty string"}, 400)

    working_path = body.get("working_path")
    if working_path is not None:
        if not isinstance(working_path, str) or not working_path.startswith("/") or ".." in working_path:
            return _json({"error": "working_path must be an absolute path with no .. segments"}, 400)

    # Check definition exists
    defn = await _engine.get_definition(workflow_id)
    if defn is None:
        return _json({"error": f"unknown workflow_id '{workflow_id}'"}, 404)

    trigger: Dict[str, Any] = {
        "kind": "manual",
        "conversation_id": conversation_id,
        "working_path": working_path or "/tmp",
        "user_message": user_message,
    }
    if body.get("parent_conversation_id"):
        trigger["parent_conversation_id"] = body["parent_conversation_id"]
    if body.get("codebase_id"):
        trigger["codebase_id"] = body["codebase_id"]

    inputs: Dict[str, Any] = body.get("variables") or {}

    try:
        run = await _engine.start_run(workflow_id, inputs, trigger)
    except ValueError as exc:
        return _json({"error": str(exc)}, 400)

    return _json({"run": run}, 201)


# ---------------------------------------------------------------------------
# Runs — GET /runs/{run_id}
# ---------------------------------------------------------------------------


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> JSONResponse:
    run = await _engine.get_run(run_id)
    if run is None:
        return _json({"error": "not found"}, 404)

    # Include node_runs and recent events for UI detail view
    node_runs = _engine._run_store.list_node_runs(run_id)
    events = _engine._run_store.list_recent_events(run_id, limit=50)

    return _json({
        "run": run,
        "nodeRuns": node_runs,
        "events": events,
    })


# ---------------------------------------------------------------------------
# Approve — POST /runs/{run_id}/approve
# ---------------------------------------------------------------------------


@router.post("/runs/{run_id}/approve")
async def approve_run(run_id: str, request: Request) -> JSONResponse:
    run = await _engine.get_run(run_id)
    if run is None:
        return _json({"error": "workflow_run not found"}, 404)

    try:
        body: Dict[str, Any] = await request.json()
    except Exception:
        return _json({"error": "Invalid JSON body"}, 400)

    node_run_id = body.get("node_run_id")
    decision = body.get("decision")
    response_text = body.get("response", "")

    if not isinstance(node_run_id, str) or not node_run_id:
        return _json({"error": "node_run_id is required"}, 400)
    if decision not in ("approved", "rejected"):
        return _json({"error": "decision must be 'approved' or 'rejected'"}, 400)
    if not isinstance(response_text, str):
        response_text = ""

    # Look up node_run by ID to get the DAG node_id
    node_run = _engine._run_store.get_node_run(node_run_id)
    if node_run is None:
        return _json({"error": "node_run not found"}, 404)
    if node_run.get("workflow_run_id") != run_id:
        return _json({"error": "node_run does not belong to this workflow_run"}, 400)

    # Map TS decision values to Python facade values
    py_decision = "approve" if decision == "approved" else "reject"
    dag_node_id: str = node_run["dag_node_id"]

    try:
        await _engine.approve(
            run_id=run_id,
            node_id=dag_node_id,
            decision=py_decision,  # type: ignore[arg-type]
            comment=response_text or None,
        )
    except ValueError as exc:
        return _json({"error": str(exc)}, 404)

    return _json({"ok": True, "decision": decision, "resumedRunId": run_id})


# ---------------------------------------------------------------------------
# Events — GET /events  (SSE)
# ---------------------------------------------------------------------------


@router.get("/events")
async def events(request: Request) -> StreamingResponse:
    params = request.query_params
    run_id: Optional[str] = params.get("runId") or params.get("run_id") or None

    async def _generate() -> AsyncIterator[str]:
        HEARTBEAT_INTERVAL = 15.0
        last_heartbeat = asyncio.get_event_loop().time()

        try:
            async for evt in _engine.subscribe_events(run_id):
                # Check client disconnect
                if await request.is_disconnected():
                    break

                kind = evt.get("event_type", "event")
                # Serialize removing non-serializable items
                try:
                    data = json.dumps(evt)
                except (TypeError, ValueError):
                    data = json.dumps({"raw": str(evt)})

                yield f"event: {kind}\ndata: {data}\n\n"

                # Heartbeat
                now = asyncio.get_event_loop().time()
                if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                    yield "event: ping\ndata: {}\n\n"
                    last_heartbeat = now
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            log.warning("SSE stream error: %s", exc)
            yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
