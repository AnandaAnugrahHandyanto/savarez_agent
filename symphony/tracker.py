"""Small injectable Linear GraphQL tracker client."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from typing import Any

from symphony.errors import SymphonyError
from symphony.models import Issue

Transport = Callable[[str, dict[str, Any]], dict[str, Any]]


CANDIDATE_ISSUES_QUERY = """
query CandidateIssues($projectSlug: String!, $activeStates: [String!]!, $first: Int!, $after: String) {
  issues(
    first: $first
    after: $after
    filter: {
      project: { slugId: { eq: $projectSlug } }
      state: { name: { in: $activeStates } }
    }
  ) {
    nodes {
      id
      identifier
      title
      url
      state { name }
      labels { nodes { name } }
      priority
      relations { nodes { type relatedIssue { id } issue { id } } }
      createdAt
    }
    pageInfo { hasNextPage endCursor }
  }
}
""".strip()


ISSUE_STATES_QUERY = """
query IssueStates($ids: [ID!]!) {
  issues(filter: { id: { in: $ids } }) {
    nodes { id state { name } }
  }
}
""".strip()

CLAIM_ISSUE_MUTATION = """
mutation ClaimIssue($issueId: String!, $body: String!) {
  commentCreate(input: { issueId: $issueId, body: $body }) { success }
}
""".strip()

POST_COMMENT_MUTATION = """
mutation PostComment($issueId: String!, $body: String!) {
  commentCreate(input: { issueId: $issueId, body: $body }) { success }
}
""".strip()


class LinearTrackerClient:
    """Linear GraphQL client with injectable transport for deterministic tests."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def fetch_candidate_issues(
        self,
        project_slug: str = "KATO",
        active_states: list[str] | None = None,
        first: int = 50,
        after: str | None = None,
    ) -> list[Issue]:
        if active_states is None:
            active_states = ["Todo", "In Progress"]
        variables = {
            "projectSlug": project_slug,
            "activeStates": active_states,
            "first": first,
            "after": after,
        }
        payload = self._execute(CANDIDATE_ISSUES_QUERY, variables)
        try:
            nodes = payload["data"]["issues"]["nodes"]
            if not isinstance(nodes, list):
                raise TypeError("issues.nodes is not a list")
            return [normalize_issue_payload(node) for node in nodes]
        except SymphonyError:
            raise
        except Exception as exc:
            raise SymphonyError("linear_malformed_payload", "Malformed Linear candidate issue payload") from exc

    def fetch_issue_states_by_ids(self, ids: Iterable[str]) -> dict[str, str]:
        variables = {"ids": list(ids)}
        payload = self._execute(ISSUE_STATES_QUERY, variables)
        try:
            nodes = payload["data"]["issues"]["nodes"]
            if not isinstance(nodes, list):
                raise TypeError("issues.nodes is not a list")
            states: dict[str, str] = {}
            for node in nodes:
                issue_id = _required_str(node, "id")
                state = _extract_state_name(node)
                states[issue_id] = state
            return states
        except Exception as exc:
            raise SymphonyError("linear_malformed_payload", "Malformed Linear issue state payload") from exc

    def claim_issue(self, issue_id: str, *, comment: str) -> bool:
        """Best-effort Linear claim marker used before runner dispatch."""

        payload = self._execute(CLAIM_ISSUE_MUTATION, {"issueId": issue_id, "body": comment})
        return _mutation_success(payload, "commentCreate")

    def post_comment(self, issue_id: str, body: str) -> None:
        """Post a run status/evidence comment to Linear."""

        payload = self._execute(POST_COMMENT_MUTATION, {"issueId": issue_id, "body": body})
        if not _mutation_success(payload, "commentCreate"):
            raise SymphonyError("linear_malformed_payload", "Malformed Linear comment mutation payload")

    def _execute(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        try:
            payload = self._transport(query, variables)
        except Exception as exc:
            raise SymphonyError("linear_transport_error", "Linear transport failed") from exc

        if not isinstance(payload, dict):
            raise SymphonyError("linear_malformed_payload", "Malformed Linear GraphQL response")
        status_code = payload.get("status_code")
        if isinstance(status_code, int) and status_code >= 400:
            raise SymphonyError("linear_transport_error", f"Linear transport returned HTTP {status_code}")
        errors = payload.get("errors")
        if errors:
            raise SymphonyError("linear_graphql_error", "Linear GraphQL response contained errors")
        return payload


def linear_http_transport(api_key: str, *, endpoint: str = "https://api.linear.app/graphql") -> Transport:
    """Return a urllib-based Linear GraphQL transport."""

    def transport(query: str, variables: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            endpoint,
            data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
            headers={
                "Authorization": api_key,
                "Content-Type": "application/json",
                "User-Agent": "hermes-symphony/0.1",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - configured HTTPS endpoint.
                body = response.read().decode("utf-8")
                payload = json.loads(body) if body else {}
                if isinstance(payload, dict):
                    payload.setdefault("status_code", response.status)
                    return payload
                return {"status_code": response.status, "body": payload}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(body) if body else {}
            except json.JSONDecodeError:
                payload = {"body": body}
            if isinstance(payload, dict):
                payload["status_code"] = exc.code
                return payload
            return {"status_code": exc.code, "body": payload}

    return transport


def normalize_issue_payload(payload: dict[str, Any]) -> Issue:
    """Normalize one Linear issue node into an Issue dataclass."""

    try:
        if not isinstance(payload, dict):
            raise TypeError("issue payload is not a dict")
        priority = payload.get("priority")
        if priority is not None and not isinstance(priority, int):
            raise TypeError("priority is not an int or None")
        return Issue(
            id=_required_str(payload, "id"),
            identifier=_required_str(payload, "identifier"),
            title=_required_str(payload, "title"),
            url=_required_str(payload, "url"),
            state=_extract_state_name(payload),
            labels=_extract_labels(payload),
            priority=priority,
            blocked_by_ids=_extract_blocked_by_ids(payload),
            created_at=_required_str(payload, "createdAt"),
        )
    except SymphonyError:
        raise
    except Exception as exc:
        raise SymphonyError("linear_malformed_payload", "Malformed Linear issue payload") from exc


def _mutation_success(payload: dict[str, Any], field: str) -> bool:
    try:
        value = payload["data"][field]["success"]
    except Exception as exc:
        raise SymphonyError("linear_malformed_payload", "Malformed Linear mutation payload") from exc
    if not isinstance(value, bool):
        raise SymphonyError("linear_malformed_payload", "Malformed Linear mutation payload")
    return value


def _required_str(mapping: dict[str, Any], key: str) -> str:
    value = mapping[key]
    if not isinstance(value, str):
        raise TypeError(f"{key} is not a string")
    return value


def _extract_state_name(payload: dict[str, Any]) -> str:
    state = payload["state"]
    if isinstance(state, str):
        return state
    if isinstance(state, dict):
        name = state["name"]
        if isinstance(name, str):
            return name
    raise TypeError("state name is malformed")


def _extract_labels(payload: dict[str, Any]) -> list[str]:
    labels = payload.get("labels", {})
    nodes = labels.get("nodes", []) if isinstance(labels, dict) else []
    if not isinstance(nodes, list):
        raise TypeError("labels.nodes is not a list")
    normalized: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            raise TypeError("label node is not a dict")
        name = node.get("name")
        if not isinstance(name, str):
            raise TypeError("label name is not a string")
        normalized.append(name.lower())
    return normalized


def _extract_blocked_by_ids(payload: dict[str, Any]) -> list[str]:
    relations = payload.get("relations", {})
    nodes = relations.get("nodes", []) if isinstance(relations, dict) else []
    if not isinstance(nodes, list):
        raise TypeError("relations.nodes is not a list")

    blocked_by_ids: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            raise TypeError("relation node is not a dict")
        relation_type = node.get("type")
        if not isinstance(relation_type, str):
            continue
        if relation_type.lower() not in {"blocked_by", "blockedby", "blocks"}:
            continue
        blocker = _blocker_from_relation(payload["id"], node)
        if blocker is not None and blocker not in blocked_by_ids:
            blocked_by_ids.append(blocker)
    return blocked_by_ids


def _blocker_from_relation(issue_id: str, relation: dict[str, Any]) -> str | None:
    relation_type = str(relation.get("type", "")).lower()
    related_issue = relation.get("relatedIssue")
    issue = relation.get("issue")

    if relation_type in {"blocked_by", "blockedby"}:
        return _optional_issue_id(related_issue)

    # Linear relation shapes can encode blocking as "issue blocks relatedIssue".
    # For the current issue, only the opposite side is a blocker.
    if relation_type == "blocks" and _optional_issue_id(related_issue) == issue_id:
        return _optional_issue_id(issue)
    return None


def _optional_issue_id(value: Any) -> str | None:
    if isinstance(value, dict) and isinstance(value.get("id"), str):
        return value["id"]
    return None
