#!/usr/bin/env python3
"""Linear GraphQL API CLI — zero dependencies, stdlib only.

Usage:
  linear_api.py <command> [args...]

Commands:
  whoami                                  Show authenticated user
  list-teams                              List all teams
  list-projects [--team KEY]              List projects (optionally filter by team)
  list-states [--team KEY]                List workflow states
  list-labels [--team KEY]                List labels (optionally filter by team)
  list-users                              List workspace members (for --assignee)
  list-issues [filters]                   List issues
    --team KEY                            Filter by team key (e.g. ENG)
    --status NAME                         Filter by workflow state name
    --assignee NAME                       Filter by assignee name (exact)
    --label NAME                          Filter by label name
    --limit N                             Max results (default: 25)
  get-issue <IDENTIFIER>                  Full issue details (e.g. ENG-42)
  search-issues <query>                   Full-text search across issues
  create-issue [options]                  Create a new issue
    --title TITLE                         Required
    --team KEY                            Required
    --description DESC
    --priority 0-4                        0=none, 1=urgent, 4=low
    --label NAME                          Repeatable / comma-separated for several
    --assignee NAME                       Name, email, or 'me'
    --parent IDENTIFIER                   Parent issue ID for sub-issues
  update-issue <IDENTIFIER> [options]     Update existing issue
    --title / --description / --priority
    --label NAME                          Added to existing labels; repeatable / comma-separated
    --assignee NAME                       Name, email, or 'me'
    --team KEY                            Scope --label lookup (else inferred from issue)
  update-status <IDENTIFIER> <STATE>      Move issue to workflow state (by state name)
  add-comment <IDENTIFIER> <body>         Add comment to issue

  list-documents [--limit N]              List documents (docs, not issues)
  get-document <SLUG_OR_ID>               Fetch a document by slugId (from URL) or UUID
  search-documents <query>                Search documents by title

  raw <graphql_query> [variables_json]    Run an arbitrary GraphQL query
                                          Use --vars '{"key":"value"}' for variables

Auth:
  Set LINEAR_API_KEY environment variable (from Linear Settings -> API).
  Uses the personal API key header format: `Authorization: <KEY>` (no Bearer prefix).

Output:
  JSON to stdout. Errors to stderr with non-zero exit code.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

API_URL = "https://api.linear.app/graphql"


def _get_key() -> str:
    key = os.environ.get("LINEAR_API_KEY", "").strip()
    if not key:
        sys.stderr.write(
            "ERROR: LINEAR_API_KEY not set.\n"
            "Create one at https://linear.app/settings/api and export it,\n"
            "or add `LINEAR_API_KEY=lin_api_...` to ~/.hermes/.env\n"
        )
        sys.exit(2)
    return key


def gql(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a GraphQL query against Linear. Raises on HTTP error or GraphQL errors."""
    key = _get_key()
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": key,  # Personal API key — NO `Bearer` prefix
            "User-Agent": "hermes-agent-linear-skill/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')}\n")
        sys.exit(1)
    except urllib.error.URLError as e:
        sys.stderr.write(f"Network error: {e}\n")
        sys.exit(1)

    result = json.loads(body)
    if "errors" in result and result["errors"]:
        sys.stderr.write(f"GraphQL errors: {json.dumps(result['errors'], indent=2)}\n")
        # Still return data if partial success; let caller decide
        if not result.get("data"):
            sys.exit(1)
    return result.get("data", {}) or {}


def emit(obj: Any) -> None:
    print(json.dumps(obj, indent=2, default=str))


# ---------- Commands ----------

def cmd_whoami(_args: argparse.Namespace) -> None:
    q = "query { viewer { id name email displayName } }"
    emit(gql(q).get("viewer"))


def cmd_list_teams(_args: argparse.Namespace) -> None:
    q = "query { teams(first: 100) { nodes { id key name description } } }"
    emit(gql(q).get("teams", {}).get("nodes", []))


