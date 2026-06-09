"""Tests for scripts/jusam_surface_smoke.py.

The closeout helper's contract: it must (a) read the canonical prompt + 11
criteria from the sywork doc rather than hardcoding them, (b) never let a
bot-origin or unconfirmed Slack artifact reach a "pass", (c) redact secrets
from every output path, and (d) classify state.db sources read-only.
"""

import sqlite3
import time

import pytest

import scripts.jusam_surface_smoke as smoke


# ── fixtures ─────────────────────────────────────────────────────────────────

DOC = """\
## 7. smoke

### Smoke-test prompt

```text
주삼 운영 원칙을 요약해줘.
포함: 세영 역할, T0~T3.
```

### Pass criteria

Pass는 아래를 모두 포함할 때다.

- 세영 = EGNIS CSO and final decision-maker; not 대표.
- Hermes/주삼 = AI 비서실장 / AI Chief Office OS.
- Desktop/Slack/CLI are interfaces, not separate identities.
- Desktop = deep-work; Slack = hot log; sywork = canonical; Notion = scan.
- Non-trivial work uses Claude/Codex worker-first; Hermes verifies.
- Decision Tier T0~T3 and gates are understood.
- Completion is evidence-backed: file/diff/test/tool output.
- T2+ requires External Lens unless bypassed with reason.
- EGNIS Context Intelligence Layer connects Meta/Cafe24 signals into risks.
- Repeated misses become violation-log entries then WARN/HARD after approval.
- 세영 should not need to memorize tool/skill names; 주삼 owns routing.

## 8. next
"""

# A response body that hits keyword signals for all 11 criteria.
GOOD_BODY = """\
세영은 EGNIS CSO이자 final decision-maker로 판단을 내린다 (대표 아님).
주삼/Hermes는 AI 비서실장이자 AI Chief Office OS다.
Desktop/Slack/CLI는 같은 주삼 core에 붙는 interface이며 별도 identity가 아니다.
Desktop은 deep work, Slack은 hot log, sywork는 canonical 정본, Notion은 scan layer.
비단순 작업은 Claude/Codex worker-first로 먼저 넓히고 Hermes가 검증/synthesis한다.
Decision Tier T0~T3와 gate/승인 escalation을 이해한다.
완료는 evidence 기반이다: file diff test tool 산출물.
T2 전략/pricing/positioning은 External Lens가 필요하며 reason으로 bypass 가능.
EGNIS Context Intelligence Layer는 Meta/Cafe24/브랜드 signal을 risk/기회로 연결.
반복 위반은 violation log 기록 후 WARN/HARD gate 승인으로 간다.
세영은 tool/skill 이름을 외울 필요 없고 주삼이 routing한다.
"""


# ── doc parsing ──────────────────────────────────────────────────────────────

def test_extract_prompt():
    p = smoke.extract_prompt(DOC)
    assert "주삼 운영 원칙" in p
    assert "```" not in p


def test_extract_criteria_count():
    crits = smoke.extract_criteria(DOC)
    assert len(crits) == 11
    assert crits[0].startswith("세영 = EGNIS CSO")


def test_matchers_align_with_canonical_count():
    # The matcher table must stay aligned with the canonical 11 criteria.
    assert len(smoke.CRITERION_MATCHERS) == 11


def test_real_canonical_doc_has_11_criteria():
    # Guard against the canonical doc drifting away from 11 criteria.
    if not smoke.CANONICAL_DOC.exists():
        pytest.skip("canonical doc not present in this environment")
    text = smoke.CANONICAL_DOC.read_text(encoding="utf-8")
    assert len(smoke.extract_criteria(text)) == 11
    assert "주삼" in smoke.extract_prompt(text)


# ── redaction ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "secret",
    [
        "xoxb-123456789-abcdefABCDEF",
        "SLACK_BOT_TOKEN=xoxb-secretvalue",
        "https://hooks.slack.com/services/T000/B000/zzz",
        "https://slack.com/oauth/v2/authorize?code=abc",
        "ANTHROPIC_API_KEY=sk-ant-deadbeef0123456789",
    ],
)
def test_redact_strips_secrets(secret):
    out = smoke.redact(f"prefix {secret} suffix")
    assert "REDACTED" in out
    # The raw secret value must not survive.
    assert "xoxb-123456789-abcdefABCDEF" not in out
    assert "secretvalue" not in out
    assert "zzz" not in out or "REDACTED" in out


