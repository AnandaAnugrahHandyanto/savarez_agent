"""Tests for publishing Hermes daily usage reports to Feishu/Lark docs."""

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from hermes_state import SessionDB
from agent import daily_report_publisher as publisher


@pytest.fixture()
def db(tmp_path):
    db_path = tmp_path / "daily_report.db"
    session_db = SessionDB(db_path=db_path)
    yield session_db
    session_db.close()


def _seed_daily_session(db: SessionDB) -> None:
    db.create_session(
        session_id="daily-1",
        source="feishu",
        model="anthropic/claude-sonnet-4-20250514",
    )
    db._conn.execute(
        "UPDATE sessions SET started_at = ?, ended_at = ? WHERE id = 'daily-1'",
        (
            datetime(2026, 4, 25, 9, 0, tzinfo=timezone.utc).timestamp(),
            datetime(2026, 4, 25, 9, 30, tzinfo=timezone.utc).timestamp(),
        ),
    )
    db.update_token_counts(
        "daily-1",
        input_tokens=1500,
        output_tokens=500,
        cache_write_tokens=100,
        billing_provider="anthropic",
    )
    db._conn.commit()


class TestPublishDailyReport:
    def test_create_doc_uses_create_command_and_parses_result(self, db, monkeypatch):
        _seed_daily_session(db)
        calls = []

        def fake_run(cmd, capture_output=False, text=False):
            calls.append((cmd, capture_output, text))
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "ok": True,
                        "data": {
                            "doc_id": "doc-create-123",
                            "doc_url": "https://feishu.example/doc-create-123",
                        },
                    }
                ),
                stderr="",
            )

        monkeypatch.setattr(publisher.subprocess, "run", fake_run)

        result = publisher.publish_daily_report(
            db_path=Path(db.db_path),
            day="2026-04-25",
            tz=timezone.utc,
            wiki_space="my_library",
            folder_token="folder-token-123",
            title="Hermes Daily Usage Report",
            lark_cli_path="/opt/homebrew/bin/lark-cli",
        )

        assert result["action"] == "created"
        assert result["doc_id"] == "doc-create-123"
        assert result["doc_url"] == "https://feishu.example/doc-create-123"
        assert result["report"]["date"] == "2026-04-25"

        assert len(calls) == 1
        cmd, capture_output, text = calls[0]
        assert capture_output is True
        assert text is True
        assert cmd[:3] == ["/opt/homebrew/bin/lark-cli", "docs", "+create"]
        assert "--wiki-space" in cmd
        assert "my_library" in cmd
        assert "--folder-token" in cmd
        assert cmd[cmd.index("--folder-token") + 1] == "folder-token-123"
        assert "--title" in cmd
        assert cmd[cmd.index("--title") + 1] == "Hermes Daily Usage Report - 2026-04-25"
        assert result["title"] == "Hermes Daily Usage Report - 2026-04-25"
        markdown = cmd[cmd.index("--markdown") + 1]
        assert "# Hermes Daily Usage Report" in markdown
        assert "- Sessions: 1" in markdown

    def test_existing_doc_uses_overwrite_update(self, db, monkeypatch):
        _seed_daily_session(db)
        calls = []

        def fake_run(cmd, capture_output=False, text=False):
            calls.append(cmd)
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "ok": True,
                        "data": {
                            "doc_id": "existing-doc-456",
                            "mode": "overwrite",
                            "success": True,
                        },
                    }
                ),
                stderr="",
            )

        monkeypatch.setattr(publisher.subprocess, "run", fake_run)

        result = publisher.publish_daily_report(
            db_path=Path(db.db_path),
            day="2026-04-25",
            tz=timezone.utc,
            doc_id="existing-doc-456",
            title="Hermes Daily Usage Report Updated",
            lark_cli_path="/opt/homebrew/bin/lark-cli",
        )

        assert result["action"] == "updated"
        assert result["doc_id"] == "existing-doc-456"
        assert result["doc_url"] == "https://thendlesssky.feishu.cn/docx/existing-doc-456"
        assert result["report"]["overview"]["total_tokens"] == 2100

        assert len(calls) == 1
        cmd = calls[0]
        assert cmd[:3] == ["/opt/homebrew/bin/lark-cli", "docs", "+update"]
        assert "--doc" in cmd
        assert "existing-doc-456" in cmd
        assert "--mode" in cmd
        assert cmd[cmd.index("--mode") + 1] == "overwrite"
        assert "--new-title" in cmd
        assert cmd[cmd.index("--new-title") + 1] == "Hermes Daily Usage Report Updated - 2026-04-25"
        assert result["title"] == "Hermes Daily Usage Report Updated - 2026-04-25"
        assert "--wiki-space" not in cmd

    def test_existing_doc_falls_back_to_default_doc_url_when_cli_omits_url(self, db, monkeypatch):
        _seed_daily_session(db)

        def fake_run(cmd, capture_output=False, text=False):
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "ok": True,
                        "data": {
                            "doc_id": "existing-doc-789",
                            "success": True,
                        },
                    }
                ),
                stderr="",
            )

        monkeypatch.setattr(publisher.subprocess, "run", fake_run)

        result = publisher.publish_daily_report(
            db_path=Path(db.db_path),
            day="2026-04-25",
            tz=timezone.utc,
            doc_id="existing-doc-789",
            title="Hermes Daily Usage Report Updated",
            lark_cli_path="/opt/homebrew/bin/lark-cli",
        )

        assert result["doc_url"] == "https://thendlesssky.feishu.cn/docx/existing-doc-789"

    def test_invalid_cli_json_raises_runtime_error(self, db, monkeypatch):
        _seed_daily_session(db)

        def fake_run(cmd, capture_output=False, text=False):
            return SimpleNamespace(returncode=0, stdout="not-json", stderr="")

        monkeypatch.setattr(publisher.subprocess, "run", fake_run)

        with pytest.raises(RuntimeError, match="Invalid JSON"):
            publisher.publish_daily_report(
                db_path=Path(db.db_path),
                day="2026-04-25",
                tz=timezone.utc,
                wiki_space="my_library",
            )
