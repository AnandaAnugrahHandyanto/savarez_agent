"""RED tests for the opt-in AI Beast orientation gateway hook.

These tests intentionally describe the next Hermes-side hook before the handler
exists.  The GREEN slice should add the smallest disabled-by-default handler
that delegates only to a caller-supplied, local/read-only AI Beast adapter.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


HOOK_MODULE = "gateway.ai_beast_orientation_hook"


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