def test_report_redacts_artifact_secrets():
    raw = GOOD_BODY + "\nSLACK_BOT_TOKEN=xoxb-leak-me-123\n"
    crits = smoke.extract_criteria(DOC)
    res = smoke.evaluate_artifact("Desktop direct", raw, crits, allow_user_origin=True)
    report = smoke.render_report([res], "prompt", date_str="2026-06-09")
    assert "xoxb-leak-me-123" not in report


# ── origin / bot-origin discipline ──────────────────────────────────────────

def test_slack_unconfirmed_is_not_user_origin():
    crits = smoke.extract_criteria(DOC)
    res = smoke.evaluate_artifact("Slack direct", GOOD_BODY, crits, allow_user_origin=False)
    # Even a perfect body must NOT pass Slack direct without confirmed origin.
    assert res.origin == "bot-origin"
    assert res.state != "pass"


def test_slack_confirmed_user_origin_can_pass():
    crits = smoke.extract_criteria(DOC)
    raw = "#smoke: origin=user\n" + GOOD_BODY
    res = smoke.evaluate_artifact("Slack direct", raw, crits, allow_user_origin=False)
    assert res.origin == "direct-user-origin"
    assert res.state == "pass"
    assert res.passed == 11


def test_explicit_bot_origin_warns():
    crits = smoke.extract_criteria(DOC)
    raw = "#smoke: origin=bot\n" + GOOD_BODY
    res = smoke.evaluate_artifact("Slack direct", raw, crits, allow_user_origin=False)
    assert res.origin == "bot-origin"
    assert res.state == "warn"


def test_missing_artifact_blocked():
    crits = smoke.extract_criteria(DOC)
    res = smoke.evaluate_artifact("Slack direct", None, crits, allow_user_origin=False)
    assert res.state == "blocked"
    assert res.origin == "artifact-missing"


def test_desktop_good_body_passes():
    crits = smoke.extract_criteria(DOC)
    res = smoke.evaluate_artifact("Desktop direct", GOOD_BODY, crits, allow_user_origin=True)
    assert res.state == "pass"
    assert res.origin == "direct-user-origin"
    assert res.passed == 11


def test_weak_body_fails_criteria():
    crits = smoke.extract_criteria(DOC)
    res = smoke.evaluate_artifact(
        "Desktop direct", "안녕하세요 오늘 날씨가 좋네요.", crits, allow_user_origin=True
    )
    assert res.state == "fail"
    assert res.passed < 11


# ── artifact override directives ─────────────────────────────────────────────

def test_reviewed_directive_marks_method():
    crits = smoke.extract_criteria(DOC)
    raw = "#smoke: reviewed\n" + GOOD_BODY
    res = smoke.evaluate_artifact("Desktop direct", raw, crits, allow_user_origin=True)
    assert all(c.method == "reviewed" for c in res.criteria)


def test_criterion_override_forces_pass():
    crits = smoke.extract_criteria(DOC)
    raw = "#smoke: criterion 8 = pass (External Lens explained inline)\n안녕하세요."
    res = smoke.evaluate_artifact("Desktop direct", raw, crits, allow_user_origin=True)
    c8 = next(c for c in res.criteria if c.number == 8)
    assert c8.status == "pass"
    assert c8.method == "reviewed"


# ── state.db classification (read-only) ──────────────────────────────────────

def test_classify_source():
    assert smoke.classify_source("tui") == "Desktop"
    assert smoke.classify_source("cli") == "CLI"
    assert smoke.classify_source("slack-gateway") == "Slack"
    assert smoke.classify_source("gateway") == "Slack"
    assert smoke.classify_source("telegram") == "?"


