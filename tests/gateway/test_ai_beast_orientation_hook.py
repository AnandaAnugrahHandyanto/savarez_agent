"""Tests for the opt-in AI Beast orientation gateway hook.

The hook must stay disabled by default, preserve Hermes-owned commands, and only
delegate read-only orientation commands through an explicit local AI Beast root.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


HOOK_MODULE = "gateway.ai_beast_orientation_hook"



def _write_fake_ai_beast_adapter(project_root: Path) -> None:
    package = project_root / "ai_beast_registry"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "loader.py").write_text(
        "from pathlib import Path\n"
        "class RegistryError(ValueError):\n"
        "    pass\n"
        "def load_registry(workspaces_path, bindings_path):\n"
        "    workspaces = Path(workspaces_path)\n"
        "    bindings = Path(bindings_path)\n"
        "    if not workspaces.exists() or not bindings.exists():\n"
        "        raise RegistryError('registry files missing')\n"
        "    return {'workspaces': workspaces, 'bindings': bindings}\n",
        encoding="utf-8",
    )
    (package / "telegram_adapter.py").write_text(
        "from .loader import RegistryError\n"
        "CALLS = []\n"
        "def handle_telegram_orientation_command(text, registry, *, chat_id=None, thread_id=None, bot_username=None):\n"
        "    CALLS.append((text, registry['workspaces'].name, registry['bindings'].name, chat_id, thread_id, bot_username))\n"
        "    if text == '/projects':\n"
        "        return 'Projects (read-only registry):\\n- AI Beast [ai-beast]'\n"
        "    if text == '/whereami':\n"
        "        return f'Workspace: AI Beast\\nchat={chat_id} thread={thread_id} bot={bot_username}'\n"
        "    raise RegistryError(f'unsupported command: {text}')\n",
        encoding="utf-8",
    )


def _write_fake_registry(project_root: Path) -> None:
    registry_root = project_root / "docs" / "interaction-layer" / "registry"
    registry_root.mkdir(parents=True)
    (registry_root / "workspaces.json").write_text('{"workspaces": [], "projects": []}\n', encoding="utf-8")
    (registry_root / "bindings.json").write_text('{"bindings": []}\n', encoding="utf-8")


def _clear_fake_ai_beast_modules() -> None:
    for name in list(sys.modules):
        if name == "ai_beast_registry" or name.startswith("ai_beast_registry."):
            sys.modules.pop(name, None)


def _load_hook_module():
    """Load the future hook module.

    RED expectation: this currently raises ModuleNotFoundError because the
    Hermes-side AI Beast orientation hook has not been implemented yet.
    """
    return importlib.import_module(HOOK_MODULE)


def _context(command: str, *, project_root: Path | None = None) -> dict:
    config: dict[str, object] = {
        "enabled": project_root is not None,
    }
    if project_root is not None:
        config["project_root"] = str(project_root)
    return {
        "command": command,
        "raw_args": "",
        "message": f"/{command}",
        "source": SimpleNamespace(
            platform="telegram",
            chat_id="chat-1",
            thread_id="thread-1",
            user_id="user-1",
        ),
        "gateway_config": SimpleNamespace(ai_beast_orientation=config),
    }


def test_ai_beast_orientation_hook_module_loads_for_green_slice():
    hook = _load_hook_module()

    assert hasattr(hook, "handle")


@pytest.mark.asyncio
async def test_ai_beast_orientation_whereami_requires_explicit_enabled_root(tmp_path):
    hook = _load_hook_module()
    fake_adapter = Mock(return_value="AI Beast: workspace orientation")

    result = await hook.handle(
        "command:whereami",
        _context("whereami", project_root=tmp_path),
        orientation_adapter=fake_adapter,
    )

    assert result == {
        "decision": "handled",
        "message": "AI Beast: workspace orientation",
    }
    fake_adapter.assert_called_once()




@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("whereami", "Workspace: AI Beast"),
        ("projects", "Projects (read-only registry):"),
    ],
)
async def test_ai_beast_orientation_lazily_wires_read_only_adapter_from_explicit_root(
    tmp_path, monkeypatch, command, expected
):
    hook = _load_hook_module()
    _write_fake_ai_beast_adapter(tmp_path)
    _write_fake_registry(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    _clear_fake_ai_beast_modules()

    result = await hook.handle(
        f"command:{command}",
        _context(command, project_root=tmp_path),
    )

    assert result["decision"] == "handled"
    assert expected in result["message"]


@pytest.mark.asyncio
async def test_ai_beast_orientation_lazy_adapter_uses_gateway_context_without_side_effects(tmp_path, monkeypatch):
    hook = _load_hook_module()
    _write_fake_ai_beast_adapter(tmp_path)
    _write_fake_registry(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    _clear_fake_ai_beast_modules()

    result = await hook.handle(
        "command:whereami",
        _context("whereami", project_root=tmp_path),
        side_effects={
            "memory_write": Mock(side_effect=AssertionError("memory write called")),
            "kanban_mutation": Mock(side_effect=AssertionError("Kanban mutation called")),
            "durable_continuation": Mock(side_effect=AssertionError("durable continuation called")),
            "binding_write": Mock(side_effect=AssertionError("binding write called")),
            "telegram_send": Mock(side_effect=AssertionError("live Telegram send called")),
        },
    )

    assert result["decision"] == "handled"
    assert "chat=chat-1 thread=thread-1" in result["message"]


@pytest.mark.asyncio
async def test_ai_beast_orientation_lazy_adapter_fails_closed_without_registry(tmp_path, monkeypatch):
    hook = _load_hook_module()
    _write_fake_ai_beast_adapter(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    _clear_fake_ai_beast_modules()

    result = await hook.handle(
        "command:whereami",
        _context("whereami", project_root=tmp_path),
    )

    assert result["decision"] == "deny"
    assert "AI Beast orientation adapter failed" in result["message"]


@pytest.mark.asyncio
async def test_ai_beast_orientation_lazy_import_does_not_pollute_sys_modules(tmp_path, monkeypatch):
    hook = _load_hook_module()
    _write_fake_ai_beast_adapter(tmp_path)
    _write_fake_registry(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    _clear_fake_ai_beast_modules()

    result = await hook.handle(
        "command:whereami",
        _context("whereami", project_root=tmp_path),
    )

    assert result["decision"] == "handled"
    assert not any(
        name == "ai_beast_registry" or name.startswith("ai_beast_registry.")
        for name in sys.modules
    )


@pytest.mark.asyncio
async def test_ai_beast_orientation_rejects_registry_file_symlink_escape(tmp_path, monkeypatch):
    hook = _load_hook_module()
    _write_fake_ai_beast_adapter(tmp_path)
    _write_fake_registry(tmp_path)
    outside_file = tmp_path.parent / "outside-workspaces.json"
    outside_file.write_text('{"workspaces": [], "projects": []}\n', encoding="utf-8")
    registry_root = tmp_path / "docs" / "interaction-layer" / "registry"
    (registry_root / "workspaces.json").unlink()
    (registry_root / "workspaces.json").symlink_to(outside_file)
    monkeypatch.syspath_prepend(str(tmp_path))
    _clear_fake_ai_beast_modules()

    result = await hook.handle(
        "command:whereami",
        _context("whereami", project_root=tmp_path),
    )

    assert result["decision"] == "deny"
    assert "AI Beast orientation adapter failed" in result["message"]


@pytest.mark.asyncio
async def test_ai_beast_orientation_is_disabled_by_default(tmp_path):
    hook = _load_hook_module()
    fake_adapter = Mock(side_effect=AssertionError("disabled hook called adapter"))

    result = await hook.handle(
        "command:whereami",
        _context("whereami", project_root=None),
        orientation_adapter=fake_adapter,
    )

    assert result is None
    fake_adapter.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("command", ["status", "sessions"])
async def test_ai_beast_orientation_cannot_hijack_hermes_owned_commands(tmp_path, command):
    hook = _load_hook_module()
    fake_adapter = Mock(side_effect=AssertionError(f"/{command} was hijacked"))

    result = await hook.handle(
        f"command:{command}",
        _context(command, project_root=tmp_path),
        orientation_adapter=fake_adapter,
    )

    assert result is None
    fake_adapter.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "command",
    ["task", "steer", "pause", "resume", "bindtopic", "switch", "open", "newsession"],
)
async def test_ai_beast_orientation_forbidden_commands_remain_unavailable(tmp_path, command):
    hook = _load_hook_module()
    fake_adapter = Mock(side_effect=AssertionError(f"forbidden /{command} dispatched"))

    result = await hook.handle(
        f"command:{command}",
        _context(command, project_root=tmp_path),
        orientation_adapter=fake_adapter,
    )

    assert result is None
    fake_adapter.assert_not_called()


@pytest.mark.asyncio
async def test_ai_beast_orientation_rejects_invalid_explicit_root(tmp_path):
    hook = _load_hook_module()
    missing_root = tmp_path / "missing-ai-beast-root"
    fake_adapter = Mock(side_effect=AssertionError("invalid root reached adapter"))

    result = await hook.handle(
        "command:whereami",
        _context("whereami", project_root=missing_root),
        orientation_adapter=fake_adapter,
    )

    assert result == {
        "decision": "deny",
        "message": "AI Beast orientation root is not available.",
    }
    fake_adapter.assert_not_called()


@pytest.mark.asyncio
async def test_ai_beast_orientation_hook_does_not_call_forbidden_side_effects(tmp_path):
    hook = _load_hook_module()
    side_effects = {
        "memory_write": Mock(side_effect=AssertionError("memory write called")),
        "kanban_mutation": Mock(side_effect=AssertionError("Kanban mutation called")),
        "durable_continuation": Mock(side_effect=AssertionError("durable continuation called")),
        "binding_write": Mock(side_effect=AssertionError("binding write called")),
        "smart_routing": Mock(side_effect=AssertionError("smart routing called")),
        "inbox_persistence": Mock(side_effect=AssertionError("inbox persistence called")),
        "telegram_send": Mock(side_effect=AssertionError("live Telegram send called")),
    }
    fake_adapter = Mock(return_value="AI Beast: read-only orientation")

    result = await hook.handle(
        "command:whereami",
        _context("whereami", project_root=tmp_path),
        orientation_adapter=fake_adapter,
        side_effects=side_effects,
    )

    assert result["decision"] == "handled"
    for forbidden_call in side_effects.values():
        forbidden_call.assert_not_called()
