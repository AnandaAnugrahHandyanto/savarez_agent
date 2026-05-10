import json
import hashlib
import stat
import threading
from pathlib import Path

from hermes_cli.config import DEFAULT_CONFIG


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_run_ledger_writes_jsonl_under_hermes_home_without_state_db(monkeypatch, tmp_path):
    home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(home))

    from agent.run_ledger import RunLedger

    ledger = RunLedger(run_id="run-a", session_id="session-a")
    event = ledger.append_event("tool.started", tool_name="read_file", tool_call_id="call-a")

    events_path = home / "runs" / "run-a" / "events.jsonl"
    assert events_path.exists()
    assert not (home / "state.db").exists()

    rows = _read_jsonl(events_path)
    assert rows == [event]
    assert rows[0]["schema_version"] == 1
    assert rows[0]["event_id"] == "evt_000000001"
    assert rows[0]["event_seq"] == 1
    assert rows[0]["run_id"] == "run-a"
    assert rows[0]["session_id"] == "session-a"
    assert rows[0]["type"] == "tool.started"


def test_large_output_writes_redacted_content_addressed_blob(monkeypatch, tmp_path):
    home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(home))

    from agent.run_ledger import RunLedger

    secret = "sk-testsecret1234567890"
    ledger = RunLedger(
        run_id="run-blob",
        session_id="session-a",
        config={"preview_chars": 64, "blob_threshold_chars": 128, "max_blob_bytes": 10_000},
    )
    event = ledger.append_event(
        "tool.finished",
        tool_name="terminal",
        tool_call_id="call-blob",
        output={"content": (f"prefix {secret} " + "x" * 300)},
    )

    output = event["output"]
    assert output["redaction_status"] == "redacted"
    assert output["safe_to_publish"] is False
    assert "sha256" in output
    assert "object_path" in output
    assert secret not in json.dumps(event)

    blob_path = home / "runs" / "run-blob" / output["object_path"]
    assert blob_path.exists()
    blob_text = blob_path.read_text()
    assert secret not in blob_text
    assert "prefix" in blob_text


def test_structured_sensitive_keys_are_redacted_from_events_and_blobs(monkeypatch, tmp_path):
    home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(home))

    from agent.run_ledger import RunLedger

    api_key = "opaque-secret-value-123456789"
    password = "p@ssw0rd-not-pattern"
    access_token = "opaque-access-token-value-123456789"
    ledger = RunLedger(
        run_id="run-structured-secrets",
        session_id="session-a",
        config={"preview_chars": 64, "blob_threshold_chars": 80, "max_blob_bytes": 10_000},
    )

    event = ledger.append_event(
        "tool.finished",
        input={"api_key": api_key, "nested": {"password": password, "accessToken": access_token}},
        output={
            "api_key": api_key,
            "nested": {"password": password, "accessToken": access_token},
            "padding": "x" * 200,
        },
    )

    events_path = home / "runs" / "run-structured-secrets" / "events.jsonl"
    event_json = events_path.read_text()
    assert api_key not in json.dumps(event)
    assert password not in json.dumps(event)
    assert access_token not in json.dumps(event)
    assert api_key not in event_json
    assert password not in event_json
    assert access_token not in event_json

    blob_path = home / "runs" / "run-structured-secrets" / event["output"]["object_path"]
    blob_text = blob_path.read_text()
    assert api_key not in blob_text
    assert password not in blob_text
    assert access_token not in blob_text


def test_recovery_reports_in_flight_started_event(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))

    from agent.run_ledger import RunLedger

    ledger = RunLedger(run_id="run-recovery", session_id="session-a")
    ledger.append_event("tool.started", tool_name="terminal", tool_call_id="call-live")
    ledger.append_event("tool.started", tool_name="read_file", tool_call_id="call-done")
    ledger.append_event(
        "tool.finished",
        tool_name="read_file",
        tool_call_id="call-done",
        status="ok",
        output={"content": "done"},
    )

    recovery = ledger.recover_state()

    assert list(recovery["in_flight"]) == ["call-live"]
    assert recovery["in_flight"]["call-live"]["tool_name"] == "terminal"
    assert [tool["tool_call_id"] for tool in recovery["recent_completed_tools"]] == ["call-done"]


def test_reader_skips_corrupt_final_jsonl_line(monkeypatch, tmp_path):
    home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(home))

    from agent.run_ledger import RunLedger

    ledger = RunLedger(run_id="run-corrupt", session_id="session-a")
    ledger.append_event("tool.started", tool_name="terminal", tool_call_id="call-a")
    with (home / "runs" / "run-corrupt" / "events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write('{"event_seq": 2, "type": "tool.finished"')

    result = ledger.read_events()

    assert [event["event_seq"] for event in result.events] == [1]
    assert result.corrupt_lines
    assert result.corrupt_lines[0]["line_number"] == 2


def test_append_after_corrupt_partial_final_line_keeps_future_events_readable(monkeypatch, tmp_path):
    home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(home))

    from agent.run_ledger import RunLedger

    ledger = RunLedger(run_id="run-corrupt-append", session_id="session-a")
    ledger.append_event("tool.started", tool_name="terminal", tool_call_id="call-a")
    with (home / "runs" / "run-corrupt-append" / "events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write('{"event_seq": 2, "type": "partial"')

    ledger.append_event("tool.finished", tool_name="terminal", tool_call_id="call-a", status="ok")
    result = ledger.read_events()

    assert [event["type"] for event in result.events] == ["tool.started", "tool.finished"]
    assert [event["event_seq"] for event in result.events] == [1, 2]
    assert result.corrupt_lines


def test_run_ledger_creates_private_directories(monkeypatch, tmp_path):
    home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(home))

    from agent.run_ledger import RunLedger

    RunLedger(run_id="run-private", session_id="session-a")

    run_root = home / "runs" / "run-private"
    private_dirs = [
        home / "runs",
        run_root,
        run_root / "capsules",
        run_root / "objects",
        run_root / "objects" / "sha256",
    ]
    for path in private_dirs:
        assert stat.S_IMODE(path.stat().st_mode) == 0o700


