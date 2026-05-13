# GitHub MCP Integration Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add a minimal-scope GitHub MCP integration that lets Quinn inspect issues, pull requests, branches, commits, and CI status without performing write actions by default.

**Architecture:** Build a new local stdio MCP server, separate from `quinn_ops`, so GitHub access can be enabled, permissioned, and audited independently. Version 1 is read-first/read-only: it uses `gh` when available and authenticated, with an optional environment-auth fallback, and returns sanitized metadata only. Mutating GitHub actions remain out of scope until an approval-gated ops phase.

**Tech Stack:** Python 3.11, MCP SDK, subprocess `gh`/`git` commands with `shell=False`, JSON responses, pytest tests with monkeypatched command runners.

---

## Security Contract

- No GitHub writes in v1: no comments, labels, assignments, branch pushes, PR edits, merges, workflow dispatches, or reruns.
- No auth values in output, logs, snapshots, or errors.
- No full patch/diff bodies by default; return path/count/stat metadata unless a future gated option is approved.
- No repository-wide content scraping; read targeted metadata from configured repositories only.
- No private issue/PR body output by default; return titles, numbers, URLs, states, labels, authors, timestamps, CI names/conclusions, and short sanitized summaries only.
- Auth detection reports `authenticated=true/false/unknown` and method (`gh`, `env_auth`, `none`) without exposing auth material.
- All subprocess calls use argv lists, `shell=False`, cwd allowlist, timeouts, and redaction.

## Proposed Files

- Create: `scripts/mcp/quinn_github_server.py`
- Create: `tests/test_quinn_github_mcp.py`
- Create: `docs/quinn_github_mcp.md`
- Optional live copy after approval: `/home/quinn/.hermes/mcp/quinn_github_server.py`

## Config Shape

Do not add automatically. Future live config snippet:

```yaml
mcp_servers:
  quinn_github:
    command: "/home/quinn/.hermes/hermes-agent/venv/bin/python"
    args:
      - "/home/quinn/.hermes/mcp/quinn_github_server.py"
    timeout: 60
    connect_timeout: 30
    sampling:
      enabled: false
```

Repository allowlist is required. Prefer an environment value or config value that lists exact `owner/repo` slugs. Example variable name for the MCP process:

```bash
QUINN_GITHUB_ALLOWED_REPOS=NousResearch/hermes-agent
```

## Tool Set v1

1. `healthcheck()` — server readiness, auth method, allowed repo count, `gh` availability.
2. `get_github_auth_status()` — metadata-only auth status.
3. `list_allowed_repositories()` — returns configured allowlist only.
4. `get_repository_summary(repo: str)` — allowlisted repo metadata.
5. `list_pull_requests(repo: str, state: str = "open", limit: int = 20)` — PR metadata, no body.
6. `get_pull_request_status(repo: str, number: int)` — PR metadata plus checks, no full diff.
7. `list_issues(repo: str, state: str = "open", limit: int = 20)` — issue metadata, no body.
8. `get_ci_status(repo: str, ref: str)` — status/check-run metadata for branch/SHA/ref.
9. `get_recent_workflow_runs(repo: str, branch: str | None = None, limit: int = 10)` — workflow run metadata, no logs.

## Task 1: Add Failing Auth and Allowlist Tests

**Objective:** Lock the privacy and allowlist contract before implementation.

**Files:**
- Create: `tests/test_quinn_github_mcp.py`

**Steps:**
1. Write tests for missing allowlist, exact allowlist matching, denied repos, nested redaction, and metadata-only auth status.
2. Run `venv/bin/python -m pytest tests/test_quinn_github_mcp.py -q`.
3. Expected: FAIL because server file/functions do not exist yet.

## Task 2: Scaffold `quinn_github_server.py`

**Objective:** Provide importable MCP server skeleton and privacy helpers.

**Files:**
- Create: `scripts/mcp/quinn_github_server.py`
- Modify: `tests/test_quinn_github_mcp.py`

**Implementation requirements:**
- Define `response(data, errors=None, warnings=None)` envelope matching `quinn_ops` style.
- Define `sanitize()` and `redact_string()` helpers.
- Define `allowed_repos()` parsing `QUINN_GITHUB_ALLOWED_REPOS` as comma/whitespace-separated exact slugs.
- Define `repo_allowed(repo)` with lowercased exact slug matching.
- Keep importable without MCP SDK; only MCP stdio startup should require SDK.