def _paginate(query: str, path: list[str], variables: dict[str, Any] | None = None,
              page_size: int = 250) -> list[dict]:
    """Collect every node from a Relay-style connection, following cursors.

    The query must accept `$first: Int!` and `$after: String` and select, at the
    given `path`, both `nodes` and `pageInfo { hasNextPage endCursor }`. This is
    what makes name resolution correct on workspaces larger than one page (250) —
    a single-page fetch would silently miss labels/users past the cap.
    """
    out: list[dict] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()
    while True:
        base = dict(variables or {})
        base["first"] = page_size
        base["after"] = cursor
        node: Any = gql(query, base)
        for key in path:
            node = (node or {}).get(key, {})
        out.extend(node.get("nodes", []))
        info = node.get("pageInfo") or {}
        cursor = info.get("endCursor")
        # Stop on last page, a missing cursor, or a repeat (defensive against loops).
        if not info.get("hasNextPage") or not cursor or cursor in seen_cursors:
            break
        seen_cursors.add(cursor)
    return out


def _resolve_team_id(key_or_name: str) -> str | None:
    """Map a team key (ENG) or name to UUID. Team keys/names are unique."""
    q = """query($first: Int!, $after: String) {
      teams(first: $first, after: $after) {
        nodes { id key name } pageInfo { hasNextPage endCursor }
      }
    }"""
    kl = key_or_name.strip().lower()
    for t in _paginate(q, ["teams"]):
        if t["key"].lower() == kl or t["name"].lower() == kl:
            return t["id"]
    return None


def _find_labels(name: str, team_id: str | None = None) -> list[dict]:
    """Return every label whose name matches (case-insensitive, trimmed).

    When team_id is given we filter server-side to that team; otherwise we search
    all labels visible to the caller. More than one result means the name is
    ambiguous (e.g. the same label name in different teams).
    """
    if not name or not name.strip():
        return []
    target = name.strip().lower()
    if team_id:
        # Team.labels is guaranteed to exist; the root labels connection is
        # `issueLabels` (there is no root `labels`).
        q = """query($teamId: String!, $first: Int!, $after: String) {
          team(id: $teamId) {
            labels(first: $first, after: $after) {
              nodes { id name } pageInfo { hasNextPage endCursor }
            }
          }
        }"""
        labels = _paginate(q, ["team", "labels"], {"teamId": team_id})
    else:
        q = """query($first: Int!, $after: String) {
          issueLabels(first: $first, after: $after) {
            nodes { id name } pageInfo { hasNextPage endCursor }
          }
        }"""
        labels = _paginate(q, ["issueLabels"])
    return [lbl for lbl in labels if (lbl.get("name") or "").strip().lower() == target]


def _find_users(name: str) -> list[dict]:
    """Return every user matching name, displayName, full email, or email
    local-part (case-insensitive, trimmed). Each node carries `active` so the
    caller can refuse to assign deactivated members."""
    if not name or not name.strip():
        return []
    target = name.strip().lower()
    q = """query($first: Int!, $after: String) {
      users(first: $first, after: $after) {
        nodes { id name displayName email active } pageInfo { hasNextPage endCursor }
      }
    }"""
    matches: list[dict] = []
    for user in _paginate(q, ["users"]):
        fields = {(user.get("name") or "").lower(), (user.get("displayName") or "").lower()}
        email = (user.get("email") or "").lower()
        if target in fields and target:
            matches.append(user)
        elif email and (email == target or email.split("@", 1)[0] == target):
            matches.append(user)
    return matches


def _label_tokens(values: list[str] | None) -> list[str]:
    """Flatten repeated --label flags and comma-separated values into names."""
    out: list[str] = []
    for value in values or []:
        out.extend(tok.strip() for tok in value.split(",") if tok.strip())
    return out


