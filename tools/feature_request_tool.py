"""Feature request tracking tool for Hermes Agent.

Provides tools to submit, list, update, and manage feature requests.
Stores feature requests as JSON files in ~/.hermes/features/.
"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from hermes_constants import get_hermes_home
from tools.registry import registry

logger = logging.getLogger(__name__)

_FEATURES_DIR = Path(get_hermes_home()) / "features"


def _ensure_features_dir() -> Path:
    """Ensure the features directory exists."""
    _FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    return _FEATURES_DIR


def _generate_id() -> str:
    """Generate a unique feature request ID."""
    return f"FR-{int(time.time())}"


def _get_feature_path(feature_id: str) -> Path:
    """Get the path for a feature request file."""
    return _ensure_features_dir() / f"{feature_id}.json"


def submit_feature_request(
    title: str,
    description: str = "",
    priority: str = "medium",
    tags: list = None,
    related_files: list = None,
) -> str:
    """Submit a new feature request.

    Args:
        title: Short title/summary of the feature request (required).
        description: Detailed description of the feature (optional).
        priority: Priority level: low, medium, high, critical (default: medium).
        tags: List of tags/categories (optional).
        related_files: List of related file paths (optional).

    Returns:
        JSON string with result.
    """
    if not title.strip():
        return json.dumps({
            "success": False,
            "error": "Feature title is required."
        })

    valid_priorities = {"low", "medium", "high", "critical"}
    priority = priority.lower().strip()
    if priority not in valid_priorities:
        priority = "medium"

    feature_id = _generate_id()
    now = datetime.utcnow().isoformat() + "Z"

    feature = {
        "id": feature_id,
        "title": title.strip(),
        "description": description.strip(),
        "status": "pending",
        "priority": priority,
        "tags": tags or [],
        "related_files": related_files or [],
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
        "notes": [],
    }

    try:
        path = _get_feature_path(feature_id)
        path.write_text(json.dumps(feature, indent=2), encoding="utf-8")
        return json.dumps({
            "success": True,
            "feature_id": feature_id,
            "message": f"Feature request submitted: {feature_id}",
            "feature": feature,
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Failed to save feature request: {e}"
        })


def list_feature_requests(
    status: str = "",
    priority: str = "",
    tag: str = "",
    limit: int = 50,
) -> str:
    """List feature requests with optional filtering.

    Args:
        status: Filter by status (pending, approved, in-progress, completed, rejected).
        priority: Filter by priority (low, medium, high, critical).
        tag: Filter by tag.
        limit: Maximum number of results (default: 50).

    Returns:
        JSON string with list of features.
    """
    try:
        _ensure_features_dir()
        features = []
        for path in sorted(_FEATURES_DIR.glob("FR-*.json"), reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                # Apply filters
                if status and data.get("status") != status:
                    continue
                if priority and data.get("priority") != priority:
                    continue
                if tag and tag not in (data.get("tags") or []):
                    continue
                features.append(data)
            except Exception:
                continue

        features = features[:limit]
        return json.dumps({
            "success": True,
            "features": features,
            "count": len(features),
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Failed to list features: {e}"
        })


def get_feature_request(feature_id: str) -> str:
    """Get a specific feature request by ID.

    Args:
        feature_id: The feature request ID.

    Returns:
        JSON string with feature details.
    """
    path = _get_feature_path(feature_id)
    if not path.exists():
        return json.dumps({
            "success": False,
            "error": f"Feature request not found: {feature_id}"
        })

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return json.dumps({
            "success": True,
            "feature": data,
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Failed to read feature: {e}"
        })


def update_feature_request(
    feature_id: str,
    status: str = "",
    priority: str = "",
    note: str = "",
) -> str:
    """Update a feature request's status, priority, or add a note.

    Args:
        feature_id: The feature request ID.
        status: New status (pending, approved, in-progress, completed, rejected).
        priority: New priority (low, medium, high, critical).
        note: Note to append to the feature request.

    Returns:
        JSON string with result.
    """
    path = _get_feature_path(feature_id)
    if not path.exists():
        return json.dumps({
            "success": False,
            "error": f"Feature request not found: {feature_id}"
        })

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        now = datetime.utcnow().isoformat() + "Z"

        valid_statuses = {"pending", "approved", "in-progress", "completed", "rejected"}
        if status and status in valid_statuses:
            data["status"] = status
            if status == "completed":
                data["completed_at"] = now
            else:
                data["completed_at"] = None

        valid_priorities = {"low", "medium", "high", "critical"}
        if priority and priority in valid_priorities:
            data["priority"] = priority

        if note.strip():
            data["notes"].append({
                "text": note.strip(),
                "added_at": now,
            })

        data["updated_at"] = now
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        return json.dumps({
            "success": True,
            "message": f"Feature request {feature_id} updated.",
            "feature": data,
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Failed to update feature: {e}"
        })


def delete_feature_request(feature_id: str) -> str:
    """Delete a feature request.

    Args:
        feature_id: The feature request ID.

    Returns:
        JSON string with result.
    """
    path = _get_feature_path(feature_id)
    if not path.exists():
        return json.dumps({
            "success": False,
            "error": f"Feature request not found: {feature_id}"
        })

    try:
        path.unlink()
        return json.dumps({
            "success": True,
            "message": f"Feature request {feature_id} deleted.",
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Failed to delete feature: {e}"
        })


# Register tools
registry.register(
    name="feature_submit",
    toolset="productivity",
    schema={
        "name": "feature_submit",
        "description": "Submit a new feature request to track ideas and improvements.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short title/summary of the feature request (required)"
                },
                "description": {
                    "type": "string",
                    "description": "Detailed description of the feature (optional)"
                },
                "priority": {
                    "type": "string",
                    "description": "Priority: low, medium, high, critical (default: medium)"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags/categories for the feature (optional)"
                },
                "related_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Related file paths (optional)"
                },
            },
            "required": ["title"],
        },
    },
    handler=lambda args, **kw: submit_feature_request(
        title=args.get("title", ""),
        description=args.get("description", ""),
        priority=args.get("priority", "medium"),
        tags=args.get("tags"),
        related_files=args.get("related_files"),
    ),
)

registry.register(
    name="feature_list",
    toolset="productivity",
    schema={
        "name": "feature_list",
        "description": "List feature requests with optional filtering by status, priority, or tag.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by status: pending, approved, in-progress, completed, rejected"
                },
                "priority": {
                    "type": "string",
                    "description": "Filter by priority: low, medium, high, critical"
                },
                "tag": {
                    "type": "string",
                    "description": "Filter by tag"
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default: 50)"
                },
            },
        },
    },
    handler=lambda args, **kw: list_feature_requests(
        status=args.get("status", ""),
        priority=args.get("priority", ""),
        tag=args.get("tag", ""),
        limit=args.get("limit", 50),
    ),
)

registry.register(
    name="feature_get",
    toolset="productivity",
    schema={
        "name": "feature_get",
        "description": "Get details of a specific feature request by ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "feature_id": {
                    "type": "string",
                    "description": "Feature request ID"
                },
            },
            "required": ["feature_id"],
        },
    },
    handler=lambda args, **kw: get_feature_request(
        feature_id=args.get("feature_id", ""),
    ),
)

registry.register(
    name="feature_update",
    toolset="productivity",
    schema={
        "name": "feature_update",
        "description": "Update a feature request's status, priority, or add a note.",
        "parameters": {
            "type": "object",
            "properties": {
                "feature_id": {
                    "type": "string",
                    "description": "Feature request ID"
                },
                "status": {
                    "type": "string",
                    "description": "New status: pending, approved, in-progress, completed, rejected"
                },
                "priority": {
                    "type": "string",
                    "description": "New priority: low, medium, high, critical"
                },
                "note": {
                    "type": "string",
                    "description": "Note to append"
                },
            },
            "required": ["feature_id"],
        },
    },
    handler=lambda args, **kw: update_feature_request(
        feature_id=args.get("feature_id", ""),
        status=args.get("status", ""),
        priority=args.get("priority", ""),
        note=args.get("note", ""),
    ),
)

registry.register(
    name="feature_delete",
    toolset="productivity",
    schema={
        "name": "feature_delete",
        "description": "Delete a feature request by ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "feature_id": {
                    "type": "string",
                    "description": "Feature request ID"
                },
            },
            "required": ["feature_id"],
        },
    },
    handler=lambda args, **kw: delete_feature_request(
        feature_id=args.get("feature_id", ""),
    ),
)
