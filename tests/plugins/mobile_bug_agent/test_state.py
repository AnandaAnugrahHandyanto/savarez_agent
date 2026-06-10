from __future__ import annotations

import sqlite3

from plugins.mobile_bug_agent.state import MonicaState


def test_state_can_store_full_run_metadata(tmp_path):
    state = MonicaState.open(tmp_path / "monica.sqlite")
    run = state.create_run(
        platform="slack",
        channel_id="C123",
        thread_ts="1710000000.000100",
        message_ts="1710000000.000100",
        user_id="U123",
        request_text="@monica fix checkout crash",
    )

    state.update_run(
        run.id,
        status="done",
        linear_identifier="MOB-42",
        linear_url="https://linear.app/acme/issue/MOB-42",
        branch_name="monica/MOB-42-checkout-crash",
        pr_url="https://github.com/acme/mobile/pull/123",
    )

    saved = state.get_run(run.id)
    assert saved is not None
    assert saved.status == "done"
    assert saved.linear_identifier == "MOB-42"
    assert saved.pr_url.endswith("/123")


def test_state_persists_raw_slack_payload(tmp_path):
    state = MonicaState.open(tmp_path / "monica.sqlite")
    run = state.create_run(
        platform="slack",
        channel_id="C123",
        thread_ts="1710000000.000100",
        message_ts="1710000000.000100",
        user_id="U123",
        request_text="@monica fix checkout crash",
        raw_event={
            "permalink": "https://slack/thread",
            "files": [{"id": "F1", "name": "crash.png", "mimetype": "image/png"}],
        },
    )

    saved = state.get_run(run.id)

    assert saved is not None
    assert saved.raw_event == {
        "files": [{"id": "F1", "mimetype": "image/png", "name": "crash.png"}],
        "permalink": "https://slack/thread",
    }


def test_state_migrates_existing_run_table(tmp_path):
    db_path = tmp_path / "old.sqlite"
    db = sqlite3.connect(db_path)
    db.execute(
        """
        CREATE TABLE runs (
            id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            thread_ts TEXT NOT NULL,
            message_ts TEXT NOT NULL,
            user_id TEXT NOT NULL,
            request_text TEXT NOT NULL,
            intent TEXT NOT NULL,
            status TEXT NOT NULL,
            UNIQUE(platform, channel_id, thread_ts)
        )
        """
    )
    db.execute(
        """
        INSERT INTO runs (
            id, platform, channel_id, thread_ts, message_ts, user_id,
            request_text, intent, status
        ) VALUES ('run-id', 'slack', 'C123', 'T1', 'T1', 'U1', '@monica bug', 'agentic_triage', 'queued')
        """
    )
    db.commit()
    db.close()

    state = MonicaState.open(db_path)
    run = state.get_run("run-id")

    assert run is not None
    assert run.linear_identifier == ""
    assert run.approved_by_user_id == ""
    assert run.raw_event == {}


def test_state_migration_adds_unique_thread_index_to_legacy_table(tmp_path):
    db_path = tmp_path / "old-without-index.sqlite"
    db = sqlite3.connect(db_path)
    db.execute(
        """
        CREATE TABLE runs (
            id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            thread_ts TEXT NOT NULL,
            message_ts TEXT NOT NULL,
            user_id TEXT NOT NULL,
            request_text TEXT NOT NULL,
            raw_event_json TEXT NOT NULL DEFAULT '{}',
            intent TEXT NOT NULL,
            status TEXT NOT NULL,
            linear_identifier TEXT NOT NULL DEFAULT '',
            linear_issue_id TEXT NOT NULL DEFAULT '',
            linear_url TEXT NOT NULL DEFAULT '',
            branch_name TEXT NOT NULL DEFAULT '',
            pr_url TEXT NOT NULL DEFAULT '',
            failure_reason TEXT NOT NULL DEFAULT '',
            approved_by_user_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    db.execute(
        """
        INSERT INTO runs (
            id, platform, channel_id, thread_ts, message_ts, user_id,
            request_text, raw_event_json, intent, status
        ) VALUES ('run-id', 'slack', 'C123', 'T1', 'T1', 'U1', '@monica bug', '{}', 'agentic_triage', 'queued')
        """
    )
    db.commit()
    db.close()

    state = MonicaState.open(db_path)

    with sqlite3.connect(db_path) as migrated:
        indexes = migrated.execute("PRAGMA index_list(runs)").fetchall()
        unique_indexes = {row[1] for row in indexes if row[2]}

    assert "idx_monica_runs_thread_unique" in unique_indexes
    run, created = state.create_run_once(
        platform="slack",
        channel_id="C123",
        thread_ts="T1",
        message_ts="T2",
        user_id="U2",
        request_text="@monica same thread",
    )
    assert created is False
    assert run.id == "run-id"


def test_state_migration_collapses_duplicate_legacy_thread_rows_before_indexing(tmp_path):
    db_path = tmp_path / "old-with-duplicates.sqlite"
    db = sqlite3.connect(db_path)
    db.execute(
        """
        CREATE TABLE runs (
            id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            thread_ts TEXT NOT NULL,
            message_ts TEXT NOT NULL,
            user_id TEXT NOT NULL,
            request_text TEXT NOT NULL,
            raw_event_json TEXT NOT NULL DEFAULT '{}',
            intent TEXT NOT NULL,
            status TEXT NOT NULL,
            linear_identifier TEXT NOT NULL DEFAULT '',
            linear_issue_id TEXT NOT NULL DEFAULT '',
            linear_url TEXT NOT NULL DEFAULT '',
            branch_name TEXT NOT NULL DEFAULT '',
            pr_url TEXT NOT NULL DEFAULT '',
            failure_reason TEXT NOT NULL DEFAULT '',
            approved_by_user_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    db.execute(
        """
        INSERT INTO runs (
            id, platform, channel_id, thread_ts, message_ts, user_id,
            request_text, raw_event_json, intent, status
        ) VALUES ('run-empty', 'slack', 'C123', 'T1', 'T1', 'U1', '@monica bug', '{}', 'agentic_triage', 'queued')
        """
    )
    db.execute(
        """
        INSERT INTO runs (
            id, platform, channel_id, thread_ts, message_ts, user_id,
            request_text, raw_event_json, intent, status,
            linear_identifier, linear_issue_id, linear_url, branch_name, pr_url
        ) VALUES (
            'run-done', 'slack', 'C123', 'T1', 'T2', 'U2', '@monica same bug',
            '{}', 'agentic_triage', 'done',
            'MOB-42', 'issue-id', 'https://linear.app/acme/issue/MOB-42',
            'monica/MOB-42-checkout-crash', 'https://github.com/acme/mobile/pull/42'
        )
        """
    )
    db.commit()
    db.close()

    state = MonicaState.open(db_path)

    runs = state.list_runs()
    assert [run.id for run in runs] == ["run-done"]
    assert runs[0].linear_identifier == "MOB-42"
    assert runs[0].pr_url.endswith("/42")
    run, created = state.create_run_once(
        platform="slack",
        channel_id="C123",
        thread_ts="T1",
        message_ts="T3",
        user_id="U3",
        request_text="@monica duplicate attempt",
    )
    assert created is False
    assert run.id == "run-done"
