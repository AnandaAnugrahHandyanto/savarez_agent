"""Tests for the ContextOps active cognitive hydration adapter.

These tests assert the *active* (pre-answer) hydration path that injects a
compact ContextOps restore/avoid/epistemic-mode block into the API-call user
context — NOT the dry-run preview/watchdog path. The adapter must:

* be disabled by default,
* fail closed (return ``None`` + skipped reason) when config, seed, or channel
  identity is missing or not allowlisted, and
* perform only metadata/context injection — no message dispatch, no memory
  writes, no kanban mutation, no gateway restart.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from contextops.active_hydration import (
    ACTIVE_HYDRATION_CONFIG_PATH,
    build_active_context,
)

SEED_PATH = Path(__file__).parent / "fixtures" / "epistemic_state_engine_seed.yaml"
PRESSURE_MESSAGE = "the unresolved coupling anomaly is recurring; restore that contradiction"
CHANNEL_KEY = "agent:main:discord:channel:contextops"


def _agent(**overrides):
    base = dict(
        platform="discord",
        _chat_id="123",
        _chat_name="#contextops",
        _thread_id=None,
        _gateway_session_key=CHANNEL_KEY,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _enabled_cfg(**overrides):
    cfg = {
        "contextops": {
            "active_cognitive_hydration": {
                "enabled": True,
                "seed_path": str(SEED_PATH),
                "channel_allowlist": [CHANNEL_KEY],
            }
        }
    }
    section = cfg["contextops"]["active_cognitive_hydration"]
    section.update(overrides)
    return cfg


def test_disabled_by_default_returns_no_injection() -> None:
    """No config at all -> no injection, no exception, skipped reason recorded."""

    text, health = build_active_context(
        agent=_agent(), original_user_message=PRESSURE_MESSAGE, config={}
    )
    assert text is None
    assert health["enabled"] is False
    assert health["skipped_reason"] == "disabled"


def test_explicit_disabled_flag_returns_no_injection() -> None:
    cfg = _enabled_cfg(enabled=False)
    text, health = build_active_context(
        agent=_agent(), original_user_message=PRESSURE_MESSAGE, config=cfg
    )
    assert text is None
    assert health["enabled"] is False
    assert health["skipped_reason"] == "disabled"


def test_enabled_and_allowlisted_injects_restore_avoid_epistemic_block() -> None:
    text, health = build_active_context(
        agent=_agent(),
        original_user_message=PRESSURE_MESSAGE,
        config=_enabled_cfg(),
    )
    assert text is not None
    assert health["enabled"] is True
    assert health["allowlisted"] is True
    assert health["skipped_reason"] is None
    lowered = text.lower()
    # Block must mark the cognitive-context framing, not generic "watchdog" /
    # "suggestion" naming.
    assert "epistemic" in lowered
    assert "watchdog" not in lowered
    assert "suggestion" not in lowered
    # Compact restore/avoid sections present.
    assert "restore" in lowered
    assert "avoid" in lowered
    # Restore-line content from the pressured thread must appear.
    assert "coupling" in lowered


def test_injection_block_is_metadata_only_no_raw_ids_paths_or_transcripts() -> None:
    text, _ = build_active_context(
        agent=_agent(),
        original_user_message=PRESSURE_MESSAGE,
        config=_enabled_cfg(),
    )
    assert text is not None
    # No raw thread/event IDs, no seed path, no gateway session key.
    assert "thread:" not in text
    assert "evt-" not in text
    assert str(SEED_PATH) not in text
    assert CHANNEL_KEY not in text
    # No transcript-style timestamps or @mentions / sender lines.
    assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", text)


def test_non_allowlisted_channel_is_skipped_closed() -> None:
    cfg = _enabled_cfg(channel_allowlist=["agent:main:discord:channel:other"])
    text, health = build_active_context(
        agent=_agent(),
        original_user_message=PRESSURE_MESSAGE,
        config=cfg,
    )
    assert text is None
    assert health["enabled"] is True
    assert health["allowlisted"] is False
    assert health["skipped_reason"] == "non_allowlisted"


def test_missing_allowlist_is_skipped_closed() -> None:
    cfg = _enabled_cfg()
    cfg["contextops"]["active_cognitive_hydration"].pop("channel_allowlist")
    text, health = build_active_context(
        agent=_agent(),
        original_user_message=PRESSURE_MESSAGE,
        config=cfg,
    )
    assert text is None
    assert health["skipped_reason"] == "non_allowlisted"


def test_no_channel_identity_is_skipped_closed() -> None:
    cfg = _enabled_cfg()
    no_channel = _agent(_gateway_session_key=None, _chat_id=None, platform=None)
    text, health = build_active_context(
        agent=no_channel,
        original_user_message=PRESSURE_MESSAGE,
        config=cfg,
    )
    assert text is None
    assert health["skipped_reason"] == "no_channel"


def test_missing_seed_path_is_skipped_closed() -> None:
    cfg = _enabled_cfg()
    cfg["contextops"]["active_cognitive_hydration"].pop("seed_path")
    text, health = build_active_context(
        agent=_agent(),
        original_user_message=PRESSURE_MESSAGE,
        config=cfg,
    )
    assert text is None
    assert health["skipped_reason"] == "no_seed"


def test_unreadable_seed_path_is_skipped_closed(tmp_path) -> None:
    bogus = tmp_path / "does_not_exist.yaml"
    cfg = _enabled_cfg(seed_path=str(bogus))
    text, health = build_active_context(
        agent=_agent(),
        original_user_message=PRESSURE_MESSAGE,
        config=cfg,
    )
    assert text is None
    assert health["skipped_reason"] == "seed_unavailable"


def test_empty_message_is_skipped_closed() -> None:
    cfg = _enabled_cfg()
    text, health = build_active_context(
        agent=_agent(), original_user_message="   ", config=cfg
    )
    assert text is None
    assert health["skipped_reason"] == "empty_message"


def test_static_scan_no_send_message_or_dispatch_or_kanban_in_adapter() -> None:
    """Hard guard: the active hydration layer must contain no send/dispatch/
    kanban-mutation/gateway-restart code paths.
    """

    src = Path("contextops/active_hydration.py").read_text(encoding="utf-8")
    forbidden = (
        "send_message",
        "dispatch_message",
        "kanban_write",
        "kanban_mutate",
        "memory_write",
        "restart_gateway",
        "subprocess.",
        "os.system",
    )
    for token in forbidden:
        assert token not in src, f"forbidden token {token!r} found in active hydration adapter"


def test_config_path_constant_is_active_cognitive_naming() -> None:
    """Naming must reflect active cognitive context, not watchdog/suggestions."""

    assert ACTIVE_HYDRATION_CONFIG_PATH == ("contextops", "active_cognitive_hydration")


def test_conversation_loop_wires_active_hydration_into_user_injections() -> None:
    """Static wiring check: ``conversation_loop.py`` must call the active
    hydration adapter and append its output alongside ``_plugin_user_context``
    in the per-turn user-message injection block.

    A static scan rather than a full end-to-end loop test keeps this regression
    cheap while still failing loudly if the integration point gets renamed,
    moved out of the API-call injection path, or wired into the system prompt
    (which would break prompt caching).
    """

    src = Path("agent/conversation_loop.py").read_text(encoding="utf-8")
    assert "from contextops.active_hydration import build_active_context" in src
    assert "_contextops_active_user_context" in src
    # Must be appended into the existing _injections list (user-message path),
    # not concatenated into the system prompt.
    assert "_injections.append(_contextops_active_user_context)" in src
    # The wiring must compute the active context BEFORE the API-call loop —
    # i.e. it appears in the file before the line that builds the system
    # prompt for the API request.
    wiring_idx = src.index("from contextops.active_hydration import build_active_context")
    sys_prompt_idx = src.index("effective_system = active_system_prompt or \"\"")
    assert wiring_idx < sys_prompt_idx


def test_returns_health_dict_structure() -> None:
    text, health = build_active_context(
        agent=_agent(),
        original_user_message=PRESSURE_MESSAGE,
        config=_enabled_cfg(),
    )
    assert text is not None
    for key in ("enabled", "allowlisted", "channel", "skipped_reason"):
        assert key in health
    assert health["channel"] == CHANNEL_KEY
