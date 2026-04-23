"""GitLab Merge Request tools for the gitlab-review plugin.

Registers 5 MR-related tools:

- gitlab_mr_view         — Fetch MR metadata, diff, and file list (merged)
- gitlab_mr_comment      — Post a general or inline comment (buffers when review session active)
- gitlab_mr_review_start — Start a buffered review session for an MR
- gitlab_mr_review_submit— Submit the buffered review (summary first, then inline comments)
- gitlab_mr_list         — List open MRs with optional filters
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from plugins.gitlab_review.gitlab_client import (
    GitLabAPIError,
    gitlab_delete,
    gitlab_get,
    gitlab_get_paginated,
    gitlab_post,
    is_available,
    project_path,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Review session buffer
# ---------------------------------------------------------------------------


@dataclass
class ReviewSession:
    """Holds buffered comments for a single MR review."""

    project: str
    mr_iid: int
    head_sha: str
    base_sha: str
    start_sha: str
    notes: List[Dict[str, Any]] = field(default_factory=list)


# Module-level review session. None = no active session.
_review_session: Optional[ReviewSession] = None


def _start_review(project: str, mr_iid: int) -> ReviewSession:
    """Initialize a new review session, fetching diff_refs from the MR."""
    global _review_session

    # Warn if previous session had unflushed comments
    if _review_session is not None and _review_session.notes:
        logger.warning(
            "Starting new review session for %s/%s but previous session "
            "had %d unflushed comments — discarding them.",
            _review_session.project,
            _review_session.mr_iid,
            len(_review_session.notes),
        )

    # Fetch MR metadata to get diff_refs
    mr_path = f"{project_path(project)}/merge_requests/{mr_iid}"
    mr_data = gitlab_get(mr_path)
    diff_refs = mr_data.get("diff_refs", {})

    head_sha = diff_refs.get("head_sha", "")
    base_sha = diff_refs.get("base_sha", "")
    start_sha = diff_refs.get("start_sha", "")

    if not head_sha:
        raise GitLabAPIError(
            "Cannot start review: MR has no head_sha in diff_refs. "
            "The MR may be merged or have no commits."
        )

    _review_session = ReviewSession(
        project=project,
        mr_iid=mr_iid,
        head_sha=head_sha,
        base_sha=base_sha,
        start_sha=start_sha,
    )
    return _review_session


def _buffer_note(note: Dict[str, Any]) -> int:
    """Add a note to the current review session buffer. Returns total buffered count."""
    global _review_session
    if _review_session is None:
        raise RuntimeError("No active review session — call gitlab_mr_review_start first")
    _review_session.notes.append(note)
    return len(_review_session.notes)


def _clear_review() -> None:
    """Clear the review session buffer."""
    global _review_session
    _review_session = None


def _flush_warning() -> Optional[str]:
    """Return a warning message if there are unflushed buffered comments, else None."""
    if _review_session is not None and _review_session.notes:
        return (
            f"GitLab review session has {len(_review_session.notes)} unflushed "
            f"comments for {_review_session.project}/!{_review_session.mr_iid}. "
            f"Call gitlab_mr_review_submit to post them."
        )
    return None


# ---------------------------------------------------------------------------
# Tool: gitlab_mr_view (merged view + diff + list_files)
# ---------------------------------------------------------------------------

GITLAB_MR_VIEW_SCHEMA = {
    "name": "gitlab_mr_view",
    "description": (
        "Fetch a GitLab Merge Request: metadata (title, author, branches, "
        "labels, state) plus the full diff and file list. Set include_diff=false "
        "to get only metadata without the diff (lighter response for large MRs). "
        "Requires GITLAB_TOKEN env var."
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
                "description": "The MR internal ID (iid, not global id).",
            },
            "include_diff": {
                "type": "boolean",
                "description": "Include the full diff and file list (default: true). Set false for metadata-only.",
            },
        },
        "required": ["project", "mr_iid"],
    },
}


def _handle_mr_view(args: dict, **kw) -> str:
    """Fetch MR metadata and optionally the full diff + file list."""
    project = args.get("project", "")
    mr_iid = args.get("mr_iid")
    include_diff = args.get("include_diff", True)

    if not project or mr_iid is None:
        return _error("Missing required parameters: project and mr_iid")

    try:
        if include_diff:
            # Use /changes endpoint which returns both metadata and diffs
            path = f"{project_path(project)}/merge_requests/{mr_iid}/changes"
            data = gitlab_get(path)
            result = {
                "iid": data.get("iid"),
                "title": data.get("title"),
                "description": data.get("description", ""),
                "state": data.get("state"),
                "author": data.get("author", {}).get("username", ""),
                "source_branch": data.get("source_branch"),
                "target_branch": data.get("target_branch"),
                "labels": data.get("labels", []),
                "milestone": (data.get("milestone") or {}).get("title"),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
                "merged_at": data.get("merged_at"),
                "web_url": data.get("web_url"),
                "draft": data.get("draft", False),
                "merge_status": data.get("merge_status"),
                "detailed_merge_status": data.get("detailed_merge_status"),
                "user_notes_count": data.get("user_notes_count"),
                "diff_refs": data.get("diff_refs"),
            }
            # Build file list and diffs from changes
            changes = data.get("changes", [])
            files = []
            diffs = []
            for change in changes:
                files.append({
                    "old_path": change.get("old_path"),
                    "new_path": change.get("new_path"),
                    "new_file": change.get("new_file", False),
                    "renamed_file": change.get("renamed_file", False),
                    "deleted_file": change.get("deleted_file", False),
                })
                diffs.append({
                    "old_path": change.get("old_path"),
                    "new_path": change.get("new_path"),
                    "diff": change.get("diff", ""),
                })
            result["files"] = files
            result["diffs"] = diffs
            result["total_changes"] = len(files)
            return json.dumps({"result": result})
        else:
            # Metadata only — use the basic MR endpoint
            path = f"{project_path(project)}/merge_requests/{mr_iid}"
            data = gitlab_get(path)
            result = {
                "iid": data.get("iid"),
                "title": data.get("title"),
                "description": data.get("description", ""),
                "state": data.get("state"),
                "author": data.get("author", {}).get("username", ""),
                "source_branch": data.get("source_branch"),
                "target_branch": data.get("target_branch"),
                "labels": data.get("labels", []),
                "milestone": (data.get("milestone") or {}).get("title"),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
                "merged_at": data.get("merged_at"),
                "web_url": data.get("web_url"),
                "draft": data.get("draft", False),
                "merge_status": data.get("merge_status"),
                "detailed_merge_status": data.get("detailed_merge_status"),
                "user_notes_count": data.get("user_notes_count"),
                "diff_refs": data.get("diff_refs"),
            }
            return json.dumps({"result": result})
    except GitLabAPIError as e:
        return _error(f"Failed to fetch MR: {e}")
    except Exception as e:
        logger.error("gitlab_mr_view error: %s", e)
        return _error(f"Unexpected error: {e}")


# ---------------------------------------------------------------------------
# Tool: gitlab_mr_review_start
# ---------------------------------------------------------------------------

GITLAB_MR_REVIEW_START_SCHEMA = {
    "name": "gitlab_mr_review_start",
    "description": (
        "Start a buffered review session for a GitLab Merge Request. "
        "After calling this, gitlab_mr_comment will BUFFER comments instead "
        "of posting them immediately. When you're done, call "
        "gitlab_mr_review_submit to post ALL comments at once. "
        "This ensures the reviewer sees your complete review in one shot. "
        "Call this BEFORE posting any review comments."
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


def _handle_mr_review_start(args: dict, **kw) -> str:
    """Start a buffered review session."""
    project = args.get("project", "")
    mr_iid = args.get("mr_iid")
    if not project or mr_iid is None:
        return _error("Missing required parameters: project and mr_iid")

    try:
        session = _start_review(project, mr_iid)
        return json.dumps({
            "result": {
                "status": "review_session_started",
                "project": project,
                "mr_iid": mr_iid,
                "head_sha": session.head_sha,
                "base_sha": session.base_sha,
                "start_sha": session.start_sha,
                "message": (
                    "Review session active. Comments will be buffered. "
                    "Call gitlab_mr_review_submit when done to post all comments at once."
                ),
            },
        })
    except GitLabAPIError as e:
        return _error(f"Failed to start review session: {e}")
    except Exception as e:
        logger.error("gitlab_mr_review_start error: %s", e)
        return _error(f"Unexpected error: {e}")


# ---------------------------------------------------------------------------
# Tool: gitlab_mr_comment (merged general + inline)
# ---------------------------------------------------------------------------

GITLAB_MR_COMMENT_SCHEMA = {
    "name": "gitlab_mr_comment",
    "description": (
        "Post a comment on a GitLab Merge Request. If file_path and line are "
        "provided, posts an inline comment on that specific line. Otherwise "
        "posts a general (top-level) comment. "
        "When a review session is active (started via gitlab_mr_review_start), "
        "comments are BUFFERED and not sent until gitlab_mr_review_submit is "
        "called. When no review session is active, comments are posted immediately."
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
            "body": {
                "type": "string",
                "description": "Comment text. Markdown is supported.",
            },
            "file_path": {
                "type": "string",
                "description": "Path of the file to comment on for inline comments (e.g. 'src/auth/login.py'). Omit for general comments.",
            },
            "line": {
                "type": "integer",
                "description": "Line number for inline comments. Line in the new version of the file by default.",
            },
            "line_type": {
                "type": "string",
                "description": "'new' (default) for added/modified lines, 'old' for deleted lines.",
                "enum": ["new", "old"],
            },
            "head_sha": {
                "type": "string",
                "description": "SHA of the head commit (required for inline comments when no review session is active). Auto-resolved during review sessions.",
            },
            "base_sha": {
                "type": "string",
                "description": "SHA of the base commit. Optional — auto-resolved during review sessions.",
            },
            "start_sha": {
                "type": "string",
                "description": "SHA of the start commit (branch point). Optional — auto-resolved during review sessions.",
            },
        },
        "required": ["project", "mr_iid", "body"],
    },
}


def _handle_mr_comment(args: dict, **kw) -> str:
    """Post a general or inline comment; buffer if review session active."""
    project = args.get("project", "")
    mr_iid = args.get("mr_iid")
    body = args.get("body", "")
    file_path = args.get("file_path", "")
    line = args.get("line")
    line_type = args.get("line_type", "new")
    head_sha = args.get("head_sha", "")
    base_sha = args.get("base_sha", "")
    start_sha = args.get("start_sha", "")

    if not project or mr_iid is None or not body:
        return _error("Missing required parameters: project, mr_iid, and body")

    is_inline = bool(file_path and line is not None)

    # --- Buffered mode (review session active) ---
    if _review_session is not None:
        # Validate that the comment targets the same MR
        if project != _review_session.project or mr_iid != _review_session.mr_iid:
            return _error(
                f"Active review session is for {_review_session.project}/!{_review_session.mr_iid}. "
                f"Cannot comment on {project}/!{mr_iid}. Submit the current review first."
            )

        if is_inline:
            # Use SHAs from the review session
            note: Dict[str, Any] = {
                "body": body,
                "position": {
                    "base_sha": base_sha or _review_session.base_sha,
                    "head_sha": head_sha or _review_session.head_sha,
                    "start_sha": start_sha or _review_session.start_sha,
                    "position_type": "text",
                    "new_path": file_path,
                    "old_path": file_path,
                },
            }
            if line_type == "new":
                note["position"]["new_line"] = line
            else:
                note["position"]["old_line"] = line
        else:
            note = {"body": body}

        count = _buffer_note(note)
        return json.dumps({
            "result": {
                "status": "buffered",
                "type": "inline" if is_inline else "general",
                "buffered_count": count,
                "message": f"Comment buffered ({count} total). Call gitlab_mr_review_submit to post all.",
            },
        })

    # --- Immediate mode (no review session) ---
    if is_inline:
        return _post_inline_comment_immediate(
            project, mr_iid, file_path, line, body,
            head_sha, base_sha, start_sha, line_type,
        )
    else:
        return _post_general_comment_immediate(project, mr_iid, body)


def _post_general_comment_immediate(project: str, mr_iid: int, body: str) -> str:
    """Post a general comment immediately (no review session)."""
    try:
        path = f"{project_path(project)}/merge_requests/{mr_iid}/notes"
        result = gitlab_post(path, json_body={"body": body})
        return json.dumps({
            "result": {
                "id": result.get("id"),
                "noteable_iid": result.get("noteable_iid"),
                "created_at": result.get("created_at"),
            },
        })
    except GitLabAPIError as e:
        return _error(f"Failed to post comment: {e}")
    except Exception as e:
        logger.error("gitlab_mr_comment (general) error: %s", e)
        return _error(f"Unexpected error: {e}")


def _post_inline_comment_immediate(
    project: str,
    mr_iid: int,
    file_path: str,
    line: int,
    body: str,
    head_sha: str,
    base_sha: str,
    start_sha: str,
    line_type: str,
) -> str:
    """Post an inline comment immediately (no review session)."""
    if not head_sha:
        return _error(
            "head_sha is required for inline comments when no review session is active. "
            "Start a review session with gitlab_mr_review_start, or provide head_sha explicitly."
        )

    # Resolve base_sha/start_sha from MR if not provided
    if not base_sha or not start_sha:
        try:
            mr_path = f"{project_path(project)}/merge_requests/{mr_iid}"
            mr_data = gitlab_get(mr_path)
            if not base_sha:
                base_sha = mr_data.get("diff_refs", {}).get("base_sha", "")
            if not start_sha:
                start_sha = mr_data.get("diff_refs", {}).get("start_sha", "")
        except GitLabAPIError:
            pass

    if not base_sha or not start_sha:
        return _error(
            "Cannot resolve base_sha/start_sha. Provide them explicitly or "
            "start a review session with gitlab_mr_review_start."
        )

    position: Dict[str, Any] = {
        "base_sha": base_sha,
        "head_sha": head_sha,
        "start_sha": start_sha,
        "position_type": "text",
        "new_path": file_path,
        "new_line": line if line_type == "new" else None,
        "old_path": file_path,
        "old_line": line if line_type == "old" else None,
    }
    # Remove None values — GitLab rejects null position fields
    position = {k: v for k, v in position.items() if v is not None}

    try:
        path = f"{project_path(project)}/merge_requests/{mr_iid}/discussions"
        result = gitlab_post(path, json_body={
            "body": body,
            "position": position,
        })
        return json.dumps({
            "result": {
                "id": result.get("id"),
                "notes": [
                    {"id": n.get("id"), "type": n.get("type")}
                    for n in result.get("notes", [])
                ],
            },
        })
    except GitLabAPIError as e:
        return _error(f"Failed to post inline comment: {e}")
    except Exception as e:
        logger.error("gitlab_mr_comment (inline) error: %s", e)
        return _error(f"Unexpected error: {e}")


# ---------------------------------------------------------------------------
# Tool: gitlab_mr_review_submit
# ---------------------------------------------------------------------------

GITLAB_MR_REVIEW_SUBMIT_SCHEMA = {
    "name": "gitlab_mr_review_submit",
    "description": (
        "Submit a buffered review on a GitLab Merge Request. Posts ALL buffered "
        "comments at once via the GitLab Reviews API. The summary (if provided) "
        "always appears at the TOP of the review, followed by inline comments — "
        "this is enforced by the tool, not the agent. "
        "Optionally approve or request changes. Clears the buffer after success. "
        "If no review session is active, performs the action (approve/request_changes) "
        "without notes."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Review summary — appears at the TOP of the review on GitLab, before all inline comments. Use this for your overall assessment.",
            },
            "action": {
                "type": "string",
                "description": "Review action: 'approve', 'request_changes', or 'comment' (default).",
                "enum": ["approve", "request_changes", "comment"],
            },
        },
        "required": [],
    },
}


def _handle_mr_review_submit(args: dict, **kw) -> str:
    """Submit a buffered review — summary first, then inline comments."""
    summary = args.get("summary", "")
    action = args.get("action", "comment")

    try:
        results: Dict[str, Any] = {"action": action}

        if _review_session is not None:
            # --- Buffered mode: submit via Reviews API ---
            project = _review_session.project
            mr_iid = _review_session.mr_iid
            notes = _review_session.notes

            review_body: Dict[str, Any] = {}
            if summary:
                review_body["body"] = summary
            if notes:
                review_body["notes"] = notes

            # If there's no summary and no notes, just do the action
            if review_body:
                review_path = f"{project_path(project)}/merge_requests/{mr_iid}/reviews"
                review_result = gitlab_post(review_path, json_body=review_body)
                results["review"] = {
                    "id": review_result.get("id"),
                    "notes_count": len(review_result.get("notes", [])),
                    "summary_posted": bool(summary),
                    "inline_comments_posted": len(notes),
                }

            # Apply approval action
            if action == "approve":
                approve_path = f"{project_path(project)}/merge_requests/{mr_iid}/approve"
                approve_result = gitlab_post(approve_path, json_body={})
                results["approval"] = {
                    "state": "approved",
                    "approved_by": approve_result.get("approved_by", []),
                }
            elif action == "request_changes":
                unapprove_path = f"{project_path(project)}/merge_requests/{mr_iid}/approvals"
                try:
                    gitlab_delete(unapprove_path)
                    results["approval"] = {"state": "unapproved"}
                except GitLabAPIError:
                    results["approval"] = {"state": "not_previously_approved"}

            # Clear the buffer
            _clear_review()
        else:
            # --- No review session: just apply the action ---
            if action == "approve":
                return _error(
                    "Cannot approve without a review session. "
                    "Start one with gitlab_mr_review_start first."
                )
            elif action == "request_changes":
                return _error(
                    "Cannot request changes without a review session. "
                    "Start one with gitlab_mr_review_start first."
                )
            # 'comment' action with no session and no notes is a no-op
            results["message"] = "No review session active and no notes to submit."

        return json.dumps({"result": results})

    except GitLabAPIError as e:
        return _error(f"Failed to submit review: {e}")
    except Exception as e:
        logger.error("gitlab_mr_review_submit error: %s", e)
        return _error(f"Unexpected error: {e}")


# ---------------------------------------------------------------------------
# Tool: gitlab_mr_list
# ---------------------------------------------------------------------------

GITLAB_MR_LIST_SCHEMA = {
    "name": "gitlab_mr_list",
    "description": (
        "List merge requests in a GitLab project with optional filters. "
        "Returns a summary of each MR: iid, title, author, state, labels."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "project": {
                "type": "string",
                "description": "Project path (e.g. 'group/project') or numeric project ID.",
            },
            "state": {
                "type": "string",
                "description": "Filter by MR state: 'opened', 'closed', 'merged', 'all'. Default: 'opened'.",
                "enum": ["opened", "closed", "merged", "all"],
            },
            "labels": {
                "type": "string",
                "description": "Comma-separated label names to filter by (e.g. 'bug,review-needed').",
            },
            "author_username": {
                "type": "string",
                "description": "Filter by author username.",
            },
            "milestone": {
                "type": "string",
                "description": "Filter by milestone title.",
            },
            "search": {
                "type": "string",
                "description": "Search MR titles and descriptions.",
            },
            "max_pages": {
                "type": "integer",
                "description": "Maximum pages to fetch (default: 3). Each page returns up to 100 MRs.",
            },
        },
        "required": ["project"],
    },
}


def _handle_mr_list(args: dict, **kw) -> str:
    """List MRs with optional filters."""
    project = args.get("project", "")
    if not project:
        return _error("Missing required parameter: project")

    params: Dict[str, Any] = {}
    if args.get("state"):
        params["state"] = args["state"]
    if args.get("labels"):
        params["labels"] = args["labels"]
    if args.get("author_username"):
        params["author_username"] = args["author_username"]
    if args.get("milestone"):
        params["milestone"] = args["milestone"]
    if args.get("search"):
        params["search"] = args["search"]

    max_pages = min(int(args.get("max_pages", 3)), 10)

    try:
        path = f"{project_path(project)}/merge_requests"
        items = gitlab_get_paginated(path, params=params, max_pages=max_pages)

        mrs = []
        for mr in items:
            mrs.append({
                "iid": mr.get("iid"),
                "title": mr.get("title"),
                "author": mr.get("author", {}).get("username", ""),
                "state": mr.get("state"),
                "labels": mr.get("labels", []),
                "draft": mr.get("draft", False),
                "web_url": mr.get("web_url"),
                "updated_at": mr.get("updated_at"),
            })

        return json.dumps({"result": {"count": len(mrs), "merge_requests": mrs}})
    except GitLabAPIError as e:
        return _error(f"Failed to list MRs: {e}")
    except Exception as e:
        logger.error("gitlab_mr_list error: %s", e)
        return _error(f"Unexpected error: {e}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error(msg: str) -> str:
    """Return a JSON error result consistent with tool_error format."""
    return json.dumps({"error": msg})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

ALL_MR_SCHEMAS = [
    (GITLAB_MR_VIEW_SCHEMA, _handle_mr_view, "🔍"),
    (GITLAB_MR_REVIEW_START_SCHEMA, _handle_mr_review_start, "🎬"),
    (GITLAB_MR_COMMENT_SCHEMA, _handle_mr_comment, "💬"),
    (GITLAB_MR_REVIEW_SUBMIT_SCHEMA, _handle_mr_review_submit, "✅"),
    (GITLAB_MR_LIST_SCHEMA, _handle_mr_list, "📋"),
]


def register_mr_tools(ctx) -> None:
    """Register all MR-related tools with the plugin context."""
    for schema, handler, emoji in ALL_MR_SCHEMAS:
        ctx.register_tool(
            name=schema["name"],
            toolset="gitlab_review",
            schema=schema,
            handler=handler,
            check_fn=is_available,
            requires_env=["GITLAB_TOKEN"],
            emoji=emoji,
        )