def _resolve_label_id_or_exit(name: str, team_id: str | None, list_hint: str) -> str:
    """Resolve one label name to a UUID, or print a precise error and exit.

    Tries the team-scoped lookup first, then falls back to a workspace-wide
    search. Exits with the candidate list when a name is ambiguous.
    """
    matches = _find_labels(name, team_id)
    if not matches and team_id:
        matches = _find_labels(name)  # workspace-wide fallback
    # Collapse exact-duplicate ids (same label seen twice) before counting.
    unique = {m["id"]: m for m in matches}
    if not unique:
        sys.stderr.write(f"Label not found: '{name}'\n")
        sys.stderr.write(f"Hint: run 'linear_api.py list-labels{list_hint}' to see available labels.\n")
        sys.exit(1)
    if len(unique) > 1:
        sys.stderr.write(f"Label '{name}' is ambiguous — {len(unique)} matches across teams:\n")
        for m in unique.values():
            sys.stderr.write(f"  - {m['id']}\n")
        sys.stderr.write("Hint: pass --team to scope the lookup to one team.\n")
        sys.exit(1)
    return next(iter(unique))


def _resolve_assignee_id_or_exit(name: str) -> str:
    """Resolve --assignee (a name, email, or 'me') to a user UUID, or exit.

    Only active users are assignable: if a name matches solely deactivated
    members, that's an error rather than a silent assignment. Ambiguous names
    exit with the candidate list.
    """
    if name.strip().lower() == "me":
        viewer = gql("query { viewer { id } }").get("viewer") or {}
        if not viewer.get("id"):
            sys.stderr.write("Could not resolve 'me' to the current user.\n")
            sys.exit(1)
        return viewer["id"]
    matches = _find_users(name)
    active = [u for u in matches if u.get("active")]
    if matches and not active:
        sys.stderr.write(f"Assignee '{name}' matches only deactivated user(s).\n")
        sys.stderr.write("Hint: assign an active member, or reactivate them in Linear.\n")
        sys.exit(1)
    unique = {u["id"]: u for u in active}
    if not unique:
        sys.stderr.write(f"Assignee not found: '{name}'\n")
        sys.stderr.write("Hint: run 'linear_api.py list-users' to see available users.\n")
        sys.exit(1)
    if len(unique) > 1:
        sys.stderr.write(f"Assignee '{name}' is ambiguous — {len(unique)} matches:\n")
        for u in unique.values():
            label = u.get("email") or u.get("displayName") or u.get("name") or u["id"]
            sys.stderr.write(f"  - {label}\n")
        sys.stderr.write("Hint: use a full email address to disambiguate.\n")
        sys.exit(1)
    return next(iter(unique))


def cmd_list_projects(args: argparse.Namespace) -> None:
    if args.team:
        tid = _resolve_team_id(args.team)
        if not tid:
            sys.stderr.write(f"Team not found: {args.team}\n")
            sys.exit(1)
        q = """query($id: String!) {
          team(id: $id) { projects(first: 100) { nodes { id name description state } } }
        }"""
        data = gql(q, {"id": tid})
        emit(data.get("team", {}).get("projects", {}).get("nodes", []))
    else:
        q = "query { projects(first: 100) { nodes { id name description state } } }"
        emit(gql(q).get("projects", {}).get("nodes", []))


def cmd_list_states(args: argparse.Namespace) -> None:
    if args.team:
        tid = _resolve_team_id(args.team)
        if not tid:
            sys.stderr.write(f"Team not found: {args.team}\n")
            sys.exit(1)
        q = """query($id: String!) {
          team(id: $id) { states(first: 100) { nodes { id name type color } } }
        }"""
        emit(gql(q, {"id": tid}).get("team", {}).get("states", {}).get("nodes", []))
    else:
        q = "query { workflowStates(first: 200) { nodes { id name type team { key } } } }"
        emit(gql(q).get("workflowStates", {}).get("nodes", []))


def cmd_list_issues(args: argparse.Namespace) -> None:
    filt: dict[str, Any] = {}
    if args.team:
        filt["team"] = {"key": {"eq": args.team}}
    if args.status:
        filt["state"] = {"name": {"eq": args.status}}
    if args.assignee:
        filt["assignee"] = {"name": {"eq": args.assignee}}
    if args.label:
        filt["labels"] = {"name": {"eq": args.label}}

    q = """query($filter: IssueFilter, $first: Int!) {
      issues(filter: $filter, first: $first, orderBy: updatedAt) {
        nodes {
          id identifier title
          state { name } priority
          assignee { name }
          team { key }
          updatedAt url
        }
      }
    }"""
    data = gql(q, {"filter": filt or None, "first": args.limit})
    emit(data.get("issues", {}).get("nodes", []))


