"""Tests for card-prep chat on Kanban cards."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hermes_cli import kanban_card_chat as card_chat
from hermes_cli import kanban_db as kb


@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


def _fake_aux_response(content: str):
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    return resp


def _patch_aux_client(content: str):
    client = MagicMock()
    client.chat.completions.create = MagicMock(return_value=_fake_aux_response(content))
    return patch(
        "agent.auxiliary_client.get_text_auxiliary_client",
        return_value=(client, "test-model"),
    ), client


def test_chat_on_card_live_edits_body_and_records_transcript(kanban_home):
    with kb.connect() as conn:
        tid = kb.create_task(
            conn,
            title="rough card",
            body="need dashboard card prep",
            tenant="mix",
        )

    body = """**Goal**
Let users prep cards with Rolly.

**Context/source**
Source: Deniz asked for card-level conversation that live modifies card contents.

**Scope**
- Add a card prep chat control in the drawer.

**Acceptance criteria**
- Sending one message updates the visible card body without page reload.
- The Rolly reply is stored in comments.
- Missing readiness items are listed when acceptance or verification is incomplete.

**Verification**
Run targeted kanban card chat tests.

**Handoff notes**
Use auxiliary LLM, no fake data.
"""
    content = json.dumps({
        "reply": "I tightened it; missing only explicit human approval.",
        "title": "Add Rolly card prep chat",
        "body": body,
        "ready": False,
        "missing": ["explicit human approval"],
    })
    p, client = _patch_aux_client(content)
    with p:
        outcome = card_chat.chat_on_card(
            tid,
            "update the card to make it ready for ai handoff",
            author="deniz",
        )

    assert outcome.ok is True
    assert outcome.title == "Add Rolly card prep chat"
    assert outcome.missing == ("explicit human approval",)
    assert client.chat.completions.create.call_count == 1

    with kb.connect() as conn:
        task = kb.get_task(conn, tid)
        comments = kb.list_comments(conn, tid)
        events = kb.list_events(conn, tid)

    assert task.title == "Add Rolly card prep chat"
    assert "**Acceptance criteria**" in (task.body or "")
    assert [c.author for c in comments] == ["deniz", "rolly"]
    assert comments[0].body == "update the card to make it ready for ai handoff"
    assert "I tightened it" in comments[1].body
    assert any(e.kind == "card_chat" for e in events)


def test_chat_on_card_prompt_treats_acceptance_help_as_first_class(kanban_home):
    with kb.connect() as conn:
        tid = kb.create_task(conn, title="rough card", body="Goal: improve cards")

    content = json.dumps({
        "reply": "Good start. What would make this accepted?",
        "title": None,
        "body": None,
        "ready": False,
        "missing": ["acceptance criteria"],
    })
    p, client = _patch_aux_client(content)
    with p:
        outcome = card_chat.chat_on_card(tid, "help me write acceptance criteria", author="deniz")

    assert outcome.ok is True
    messages = client.chat.completions.create.call_args.kwargs["messages"]
    system_prompt = messages[0]["content"]
    assert "first-class job is helping the human create acceptance criteria" in system_prompt
    assert "title/body must be null" in system_prompt

    with kb.connect() as conn:
        task = kb.get_task(conn, tid)
        comments = kb.list_comments(conn, tid)
    assert task is not None
    assert task.body == "Goal: improve cards"
    assert [c.author for c in comments] == ["deniz", "rolly"]


def test_chat_on_card_ignores_unsolicited_card_edits(kanban_home):
    with kb.connect() as conn:
        tid = kb.create_task(conn, title="rough card", body="original")

    content = json.dumps({
        "reply": "Here is a possible tighter shape.",
        "title": "New title",
        "body": "new body",
        "ready": False,
        "missing": ["approval"],
    })
    p, _client = _patch_aux_client(content)
    with p:
        outcome = card_chat.chat_on_card(tid, "help me think this through", author="deniz")

    assert outcome.ok is True
    assert outcome.title is None
    assert outcome.body is None
    with kb.connect() as conn:
        task = kb.get_task(conn, tid)
        comments = kb.list_comments(conn, tid)
    assert task is not None
    assert task.title == "rough card"
    assert task.body == "original"
    assert [c.author for c in comments] == ["deniz", "rolly"]


def test_chat_on_card_rejects_empty_message_without_llm(kanban_home):
    with kb.connect() as conn:
        tid = kb.create_task(conn, title="rough card")

    p, client = _patch_aux_client("unused")
    with p:
        outcome = card_chat.chat_on_card(tid, "   ")

    assert outcome.ok is False
    assert "message is required" in outcome.reason
    assert client.chat.completions.create.call_count == 0


def test_chat_on_card_malformed_json_does_not_edit(kanban_home):
    with kb.connect() as conn:
        tid = kb.create_task(conn, title="rough card", body="original")

    p, _client = _patch_aux_client("not json")
    with p:
        outcome = card_chat.chat_on_card(tid, "tighten it")

    assert outcome.ok is False
    assert "malformed JSON" in outcome.reason
    with kb.connect() as conn:
        task = kb.get_task(conn, tid)
        comments = kb.list_comments(conn, tid)
    assert task.body == "original"
    assert comments == []
