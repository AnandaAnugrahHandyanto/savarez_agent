import sys


def test_sessions_repair_stale_open_calls_conservative_repair(monkeypatch, capsys):
    import hermes_cli.main as main_mod
    import hermes_state

    captured = {}

    class FakeDB:
        def repair_stale_open_sessions(self, *, older_than_seconds, end_reason):
            captured["older_than_seconds"] = older_than_seconds
            captured["end_reason"] = end_reason
            return 7

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr(hermes_state, "SessionDB", lambda: FakeDB())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hermes",
            "sessions",
            "repair-stale-open",
            "--older-than-hours",
            "6",
            "--reason",
            "runtime_repair",
            "--yes",
        ],
    )

    main_mod.main()

    output = capsys.readouterr().out
    assert captured == {
        "older_than_seconds": 21600.0,
        "end_reason": "runtime_repair",
        "closed": True,
    }
    assert "Repaired 7 stale open session(s)." in output


def test_sessions_repair_stale_open_handles_eoferror_on_confirm(monkeypatch, capsys):
    import hermes_cli.main as main_mod
    import hermes_state

    class FakeDB:
        def repair_stale_open_sessions(self, **kwargs):
            raise AssertionError("repair_stale_open_sessions should not run when cancelled")

        def close(self):
            pass

    monkeypatch.setattr(hermes_state, "SessionDB", lambda: FakeDB())
    monkeypatch.setattr(sys, "argv", ["hermes", "sessions", "repair-stale-open"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": (_ for _ in ()).throw(EOFError))

    main_mod.main()

    output = capsys.readouterr().out
    assert "Cancelled" in output
