from __future__ import annotations

import importlib.util
from pathlib import Path


def test_default_profiles_root_ignores_profile_scoped_hermes_home(monkeypatch, tmp_path):
    root = tmp_path / ".hermes"
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_HOME", str(root / "profiles" / "worker"))
    monkeypatch.delenv("HERMES_ROOT", raising=False)
    monkeypatch.delenv("HERMES_MATRIX_PROFILES_ROOT", raising=False)
    module = load_script_module()

    assert module.default_profiles_root() == root


def test_default_profiles_root_collapses_synthetic_profile_home(monkeypatch, tmp_path):
    root = tmp_path / ".hermes"
    monkeypatch.setenv("HOME", str(root / "profiles" / "worker" / "home"))
    monkeypatch.delenv("HERMES_HOME", raising=False)
    monkeypatch.delenv("HERMES_ROOT", raising=False)
    monkeypatch.delenv("HERMES_MATRIX_PROFILES_ROOT", raising=False)
    module = load_script_module()

    assert module.default_profiles_root() == root


def test_default_profiles_root_accepts_explicit_profiles_root(monkeypatch, tmp_path):
    explicit_root = tmp_path / "custom-hermes-root"
    monkeypatch.setenv("HERMES_MATRIX_PROFILES_ROOT", str(explicit_root))
    module = load_script_module()

    assert module.default_profiles_root() == explicit_root


def load_script_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "verify_matrix_profile_devices.py"
    spec = importlib.util.spec_from_file_location("verify_matrix_profile_devices", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manual_fallback_notice_says_client_command_not_room_message():
    module = load_script_module()

    lines = module.manual_verification_lines("DEVICE123", "ed25519-fingerprint")

    joined = "\n".join(lines)
    assert "manual_verify_command=/verify DEVICE123 ed25519-fingerprint" in joined
    assert "run_from=already_verified_matrix_client_for_same_account" in joined
    assert "do_not_send_as=bot_gateway_message_or_room_chat" in joined
    assert "This is a local Matrix client command" in joined


def test_sign_without_recovery_key_prints_manual_action_and_no_send_instruction(monkeypatch, capsys, tmp_path):
    module = load_script_module()
    root = tmp_path
    (root / "profiles" / "worker").mkdir(parents=True)
    (root / "profiles" / "worker" / ".env").write_text(
        "MATRIX_HOMESERVER=https://matrix.example\n"
        "MATRIX_ACCESS_TOKEN=secret-token\n"
        "MATRIX_USER_ID=@bot:matrix.example\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setattr(
        module,
        "query_signature_status",
        lambda env: {
            "user": "@bot:matrix.example",
            "device_id": "DEVICE123",
            "ed25519": "ed25519-fingerprint",
            "self_signing_public_key": "ssk-public",
            "signed_by_self_signing_key": False,
            "signature_keyids": [],
        },
    )

    exit_code = module.main_sync(["--profiles", "worker", "--sign", "--require-signed"])

    out = capsys.readouterr().out
    assert exit_code == 2
    assert "sign_attempt=skipped_missing_MATRIX_RECOVERY_KEY" in out
    assert "manual_verify_command=/verify DEVICE123 ed25519-fingerprint" in out
    assert "manual_verify_run_from=already_verified_matrix_client_for_same_account" in out
    assert "manual_verify_do_not_send_as=bot_gateway_message_or_room_chat" in out
    assert "no bot/gateway message will be sent" in out
