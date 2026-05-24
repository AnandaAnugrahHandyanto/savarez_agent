#!/usr/bin/env python3
"""Route explicitly labelled GitHub issues/PRs into Hermes Kanban tasks.

This deterministic script is intended for cron ``--no-agent`` runs. It scans
configured repositories for the Snowman-style label contract and creates
idempotent Kanban tasks; it prints only when it creates work or hits lane
errors so no-op ticks stay silent.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hermes_cli import kanban_db as kb  # noqa: E402

WORK_LABEL = "snowman:work"
REVIEW_LABEL = "snowman:review"
BLOCKED_LABEL = "snowman:blocked"
CREATED_BY = os.getenv("HERMES_GITHUB_ROUTER_CREATED_BY", "github-router")
DEFAULT_BOARD = os.getenv("HERMES_GITHUB_ROUTER_BOARD", "deepwork")
DEFAULT_ASSIGNEE = os.getenv("HERMES_GITHUB_ROUTER_ASSIGNEE", "default")
DEFAULT_MAX_RUNTIME = os.getenv("HERMES_GITHUB_ROUTER_MAX_RUNTIME", "2h")
DEFAULT_SKILLS = tuple(
    s.strip()
    for s in os.getenv("HERMES_GITHUB_ROUTER_SKILLS", "github-pr-workflow").split(",")
    if s.strip()
)
COMMENT_MARKER_PREFIX = "<!-- hermes-github-router:key="
DEPENDENCY_RE = re.compile(r"^(?:Depends on|Blocked by):\s*(.+)$", re.IGNORECASE | re.MULTILINE)
ISSUE_REF_RE = re.compile(r"#(\d+)")
OK_CHECK_CONCLUSIONS = {"success", "neutral", "skipped"}
OK_STATUS_STATES = {"success"}


class RouterError(RuntimeError):
    """Lane-local router failure."""


@dataclass(frozen=True)
class RepoConfig:
    owner: str
    repo: str
    workspace: str
    board: str = DEFAULT_BOARD
    assignee: str = DEFAULT_ASSIGNEE
    max_runtime: str = DEFAULT_MAX_RUNTIME
    skills: tuple[str, ...] = DEFAULT_SKILLS

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"


@dataclass(frozen=True)
class QueueResult:
    task_id: str
    created: bool


class GitHubApi(Protocol):
    def api(self, path: str, *, method: str = "GET", fields: dict[str, Any] | None = None) -> Any: ...


class GitHubClient:
    """Tiny ``gh api`` wrapper kept injectable for tests."""

    def __init__(self, runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run):
        self._runner = runner

    def api(self, path: str, *, method: str = "GET", fields: dict[str, Any] | None = None) -> Any:
        cmd = ["gh", "api", path, "--method", method]
        if fields:
            for key, value in fields.items():
                cmd.extend(["-f", f"{key}={value}"])
        proc = self._runner(cmd, text=True, capture_output=True, check=False)
        if proc.returncode != 0:
            raise RouterError(f"gh api {method} {path} failed: {proc.stderr.strip() or proc.stdout.strip()}")
        raw = proc.stdout.strip()
        if not raw:
            return None
        return json.loads(raw)


def parse_repos_from_env(env: dict[str, str] | None = None) -> list[RepoConfig]:
    env_map = env if env is not None else os.environ
    raw_config = env_map.get("HERMES_GITHUB_ROUTER_CONFIG")
    if raw_config:
        data_raw = json.loads(raw_config)
        defaults: dict[str, Any] = data_raw if isinstance(data_raw, dict) else {}
        repo_items = defaults.get("repos", data_raw if isinstance(data_raw, list) else [])
        parsed: list[RepoConfig] = []
        for item_raw in repo_items:
            item: dict[str, Any] = dict(item_raw)
            full_name = str(item.get("full_name") or "")
            owner = str(item.get("owner") or full_name.split("/", 1)[0])
            repo = str(item.get("repo") or full_name.split("/", 1)[1])
            parsed.append(
                RepoConfig(
                    owner=owner,
                    repo=repo,
                    workspace=str(item["workspace"]),
                    board=str(item.get("board") or defaults.get("board") or DEFAULT_BOARD),
                    assignee=str(item.get("assignee") or defaults.get("assignee") or DEFAULT_ASSIGNEE),
                    max_runtime=str(item.get("max_runtime") or defaults.get("max_runtime") or DEFAULT_MAX_RUNTIME),
                    skills=tuple(item.get("skills") or defaults.get("skills") or DEFAULT_SKILLS),
                )
            )
        return parsed

    raw_repos = env_map.get("HERMES_GITHUB_ROUTER_REPOS", "")
    workspace_root = env_map.get("HERMES_GITHUB_ROUTER_WORKSPACE_ROOT", str(Path.home()))
    repos: list[RepoConfig] = []
    for full_name in [part.strip() for part in raw_repos.split(",") if part.strip()]:
        owner, repo = full_name.split("/", 1)
        workspace = env_map.get(f"HERMES_GITHUB_ROUTER_WORKSPACE_{repo.upper().replace('-', '_')}")
        repos.append(RepoConfig(owner=owner, repo=repo, workspace=workspace or str(Path(workspace_root) / repo)))
    return repos


def labels(item: dict[str, Any]) -> set[str]:
    return {label.get("name", "") for label in item.get("labels", [])}


def is_pr_issue(item: dict[str, Any]) -> bool:
    return "pull_request" in item


def parse_dependencies(body: str | None) -> set[int]:
    deps: set[int] = set()
    for match in DEPENDENCY_RE.finditer(body or ""):
        deps.update(int(n) for n in ISSUE_REF_RE.findall(match.group(1)))
    return deps


def issue_closed(gh: GitHubApi, repo: RepoConfig, number: int) -> bool:
    data = gh.api(f"repos/{repo.full_name}/issues/{number}")
    return data.get("state") == "closed"


def comment_exists(gh: GitHubApi, repo: RepoConfig, number: int, key: str) -> bool:
    marker = f"{COMMENT_MARKER_PREFIX}{key} -->"
    comments = gh.api(f"repos/{repo.full_name}/issues/{number}/comments?per_page=100") or []
    return any(marker in (c.get("body") or "") for c in comments)


def post_tracking_comment(gh: GitHubApi, repo: RepoConfig, number: int, key: str, body: str) -> None:
    if comment_exists(gh, repo, number, key):
        return
    gh.api(
        f"repos/{repo.full_name}/issues/{number}/comments",
        method="POST",
        fields={"body": f"{COMMENT_MARKER_PREFIX}{key} -->\n{body}"},
    )


def add_label(gh: GitHubApi, repo: RepoConfig, number: int, label: str) -> None:
    gh.api(f"repos/{repo.full_name}/issues/{number}/labels", method="POST", fields={"labels[]": label})


def remove_label(gh: GitHubApi, repo: RepoConfig, number: int, label: str) -> None:
    gh.api(f"repos/{repo.full_name}/issues/{number}/labels/{quote(label, safe='')}", method="DELETE")


def item_labels(gh: GitHubApi, repo: RepoConfig, item: dict[str, Any]) -> set[str]:
    """Return labels for an issue or PR, falling back to the issues endpoint.

    GitHub's pull request payloads have varied by endpoint/version; the
    issues endpoint is the canonical source for labels on both issues and PRs.
    """
    if "labels" in item:
        return labels(item)
    issue = gh.api(f"repos/{repo.full_name}/issues/{item['number']}") or {}
    return labels(issue)


def latest_label_event_id(gh: GitHubApi, repo: RepoConfig, number: int, label: str) -> str:
    events = gh.api(f"repos/{repo.full_name}/issues/{number}/events?per_page=100") or []
    matching = [e for e in events if e.get("event") == "labeled" and e.get("label", {}).get("name") == label]
    if not matching:
        return "none"
    return str(matching[-1].get("id") or matching[-1].get("created_at") or "latest")


def checks_ready_for_review(gh: GitHubApi, repo: RepoConfig, sha: str) -> bool:
    check_runs = gh.api(f"repos/{repo.full_name}/commits/{sha}/check-runs") or {}
    for run in check_runs.get("check_runs", []):
        if run.get("status") != "completed":
            return False
        if (run.get("conclusion") or "").lower() not in OK_CHECK_CONCLUSIONS:
            return False

    status = gh.api(f"repos/{repo.full_name}/commits/{sha}/status") or {}
    state = status.get("state")
    statuses = status.get("statuses") or []
    if statuses and state not in OK_STATUS_STATES:
        return False
    return True


def task_by_idempotency_key(board: str, key: str) -> str | None:
    with kb.connect(board=board) as conn:
        row = conn.execute(
            "SELECT id FROM tasks WHERE idempotency_key = ? AND status != 'archived' "
            "ORDER BY created_at DESC LIMIT 1",
            (key,),
        ).fetchone()
        return row["id"] if row else None


def parse_duration(value: str) -> int | None:
    # Reuse the CLI parser so script semantics match `hermes kanban create`.
    from hermes_cli.kanban import _parse_duration  # local import avoids parser work on import

    return _parse_duration(value)


def create_queue_task(repo: RepoConfig, *, title: str, body: str, key: str) -> QueueResult:
    existing = task_by_idempotency_key(repo.board, key)
    if existing:
        return QueueResult(task_id=existing, created=False)
    with kb.connect(board=repo.board) as conn:
        task_id = kb.create_task(
            conn,
            title=title,
            body=body,
            assignee=repo.assignee,
            created_by=CREATED_BY,
            workspace_kind="dir",
            workspace_path=repo.workspace,
            idempotency_key=key,
            max_runtime_seconds=parse_duration(repo.max_runtime),
            skills=repo.skills,
            initial_status="running",
            board=repo.board,
        )
    return QueueResult(task_id=task_id, created=True)


def issue_worker_body(repo: RepoConfig, issue: dict[str, Any]) -> str:
    n = issue["number"]
    return f"""역할: 구현