def cmd_get_issue(args: argparse.Namespace) -> None:
    q = """query($id: String!) {
      issue(id: $id) {
        id identifier title description
        state { name type }
        priority priorityLabel
        assignee { name email }
        creator { name }
        team { key name }
        project { name }
        labels { nodes { name } }
        parent { identifier title }
        children { nodes { identifier title state { name } } }
        comments { nodes { user { name } body createdAt } }
        createdAt updatedAt url
      }
    }"""
    emit(gql(q, {"id": args.identifier}).get("issue"))


def cmd_search_issues(args: argparse.Namespace) -> None:
    q = """query($term: String!, $first: Int!) {
      searchIssues(term: $term, first: $first) {
        nodes { id identifier title state { name } url }
      }
    }"""
    emit(gql(q, {"term": args.query, "first": args.limit}).get("searchIssues", {}).get("nodes", []))


def cmd_create_issue(args: argparse.Namespace) -> None:
    tid = _resolve_team_id(args.team)
    if not tid:
        sys.stderr.write(f"Team not found: {args.team}\n")
        sys.exit(1)
    inp: dict[str, Any] = {"title": args.title, "teamId": tid}
    if args.description:
        inp["description"] = args.description
    if args.priority is not None:
        inp["priority"] = args.priority
    if args.parent:
        inp["parentId"] = args.parent
    label_ids: list[str] = []
    for token in _label_tokens(args.label):
        label_id = _resolve_label_id_or_exit(token, tid, f" --team {args.team}")
        if label_id not in label_ids:
            label_ids.append(label_id)
    if label_ids:
        inp["labelIds"] = label_ids
    if args.assignee:
        inp["assigneeId"] = _resolve_assignee_id_or_exit(args.assignee)

    q = """mutation($input: IssueCreateInput!) {
      issueCreate(input: $input) {
        success issue { id identifier title url }
      }
    }"""
    emit(gql(q, {"input": inp}).get("issueCreate"))


def cmd_update_issue(args: argparse.Namespace) -> None:
    inp: dict[str, Any] = {}
    if args.title:
        inp["title"] = args.title
    if args.description:
        inp["description"] = args.description
    if args.priority is not None:
        inp["priority"] = args.priority
    if args.label:
        # issueUpdate REPLACES the whole label set, so fetch the issue's current
        # labels (and team) up front and append to them — we never silently drop
        # labels the caller didn't mention. Labels are team-scoped, so resolve
        # within the issue's team (or an explicit --team), falling back to a
        # workspace-wide search.
        issue = gql(
            "query($id: String!) { issue(id: $id) { team { id } labels { nodes { id } } } }",
            {"id": args.identifier},
        ).get("issue")
        if not issue:
            sys.stderr.write(f"Issue not found: {args.identifier}\n")
            sys.exit(1)
        if args.team:
            team_id = _resolve_team_id(args.team)
            if not team_id:
                sys.stderr.write(f"Team not found: {args.team}\n")
                sys.exit(1)
        else:
            team_id = (issue.get("team") or {}).get("id")
        label_ids = [lbl["id"] for lbl in (issue.get("labels") or {}).get("nodes", [])]
        for token in _label_tokens(args.label):
            label_id = _resolve_label_id_or_exit(token, team_id, " --team <KEY>")
            if label_id not in label_ids:
                label_ids.append(label_id)
        inp["labelIds"] = label_ids
    if args.assignee:
        inp["assigneeId"] = _resolve_assignee_id_or_exit(args.assignee)
    if not inp:
        sys.stderr.write("No update fields provided.\n")
        sys.exit(1)
    q = """mutation($id: String!, $input: IssueUpdateInput!) {
      issueUpdate(id: $id, input: $input) {
        success issue { identifier title url }
      }
    }"""
    emit(gql(q, {"id": args.identifier, "input": inp}).get("issueUpdate"))


