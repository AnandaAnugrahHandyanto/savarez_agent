"""GitLab MR context tools for the gitlab-review plugin.

Registers 1 context-related tool:

- gitlab_mr_discussions — List existing discussions/comments on an MR
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from plugins.gitlab_review.gitlab_client import (
    GitLabAPIError,
    gitlab_get,
    gitlab_get_paginated,
    is_available,
    project_path,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool: gitlab_mr_discussions
# ---------------------------------------------------------------------------

GITLAB_MR_DISCUSSIONS_SCHEMA = {
    "name": "gitlab_mr_discussions",
    "description": (
        "List existing discussions (comment threads) on a GitLab Merge "
        "Request. Use this before reviewing to avoid duplicating feedback "
        "that was already provided."
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


def _handle_mr_discussions(args: dict, **kw) -> str:
    """List discussions on an MR."""
    project = args.get("project", "")
    mr_iid = args.get("mr_iid")
    if not project or mr_iid is None:
        return _error("Missing required parameters: project and mr_iid")

    try:
        path = f"{project_path(project)}/merge_requests/{mr_iid}/discussions"
        items = gitlab_get_paginated(path, max_pages=5)

        discussions = []
        for d in items:
            notes = d.get("notes", [])
            discussion_entry = {
                "id": d.get("id"),
                "noteable_type": d.get("noteable_type"),
                "notes": [
                    {
                        "id": n.get("id"),
                        "type": n.get("type"),
                        "body": n.get("body", ""),
                        "author": n.get("author", {}).get("username", ""),
                        "created_at": n.get("created_at"),
                        "resolvable": n.get("resolvable", False),
                        "resolved": n.get("resolved", False),
                    }
                    for n in notes
                ],
            }
            # Include position info for inline comments
            for n in notes:
                if n.get("position"):
                    discussion_entry["position"] = {
                        "new_path": n["position"].get("new_path"),
                        "new_line": n["position"].get("new_line"),
                        "old_path": n["position"].get("old_path"),
                        "old_line": n["position"].get("old_line"),
                    }
                    break

            discussions.append(discussion_entry)

        return json.dumps({
            "result": {
                "count": len(discussions),
                "discussions": discussions,
            },
        })
    except GitLabAPIError as e:
        return _error(f"Failed to fetch discussions: {e}")
    except Exception as e:
        logger.error("gitlab_mr_discussions error: %s", e)
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

ALL_CONTEXT_SCHEMAS = [
    (GITLAB_MR_DISCUSSIONS_SCHEMA, _handle_mr_discussions, "💭"),
]


def register_context_tools(ctx) -> None:
    """Register all context-related tools with the plugin context."""
    for schema, handler, emoji in ALL_CONTEXT_SCHEMAS:
        ctx.register_tool(
            name=schema["name"],
            toolset="gitlab_review",
            schema=schema,
            handler=handler,
            check_fn=is_available,
            requires_env=["GITLAB_TOKEN"],
            emoji=emoji,
        )