repo: {repo.full_name}
local repo path: {repo.workspace}
issue: #{n} {issue.get('html_url')} — {issue.get('title')}

공유 checkout에서 직접 파일을 수정하지 마세요. 작업 시작 시 반드시 {repo.workspace}/.worktrees/issue-{n}-<slug> 형태의 별도 git worktree를 만들고 그 안에서만 수정/테스트/커밋/푸시하세요.

완료 조건:
- 관련 코드 변경 구현
- 관련 테스트/체크 실행 또는 실행 불가 사유 기록
- 브랜치 push
- main 대상으로 PR 생성
- PR 본문에 한국어 요약, 테스트 노트, UI 변경 여부 포함
- PR에 {REVIEW_LABEL} 라벨 추가
- 원 이슈의 {WORK_LABEL} 라벨 제거
- kanban/task 완료 요약에 repo, issue, branch, commit SHA, PR URL, 테스트, 리스크 기록
"""


def pr_review_body(repo: RepoConfig, pr: dict[str, Any], sha: str) -> str:
    n = pr["number"]
    return f"""역할: 코드 리뷰
repo: {repo.full_name}
PR: #{n} {pr.get('html_url')} — {pr.get('title')}
review target head SHA: {sha}

리뷰 시작 시 반드시 {repo.workspace}/.worktrees/review-pr-{n}-{sha[:12]} 형태의 별도 git worktree를 만들고 그 안에서 diff 확인/테스트를 수행하세요.
리뷰 작업은 원칙적으로 코드를 수정/커밋/푸시하지 않습니다.
blocking 이슈가 없으면 APPROVE, 있으면 REQUEST_CHANGES, 참고성 피드백만 있으면 COMMENT로 정식 GitHub review를 제출하세요.
리뷰 본문에 대상 head SHA를 반드시 남기세요.
구 상태 라벨은 사용하지 말고, review/comment/완료 요약은 한국어로 작성하세요.
"""


def pr_fix_body(repo: RepoConfig, pr: dict[str, Any], sha: str) -> str:
    n = pr["number"]
    return f"""역할: PR 리뷰 피드백 반영