def test_run_id_rejects_path_traversal_without_creating_escape_directory(monkeypatch, tmp_path):
    home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(home))

    from agent.run_ledger import RunLedger

    try:
        RunLedger(run_id="../escape", session_id="session-a")
    except ValueError:
        pass
    else:
        raise AssertionError("unsafe run_id was accepted")

    assert not (home / "escape").exists()
    assert not (home.parent / "escape").exists()


def test_existing_corrupt_blob_is_rewritten_atomically(monkeypatch, tmp_path):
    home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(home))

    from agent.run_ledger import RunLedger

    payload = {"content": "known payload " + "x" * 200}
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(data).hexdigest()
    object_path = home / "runs" / "run-corrupt-blob" / "objects" / "sha256" / digest[:2] / digest
    object_path.parent.mkdir(parents=True)
    object_path.write_text("corrupt")

    ledger = RunLedger(
        run_id="run-corrupt-blob",
        session_id="session-a",
        config={"preview_chars": 32, "blob_threshold_chars": 40, "max_blob_bytes": 10_000},
    )
    event = ledger.append_event("tool.finished", output=payload)

    assert event["output"]["object_path"] == object_path.relative_to(home / "runs" / "run-corrupt-blob").as_posix()
    assert object_path.read_bytes() == data


def test_artifact_refs_written_for_content_addressed_blobs(monkeypatch, tmp_path):
    home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(home))

    from agent.run_ledger import RunLedger

    ledger = RunLedger(
        run_id="run-artifacts",
        session_id="session-a",
        config={"preview_chars": 32, "blob_threshold_chars": 40, "max_blob_bytes": 10_000},
    )
    event = ledger.append_event("tool.finished", output={"content": "x" * 200})

    assert (home / "runs" / "run-artifacts" / "artifacts.json").exists()
    artifacts = json.loads((home / "runs" / "run-artifacts" / "artifacts.json").read_text())
    assert artifacts == event["artifact_refs"]
    assert artifacts[0]["type"] == "blob"
    assert artifacts[0]["sha256"] == event["output"]["sha256"]
    assert artifacts[0]["path"] == event["output"]["object_path"]
    assert artifacts[0]["bytes"] == event["output"]["bytes"]
    assert artifacts[0]["safe_to_publish"] is False
    assert artifacts[0]["redaction_status"] == "redacted"


def test_max_run_bytes_skips_blob_write_and_marks_policy_truncation(monkeypatch, tmp_path):
    home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(home))

    from agent.run_ledger import RunLedger

    ledger = RunLedger(
        run_id="run-size-guardrail",
        session_id="session-a",
        config={"preview_chars": 32, "blob_threshold_chars": 40, "max_blob_bytes": 10_000, "max_run_bytes": 100},
    )
    event = ledger.append_event("tool.finished", output={"content": "x" * 500})

    assert event["output"]["truncated_due_to_policy"] is True
    assert "object_path" not in event["output"]
    assert list((home / "runs" / "run-size-guardrail" / "objects" / "sha256").glob("*/*")) == []


def test_multiple_threads_write_unique_monotonic_events(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))

    from agent.run_ledger import RunLedger

    ledger = RunLedger(run_id="run-threads", session_id="session-a")

    def write_events(offset: int) -> None:
        for idx in range(20):
            ledger.append_event(
                "tool.started",
                tool_name="test_tool",
                tool_call_id=f"call-{offset}-{idx}",
            )

    threads = [threading.Thread(target=write_events, args=(i,)) for i in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    result = ledger.read_events()
    seqs = [event["event_seq"] for event in result.events]
    event_ids = [event["event_id"] for event in result.events]

    assert seqs == list(range(1, 101))
    assert event_ids == [f"evt_{seq:09d}" for seq in seqs]
    assert len(set(event_ids)) == 100


def test_run_ledger_config_defaults_are_safe():
    cfg = DEFAULT_CONFIG["sessions"]["run_ledger"]

    assert cfg["enabled"] is True
    assert cfg["preview_chars"] == 4096
    assert cfg["blob_threshold_chars"] == 16384
    assert cfg["max_blob_bytes"] == 10_000_000
    assert cfg["max_capsule_events"] == 200
    assert cfg["lock_timeout_seconds"] == 30
    assert cfg["fsync"] is False
    assert cfg["retention_days"] == 90
    assert cfg["max_run_bytes"] == 268435456
