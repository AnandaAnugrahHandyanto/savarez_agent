from types import SimpleNamespace

from hermes_cli.status import show_status


def test_show_status_includes_tavily_key(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-1234567890abcdef")

    show_status(SimpleNamespace(all=False, deep=False))

    output = capsys.readouterr().out
    assert "Tavily" in output
    assert "tvly...cdef" in output


def test_show_status_keeps_kasia_generic(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("KASIA_ENABLED", "true")
    monkeypatch.setenv("KASIA_SEED_PHRASE", "seed words go here")
    monkeypatch.setenv("KASIA_INDEXER_URL", "https://indexer.example.com")
    monkeypatch.setenv(
        "KASIA_INDEXER_URLS",
        "https://indexer.example.com,https://indexer-backup.example.com",
    )
    monkeypatch.setenv("KASIA_NODE_WBORSH_URL", "ws://node.example.com:17110")
    monkeypatch.setenv(
        "KASIA_NODE_WBORSH_URLS",
        "ws://node.example.com:17110,ws://node-backup.example.com:17110",
    )
    monkeypatch.setenv("KASIA_KNS_URL", "https://kns.example.com/api/v1")
    monkeypatch.setenv("KASIA_ALLOWED_BROADCAST_CHANNELS", "alerts,ops")
    monkeypatch.setenv("KASIA_HOME_CHANNEL", "kaspa:qhome")
    monkeypatch.setattr(
        "hermes_cli.status.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout="", returncode=1),
    )

    show_status(SimpleNamespace(all=False, deep=False))

    output = capsys.readouterr().out
    assert "Kasia" in output
    assert "home: kaspa:qhome" in output
    assert "KNS:        https://kns.example.com/api/v1" not in output
    assert "Indexers:   2 configured" not in output
    assert "Nodes:      2 configured" not in output
    assert "Broadcasts: publish allowlist for #alerts, #ops" not in output
    assert "Active indexer:" not in output
    assert "Active node:" not in output
    assert "Indexer pool:" not in output
