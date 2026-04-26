import argparse
import sys
from pathlib import Path


def test_chat_passes_system_prompt_flags_to_cli_main(monkeypatch, tmp_path):
    import hermes_cli.main as main_mod

    captured = {}
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("override from file", encoding="utf-8")

    monkeypatch.setattr(main_mod, "_has_any_provider_configured", lambda: True)
    monkeypatch.setitem(sys.modules, "cli", type("C", (), {"main": lambda **kwargs: captured.update(kwargs)}))

    args = argparse.Namespace(
        yolo=False,
        ignore_user_config=False,
        ignore_rules=False,
        source=None,
        system_prompt=None,
        system_prompt_file=str(prompt_file),
        append_system_prompt="append me",
        model=None,
        provider=None,
        toolsets=None,
        skills=None,
        verbose=False,
        quiet=True,
        query="hi",
        image=None,
        resume=None,
        worktree=False,
        checkpoints=False,
        pass_session_id=False,
        max_turns=None,
        tui=False,
        tui_dev=False,
    )

    main_mod.cmd_chat(args)

    assert captured["system_prompt_override"] == "override from file"
    assert captured["append_system_prompt"] == "append me"


def test_chat_rejects_mutually_exclusive_system_prompt_flags(monkeypatch, capsys):
    import hermes_cli.main as main_mod

    monkeypatch.setattr(main_mod, "_has_any_provider_configured", lambda: True)

    args = argparse.Namespace(
        yolo=False,
        ignore_user_config=False,
        ignore_rules=False,
        source=None,
        system_prompt="inline override",
        system_prompt_file="/tmp/ignored.txt",
        append_system_prompt=None,
        model=None,
        provider=None,
        toolsets=None,
        skills=None,
        verbose=False,
        quiet=True,
        query="hi",
        image=None,
        resume=None,
        worktree=False,
        checkpoints=False,
        pass_session_id=False,
        max_turns=None,
        tui=False,
        tui_dev=False,
    )

    try:
        main_mod.cmd_chat(args)
        raised = False
    except SystemExit as exc:
        raised = True
        assert exc.code == 2

    assert raised
    assert "mutually exclusive" in capsys.readouterr().out


def test_chat_rejects_prompt_flags_in_tui_mode(monkeypatch, capsys):
    import hermes_cli.main as main_mod

    monkeypatch.setattr(main_mod, "_has_any_provider_configured", lambda: True)

    args = argparse.Namespace(
        yolo=False,
        ignore_user_config=False,
        ignore_rules=False,
        source=None,
        system_prompt="inline override",
        system_prompt_file=None,
        append_system_prompt=None,
        model=None,
        provider=None,
        toolsets=None,
        skills=None,
        verbose=False,
        quiet=True,
        query="hi",
        image=None,
        resume=None,
        worktree=False,
        checkpoints=False,
        pass_session_id=False,
        max_turns=None,
        tui=True,
        tui_dev=False,
    )

    try:
        main_mod.cmd_chat(args)
        raised = False
    except SystemExit as exc:
        raised = True
        assert exc.code == 2

    assert raised
    assert "not yet supported with --tui" in capsys.readouterr().out


def test_top_level_chat_path_accepts_system_prompt_flags(monkeypatch):
    import hermes_cli.main as main_mod

    captured = {}
    monkeypatch.setattr(main_mod, "_has_any_provider_configured", lambda: True)
    monkeypatch.setitem(sys.modules, "cli", type("C", (), {"main": lambda **kwargs: captured.update(kwargs)}))
    monkeypatch.setattr(
        sys,
        "argv",
        ["hermes", "--system-prompt", "top level override", "chat", "-q", "hi", "-Q"],
    )

    main_mod.main()

    assert captured["system_prompt_override"] == "top level override"
