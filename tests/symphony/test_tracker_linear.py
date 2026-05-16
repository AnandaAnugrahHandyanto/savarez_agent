import pytest

from symphony.errors import SymphonyError
from symphony.models import Issue
from symphony.tracker import LinearTrackerClient, normalize_issue_payload


def linear_issue_payload(**overrides):
    payload = {
        "id": "issue-id-1",
        "identifier": "KATO-123",
        "title": "Implement tracker",
        "url": "https://linear.app/acme/issue/KATO-123/implement-tracker",
        "state": {"name": "Todo"},
        "labels": {"nodes": [{"name": "Backend"}, {"name": "SYMPHONY"}]},
        "priority": 2,
        "relations": {
            "nodes": [
                {
                    "type": "blocks",
                    "relatedIssue": {"id": "blocked-issue-id"},
                    "issue": {"id": "issue-id-1"},
                },
                {
                    "type": "blocked_by",
                    "relatedIssue": {"id": "blocker-id-1"},
                },
                {
                    "type": "related",
                    "relatedIssue": {"id": "not-a-blocker"},
                },
            ]
        },
        "createdAt": "2026-05-14T00:00:00.000Z",
    }
    payload.update(overrides)
    return payload


def test_normalize_issue_payload_returns_issue_dataclass_with_lowercase_labels_and_blockers():
    issue = normalize_issue_payload(linear_issue_payload(priority=None))

    assert issue == Issue(
        id="issue-id-1",
        identifier="KATO-123",
        title="Implement tracker",
        url="https://linear.app/acme/issue/KATO-123/implement-tracker",
        state="Todo",
        labels=["backend", "symphony"],
        priority=None,
        blocked_by_ids=["blocker-id-1"],
        created_at="2026-05-14T00:00:00.000Z",
    )


def test_fetch_candidate_issues_sends_project_slug_active_states_first_and_after():
    calls = []

    def transport(query, variables):
        calls.append((query, variables))
        return {"data": {"issues": {"nodes": [linear_issue_payload()], "pageInfo": {"hasNextPage": False, "endCursor": None}}}}

    client = LinearTrackerClient(transport=transport)
    issues = client.fetch_candidate_issues(
        project_slug="KATO",
        active_states=["Todo", "In Progress"],
        first=50,
        after="cursor-1",
    )

    assert len(issues) == 1
    query, variables = calls[0]
    assert "project: { slugId: { eq: $projectSlug } }" in query
    assert "state: { name: { in: $activeStates } }" in query
    assert "$after" in query
    assert variables == {
        "projectSlug": "KATO",
        "activeStates": ["Todo", "In Progress"],
        "first": 50,
        "after": "cursor-1",
    }


def test_fetch_issue_states_by_ids_uses_id_list_variable():
    calls = []

    def transport(query, variables):
        calls.append((query, variables))
        return {"data": {"issues": {"nodes": [{"id": "issue-id-1", "state": {"name": "Done"}}]}}}

    states = LinearTrackerClient(transport=transport).fetch_issue_states_by_ids(["issue-id-1"])

    query, variables = calls[0]
    assert "$ids: [ID!]" in query
    assert variables == {"ids": ["issue-id-1"]}
    assert states == {"issue-id-1": "Done"}


def test_claim_issue_posts_linear_comment_and_returns_success():
    calls = []

    def transport(query, variables):
        calls.append((query, variables))
        return {"data": {"commentCreate": {"success": True}}}

    claimed = LinearTrackerClient(transport=transport).claim_issue("issue-id-1", comment="claimed")

    query, variables = calls[0]
    assert "commentCreate" in query
    assert variables == {"issueId": "issue-id-1", "body": "claimed"}
    assert claimed is True


def test_post_comment_raises_when_mutation_payload_is_malformed():
    def transport(query, variables):
        return {"data": {"commentCreate": {"success": "yes"}}}

    with pytest.raises(SymphonyError) as exc_info:
        LinearTrackerClient(transport=transport).post_comment("issue-id-1", "done")

    assert exc_info.value.code == "linear_malformed_payload"


def test_transport_exception_maps_to_symphony_error():
    def transport(query, variables):
        raise RuntimeError("network down")

    with pytest.raises(SymphonyError) as exc_info:
        LinearTrackerClient(transport=transport).fetch_candidate_issues()

    assert exc_info.value.code == "linear_transport_error"


def test_graphql_errors_map_to_symphony_error():
    def transport(query, variables):
        return {"errors": [{"message": "bad query"}]}

    with pytest.raises(SymphonyError) as exc_info:
        LinearTrackerClient(transport=transport).fetch_issue_states_by_ids(["issue-id-1"])

    assert exc_info.value.code == "linear_graphql_error"


def test_malformed_payload_maps_to_symphony_error():
    def transport(query, variables):
        return {"data": {"issues": {"nodes": [{"id": "missing required fields"}]}}}

    with pytest.raises(SymphonyError) as exc_info:
        LinearTrackerClient(transport=transport).fetch_candidate_issues()

    assert exc_info.value.code == "linear_malformed_payload"


def test_non_200_transport_payload_maps_to_transport_error():
    def transport(query, variables):
        return {"status_code": 500, "body": "server error"}

    with pytest.raises(SymphonyError) as exc_info:
        LinearTrackerClient(transport=transport).fetch_candidate_issues()

    assert exc_info.value.code == "linear_transport_error"