**Verification:**
```bash
python3 -m py_compile scripts/mcp/quinn_github_server.py tests/test_quinn_github_mcp.py
venv/bin/python -m pytest tests/test_quinn_github_mcp.py -q
```

## Task 3: Implement Safe Command Runner and Auth Status

**Objective:** Add bounded subprocess execution and auth detection.

**Files:**
- Modify: `scripts/mcp/quinn_github_server.py`
- Modify: `tests/test_quinn_github_mcp.py`

**Implementation requirements:**
- `run_cmd(argv, source, timeout=15, cwd=None)` uses `subprocess.run(..., shell=False, text=True, capture_output=True)`.
- Never include raw command env or auth values in errors.
- `get_github_auth_status()` checks `gh` availability/auth and an optional environment auth as boolean-only fallback.
- Return `auth_method` as `gh`, `env_auth`, `none`, or `unknown`.

## Task 4: Repository Summary via `gh api`

**Objective:** Read repository metadata for allowlisted repos only.

**Files:**
- Modify: `scripts/mcp/quinn_github_server.py`
- Modify: `tests/test_quinn_github_mcp.py`

**Implementation requirements:**
- Add `gh_api(path, fields=None)` helper around `gh api`.
- `get_repository_summary(repo)` rejects non-allowlisted repo before command execution.
- Parse safe fields: `full_name`, `private`, `default_branch`, `open_issues_count`, `pushed_at`, `updated_at`, `html_url`.
- Do not return clone URLs containing embedded auth.

## Task 5: Pull Request and Issue Listing

**Objective:** Provide read-only work queue visibility.

**Files:**
- Modify: `scripts/mcp/quinn_github_server.py`
- Modify: `tests/test_quinn_github_mcp.py`

**Implementation requirements:**
- Implement `list_pull_requests()` using `gh pr list --json number,title,state,author,labels,isDraft,url,updatedAt`.
- Implement `list_issues()` using `gh issue list --json number,title,state,author,labels,assignees,url,updatedAt`.
- Clamp `limit` to safe bounds, e.g. `1..50`.
- Sanitize author/label structures to metadata only.

## Task 6: PR CI Status and Workflow Runs

**Objective:** Let Quinn answer “what is blocking this PR/branch?” without reading logs.

**Files:**
- Modify: `scripts/mcp/quinn_github_server.py`
- Modify: `tests/test_quinn_github_mcp.py`

**Implementation requirements:**
- `get_pull_request_status(repo, number)` reads PR metadata and check status.
- `get_ci_status(repo, ref)` reads combined statuses/check runs.
- `get_recent_workflow_runs(repo, branch=None, limit=10)` reads run metadata only.
- No log downloads in v1.
- No reruns in v1.

## Task 7: Register MCP Tools and Docs

**Objective:** Make the server usable and documented without enabling it live.

**Files:**
- Modify: `scripts/mcp/quinn_github_server.py`
- Create: `docs/quinn_github_mcp.md`

**Implementation requirements:**
- Add `TOOL_FUNCTIONS` with the v1 tools.
- Add MCP stdio startup analogous to `quinn_ops`.
- Document config snippet, env allowlist, auth requirements, tools, security boundaries, verification.

## Task 8: Live Promotion Gate

**Objective:** Define the approval boundary; do not promote automatically.

**Requirements before live promotion:**
1. Frank approval.
2. Repo tests pass.
3. Backup any existing live `/home/quinn/.hermes/mcp/quinn_github_server.py`.
4. Copy repo server to live MCP path.
5. Add config only if approved and allowlist is explicit.
6. Restart gateway.
7. Verify `hermes mcp test quinn_github`.
8. Verify native MCP calls return no auth material and reject non-allowlisted repos.

## Acceptance Criteria

- `quinn_github` cannot access a repo unless it is explicitly allowlisted.
- All tools are read-only in v1.
- Auth material never appears in output.
- Issue/PR bodies and log bodies are omitted by default.
- CI status is summarized enough to answer “green/red/pending and what failed?” without downloading raw logs.
- Tests cover allowlist denial, auth metadata privacy, limit clamping, read-only command construction, malformed JSON, and redaction.

## Open Questions Requiring Frank

1. Which repositories should be in the initial allowlist?
2. Should v1 use `gh` only, or allow environment-auth fallback?
3. Should PR/issue titles be considered safe to show in all contexts, or should this MCP be restricted to protected contexts only?
4. When write actions are eventually added, should they live in this MCP behind approvals or in a separate approval-ops MCP?