def _make_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT NOT NULL);
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            timestamp REAL NOT NULL
        );
        """
    )
    now = time.time()
    conn.execute("INSERT INTO sessions VALUES ('s-tui', 'tui')")
    conn.execute("INSERT INTO sessions VALUES ('s-slack', 'slack-gateway')")
    conn.execute(
        "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?,?,?,?)",
        ("s-tui", "user", "주삼 요약 MARK123", now),
    )
    conn.execute(
        "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?,?,?,?)",
        ("s-slack", "user", "주삼 요약 MARK123 with token xoxb-AAA-BBB", now + 1),
    )
    conn.commit()
    conn.close()


def test_find_candidates_classifies_and_redacts(tmp_path):
    db = tmp_path / "state.db"
    _make_db(db)
    cands = smoke.find_candidates(db, "MARK123")
    surfaces = {c.surface for c in cands}
    assert surfaces == {"Desktop", "Slack"}
    # token in the Slack message snippet must be redacted.
    joined = " ".join(c.snippet for c in cands)
    assert "xoxb-AAA-BBB" not in joined


def test_find_candidates_missing_db(tmp_path):
    with pytest.raises(FileNotFoundError):
        smoke.find_candidates(tmp_path / "nope.db", "X")


# ── user-origin marker + following assistant response pairing ────────────────

def _make_db_pairs(path):
    """DB where a user marker is followed by an assistant reply WITHOUT marker."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT NOT NULL);
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            timestamp REAL NOT NULL
        );
        """
    )
    now = time.time()
    conn.execute("INSERT INTO sessions VALUES ('s-tui', 'tui')")
    conn.execute("INSERT INTO sessions VALUES ('s-slack', 'slack-gateway')")
    conn.execute("INSERT INTO sessions VALUES ('s-cli', 'cli')")
    ins = (
        "INSERT INTO messages (session_id, role, content, timestamp) "
        "VALUES (?,?,?,?)"
    )
    # Desktop: user marker, then assistant reply that does NOT contain the marker.
    conn.execute(ins, ("s-tui", "user", "주삼 요약해줘 MARK123", now))
    conn.execute(ins, ("s-tui", "assistant", GOOD_BODY, now + 1))
    # Slack: user marker from a slack/gateway source + assistant reply (with leak).
    conn.execute(ins, ("s-slack", "user", "주삼 요약 MARK123", now + 2))
    conn.execute(
        ins, ("s-slack", "assistant", GOOD_BODY + "\ntoken xoxb-AAA-BBB", now + 3)
    )
    # CLI: user marker + assistant reply.
    conn.execute(ins, ("s-cli", "user", "MARK123 주삼 요약", now + 4))
    conn.execute(ins, ("s-cli", "assistant", GOOD_BODY, now + 5))
    conn.commit()
    conn.close()


def test_find_candidates_includes_following_assistant(tmp_path):
    db = tmp_path / "state.db"
    _make_db_pairs(db)
    cands = smoke.find_candidates(db, "MARK123")
    following = [c for c in cands if c.relation == "following-assistant"]
    # Every user marker should pull its following assistant response.
    assert following, "expected following assistant candidates"
    assert all(c.role == "assistant" for c in following)
    # The assistant body need not contain the marker itself.
    assert any("MARK123" not in c.snippet for c in following)
    desktop_follow = [c for c in following if c.surface == "Desktop"]
    assert desktop_follow and "MARK123" not in desktop_follow[0].snippet


def test_extract_state_db_artifacts_pairs_user_and_assistant(tmp_path):
    db = tmp_path / "state.db"
    _make_db_pairs(db)
    arts = smoke.extract_state_db_artifacts(db, "MARK123")
    assert set(arts) == {"Desktop", "Slack", "CLI"}
    # Desktop artifact carries the assistant body (which lacks the marker).
    assert "비서실장" in arts["Desktop"].assistant_text
    assert arts["Desktop"].user_origin is True
    # Slack assistant leak must be redacted, and a not-bot-origin note attached.
    assert "xoxb-AAA-BBB" not in arts["Slack"].assistant_text
    assert "bot" in arts["Slack"].note.lower()


def test_extract_state_db_only_user_role_is_marker(tmp_path):
    # Marker appears ONLY in an assistant message; the user turn has no marker.
    db = tmp_path / "state.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT NOT NULL);
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            timestamp REAL NOT NULL
        );
        """
    )
    now = time.time()
    conn.execute("INSERT INTO sessions VALUES ('s-slack', 'slack-gateway')")
    ins = (
        "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?,?,?,?)"
    )
    conn.execute(ins, ("s-slack", "user", "주삼 요약 부탁", now))
    conn.execute(ins, ("s-slack", "assistant", "응답 MARK123", now + 1))
    conn.commit()
    conn.close()
    arts = smoke.extract_state_db_artifacts(db, "MARK123")
    # No role=user marker -> nothing is treated as user-origin (default-safe).
    assert arts == {}