repo: {repo.full_name}
PR: #{n} {pr.get('html_url')} — {pr.get('title')}
기준 head SHA: {sha}

{repo.workspace}/.worktrees/fix-pr-{n}-{sha[:12]} 형태의 별도 git worktree를 만들고 그 안에서만 수정하세요.
GitHub review의 blocking 피드백과 unresolved comment를 확인하고 필요한 수정만 반영하세요.
수정 후 PR branch에 push하세요.
완료 후 PR에 {REVIEW_LABEL} 라벨을 다시 추가하고 {WORK_LABEL} 라벨은 제거하세요.
완료 요약은 한국어로 작성하세요.
"""


def scan_issue_dependency_unblock(gh: GitHubApi, repo: RepoConfig) -> list[str]:
    out: list[str] = []
    issues = gh.api(f"repos/{repo.full_name}/issues?state=open&labels={WORK_LABEL}&per_page=100") or []
    for issue in issues:
        if is_pr_issue(issue):
            continue
        n = issue["number"]
        deps = parse_dependencies(issue.get("body"))
        if not deps:
            continue
        open_deps = [d for d in deps if not issue_closed(gh, repo, d)]
        lbls = labels(issue)
        if open_deps and BLOCKED_LABEL not in lbls:
            add_label(gh, repo, n, BLOCKED_LABEL)
            post_tracking_comment(
                gh,
                repo,
                n,
                f"{repo.full_name}:issue:{n}:blocked-by:{','.join(map(str, open_deps))}",
                f"자동화 대기: 선행 이슈 {', '.join(f'#{d}' for d in open_deps)} 가 아직 열려 있어 `{BLOCKED_LABEL}` 라벨을 추가했습니다.",
            )
            out.append(f"{repo.full_name} issue #{n}: blocked by {open_deps}")
        elif not open_deps and BLOCKED_LABEL in lbls:
            remove_label(gh, repo, n, BLOCKED_LABEL)
            out.append(f"{repo.full_name} issue #{n}: dependencies cleared")
    return out


def scan_issue_work(gh: GitHubApi, repo: RepoConfig) -> list[str]:
    created: list[str] = []
    issues = gh.api(f"repos/{repo.full_name}/issues?state=open&labels={WORK_LABEL}&per_page=100") or []
    for issue in issues:
        if is_pr_issue(issue) or BLOCKED_LABEL in labels(issue):
            continue
        n = issue["number"]
        key = f"{repo.full_name}:issue:{n}:work"
        result = create_queue_task(
            repo,
            title=f"[{repo.repo}] 이슈 구현 #{n}: {issue.get('title')}",
            body=issue_worker_body(repo, issue),
            key=key,
        )
        if result.created:
            post_tracking_comment(gh, repo, n, key, f"자동화 작업을 생성했습니다: kanban `{result.task_id}`")
            created.append(f"{repo.full_name} issue #{n} -> {result.task_id}")
    return created


def list_open_prs(gh: GitHubApi, repo: RepoConfig) -> list[dict[str, Any]]:
    return gh.api(f"repos/{repo.full_name}/pulls?state=open&per_page=100") or []


def scan_pr_work(gh: GitHubApi, repo: RepoConfig) -> list[str]:
    created: list[str] = []
    for pr in list_open_prs(gh, repo):
        if pr.get("draft"):
            continue
        lbls = item_labels(gh, repo, pr)
        if WORK_LABEL not in lbls or BLOCKED_LABEL in lbls:
            continue
        n = pr["number"]
        sha = pr.get("head", {}).get("sha") or "unknown"
        key = f"{repo.full_name}:pr:{n}:work:{sha}"
        result = create_queue_task(
            repo,
            title=f"[{repo.repo}] PR 수정 #{n}: {pr.get('title')}",
            body=pr_fix_body(repo, pr, sha),
            key=key,
        )
        if result.created:
            post_tracking_comment(gh, repo, n, key, f"PR 수정 자동화 작업을 생성했습니다: kanban `{result.task_id}`")
            created.append(f"{repo.full_name} PR #{n} fix -> {result.task_id}")
    return created


def scan_pr_review(gh: GitHubApi, repo: RepoConfig) -> list[str]:
    created: list[str] = []
    for pr in list_open_prs(gh, repo):
        if pr.get("draft"):
            continue
        lbls = item_labels(gh, repo, pr)
        if REVIEW_LABEL not in lbls or BLOCKED_LABEL in lbls:
            continue
        n = pr["number"]
        sha = pr.get("head", {}).get("sha") or "unknown"
        if not checks_ready_for_review(gh, repo, sha):
            continue
        label_event = latest_label_event_id(gh, repo, n, REVIEW_LABEL)
        key = f"{repo.full_name}:pr:{n}:review:{sha}:label:{label_event}"
        result = create_queue_task(
            repo,
            title=f"[{repo.repo}] PR 리뷰 #{n}: {pr.get('title')}",
            body=pr_review_body(repo, pr, sha),
            key=key,
        )
        if result.created:
            post_tracking_comment(gh, repo, n, key, f"PR 리뷰 자동화 작업을 생성했습니다: kanban `{result.task_id}`")
            created.append(f"{repo.full_name} PR #{n} review -> {result.task_id}")
    return created


def run_lane(name: str, fn: Callable[[GitHubApi, RepoConfig], list[str]], gh: GitHubApi, repo: RepoConfig, created: list[str], errors: list[str]) -> None:
    try:
        created.extend(fn(gh, repo))
    except Exception as exc:  # lane isolation is intentional for cron robustness
        errors.append(f"{name} {repo.full_name}: {exc}")


def run(repos: Sequence[RepoConfig], gh: GitHubApi | None = None) -> tuple[list[str], list[str]]:
    gh = gh or GitHubClient()
    created: list[str] = []
    errors: list[str] = []
    for repo in repos:
        run_lane("issue-dependency-unblock", scan_issue_dependency_unblock, gh, repo, created, errors)
        run_lane("issue-work", scan_issue_work, gh, repo, created, errors)
        run_lane("pr-work", scan_pr_work, gh, repo, created, errors)
        run_lane("pr-review", scan_pr_review, gh, repo, created, errors)
    return created, errors


def main(argv: Sequence[str] | None = None) -> int:
    repos = parse_repos_from_env()
    if not repos:
        print("github-router: no repos configured; set HERMES_GITHUB_ROUTER_CONFIG or HERMES_GITHUB_ROUTER_REPOS", file=sys.stderr)
        return 2
    created, errors = run(repos)
    lines: list[str] = []
    if created:
        lines.append(f"GitHub router: 작업 생성/상태 변경 {len(created)}건")
        lines.extend(f"- {line}" for line in created)
    if errors:
        lines.append(f"router lane failure {len(errors)}건")
        lines.extend(f"- {line}" for line in errors)
    if lines:
        print("\n".join(lines))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
