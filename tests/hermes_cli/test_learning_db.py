"""Tests for the Learning store (hermes_cli.learning_db).

Covers the SM-2 spaced-repetition logic, the weak-spot signal, and a basic
topic/lesson/card round trip. The DB path is pinned to a tmp file via
``HERMES_LEARNING_DB`` so tests never touch the real ~/.hermes/learning.db.
"""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture()
def L(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_LEARNING_DB", str(tmp_path / "learning.db"))
    import hermes_cli.learning_db as learning_db

    importlib.reload(learning_db)
    return learning_db


def _make_card(L, conn):
    tid = L.create_topic(conn, title="Python", goal="basics")
    cid = L.add_card(conn, topic_id=tid, question="q?", answer="a")
    return tid, cid


def test_topic_lesson_card_round_trip(L):
    with L.connect_closing() as conn:
        tid = L.create_topic(conn, title="Mortgages", cadence="every Sunday")
        assert L.get_topic(conn, tid).title == "Mortgages"
        # Case-insensitive title lookup avoids duplicate topics.
        assert L.find_topic_by_title(conn, "mortgages").id == tid

        lid = L.add_lesson(conn, topic_id=tid, title="APR", status="planned")
        assert L.next_planned_lesson(conn, tid).id == lid
        L.mark_lesson_taught(conn, lid, summary="annual rate")
        assert L.next_planned_lesson(conn, tid) is None
        assert L.get_topic(conn, tid).last_taught_at is not None


def test_sm2_miss_resets_and_increments_lapses(L):
    with L.connect_closing() as conn:
        _, cid = _make_card(L, conn)
        res = L.record_attempt(conn, card_id=cid, grade=2, user_answer="wrong")
        assert res["correct"] is False
        assert res["lapses"] == 1
        assert res["interval_days"] == 1
        # The missed card is now a weak spot.
        weak = L.weak_spots(conn, L.get_card(conn, cid).topic_id)
        assert len(weak) == 1 and weak[0].id == cid


def test_sm2_pass_grows_interval(L):
    with L.connect_closing() as conn:
        _, cid = _make_card(L, conn)
        intervals = []
        for _ in range(3):
            res = L.record_attempt(conn, card_id=cid, grade=5)
            intervals.append(res["interval_days"])
        # Classic SM-2 ramp: 1 -> 6 -> >6.
        assert intervals[0] == 1
        assert intervals[1] == 6
        assert intervals[2] > 6
        assert res["correct"] is True


def test_pure_sm2_update_is_side_effect_free(L):
    with L.connect_closing() as conn:
        _, cid = _make_card(L, conn)
        card = L.get_card(conn, cid)
    # No DB write — just the math.
    new = L.sm2_update(card, 5)
    assert new["reps"] == 1
    assert new["interval_days"] == 1
    assert new["ease"] >= L.SM2_MIN_EASE


def test_progress_accuracy(L):
    with L.connect_closing() as conn:
        tid, cid = _make_card(L, conn)
        L.record_attempt(conn, card_id=cid, grade=5)  # correct
        L.record_attempt(conn, card_id=cid, grade=1)  # miss
        prog = L.topic_progress(conn, tid)
        assert prog["attempts_total"] == 2
        assert prog["accuracy"] == 0.5
        assert prog["weak_spots"] == 1