def test_extract_state_db_skips_marker_without_assistant(tmp_path):
    db = tmp_path / "state.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT NOT NULL);
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            timestamp REAL NOT NULL
        );
        """
    )
    now = time.time()
    conn.execute("INSERT INTO sessions VALUES ('s-tui', 'tui')")
    conn.execute(
        "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?,?,?,?)",
        ("s-tui", "user", "주삼 요약 MARK123", now),
    )
    conn.commit()
    conn.close()
    # User-origin marker with no following assistant response -> not extractable.
    assert smoke.extract_state_db_artifacts(db, "MARK123") == {}


def test_from_state_db_cli_fills_artifacts(tmp_path, capsys):
    doc = tmp_path / "doc.md"
    doc.write_text(DOC, encoding="utf-8")
    db = tmp_path / "state.db"
    _make_db_pairs(db)
    rc = smoke.main(
        [
            "--doc",
            str(doc),
            "--from-state-db",
            "--marker",
            "MARK123",
            "--state-db",
            str(db),
            "--dry-run",
        ]
    )
    out = capsys.readouterr().out
    # Desktop, Slack, and CLI all backfilled from genuine user-origin markers.
    assert "Desktop direct" in out
    assert "Slack direct" in out
    assert "filled from state.db" in out
    # Slack leak from the assistant body must not survive into the report.
    assert "xoxb-AAA-BBB" not in out
    # All three surfaces reach a user-origin pass -> overall zero.
    assert rc == 0


def test_from_state_db_requires_marker(tmp_path, capsys):
    doc = tmp_path / "doc.md"
    doc.write_text(DOC, encoding="utf-8")
    rc = smoke.main(["--doc", str(doc), "--from-state-db"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "requires --marker" in err


# ── active (soft-delete) filtering ───────────────────────────────────────────
#
# The live Hermes schema soft-deletes rewound/edited rows via messages.active
# (1 = live, 0 = superseded). The closeout must ignore active=0 rows so a stale
# or rewound exchange is never mistaken for the current user-origin one, while
# still running against older/test schemas that lack the column.


def _active_schema(conn):
    conn.executescript(
        """
        CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT NOT NULL);
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            timestamp REAL NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        );
        """
    )


def _ins_active(conn, session_id, role, content, ts, active=1):
    conn.execute(
        "INSERT INTO messages (session_id, role, content, timestamp, active) "
        "VALUES (?,?,?,?,?)",
        (session_id, role, content, ts, active),
    )


def test_active_clause_detected_when_column_present(tmp_path):
    db = tmp_path / "state.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _active_schema(conn)
    try:
        assert smoke._active_clause(conn) == " AND m.active = 1"
    finally:
        conn.close()


def test_active_clause_empty_without_column(tmp_path):
    db = tmp_path / "state.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "CREATE TABLE messages (id INTEGER PRIMARY KEY, role TEXT, content TEXT);"
    )
    try:
        assert smoke._active_clause(conn) == ""
    finally:
        conn.close()


def test_active_inactive_user_marker_excluded(tmp_path):
    # An inactive (rewound) user marker must yield no candidate and no artifact,
    # even though a live assistant reply sits in the same session.
    db = tmp_path / "state.db"
    conn = sqlite3.connect(db)
    _active_schema(conn)
    now = time.time()
    conn.execute("INSERT INTO sessions VALUES ('s-tui', 'tui')")
    _ins_active(conn, "s-tui", "user", "주삼 요약 MARK123", now, active=0)
    _ins_active(conn, "s-tui", "assistant", GOOD_BODY, now + 1, active=1)
    conn.commit()
    conn.close()

    cands = smoke.find_candidates(db, "MARK123")
    assert cands == [], "inactive user marker must not surface as a candidate"
    assert smoke.extract_state_db_artifacts(db, "MARK123") == {}


def test_active_marker_pairs_with_active_assistant(tmp_path):
    # A live user marker pairs with the following live assistant response.
    db = tmp_path / "state.db"
    conn = sqlite3.connect(db)
    _active_schema(conn)
    now = time.time()
    conn.execute("INSERT INTO sessions VALUES ('s-tui', 'tui')")
    _ins_active(conn, "s-tui", "user", "주삼 요약 MARK123", now, active=1)
    _ins_active(conn, "s-tui", "assistant", GOOD_BODY, now + 1, active=1)
    conn.commit()
    conn.close()

    arts = smoke.extract_state_db_artifacts(db, "MARK123")
    assert set(arts) == {"Desktop"}
    assert "비서실장" in arts["Desktop"].assistant_text
    assert arts["Desktop"].user_origin is True


def test_active_inactive_assistant_skipped_for_later_active(tmp_path):
    # After a live marker, an inactive (rewound) assistant reply is skipped in
    # favour of the later live assistant reply.
    db = tmp_path / "state.db"
    conn = sqlite3.connect(db)
    _active_schema(conn)
    now = time.time()
    conn.execute("INSERT INTO sessions VALUES ('s-tui', 'tui')")
    _ins_active(conn, "s-tui", "user", "주삼 요약 MARK123", now, active=1)
    _ins_active(
        conn, "s-tui", "assistant", "INACTIVE_REPLY 폐기된 응답", now + 1, active=0
    )
    _ins_active(conn, "s-tui", "assistant", GOOD_BODY, now + 2, active=1)
    conn.commit()
    conn.close()

    arts = smoke.extract_state_db_artifacts(db, "MARK123")
    assert set(arts) == {"Desktop"}
    text = arts["Desktop"].assistant_text
    assert "INACTIVE_REPLY" not in text
    assert "비서실장" in text


def test_active_marker_with_only_inactive_assistant_yields_nothing(tmp_path):
    # A live marker whose only following assistant reply is inactive has no live
    # response to pair with -> not extractable.
    db = tmp_path / "state.db"
    conn = sqlite3.connect(db)
    _active_schema(conn)
    now = time.time()
    conn.execute("INSERT INTO sessions VALUES ('s-tui', 'tui')")
    _ins_active(conn, "s-tui", "user", "주삼 요약 MARK123", now, active=1)
    _ins_active(
        conn, "s-tui", "assistant", "INACTIVE_REPLY 폐기된 응답", now + 1, active=0
    )
    conn.commit()
    conn.close()

    assert smoke.extract_state_db_artifacts(db, "MARK123") == {}


# ── CLI entrypoint ───────────────────────────────────────────────────────────

def test_print_prompt_cli(tmp_path, capsys):
    doc = tmp_path / "doc.md"
    doc.write_text(DOC, encoding="utf-8")
    rc = smoke.main(["--doc", str(doc), "--print-prompt"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "주삼 운영 원칙" in out


def test_dry_run_report_cli(tmp_path, capsys):
    doc = tmp_path / "doc.md"
    doc.write_text(DOC, encoding="utf-8")
    art = tmp_path / "desktop.txt"
    art.write_text(GOOD_BODY, encoding="utf-8")
    rc = smoke.main(
        ["--doc", str(doc), "--desktop-artifact", str(art), "--dry-run"]
    )
    out = capsys.readouterr().out
    assert "Surface matrix" in out
    assert "Desktop direct" in out
    # Desktop passes but Slack is missing -> non-zero overall.
    assert rc == 1


def test_slack_summary_not_posted(tmp_path, capsys):
    doc = tmp_path / "doc.md"
    doc.write_text(DOC, encoding="utf-8")
    art = tmp_path / "slack.txt"
    art.write_text("#smoke: origin=user\n" + GOOD_BODY, encoding="utf-8")
    rc = smoke.main(
        ["--doc", str(doc), "--slack-artifact", str(art), "--slack-summary"]
    )
    out = capsys.readouterr().out
    assert "not posted" in out
    assert "Slack direct" in out
    assert rc == 1  # Desktop artifact missing
