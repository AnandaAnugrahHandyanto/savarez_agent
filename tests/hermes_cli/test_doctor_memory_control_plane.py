import sqlite3

import hermes_cli.doctor as doctor


def test_check_persistent_memory_health_reports_control_plane_state_files(tmp_path, monkeypatch, capsys):
    hermes_home = tmp_path / ".hermes"
    memories = hermes_home / "memories"
    memories.mkdir(parents=True)
    (memories / "MEMORY.md").write_text("alpha", encoding="utf-8")
    (memories / "USER.md").write_text("beta", encoding="utf-8")

    db_path = hermes_home / "memory.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE memory_entries (id TEXT PRIMARY KEY, target TEXT, kind TEXT, content TEXT, status TEXT)")
    conn.execute("INSERT INTO memory_entries(id, target, kind, content, status) VALUES ('1', 'memory', 'lesson', 'alpha', 'active')")
    conn.commit()
    conn.close()

    state_dir = hermes_home / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "last_memory_event.json").write_text("{}", encoding="utf-8")
    (state_dir / "last_recall_receipt.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(doctor, "HERMES_HOME", hermes_home)
    monkeypatch.setattr(doctor, "_DHH", "~/.hermes")

    doctor._check_persistent_memory_health([])
    out = capsys.readouterr().out

    assert "last_memory_event.json exists" in out
    assert "last_recall_receipt.json exists" in out
