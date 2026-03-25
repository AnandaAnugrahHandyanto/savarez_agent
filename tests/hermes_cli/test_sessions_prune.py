import sys


def test_sessions_prune_cancel_skips_deletion(monkeypatch, capsys):
    import hermes_cli.main as main_mod
    import hermes_state

    captured = {}

    class FakeDB:
        def prune_sessions(self, older_than_days, source=None):
            raise AssertionError("prune_sessions should not be called when the user cancels")

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr(hermes_state, "SessionDB", lambda: FakeDB())
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")
    monkeypatch.setattr(
        sys,
        "argv",
        ["hermes", "sessions", "prune", "--older-than", "30"],
    )

    main_mod.main()

    output = capsys.readouterr().out
    assert "Cancelled." in output
    assert captured == {"closed": True}


def test_sessions_prune_passes_filters_to_db(monkeypatch, capsys):
    import hermes_cli.main as main_mod
    import hermes_state

    captured = {}

    class FakeDB:
        def prune_sessions(self, older_than_days, source=None):
            captured["older_than_days"] = older_than_days
            captured["source"] = source
            return 7

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr(hermes_state, "SessionDB", lambda: FakeDB())
    monkeypatch.setattr(
        sys,
        "argv",
        ["hermes", "sessions", "prune", "--older-than", "45", "--source", "cli", "--yes"],
    )

    main_mod.main()

    output = capsys.readouterr().out
    assert captured == {
        "older_than_days": 45,
        "source": "cli",
        "closed": True,
    }
    assert "Pruned 7 session(s)." in output
