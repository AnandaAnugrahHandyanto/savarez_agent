import json

from hermes_cli.ops_social_live_counts import credential_inventory, probe_social_counts


def test_credential_inventory_redacts_values(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("YOUTUBE_API_KEY=secret-youtube-key\nYOUTUBE_CHANNEL_ID=channel-123456\n", encoding="utf-8")
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.delenv("YOUTUBE_CHANNEL_ID", raising=False)

    result = credential_inventory(["youtube"], env_file=env_file)
    payload = json.dumps(result)

    assert result["mode"] == "redacted_presence_only"
    assert "secret-youtube-key" not in payload
    assert "channel-123456" not in payload
    platform = result["platforms"][0]
    assert platform["can_attempt_probe"] is True
    assert {item["key"] for item in platform["credentials"]} >= {"YOUTUBE_API_KEY", "YOUTUBE_CHANNEL_ID"}


def test_probe_dry_run_does_not_call_http(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("TIKTOK_ACCESS_TOKEN=tiktok-token-123456\n", encoding="utf-8")

    def fail_http(*_args, **_kwargs):
        raise AssertionError("dry run must not call HTTP")

    result = probe_social_counts(["tiktok"], env_file=env_file, http_get=fail_http, dry_run=True)

    assert result["dry_run"] is True
    assert result["platforms"][0]["platform"] == "TikTok"
    assert result["platforms"][0]["status"] == "needs_sync"
    assert result["snapshot"] is None


def test_youtube_token_file_inventory_and_probe(tmp_path, monkeypatch):
    token_file = tmp_path / "youtube_token_signalroom.json"
    token_file.write_text(json.dumps({"token": "youtube-access-token", "channel_id": "UC123", "scopes": ["scope"], "expiry": "2099-01-01T00:00:00Z"}), encoding="utf-8")
    monkeypatch.setenv("YOUTUBE_TOKEN_FILE", str(token_file))

    inventory = credential_inventory(["youtube"], env_file=tmp_path / ".env")
    token_meta = [item for item in inventory["platforms"][0]["credentials"] if item["key"] == "YOUTUBE_TOKEN_FILE"][0]
    assert inventory["platforms"][0]["can_attempt_probe"] is True
    assert token_meta["present"] is True
    assert token_meta["path_name"] == "youtube_token_signalroom.json"

    def fake_http(url, headers, timeout):
        assert "mine=true" in url
        assert headers["Authorization"] == "Bearer youtube-access-token"
        return {"ok": True, "status_code": 200, "json": {"items": [{"statistics": {"videoCount": "7"}}]}}

    result = probe_social_counts(["youtube"], env_file=tmp_path / ".env", http_get=fake_http)
    payload = json.dumps(result)
    assert result["platforms"][0]["published"] == "7"
    assert "youtube-access-token" not in payload


def test_probe_youtube_with_mock_http_writes_snapshot(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("YOUTUBE_API_KEY=secret-youtube-key\nYOUTUBE_CHANNEL_ID=channel-123456\n", encoding="utf-8")
    calls = []

    def fake_http(url, headers, timeout):
        calls.append((url, headers, timeout))
        return {"ok": True, "status_code": 200, "json": {"items": [{"statistics": {"videoCount": "42"}}]}}

    result = probe_social_counts(["youtube"], env_file=env_file, http_get=fake_http, write_snapshot=False)
    payload = json.dumps(result)

    assert calls
    assert result["platforms"][0]["published"] == "42"
    assert result["platforms"][0]["status"] == "ok"
    assert "secret-youtube-key" not in payload
    assert "channel-123456" not in payload


def test_probe_missing_credentials_returns_not_connected(tmp_path):
    result = probe_social_counts(["facebook"], env_file=tmp_path / ".env")

    assert result["platforms"][0]["platform"] == "Facebook"
    assert result["platforms"][0]["status"] == "not_connected"
    assert result["credential_inventory"]["platforms"][0]["can_attempt_probe"] is False


def test_probe_http_error_redacts_env_secret(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("TIKTOK_ACCESS_TOKEN=file-token-should-not-print\n", encoding="utf-8")
    monkeypatch.setenv("TIKTOK_ACCESS_TOKEN", "process-token-should-not-print")

    def fake_http(_url, _headers, _timeout):
        return {"ok": False, "status_code": 401, "error": "bad process-token-should-not-print"}

    result = probe_social_counts(["tiktok"], env_file=env_file, http_get=fake_http)
    payload = json.dumps(result)

    assert result["platforms"][0]["status"] == "needs_review"
    assert "process-token-should-not-print" not in payload
    assert "file-token-should-not-print" not in payload
