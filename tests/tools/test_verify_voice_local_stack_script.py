import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "verify_voice_local_stack.py"
)


def _load_script_module():
    spec = importlib.util.spec_from_file_location("verify_voice_local_stack", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _args(**overrides):
    values = {
        "provider": "kokoro",
        "voice": "af_heart",
        "speed": "1.0",
        "tts_timeout": 180.0,
        "stream_timeout": 180.0,
        "full_duplex_timeout": 90.0,
        "command_text": "command smoke",
        "stream_text": "stream smoke",
        "stream_command_template": None,
        "skip_full_duplex": False,
        "voice_repo": Path("/voice"),
        "webrtc_python_bin": None,
        "full_duplex_inbound_text": "hello world",
        "full_duplex_outbound_text": "hello back",
        "expect_word": ["hello", "world"],
        "keep_home": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_command_tts_command_uses_isolated_hermes_home():
    script = _load_script_module()

    command = script.command_tts_command(
        _args(keep_home=True),
        voice_bin="/tmp/voice",
        hermes_home=Path("/tmp/hermes-home"),
    )

    assert command[:2] == [sys.executable, str(script.script_path("verify_voice_command_tts.py"))]
    assert "--voice-bin" in command
    assert "/tmp/voice" in command
    assert "--hermes-home" in command
    assert "/tmp/hermes-home" in command
    assert "--force" in command
    assert "--keep-home" in command
    assert command[-2:] == ["--text", "command smoke"]


def test_stream_tts_command_can_use_custom_template():
    script = _load_script_module()

    command = script.stream_tts_command(
        _args(stream_command_template="voice stream --raw-output -"),
        voice_bin="/tmp/voice",
    )

    assert command[:2] == [sys.executable, str(script.script_path("verify_voice_stream_tts.py"))]
    assert "--voice-bin" in command
    assert "/tmp/voice" in command
    assert "--command-template" in command
    assert "voice stream --raw-output -" in command


def test_full_duplex_command_passes_voice_repo_and_python():
    script = _load_script_module()

    command = script.full_duplex_command(
        _args(webrtc_python_bin="/tmp/venv/bin/python", expect_word=["testing"]),
        voice_bin="/tmp/voice",
        voice_repo=Path("/voice"),
    )

    assert command[:2] == [
        sys.executable,
        str(script.script_path("verify_voice_full_duplex_sidecar.py")),
    ]
    assert "--voice-repo" in command
    assert "/voice" in command
    assert "--python-bin" in command
    assert "/tmp/venv/bin/python" in command
    assert command[-2:] == ["--expect-word", "testing"]


def test_resolve_voice_repo_requires_full_duplex_checkout(tmp_path: Path):
    script = _load_script_module()

    with pytest.raises(SystemExit, match="full-duplex validation needs"):
        script.resolve_voice_repo_for_full_duplex(_args(voice_repo=None))

    assert script.resolve_voice_repo_for_full_duplex(
        _args(skip_full_duplex=True, voice_repo=None)
    ) is None

    with pytest.raises(SystemExit, match="voice full-duplex smoke not found"):
        script.resolve_voice_repo_for_full_duplex(_args(voice_repo=tmp_path))


def test_parse_json_object_accepts_progress_prefix():
    script = _load_script_module()

    parsed = script.parse_json_object('progress\n{"success": true, "value": 1}\n')

    assert parsed == {"success": True, "value": 1}


def test_run_json_step_rejects_unsuccessful_result(monkeypatch):
    script = _load_script_module()

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"success": False, "error": "bad"}),
            stderr="",
        )

    monkeypatch.setattr(script, "run_process", fake_run)

    with pytest.raises(SystemExit, match="reported failure"):
        script.run_json_step("demo", ["demo"], timeout=1.0, env={})
