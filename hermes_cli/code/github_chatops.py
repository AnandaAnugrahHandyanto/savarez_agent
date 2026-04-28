#!/usr/bin/env python3
"""ChatOps parsing and orchestration bridge for GitHub events."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from hermes_cli.code.agent_orchestrator import AgentOrchestrator, OrchestratorState
from hermes_cli.code.artifact_ledger import ArtifactLedger
from hermes_cli.code.github_integration import GitHubIntegrationDB

SUPPORTED_COMMANDS = frozenset({"plan", "review", "fix", "explain", "status"})
_COMMAND_RE = re.compile(
    r"(?im)^\s*@hermes(?:\s+|:)(plan|review|fix|explain|status)\b[ \t]*(.*)$"
)


@dataclass(frozen=True)
class ChatOpsCommand:
    command: str
    args: str = ""


def parse_chatops_commands(text: str) -> List[ChatOpsCommand]:
    """Extract supported `@hermes` commands from comment text."""
    if not text:
        return []
    commands: List[ChatOpsCommand] = []
    for match in _COMMAND_RE.finditer(text):
        command = match.group(1).lower()
        if command in SUPPORTED_COMMANDS:
            commands.append(ChatOpsCommand(command=command, args=match.group(2).strip()))
    return commands


def _task_title(command: Dict[str, Any]) -> str:
    subject = command.get("repo_full_name") or "GitHub"
    number = command.get("pr_number") or command.get("issue_number")
    suffix = f" #{number}" if number else ""
    return f"GitHub @{command.get('command')} request: {subject}{suffix}"


def _task_description(command: Dict[str, Any]) -> str:
    args = command.get("args") or ""
    lines = [
        f"GitHub ChatOps command: @hermes {command.get('command')}",
        f"Repository: {command.get('repo_full_name')}",
        f"Sender: {command.get('sender_login') or 'unknown'}",
    ]
    if command.get("issue_number"):
        lines.append(f"Issue: #{command.get('issue_number')}")
    if command.get("pr_number"):
        lines.append(f"Pull request: #{command.get('pr_number')}")
    if command.get("comment_id"):
        lines.append(f"Comment: {command.get('comment_id')}")
    if args:
        lines.extend(["", args])
    return "\n".join(lines)


class GitHubChatOpsService:
    """Create Hermes Code Mode artifacts and orchestrated runs from ChatOps."""

    def __init__(self, db_path: Optional[Path] = None, realtime_hub=None) -> None:
        self._db_path = db_path
        self._realtime_hub = realtime_hub

    def _db(self) -> GitHubIntegrationDB:
        return GitHubIntegrationDB(db_path=self._db_path)

    def create_commands_from_comment(
        self,
        *,
        delivery_id: Optional[str],
        repo_full_name: str,
        issue_number: Optional[int],
        pr_number: Optional[int],
        comment_id: Optional[int],
        sender_login: Optional[str],
        body: str,
    ) -> List[Dict[str, Any]]:
        parsed = parse_chatops_commands(body)
        if not parsed:
            return []
        db = self._db()
        try:
            return [
                db.create_chatops_command(
                    delivery_id=delivery_id,
                    repo_full_name=repo_full_name,
                    issue_number=issue_number,
                    pr_number=pr_number,
                    comment_id=comment_id,
                    sender_login=sender_login,
                    command=item.command,
                    args=item.args,
                )
                for item in parsed
            ]
        finally:
            db.close()

    def _workspace_for_repo(self, repo_full_name: str) -> tuple[Optional[str], Optional[dict]]:
        try:
            from hermes_state import WorkspaceDB

            wdb = WorkspaceDB(db_path=self._db_path)
            try:
                for workspace in wdb.list_workspaces(limit=500):
                    repo_url = str(workspace.get("repo_url") or "")
                    normalized = repo_url.removesuffix(".git")
                    if normalized.endswith(f"github.com/{repo_full_name}") or normalized.endswith(f":{repo_full_name}"):
                        return workspace.get("id"), workspace
            finally:
                wdb.close()
        except Exception:
            pass
        return None, None

    def _repo_guidance(self, workspace: Optional[dict]) -> Optional[dict]:
        if not workspace:
            return None
        try:
            from hermes_cli.code.repo_knowledge import RepoKnowledgeService

            path = Path(workspace["path"])
            return RepoKnowledgeService().detect(path)
        except Exception:
            return None

    def run_command(self, command_id: str) -> Dict[str, Any]:
        db = self._db()
        try:
            command = db.get_chatops_command(command_id)
        finally:
            db.close()
        if not command:
            raise ValueError(f"GitHub ChatOps command not found: {command_id}")
        if command.get("orchestrated_run_id"):
            run = AgentOrchestrator(db_path=self._db_path).get_run(command["orchestrated_run_id"])
            return {"command": command, "run": run, "resumed": True}

        workspace_id, workspace = self._workspace_for_repo(command["repo_full_name"])
        guidance = self._repo_guidance(workspace)
        title = _task_title(command)
        description = _task_description(command)
        metadata = {
            "source": "github_chatops",
            "github": {
                "repo_full_name": command.get("repo_full_name"),
                "issue_number": command.get("issue_number"),
                "pr_number": command.get("pr_number"),
                "comment_id": command.get("comment_id"),
                "sender_login": command.get("sender_login"),
                "command": command.get("command"),
                "args": command.get("args"),
            },
            "repo_guidance": guidance,
        }

        orch = AgentOrchestrator(db_path=self._db_path, realtime_hub=self._realtime_hub)
        run = orch.create_run(
            workspace_id=workspace_id,
            title=title,
            task_description=description,
            metadata=metadata,
            auto_create_intake_artifact=True,
        )

        command_name = str(command.get("command") or "")
        if command_name == "plan":
            orch.attach_artifact(
                run["id"],
                "implementation_plan",
                content=f"Planning requested from GitHub.\n\n{description}",
                title="GitHub Planning Request",
            )
        elif command_name == "review":
            orch.attach_artifact(
                run["id"],
                "review_report",
                content=f"Review requested from GitHub.\n\n{description}",
                title="GitHub Review Request",
            )
        elif command_name == "fix":
            run = orch.transition(run["id"], OrchestratorState.DISCOVERY, message="GitHub fix request intake")
            run = orch.transition(run["id"], OrchestratorState.PLANNING, message="Plan fix before implementation")
            run = orch.transition(
                run["id"],
                OrchestratorState.APPROVAL,
                message="Fix request requires approval before implementation",
                payload={"source": "github_chatops"},
            )
        elif command_name == "explain":
            orch.attach_artifact(
                run["id"],
                "architecture_note",
                content=f"Explanation requested from GitHub.\n\n{description}",
                title="GitHub Explanation Request",
            )

        db = self._db()
        try:
            updated = db.update_chatops_command(
                command_id,
                status="run_created",
                orchestrated_run_id=run["id"],
                code_session_id=run.get("code_session_id"),
            )
        finally:
            db.close()
        return {"command": updated, "run": run, "resumed": False}