def cmd_update_status(args: argparse.Namespace) -> None:
    # Resolve state name -> id within the issue's team
    get_q = """query($id: String!) {
      issue(id: $id) { team { id states(first: 100) { nodes { id name } } } }
    }"""
    issue = gql(get_q, {"id": args.identifier}).get("issue")
    if not issue:
        sys.stderr.write(f"Issue not found: {args.identifier}\n")
        sys.exit(1)
    sl = args.state.lower()
    match = next((s for s in issue["team"]["states"]["nodes"] if s["name"].lower() == sl), None)
    if not match:
        sys.stderr.write(
            f"State '{args.state}' not found. Available: "
            f"{[s['name'] for s in issue['team']['states']['nodes']]}\n"
        )
        sys.exit(1)

    q = """mutation($id: String!, $stateId: String!) {
      issueUpdate(id: $id, input: { stateId: $stateId }) {
        success issue { identifier state { name } url }
      }
    }"""
    emit(gql(q, {"id": args.identifier, "stateId": match["id"]}).get("issueUpdate"))


def cmd_list_labels(args: argparse.Namespace) -> None:
    if args.team:
        tid = _resolve_team_id(args.team)
        if not tid:
            sys.stderr.write(f"Team not found: {args.team}\n")
            sys.exit(1)
        q = """query($teamId: String!, $first: Int!, $after: String) {
          team(id: $teamId) {
            labels(first: $first, after: $after) {
              nodes { id name color } pageInfo { hasNextPage endCursor }
            }
          }
        }"""
        emit(_paginate(q, ["team", "labels"], {"teamId": tid}))
    else:
        q = """query($first: Int!, $after: String) {
          issueLabels(first: $first, after: $after) {
            nodes { id name color } pageInfo { hasNextPage endCursor }
          }
        }"""
        emit(_paginate(q, ["issueLabels"]))


def cmd_list_users(_args: argparse.Namespace) -> None:
    q = """query($first: Int!, $after: String) {
      users(first: $first, after: $after) {
        nodes { id name displayName email active } pageInfo { hasNextPage endCursor }
      }
    }"""
    emit(_paginate(q, ["users"]))


def cmd_add_comment(args: argparse.Namespace) -> None:
    q = """mutation($input: CommentCreateInput!) {
      commentCreate(input: $input) {
        success comment { id body createdAt }
      }
    }"""
    emit(gql(q, {"input": {"issueId": args.identifier, "body": args.body}}).get("commentCreate"))


# ---- Documents ----

def cmd_list_documents(args: argparse.Namespace) -> None:
    q = """query($first: Int!) {
      documents(first: $first, orderBy: updatedAt) {
        nodes { id title slugId updatedAt url project { name } creator { name } }
      }
    }"""
    emit(gql(q, {"first": args.limit}).get("documents", {}).get("nodes", []))


def cmd_get_document(args: argparse.Namespace) -> None:
    """Fetch a document by slugId (from URL) OR full UUID.

    Linear document URLs look like:
      https://linear.app/<workspace>/document/<slug>-<shortid>
    The part we want is the final hex segment (the slugId).
    """
    ref = args.ref
    # If it looks like a UUID, query by id. Otherwise, assume slugId.
    is_uuid = len(ref) == 36 and ref.count("-") == 4
    if is_uuid:
        q = """query($id: String!) {
          document(id: $id) {
            id title content contentState slugId
            createdAt updatedAt url
            creator { name } project { name }
          }
        }"""
        emit(gql(q, {"id": ref}).get("document"))
    else:
        # Query the collection and filter by slugId — the doc() query only accepts UUIDs.
        q = """query($slug: String!) {
          documents(filter: { slugId: { eq: $slug } }, first: 1) {
            nodes {
              id title content contentState slugId
              createdAt updatedAt url
              creator { name } project { name }
            }
          }
        }"""
        nodes = gql(q, {"slug": ref}).get("documents", {}).get("nodes", [])
        emit(nodes[0] if nodes else None)


