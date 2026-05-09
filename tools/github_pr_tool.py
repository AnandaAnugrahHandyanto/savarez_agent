"""GitHub PR creation tool for Hermes Agent.

Provides tools to create GitHub pull requests from within the agent.
Requires the `gh` CLI to be installed and authenticated.
"""

import json
import logging
import os
import re
import subprocess
from typing import Optional

from tools.registry import registry

logger = logging.getLogger(__name__)


def _check_gh_cli() -> bool:
    """Check if the GitHub CLI (gh) is installed and authenticated."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _run_gh_command(args: list, cwd: Optional[str] = None, timeout: int = 60) -> tuple:
    """Run a gh CLI command and return (success, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )
        return (result.returncode == 0, result.stdout.strip(), result.stderr.strip())
    except subprocess.TimeoutExpired:
        return (False, "", "Command timed out")
    except Exception as e:
        return (False, "", str(e))


def _get_repo_info(cwd: Optional[str] = None) -> dict:
    """Get current repository information."""
    success, stdout, stderr = _run_gh_command(
        ["repo", "view", "--json", "url,owner,name,defaultBranch"],
        cwd=cwd,
    )
    if success:
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            pass
    return {}


def create_pull_request(
    title: str,
    body: str = "",
    base: str = "",
    head: str = "",
    draft: bool = False,
    cwd: Optional[str] = None,
) -> str:
    """Create a GitHub pull request.

    Args:
        title: PR title (required).
        body: PR description/body (optional).
        base: Base branch to merge into (default: repo default branch).
        head: Head branch (default: current branch).
        draft: Create as draft PR.
        cwd: Working directory (default: current directory).

    Returns:
        JSON string with result.
    """
    if not _check_gh_cli():
        return json.dumps({
            "success": False,
            "error": "GitHub CLI (gh) is not installed or not authenticated. Run 'gh auth login' first."
        })

    if not title.strip():
        return json.dumps({
            "success": False,
            "error": "PR title is required."
        })

    args = ["pr", "create", "--title", title.strip()]

    if body.strip():
        args.extend(["--body", body.strip()])
    else:
        args.append("--fill")  # Use commit messages as body

    if base.strip():
        args.extend(["--base", base.strip()])

    if head.strip():
        args.extend(["--head", head.strip()])

    if draft:
        args.append("--draft")

    success, stdout, stderr = _run_gh_command(args, cwd=cwd, timeout=120)

    if success:
        # Extract PR URL from output
        pr_url = stdout.strip()
        return json.dumps({
            "success": True,
            "pr_url": pr_url,
            "message": f"Pull request created successfully: {pr_url}"
        })
    else:
        return json.dumps({
            "success": False,
            "error": stderr or stdout or "Unknown error creating PR"
        })


def list_pull_requests(
    state: str = "open",
    limit: int = 10,
    cwd: Optional[str] = None,
) -> str:
    """List GitHub pull requests for the current repository.

    Args:
        state: PR state filter (open, closed, merged, all). Default: open.
        limit: Maximum number of PRs to return. Default: 10.
        cwd: Working directory (default: current directory).

    Returns:
        JSON string with list of PRs.
    """
    if not _check_gh_cli():
        return json.dumps({
            "success": False,
            "error": "GitHub CLI (gh) is not installed or not authenticated."
        })

    args = [
        "pr", "list",
        "--state", state,
        "--limit", str(limit),
        "--json", "number,title,author,state,url,createdAt,headRefName,baseRefName"
    ]

    success, stdout, stderr = _run_gh_command(args, cwd=cwd, timeout=60)

    if success:
        try:
            prs = json.loads(stdout)
            return json.dumps({
                "success": True,
                "pull_requests": prs,
                "count": len(prs),
            })
        except json.JSONDecodeError:
            return json.dumps({
                "success": False,
                "error": "Failed to parse PR list response."
            })
    else:
        return json.dumps({
            "success": False,
            "error": stderr or stdout or "Unknown error listing PRs"
        })


def view_pull_request(
    number: int,
    cwd: Optional[str] = None,
) -> str:
    """View details of a specific GitHub pull request.

    Args:
        number: PR number.
        cwd: Working directory (default: current directory).

    Returns:
        JSON string with PR details.
    """
    if not _check_gh_cli():
        return json.dumps({
            "success": False,
            "error": "GitHub CLI (gh) is not installed or not authenticated."
        })

    args = [
        "pr", "view", str(number),
        "--json", "number,title,body,author,state,url,createdAt,headRefName,baseRefName,mergeStateStatus,commits"
    ]

    success, stdout, stderr = _run_gh_command(args, cwd=cwd, timeout=60)

    if success:
        try:
            pr = json.loads(stdout)
            return json.dumps({
                "success": True,
                "pull_request": pr,
            })
        except json.JSONDecodeError:
            return json.dumps({
                "success": False,
                "error": "Failed to parse PR details response."
            })
    else:
        return json.dumps({
            "success": False,
            "error": stderr or stdout or f"Unknown error viewing PR #{number}"
        })


