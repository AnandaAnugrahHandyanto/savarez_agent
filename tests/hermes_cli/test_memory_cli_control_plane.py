from argparse import Namespace
import json

from hermes_cli import memory_cli


def test_memory_status_reports_latest_event_and_receipt(tmp_path, monkeypatch, capsys):
    home = tmp_path / ".hermes"
    monkeypatch.setattr(memory_cli, "get_hermes_home", lambda: home)
    store = memory_cli._store()
    store.add_entry("memory", "Fact A", kind="lesson")
    store.add_entry("user", "Fact B", kind="preference")

    state_dir = home / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "last_memory_event.json").write_text(
        json.dumps({"event_id": "evt-1", "action": "add", "target_lanes": ["sqlite_memory", "wiki_compiled"]}),
        encoding="utf-8",
    )
    (state_dir / "last_recall_receipt.json").write_text(
        json.dumps({"receipt_id": "rr-1", "lanes_used": ["sqlite_memory", "session_search"]}),
        encoding="utf-8",
    )

    memory_cli.memory_command(Namespace(memory_action="status", output=None, input=None))
    out = capsys.readouterr().out

    assert "last memory event: evt-1" in out
    assert "last recall receipt: rr-1" in out
