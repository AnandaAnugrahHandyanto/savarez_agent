import importlib
import json

from plugins.memory import load_memory_provider


def test_obsidian_provider_loads_from_plugin_registry(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))
    provider = load_memory_provider("obsidian")
    assert provider is not None
    assert provider.name == "obsidian"
    assert provider.is_available() is True


def test_obsidian_provider_writes_precompress_note(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))

    provider = load_memory_provider("obsidian")
    provider.initialize("session-obsidian", hermes_home=str(tmp_path), platform="cli")

    hint = provider.on_pre_compress([
        {"role": "user", "content": "User prefers short direct answers."},
        {"role": "assistant", "content": "I documented the root cause and next steps."},
        {"role": "user", "content": "Step 1: run tests. Then patch the file. Finally verify output."},
    ])
    assert "downshifted to Obsidian" in hint
    assert "Memory candidates" in hint
    assert "Skill candidates" in hint

    inbox = vault / "Inbox" / "Hermes"
    notes = list(inbox.glob("*.md"))
    assert notes
    content = notes[0].read_text(encoding="utf-8")
    assert "pre-compress" in content
    assert "root cause and next steps" in content


def test_obsidian_provider_precompress_failure_keeps_session_end_fallback(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))

    provider = load_memory_provider("obsidian")
    provider.initialize("session-obsidian", hermes_home=str(tmp_path), platform="cli")

    module = importlib.import_module("plugins.memory.obsidian")
    monkeypatch.setattr(
        module,
        "write_obsidian_downshift_note",
        lambda **kwargs: {"success": False, "error": "disk full", "vault_path": str(vault)},
    )
    hint = provider.on_pre_compress([
        {"role": "user", "content": "save this before compaction"},
        {"role": "assistant", "content": "done"},
    ])
    assert "capture failed" in hint
    assert provider._captured_precompress is False

    calls = []
    monkeypatch.setattr(
        module,
        "write_obsidian_downshift_note",
        lambda **kwargs: calls.append(kwargs) or {"success": True, "path": str(vault / "Inbox" / "Hermes" / "session-end.md"), "vault_path": str(vault), "title": "session-end"},
    )
    provider.on_session_end([
        {"role": "user", "content": "save this before compaction"},
        {"role": "assistant", "content": "done"},
    ])
    assert calls and calls[0]["trigger"] == "session-end"


def test_obsidian_provider_session_end_skips_duplicate_after_precompress(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))

    provider = load_memory_provider("obsidian")
    provider.initialize("session-obsidian", hermes_home=str(tmp_path), platform="cli")
    provider.on_pre_compress([
        {"role": "user", "content": "save this before compaction"},
        {"role": "assistant", "content": "done"},
    ])
    provider.on_session_end([
        {"role": "user", "content": "save this before compaction"},
        {"role": "assistant", "content": "done"},
    ])

    inbox = vault / "Inbox" / "Hermes"
    notes = list(inbox.glob("*.md"))
    assert len(notes) == 1
