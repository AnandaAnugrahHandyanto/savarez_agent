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
