from pathlib import Path
import json

import pytest
from fastapi import HTTPException

from hermes_cli import web_server as ws


def test_workspace_preview_blocks_paths_outside_workspace(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside.txt"
    workspace.mkdir()
    outside.write_text("outside-data", encoding="utf-8")
    monkeypatch.setenv("TERMINAL_CWD", str(workspace))

    with pytest.raises(HTTPException) as exc:
        ws._workspace_preview_target(str(outside), str(workspace))

    assert exc.value.status_code == 403
    assert "outside workspace" in str(exc.value.detail).lower()


def test_workspace_text_read_blocks_sensitive_env_files(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("TERMINAL_CWD", str(workspace))
    env_file = workspace / ".env"
    env_file.write_text("TOKEN=project-value\n", encoding="utf-8")

    with pytest.raises(HTTPException) as exc:
        ws._workspace_read_file_text(str(env_file), str(workspace))

    assert exc.value.status_code == 403
    assert "environment file" in str(exc.value.detail)


@pytest.mark.parametrize(
    "relative_path",
    [
        ".ssh/id_ed25519",
        ".ssh/config",
        ".gnupg/private-keys-v1.d/key",
        ".aws/credentials",
        ".npmrc",
        ".netrc",
        ".pypirc",
        "certs/client.pem",
        "certs/client.p12",
        "certs/client.pfx",
    ],
)
def test_workspace_text_read_blocks_common_credential_files(monkeypatch, tmp_path: Path, relative_path: str):
    workspace = tmp_path / "workspace"
    target = workspace / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("credential material", encoding="utf-8")
    monkeypatch.setenv("TERMINAL_CWD", str(workspace))

    with pytest.raises(HTTPException) as exc:
        ws._workspace_read_file_text(str(target), str(workspace))

    assert exc.value.status_code == 403


@pytest.mark.parametrize(
    "sensitive_link",
    [
        ".env",
        ".npmrc",
        ".aws/credentials",
        ".ssh/config",
    ],
)
def test_workspace_text_read_blocks_symlinked_sensitive_names(monkeypatch, tmp_path: Path, sensitive_link: str):
    workspace = tmp_path / "workspace"
    target = workspace / "storage" / "plain.txt"
    link = workspace / sensitive_link
    target.parent.mkdir(parents=True, exist_ok=True)
    link.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("credential material", encoding="utf-8")
    link.symlink_to(target)
    monkeypatch.setenv("TERMINAL_CWD", str(workspace))

    with pytest.raises(HTTPException) as exc:
        ws._workspace_read_file_text(str(link), str(workspace))

    assert exc.value.status_code == 403


def test_workspace_text_read_is_bounded_before_loading(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("TERMINAL_CWD", str(workspace))
    target = workspace / "notes.txt"
    target.write_text("hello", encoding="utf-8")

    def fail_read_bytes(self):  # pragma: no cover - should never be called
        raise AssertionError("workspace text preview must not use Path.read_bytes()")

    monkeypatch.setattr(Path, "read_bytes", fail_read_bytes)

    result = ws._workspace_read_file_text(str(target), str(workspace))

    assert result["text"] == "hello"
    assert result["truncated"] is False


def test_workspace_read_dir_filters_sensitive_and_symlink_escape(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    monkeypatch.setenv("TERMINAL_CWD", str(workspace))
    (workspace / "safe.txt").write_text("ok", encoding="utf-8")
    (workspace / ".env").write_text("TOKEN=project-value", encoding="utf-8")
    (workspace / ".ssh").mkdir()
    (workspace / ".ssh" / "id_ed25519").write_text("credential material", encoding="utf-8")
    (workspace / ".npmrc").write_text("registry token", encoding="utf-8")
    (workspace / "plain-netrc-target").write_text("machine example", encoding="utf-8")
    (workspace / ".netrc").symlink_to(workspace / "plain-netrc-target")
    (outside / "leak.txt").write_text("leak", encoding="utf-8")
    (workspace / "outside-link").symlink_to(outside, target_is_directory=True)

    result = ws._workspace_read_dir(str(workspace), str(workspace))
    names = {entry["name"] for entry in result["entries"]}

    assert "safe.txt" in names
    assert ".env" not in names
    assert ".ssh" not in names
    assert ".npmrc" not in names
    assert ".netrc" not in names
    assert "outside-link" not in names


def test_workspace_data_url_blocks_outside_workspace(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside.png"
    workspace.mkdir()
    outside.write_bytes(b"not really an image")
    monkeypatch.setenv("TERMINAL_CWD", str(workspace))

    with pytest.raises(HTTPException) as exc:
        ws._workspace_read_file_data_url(str(outside), str(workspace))

    assert exc.value.status_code == 403


def test_workspace_base_dir_cannot_define_trust_root(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("TERMINAL_CWD", str(workspace))

    with pytest.raises(HTTPException) as exc:
        ws._workspace_read_file_text("/etc/passwd", "/")

    assert exc.value.status_code == 403
    detail = str(exc.value.detail).lower()
    assert "outside workspace" in detail or "base directory" in detail


def test_session_changes_ignore_legacy_write_file_diff():
    tool_msg = {
        "id": 10,
        "role": "tool",
        "tool_name": "write_file",
        "tool_call_id": "call-1",
        "content": json.dumps(
            {
                "files_modified": ["settings.txt"],
                "bytes_written": 12,
                "diff": "--- a/settings.txt\n+++ b/settings.txt\n@@\n-LEAKED_OLD_VALUE\n+replacement\n",
            }
        ),
    }
    call_args = {"call-1": {"path": "settings.txt", "content": "NEW_PRIVATE_VALUE\n"}}

    changes = ws._extract_tool_changes(tool_msg, call_args)
    payload = json.dumps(changes)

    assert "LEAKED_OLD_VALUE" not in payload
    assert "NEW_PRIVATE_VALUE" not in payload
    assert changes == [
        {
            "path": "settings.txt",
            "status": "modified",
            "added": 0,
            "removed": 0,
            "binary": False,
            "diff": [],
            "toolName": "write_file",
            "messageId": 10,
            "timestamp": None,
        }
    ]
