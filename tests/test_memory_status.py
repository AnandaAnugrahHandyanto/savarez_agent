from pathlib import Path


def test_build_memory_status_lines_renders_bars_and_provider_summary():
    from hermes_cli.memory_status import build_memory_status_lines

    snapshot = {
        "stores": [
            {
                "key": "memory",
                "label": "Agent memory",
                "file_name": "MEMORY.md",
                "file_path": str(Path("/tmp/MEMORY.md")),
                "entries": 2,
                "used_chars": 1100,
                "char_limit": 2200,
            },
            {
                "key": "user",
                "label": "User profile",
                "file_name": "USER.md",
                "file_path": str(Path("/tmp/USER.md")),
                "entries": 1,
                "used_chars": 1300,
                "char_limit": 1375,
            },
        ],
        "provider": {
            "name": "mem0",
            "installed": True,
            "available": True,
            "config": {"org": "demo"},
        },
    }

    lines = build_memory_status_lines(snapshot, use_color=False)
    rendered = "\n".join(lines)

    assert any("/memory" in line for line in lines)
    assert any("MEMORY.md" in line for line in lines)
    assert any("USER.md" in line for line in lines)
    assert any("[" in line and "█" in line for line in lines)
    assert "50%" in rendered
    assert "95%" in rendered
    assert "mem0" in rendered
    assert "available" in rendered.lower()


def test_build_memory_status_lines_colorizes_high_usage_when_enabled():
    from hermes_cli.memory_status import build_memory_status_lines

    snapshot = {
        "stores": [
            {
                "key": "user",
                "label": "User profile",
                "file_name": "USER.md",
                "file_path": str(Path("/tmp/USER.md")),
                "entries": 3,
                "used_chars": 1360,
                "char_limit": 1375,
            }
        ],
        "provider": {
            "name": "",
            "installed": False,
            "available": False,
            "config": {},
        },
    }

    lines = build_memory_status_lines(snapshot, use_color=True)

    assert any("\x1b[" in line for line in lines)
    assert any("99%" in line for line in lines)


def test_cmd_status_shows_built_in_memory_bars(monkeypatch, tmp_path, capsys):
    from hermes_cli.memory_setup import cmd_status

    mem_dir = tmp_path / "memories"
    mem_dir.mkdir(parents=True)
    (mem_dir / "MEMORY.md").write_text("alpha\n§\nbeta\n", encoding="utf-8")
    (mem_dir / "USER.md").write_text("pref one\n§\npref two\n", encoding="utf-8")

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setattr(
        "hermes_cli.memory_setup.load_config",
        lambda: {"memory": {"provider": ""}},
        raising=False,
    )
    monkeypatch.setattr("hermes_cli.memory_setup._get_available_providers", lambda: [])

    cmd_status(None)
    out = capsys.readouterr().out

    assert "/memory" in out
    assert "MEMORY.md" in out
    assert "USER.md" in out
    assert "[" in out
