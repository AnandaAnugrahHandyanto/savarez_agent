"""GitLab CI/CD Pipeline tools for the gitlab-review plugin.

Registers 1 pipeline-related tool:

- gitlab_mr_pipelines  — Check CI/CD pipeline status for an MR
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from plugins.gitlab_review.gitlab_client import (
    GitLabAPIError,
    gitlab_get_paginated,
    is_available,
    project_path,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool: gitlab_mr_pipelines
# ---------------------------------------------------------------------------

GITLAB_MR_PIPELINES_SCHEMA = {
    "name": "gitlab_mr_pipelines",
    "description": (
        "Check CI/CD pipeline status for a GitLab Merge Request's latest "
        "commit. Returns pipeline IDs, status, and ref for each pipeline "
        "associated with the MR."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "project": {
                "type": "string",
                "description": "Project path (e.g. 'group/project') or numeric project ID.",
            },
            "mr_iid": {
                "type": "integer",
                "description": "The MR internal ID (iid).",
            },
        },
        "required": ["project", "mr_iid"],
    },
}


def _handle_mr_pipelines(args: dict, **kw) -> str:
    """Fetch pipeline status for an MR."""
    project = args.get("project", "")
    mr_iid = args.get("mr_iid")
    if not project or mr_iid is None:
        return _error("Missing required parameters: project and mr_iid")

    try:
        path = f"{project_path(project)}/merge_requests/{mr_iid}/pipelines"
        items = gitlab_get_paginated(path, max_pages=3)

        pipelines = []
        for p in items:
            pipelines.append({
                "id": p.get("id"),
                "sha": p.get("sha"),
                "ref": p.get("ref"),
                "status": p.get("status"),
                "source": p.get("source"),
                "created_at": p.get("created_at"),
                "updated_at": p.get("updated_at"),
                "web_url": p.get("web_url"),
            })

        return json.dumps({"result": {"count": len(pipelines), "pipelines": pipelines}})
    except GitLabAPIError as e:
        return _error(f"Failed to fetch pipelines: {e}")
    except Exception as e:
        logger.error("gitlab_mr_pipelines error: %s", e)
        return _error(f"Unexpected error: {e}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error(msg: str) -> str:
    """Return a JSON error result."""
    return json.dumps({"error": msg})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

ALL_PIPELINE_SCHEMAS = [
    (GITLAB_MR_PIPELINES_SCHEMA, _handle_mr_pipelines, "🔄"),
]


def register_pipeline_tools(ctx) -> None:
    """Register all pipeline-related tools with the plugin context."""
    for schema, handler, emoji in ALL_PIPELINE_SCHEMAS:
        ctx.register_tool(
            name=schema["name"],
            toolset="gitlab_review",
            schema=schema,
            handler=handler,
            check_fn=is_available,
            requires_env=["GITLAB_TOKEN"],
            emoji=emoji,
        )
