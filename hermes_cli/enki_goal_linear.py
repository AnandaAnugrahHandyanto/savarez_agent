"""Enki-specific Linear/task mapping for Hermes persistent /goal.

This module is intentionally fail-soft. Upstream Hermes goal state remains
canonical for the runtime loop; this layer mirrors/attaches goals to Enki's
local operational DB and Linear when those dependencies are available.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Protocol


ENKI_PROJECT_NAME = "Hermes / Enki Operations"
ENKI_PROJECT_DESCRIPTION = (
    "Operational work for Enki, Hermes config, slash commands, DB, backups, "
    "and Linear sync. Active repo: https://github.com/arnokha/hermes"
)
LINEAR_GRAPHQL_URL = "https://api.linear.app/graphql"


@dataclass(frozen=True)
class LinearIssue:
    issue_id: str
    identifier: str
    title: str
    url: str


@dataclass(frozen=True)
class GoalLinearLink:
    session_id: str
    goal: str
    goal_fingerprint: str
    task_id: str | None = None
    linear_issue_id: str | None = None
    linear_identifier: str | None = None
    linear_url: str | None = None
    source: str = "created"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GoalLinearStore(Protocol):
    def find_link_by_fingerprint(self, fingerprint: str) -> GoalLinearLink | None: ...

    def find_task_by_goal_fingerprint(self, fingerprint: str) -> dict[str, Any] | None: ...

    def create_task_for_goal(
        self,
        *,
        goal: str,
        fingerprint: str,
        issue: LinearIssue | None = None,
    ) -> dict[str, Any]: ...

    def upsert_goal_link(self, link: GoalLinearLink) -> GoalLinearLink: ...


class GoalLinearClient(Protocol):
    def find_issue_for_goal(self, goal: str, fingerprint: str) -> LinearIssue | None: ...

    def create_issue_for_goal(self, goal: str) -> LinearIssue: ...


_WHITESPACE_RE = re.compile(r"\s+")
_TRUE_MARKERS = {"enki-goal", "standing-goal", "run-as-goal", "goal"}
_SIZE_MARKERS = {"large", "xl", "xlarge", "epic"}


def normalize_goal_text(goal: str) -> str:
    return _WHITESPACE_RE.sub(" ", (goal or "").strip().lower())


def goal_fingerprint(goal: str) -> str:
    normalized = normalize_goal_text(goal)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


def _labels(task: dict[str, Any]) -> set[str]:
    raw = task.get("labels") or task.get("label_names") or []
    if isinstance(raw, str):
        raw = [part.strip() for part in re.split(r"[,;]", raw) if part.strip()]
    return {str(label).strip().lower() for label in raw if str(label).strip()}


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _numeric(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def should_run_task_as_goal(task: dict[str, Any], *, min_estimate: float = 5) -> bool:
    """Return True only when a Linear/local task explicitly calls for /goal.

    The conservative default avoids silently turning vague tickets into an
    autonomous loop. Today this recognizes explicit labels/markers plus a
    synced estimate/size signal when available; it refuses Arno-action tasks.
    """
    if _truthy(task.get("requires_user_action")):
        return False

    labels = _labels(task)
    if labels & _TRUE_MARKERS:
        return True

    title = str(task.get("title") or "").lower()
    context = str(task.get("context_md") or task.get("context") or "").lower()
    if "[enki-goal]" in title or "[standing-goal]" in title:
        return True
    if "run as /goal: yes" in context or "standing goal: yes" in context:
        return True

    estimate = _numeric(task.get("linear_estimate") or task.get("estimate") or task.get("estimated_size"))
    if estimate is not None and estimate >= min_estimate:
        return True

    size = str(task.get("size") or task.get("estimated_size") or "").strip().lower()
    return size in _SIZE_MARKERS


def goal_text_from_task(task: dict[str, Any]) -> str:
    ident = str(task.get("linear_identifier") or "").strip()
    title = str(task.get("title") or "").strip()
    context = str(task.get("context_md") or task.get("context") or "").strip()
    heading = f"{ident}: {title}" if ident else title
    if context:
        return f"Work the Linear ticket {heading}.\n\nContext / acceptance criteria:\n{context}"
    return f"Work the Linear ticket {heading}." if ident else title


def ensure_goal_linear_link(
    session_id: str,
    goal: str,
    *,
    store: GoalLinearStore,
    linear: GoalLinearClient | None,
) -> GoalLinearLink:
    goal = (goal or "").strip()
    if not goal:
        raise ValueError("goal text is empty")
    fingerprint = goal_fingerprint(goal)

    existing = store.find_link_by_fingerprint(fingerprint)
    if existing is not None:
        link = GoalLinearLink(
            session_id=session_id,
            goal=goal,
            goal_fingerprint=fingerprint,
            task_id=existing.task_id,
            linear_issue_id=existing.linear_issue_id,
            linear_identifier=existing.linear_identifier,
            linear_url=existing.linear_url,
            source=existing.source or "existing-link",
        )
        return store.upsert_goal_link(link)

    task = store.find_task_by_goal_fingerprint(fingerprint)
    issue: LinearIssue | None = None
    source = "created"

    if task and task.get("linear_issue_id"):
        issue = LinearIssue(
            issue_id=str(task.get("linear_issue_id") or ""),
            identifier=str(task.get("linear_identifier") or ""),
            title=str(task.get("title") or goal),
            url=str(task.get("linear_url") or ""),
        )
        source = "existing-task"
    elif linear is not None:
        found = linear.find_issue_for_goal(goal, fingerprint)
        if found is not None:
            issue = found
            source = "existing-linear"
        else:
            issue = linear.create_issue_for_goal(goal)
            source = "created"

    if task is None:
        task = store.create_task_for_goal(goal=goal, fingerprint=fingerprint, issue=issue)

    if issue is None and task and task.get("linear_issue_id"):
        issue = LinearIssue(
            issue_id=str(task.get("linear_issue_id") or ""),
            identifier=str(task.get("linear_identifier") or ""),
            title=str(task.get("title") or goal),
            url=str(task.get("linear_url") or ""),
        )

    link = GoalLinearLink(
        session_id=session_id,
        goal=goal,
        goal_fingerprint=fingerprint,
        task_id=str(task.get("task_id") or task.get("id") or "") or None,
        linear_issue_id=issue.issue_id if issue else None,
        linear_identifier=issue.identifier if issue else None,
        linear_url=issue.url if issue else None,
        source=source,
    )
    return store.upsert_goal_link(link)


def _sql_lit(value: Any) -> str:
    if value is None:
        return "null"
    return "'" + str(value).replace("'", "''") + "'"


class PsqlGoalLinearStore:
    """Local enki_ops-backed goal/Linear mapping store."""

    def __init__(self, db_name: str | None = None):
        self.db_name = db_name or os.getenv("ENKI_DB_NAME") or os.getenv("ENKI_DB") or "enki_ops"
        self._schema_checked = False

    def _psql_json(self, sql: str) -> list[dict[str, Any]]:
        self._ensure_schema()
        cmd = [
            "psql",
            "-d",
            self.db_name,
            "-Atqc",
            "select coalesce(json_agg(t), '[]'::json) from (" + sql + ") t",
        ]
        out = subprocess.check_output(cmd, text=True)
        return json.loads(out or "[]")

    def _psql_exec(self, sql: str) -> None:
        cmd = ["psql", "-d", self.db_name, "-v", "ON_ERROR_STOP=1", "-c", sql]
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _ensure_schema(self) -> None:
        if self._schema_checked:
            return
        self._schema_checked = True
        self._psql_exec(
            """
            create table if not exists enki_goal_runs (
              id uuid primary key,
              session_id text not null,
              goal_fingerprint text not null unique,
              goal text not null,
              status text not null default 'active',
              task_id uuid,
              linear_issue_id text,
              linear_identifier text,
              linear_url text,
              source text,
              turns_used integer not null default 0,
              max_turns integer,
              last_verdict text,
              last_reason text,
              paused_reason text,
              state_json jsonb not null default '{}'::jsonb,
              created_at timestamptz not null default now(),
              modified_at timestamptz not null default now(),
              completed_at timestamptz
            );
            alter table enki_goal_runs add column if not exists turns_used integer not null default 0;
            alter table enki_goal_runs add column if not exists max_turns integer;
            alter table enki_goal_runs add column if not exists last_verdict text;
            alter table enki_goal_runs add column if not exists last_reason text;
            alter table enki_goal_runs add column if not exists paused_reason text;
            create index if not exists idx_enki_goal_runs_linear_identifier on enki_goal_runs (linear_identifier);
            create index if not exists idx_enki_goal_runs_session_id on enki_goal_runs (session_id);
            """
        )

    def find_link_by_fingerprint(self, fingerprint: str) -> GoalLinearLink | None:
        rows = self._psql_json(
            f"""
            select session_id, goal, goal_fingerprint, task_id::text, linear_issue_id,
                   linear_identifier, linear_url, coalesce(source, 'existing-link') as source
            from enki_goal_runs
            where goal_fingerprint = {_sql_lit(fingerprint)}
            order by modified_at desc
            limit 1
            """
        )
        if not rows:
            return None
        return GoalLinearLink(**rows[0])

    def find_task_by_goal_fingerprint(self, fingerprint: str) -> dict[str, Any] | None:
        rows = self._psql_json(
            f"""
            select id::text as task_id, title, linear_issue_id, linear_identifier, linear_url
            from enki_tasks
            where context_md ilike {_sql_lit('%Goal fingerprint: ' + fingerprint + '%')}
            order by created_at asc
            limit 1
            """
        )
        return rows[0] if rows else None

    def create_task_for_goal(
        self,
        *,
        goal: str,
        fingerprint: str,
        issue: LinearIssue | None = None,
    ) -> dict[str, Any]:
        task_id = str(uuid.uuid4())
        title = goal if len(goal) <= 180 else goal[:177].rstrip() + "…"
        context_lines = [
            "Created automatically for an explicit Hermes `/goal` command.",
            "",
            f"Goal fingerprint: {fingerprint}",
            "",
            "## Goal",
            goal,
        ]
        if issue is not None:
            context_lines.extend(["", "## Linear", f"- {issue.identifier}: {issue.url}"])
        context = "\n".join(context_lines).strip()
        self._psql_exec(
            f"""
            insert into enki_tasks (
              id, title, status, priority, source, workstream, project_path,
              repo_url, context_md, linear_issue_id, linear_identifier, linear_url,
              owner, requires_user_action
            ) values (
              {_sql_lit(task_id)}::uuid,
              {_sql_lit(title)},
              'pending',
              2,
              'hermes-goal',
              'Hermes / Enki Operations',
              {_sql_lit(ENKI_PROJECT_NAME)},
              'https://github.com/NousResearch/hermes-agent',
              {_sql_lit(context)},
              {_sql_lit(issue.issue_id if issue else None)},
              {_sql_lit(issue.identifier if issue else None)},
              {_sql_lit(issue.url if issue else None)},
              'enki',
              false
            );
            insert into task_events (task_id, event_type, body_md)
            values ({_sql_lit(task_id)}::uuid, 'goal_created', {_sql_lit('Created from explicit Hermes `/goal` command.')});
            """
        )
        return {
            "task_id": task_id,
            "title": title,
            "linear_issue_id": issue.issue_id if issue else None,
            "linear_identifier": issue.identifier if issue else None,
            "linear_url": issue.url if issue else None,
        }

    def upsert_goal_link(self, link: GoalLinearLink) -> GoalLinearLink:
        task_expr = f"{_sql_lit(link.task_id)}::uuid" if link.task_id else "null"
        self._psql_exec(
            f"""
            insert into enki_goal_runs (
              id, session_id, goal_fingerprint, goal, status, task_id,
              linear_issue_id, linear_identifier, linear_url, source, state_json
            ) values (
              {_sql_lit(str(uuid.uuid4()))}::uuid,
              {_sql_lit(link.session_id)},
              {_sql_lit(link.goal_fingerprint)},
              {_sql_lit(link.goal)},
              'active',
              {task_expr},
              {_sql_lit(link.linear_issue_id)},
              {_sql_lit(link.linear_identifier)},
              {_sql_lit(link.linear_url)},
              {_sql_lit(link.source)},
              {_sql_lit(json.dumps(link.to_dict(), ensure_ascii=False))}::jsonb
            )
            on conflict (goal_fingerprint) do update set
              session_id = excluded.session_id,
              goal = excluded.goal,
              status = excluded.status,
              task_id = coalesce(excluded.task_id, enki_goal_runs.task_id),
              linear_issue_id = coalesce(excluded.linear_issue_id, enki_goal_runs.linear_issue_id),
              linear_identifier = coalesce(excluded.linear_identifier, enki_goal_runs.linear_identifier),
              linear_url = coalesce(excluded.linear_url, enki_goal_runs.linear_url),
              source = excluded.source,
              state_json = excluded.state_json,
              modified_at = now();
            """
        )
        return link


class LinearGoalClient:
    def __init__(self):
        _load_env_files()
        self.api_key = os.getenv("ENKI_LINEAR_API_KEY") or os.getenv("LINEAR_API_KEY")
        if not self.api_key:
            raise RuntimeError("ENKI_LINEAR_API_KEY not configured")
        self._basics: tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any], str | None] | None = None

    def _gql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        req = urllib.request.Request(
            LINEAR_GRAPHQL_URL,
            data=json.dumps({"query": query, "variables": variables or {}}).encode(),
            headers={"Authorization": self.api_key, "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        if data.get("errors"):
            raise RuntimeError(json.dumps(data["errors"], indent=2))
        return data["data"]

    def _ensure_basics(self):
        if self._basics is not None:
            return self._basics
        viewer = self._gql("{ viewer { id email } }")["viewer"]
        teams = self._gql("{ teams { nodes { id name key } } }")["teams"]["nodes"]
        team = next((t for t in teams if t.get("key") == "ENK"), next((t for t in teams if "enki" in (t["name"] + t["key"]).lower()), teams[0]))
        users = self._gql("{ users { nodes { id email active } } }")["users"]["nodes"]
        enki_email = os.getenv("ENKI_LINEAR_EMAIL_ADDRESS") or os.getenv("ENKI_EMAIL_ADDRESS") or viewer.get("email")
        enki_user = next((u for u in users if u.get("email") == enki_email and u.get("active")), None)
        states = self._gql(
            """
            query($teamKey: String!) {
              workflowStates(filter: { team: { key: { eq: $teamKey } } }) {
                nodes { id name type }
              }
            }
            """,
            {"teamKey": team["key"]},
        )["workflowStates"]["nodes"]
        state_by_name = {s["name"].lower(): s["id"] for s in states}
        state_by_type: dict[str, str] = {}
        for state in states:
            state_by_type.setdefault(state["type"], state["id"])
        state_id = state_by_name.get("todo") or state_by_type.get("unstarted") or state_by_type.get("backlog")
        projects = self._gql("{ projects(first: 100) { nodes { id name url } } }")["projects"]["nodes"]
        project = next((p for p in projects if p.get("name", "").lower() == ENKI_PROJECT_NAME.lower()), None)
        if project is None:
            project = self._gql(
                """
                mutation($input: ProjectCreateInput!) {
                  projectCreate(input: $input) { success project { id name url } }
                }
                """,
                {"input": {"name": ENKI_PROJECT_NAME, "description": ENKI_PROJECT_DESCRIPTION, "teamIds": [team["id"]]}},
            )["projectCreate"]["project"]
        self._basics = (team, enki_user, project, state_id)
        return self._basics

    def find_issue_for_goal(self, goal: str, fingerprint: str) -> LinearIssue | None:
        data = self._gql(
            """
            query($title: String!) {
              issues(filter: { title: { eq: $title } }, first: 10) {
                nodes { id identifier title url }
              }
            }
            """,
            {"title": goal},
        )
        for issue in data["issues"]["nodes"]:
            if issue.get("title") == goal:
                return LinearIssue(
                    issue_id=issue["id"],
                    identifier=issue["identifier"],
                    title=issue["title"],
                    url=issue["url"],
                )
        return None

    def create_issue_for_goal(self, goal: str) -> LinearIssue:
        team, enki_user, project, state_id = self._ensure_basics()
        description = "\n".join([
            "# Created from Hermes `/goal`",
            "",
            "This Linear issue was created automatically for an explicit standing goal.",
            "",
            "## Goal",
            goal,
        ])
        input_data: dict[str, Any] = {
            "teamId": team["id"],
            "title": goal if len(goal) <= 180 else goal[:177].rstrip() + "…",
            "description": description,
            "priority": 2,
            "projectId": project["id"],
            "dueDate": (date.today() + timedelta(days=14)).isoformat(),
        }
        if enki_user:
            input_data["assigneeId"] = enki_user["id"]
        if state_id:
            input_data["stateId"] = state_id
        issue = self._gql(
            """
            mutation($input: IssueCreateInput!) {
              issueCreate(input: $input) { success issue { id identifier title url } }
            }
            """,
            {"input": input_data},
        )["issueCreate"]["issue"]
        return LinearIssue(
            issue_id=issue["id"],
            identifier=issue["identifier"],
            title=issue["title"],
            url=issue["url"],
        )


def _load_env_files() -> None:
    for path in [Path.home() / "hermes/.env", Path.home() / ".hermes/.env"]:
        if not path.exists():
            continue
        for raw in path.read_text(errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def link_goal_to_linear(session_id: str, goal: str) -> GoalLinearLink | None:
    """Best-effort real Enki link path used by GoalManager.set()."""
    store = PsqlGoalLinearStore()
    linear = LinearGoalClient()
    return ensure_goal_linear_link(session_id, goal, store=store, linear=linear)


__all__ = [
    "GoalLinearLink",
    "LinearIssue",
    "ensure_goal_linear_link",
    "goal_fingerprint",
    "goal_text_from_task",
    "link_goal_to_linear",
    "normalize_goal_text",
    "should_run_task_as_goal",
]
