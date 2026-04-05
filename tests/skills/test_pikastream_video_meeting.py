from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "optional-skills"
    / "productivity"
    / "pikastream-video-meeting"
    / "scripts"
    / "pikastreaming_videomeeting.py"
)


def load_module():
    sys.modules.setdefault("requests", types.SimpleNamespace(delete=None, get=None, post=None, RequestException=Exception))
    spec = importlib.util.spec_from_file_location("pikastream_video_meeting_skill", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_infer_platform_recognizes_google_meet_and_zoom():
    mod = load_module()

    assert mod.infer_platform("https://meet.google.com/abc-defg-hij") == "google_meet"
    assert mod.infer_platform("https://us05web.zoom.us/j/123456789") == "zoom"
    assert mod.infer_platform("https://example.com/not-a-meeting") is None


def test_prepare_audio_returns_native_format_without_conversion(tmp_path: Path):
    mod = load_module()
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"fake-wav-data")

    assert mod.prepare_audio(str(audio)) == str(audio)


def test_get_devkey_falls_back_to_file(tmp_path: Path, monkeypatch):
    mod = load_module()
    devkey_file = tmp_path / ".pika" / "devkey"
    devkey_file.parent.mkdir(parents=True)
    devkey_file.write_text("dk_test_123\n", encoding="utf-8")

    monkeypatch.delenv("PIKA_DEV_KEY", raising=False)
    monkeypatch.setattr(mod, "DEVKEY_FILE", devkey_file)

    assert mod.get_devkey() == "dk_test_123"


def test_cmd_leave_returns_http_error_code_on_failed_delete(monkeypatch):
    mod = load_module()

    class Response:
        ok = False
        status_code = 500
        text = "boom"

    monkeypatch.setattr(mod, "get_api_config", lambda: ("https://api.example.test", {"Authorization": "DevKey dk_test"}))
    monkeypatch.setattr(mod.requests, "delete", lambda *args, **kwargs: Response())

    args = type("Args", (), {"session_id": "sess_123"})()
    assert mod.cmd_leave(args) == 3


def test_cmd_leave_returns_success_payload(monkeypatch, capsys):
    mod = load_module()

    class Response:
        ok = True
        status_code = 200
        text = ""

    monkeypatch.setattr(mod, "get_api_config", lambda: ("https://api.example.test", {"Authorization": "DevKey dk_test"}))
    monkeypatch.setattr(mod.requests, "delete", lambda *args, **kwargs: Response())

    args = type("Args", (), {"session_id": "sess_123"})()
    assert mod.cmd_leave(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"session_id": "sess_123", "closed": True}