def create_branch_and_commit(
    branch_name: str,
    commit_message: str,
    cwd: Optional[str] = None,
) -> str:
    """Create a new branch, commit all changes, and push to origin.

    Args:
        branch_name: Name of the new branch.
        commit_message: Commit message.
        cwd: Working directory (default: current directory).

    Returns:
        JSON string with result.
    """
    if not _check_gh_cli():
        return json.dumps({
            "success": False,
            "error": "GitHub CLI (gh) is not installed or not authenticated."
        })

    # Check if we're in a git repo
    git_check = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=10,
    )
    if git_check.returncode != 0:
        return json.dumps({
            "success": False,
            "error": "Not in a git repository."
        })

    # Create branch
    branch_result = subprocess.run(
        ["git", "checkout", "-b", branch_name],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=10,
    )
    if branch_result.returncode != 0:
        return json.dumps({
            "success": False,
            "error": f"Failed to create branch: {branch_result.stderr}"
        })

    # Stage all changes
    add_result = subprocess.run(
        ["git", "add", "-A"],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=10,
    )
    if add_result.returncode != 0:
        return json.dumps({
            "success": False,
            "error": f"Failed to stage changes: {add_result.stderr}"
        })

    # Check if there are changes to commit
    diff_result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=10,
    )
    if diff_result.returncode == 0:
        # No changes
        return json.dumps({
            "success": False,
            "error": "No changes to commit. Make some edits first."
        })

    # Commit
    commit_result = subprocess.run(
        ["git", "commit", "-m", commit_message],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=10,
    )
    if commit_result.returncode != 0:
        return json.dumps({
            "success": False,
            "error": f"Failed to commit: {commit_result.stderr}"
        })

    # Push
    push_result = subprocess.run(
        ["git", "push", "-u", "origin", branch_name],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=60,
    )
    if push_result.returncode != 0:
        return json.dumps({
            "success": False,
            "error": f"Failed to push: {push_result.stderr}"
        })

    return json.dumps({
        "success": True,
        "message": f"Branch '{branch_name}' created, committed, and pushed to origin.",
        "branch": branch_name,
    })


# Register tools
registry.register(
    name="github_create_pr",
    toolset="github",
    schema={
        "name": "github_create_pr",
        "description": "Create a GitHub pull request for the current repository. Requires gh CLI to be installed and authenticated.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Title of the pull request (required)"
                },
                "body": {
                    "type": "string",
                    "description": "Body/description of the pull request (optional)"
                },
                "base": {
                    "type": "string",
                    "description": "Base branch to merge into (default: repo default branch)"
                },
                "head": {
                    "type": "string",
                    "description": "Head branch (default: current branch)"
                },
                "draft": {
                    "type": "boolean",
                    "description": "Create as draft PR (default: false)"
                },
            },
            "required": ["title"],
        },
    },
    handler=lambda args, **kw: create_pull_request(
        title=args.get("title", ""),
        body=args.get("body", ""),
        base=args.get("base", ""),
        head=args.get("head", ""),
        draft=args.get("draft", False),
        cwd=args.get("cwd", None),
    ),
    check_fn=_check_gh_cli,
)

registry.register(
    name="github_list_prs",
    toolset="github",
    schema={
        "name": "github_list_prs",
        "description": "List GitHub pull requests for the current repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "description": "PR state filter: open, closed, merged, all (default: open)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of PRs to return (default: 10)"
                },
            },
        },
    },
    handler=lambda args, **kw: list_pull_requests(
        state=args.get("state", "open"),
        limit=args.get("limit", 10),
        cwd=args.get("cwd", None),
    ),
    check_fn=_check_gh_cli,
)

registry.register(
    name="github_view_pr",
    toolset="github",
    schema={
        "name": "github_view_pr",
        "description": "View details of a specific GitHub pull request.",
        "parameters": {
            "type": "object",
            "properties": {
                "number": {
                    "type": "integer",
                    "description": "PR number"
                },
            },
            "required": ["number"],
        },
    },
    handler=lambda args, **kw: view_pull_request(
        number=args.get("number", 0),
        cwd=args.get("cwd", None),
    ),
    check_fn=_check_gh_cli,
)

registry.register(
    name="github_branch_and_commit",
    toolset="github",
    schema={
        "name": "github_branch_and_commit",
        "description": "Create a new git branch, commit all current changes, and push to origin. Useful before creating a PR.",
        "parameters": {
            "type": "object",
            "properties": {
                "branch_name": {
                    "type": "string",
                    "description": "Name for the new branch (required)"
                },
                "commit_message": {
                    "type": "string",
                    "description": "Commit message (required)"
                },
            },
            "required": ["branch_name", "commit_message"],
        },
    },
    handler=lambda args, **kw: create_branch_and_commit(
        branch_name=args.get("branch_name", ""),
        commit_message=args.get("commit_message", ""),
        cwd=args.get("cwd", None),
    ),
    check_fn=_check_gh_cli,
)