def cmd_search_documents(args: argparse.Namespace) -> None:
    # Linear doesn't have a first-class searchDocuments — use title filter as a fallback.
    q = """query($term: String!, $first: Int!) {
      documents(filter: { title: { containsIgnoreCase: $term } }, first: $first) {
        nodes { id title slugId url updatedAt }
      }
    }"""
    emit(gql(q, {"term": args.query, "first": args.limit}).get("documents", {}).get("nodes", []))


def cmd_raw(args: argparse.Namespace) -> None:
    variables = json.loads(args.vars) if args.vars else None
    emit(gql(args.query, variables))


# ---------- Arg parsing ----------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="linear_api.py", description="Linear GraphQL CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("whoami").set_defaults(func=cmd_whoami)
    sub.add_parser("list-teams").set_defaults(func=cmd_list_teams)

    lp = sub.add_parser("list-projects")
    lp.add_argument("--team")
    lp.set_defaults(func=cmd_list_projects)

    ls = sub.add_parser("list-states")
    ls.add_argument("--team")
    ls.set_defaults(func=cmd_list_states)

    ll = sub.add_parser("list-labels")
    ll.add_argument("--team")
    ll.set_defaults(func=cmd_list_labels)

    lu = sub.add_parser("list-users")
    lu.set_defaults(func=cmd_list_users)

    li = sub.add_parser("list-issues")
    li.add_argument("--team")
    li.add_argument("--status")
    li.add_argument("--assignee")
    li.add_argument("--label")
    li.add_argument("--limit", type=int, default=25)
    li.set_defaults(func=cmd_list_issues)

    gi = sub.add_parser("get-issue")
    gi.add_argument("identifier")
    gi.set_defaults(func=cmd_get_issue)

    si = sub.add_parser("search-issues")
    si.add_argument("query")
    si.add_argument("--limit", type=int, default=25)
    si.set_defaults(func=cmd_search_issues)

    ci = sub.add_parser("create-issue")
    ci.add_argument("--title", required=True)
    ci.add_argument("--team", required=True)
    ci.add_argument("--description")
    ci.add_argument("--priority", type=int, choices=[0, 1, 2, 3, 4])
    ci.add_argument("--label", action="append", help="Label name; repeat or comma-separate for several")
    ci.add_argument("--assignee", help="Name, email, or 'me'")
    ci.add_argument("--parent")
    ci.set_defaults(func=cmd_create_issue)

    ui = sub.add_parser("update-issue")
    ui.add_argument("identifier")
    ui.add_argument("--title")
    ui.add_argument("--description")
    ui.add_argument("--priority", type=int, choices=[0, 1, 2, 3, 4])
    ui.add_argument("--label", action="append", help="Label name to add; repeat or comma-separate for several")
    ui.add_argument("--assignee", help="Name, email, or 'me'")
    ui.add_argument("--team", help="Scope --label lookup; inferred from the issue if omitted")
    ui.set_defaults(func=cmd_update_issue)

    us = sub.add_parser("update-status")
    us.add_argument("identifier")
    us.add_argument("state")
    us.set_defaults(func=cmd_update_status)

    ac = sub.add_parser("add-comment")
    ac.add_argument("identifier")
    ac.add_argument("body")
    ac.set_defaults(func=cmd_add_comment)

    ld = sub.add_parser("list-documents")
    ld.add_argument("--limit", type=int, default=50)
    ld.set_defaults(func=cmd_list_documents)

    gd = sub.add_parser("get-document")
    gd.add_argument("ref", help="slugId (hex suffix from URL) or full UUID")
    gd.set_defaults(func=cmd_get_document)

    sd = sub.add_parser("search-documents")
    sd.add_argument("query")
    sd.add_argument("--limit", type=int, default=25)
    sd.set_defaults(func=cmd_search_documents)

    r = sub.add_parser("raw")
    r.add_argument("query")
    r.add_argument("--vars", help="JSON string of variables")
    r.set_defaults(func=cmd_raw)

    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
