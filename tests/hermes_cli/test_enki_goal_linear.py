"""Tests for Enki's Linear-aware layer around upstream /goal."""

from __future__ import annotations

from dataclasses import replace


class FakeStore:
    def __init__(self):
        self.links = {}
        self.tasks_by_fingerprint = {}
        self.created_tasks = []
        self.upserted_links = []

    def find_link_by_fingerprint(self, fingerprint):
        return self.links.get(fingerprint)

    def find_task_by_goal_fingerprint(self, fingerprint):
        return self.tasks_by_fingerprint.get(fingerprint)

    def create_task_for_goal(self, *, goal, fingerprint, issue=None):
        task = {
            "task_id": f"task-{len(self.created_tasks) + 1}",
            "title": goal,
            "goal_fingerprint": fingerprint,
            "linear_issue_id": issue.issue_id if issue else None,
            "linear_identifier": issue.identifier if issue else None,
            "linear_url": issue.url if issue else None,
        }
        self.created_tasks.append(task)
        self.tasks_by_fingerprint[fingerprint] = task
        return task

    def upsert_goal_link(self, link):
        self.upserted_links.append(link)
        self.links[link.goal_fingerprint] = link
        return link


class FakeLinear:
    def __init__(self, existing=None):
        self.existing = existing
        self.created = []

    def find_issue_for_goal(self, goal, fingerprint):
        return self.existing

    def create_issue_for_goal(self, goal):
        from hermes_cli.enki_goal_linear import LinearIssue

        issue = LinearIssue(
            issue_id=f"issue-{len(self.created) + 1}",
            identifier=f"ENK-{len(self.created) + 100}",
            title=goal,
            url=f"https://linear.app/enki-arno/issue/ENK-{len(self.created) + 100}",
        )
        self.created.append(issue)
        return issue


def test_goal_fingerprint_normalizes_case_and_spacing():
    from hermes_cli.enki_goal_linear import goal_fingerprint

    assert goal_fingerprint("  Ship   the Thing\n") == goal_fingerprint("ship the thing")
    assert goal_fingerprint("ship the thing") != goal_fingerprint("ship another thing")


def test_ensure_goal_linear_link_reuses_existing_mapping_without_creating_ticket():
    from hermes_cli.enki_goal_linear import GoalLinearLink, ensure_goal_linear_link, goal_fingerprint

    fp = goal_fingerprint("Ship the thing")
    existing = GoalLinearLink(
        session_id="old-session",
        goal="Ship the thing",
        goal_fingerprint=fp,
        task_id="task-1",
        linear_issue_id="issue-1",
        linear_identifier="ENK-1",
        linear_url="https://linear.app/enki-arno/issue/ENK-1/ship-the-thing",
        source="existing-link",
    )
    store = FakeStore()
    store.links[fp] = existing
    linear = FakeLinear()

    link = ensure_goal_linear_link("new-session", "Ship the thing", store=store, linear=linear)

    assert link.session_id == "new-session"
    assert link.task_id == "task-1"
    assert link.linear_identifier == "ENK-1"
    assert link.source == "existing-link"
    assert linear.created == []
    assert store.created_tasks == []
    assert store.upserted_links[-1] == link


def test_ensure_goal_linear_link_attaches_existing_linear_issue_and_creates_local_task():
    from hermes_cli.enki_goal_linear import LinearIssue, ensure_goal_linear_link

    issue = LinearIssue(
        issue_id="issue-2",
        identifier="ENK-2",
        title="Integrate /goal with Linear",
        url="https://linear.app/enki-arno/issue/ENK-2/integrate-goal-with-linear",
    )
    store = FakeStore()
    linear = FakeLinear(existing=issue)

    link = ensure_goal_linear_link("session-2", "Integrate /goal with Linear", store=store, linear=linear)

    assert link.task_id == "task-1"
    assert link.linear_issue_id == "issue-2"
    assert link.linear_identifier == "ENK-2"
    assert link.source == "existing-linear"
    assert len(store.created_tasks) == 1
    assert linear.created == []


def test_ensure_goal_linear_link_creates_ticket_when_no_match_exists():
    from hermes_cli.enki_goal_linear import ensure_goal_linear_link

    store = FakeStore()
    linear = FakeLinear()

    link = ensure_goal_linear_link("session-3", "Create a mapped goal", store=store, linear=linear)

    assert link.task_id == "task-1"
    assert link.linear_identifier == "ENK-100"
    assert link.source == "created"
    assert len(linear.created) == 1
    assert len(store.created_tasks) == 1
    assert store.upserted_links[-1] == link


def test_should_run_task_as_goal_is_explicit_and_conservative():
    from hermes_cli.enki_goal_linear import should_run_task_as_goal

    assert should_run_task_as_goal({"title": "small task", "context_md": "do one thing"}) is False
    assert should_run_task_as_goal({"title": "[enki-goal] durable objective", "context_md": ""}) is True
    assert should_run_task_as_goal({"title": "big task", "labels": ["standing-goal"]}) is True
    assert should_run_task_as_goal({"title": "big scoped task", "linear_estimate": 8, "context_md": "clear acceptance criteria"}) is True
    assert should_run_task_as_goal({"title": "blocked goal", "labels": ["standing-goal"], "requires_user_action": True}) is False


def test_goal_text_from_task_includes_linear_identifier_and_acceptance_context():
    from hermes_cli.enki_goal_linear import goal_text_from_task

    text = goal_text_from_task({
        "linear_identifier": "ENK-38",
        "title": "Integrate upstream /goal with Linear tickets",
        "context_md": "Acceptance: mapping table exists and dispatcher can attach.",
    })

    assert "ENK-38" in text
    assert "Integrate upstream /goal" in text
    assert "Acceptance: mapping table exists" in text
