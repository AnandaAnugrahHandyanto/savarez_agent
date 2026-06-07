from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent
from gateway.session import SessionEntry, SessionSource, build_session_key
from gateway.status_card import format_hermes_status_card


def test_format_hermes_status_card_matches_compact_telegram_shape():
    text = format_hermes_status_card(
        {
            "version": "0.15.1",
            "commit": "c6501c0",
            "gateway_uptime_seconds": 2 * 3600 + 14 * 60,
            "system_uptime_seconds": 1 * 86400 + 5 * 3600,
            "model": "azure-foundry/gpt-5.5-1",
            "fallbacks": ["deepseek/deepseek-v4-pro", "deepseek/deepseek-v4-flash"],
            "input_tokens": 64_000,
            "output_tokens": 3_000,
            "estimated_cost_usd": 0.12,
            "cache_hit_pct": 22,
            "cache_read_tokens": 14_000,
            "cache_write_tokens": 0,
            "context_tokens": 64_000,
            "context_limit": 1_000_000,
            "compactions": 0,
            "session_id": "20260602_xxx",
            "active_tasks": 0,
            "queue_mode": "steer",
            "queue_depth": 0,
        }
    )

    assert text == "\n".join(
        [
            "🪽 Hermes 0.15.1 (c6501c0)",
            "⏱️ Uptime: gateway 2h 14m · system 1d 5h",
            "🧠 Model: azure-foundry/gpt-5.5-1",
            "🔄 Fallbacks: deepseek/deepseek-v4-pro, deepseek/deepseek-v4-flash",
            "🧮 Tokens: 64k in / 3k out · 💵 Cost: $0.12",
            "🗄️ Cache: 22% hit · 14k read, 0 write",
            "📚 Context: 64k/1.0m (6%) · 🧹 Compactions: 0",
            "🧵 Session: 20260602_xxx",
            "📌 Tasks: 0 active",
            "🪢 Queue: steer (depth 0)",
        ]
    )
    assert "Execution" not in text
    assert "Runtime" not in text
    assert "Platforms" not in text


def test_format_hermes_status_card_handles_missing_optional_values():
    text = format_hermes_status_card(
        {
            "version": "0.15.1",
            "commit": None,
            "gateway_uptime_seconds": None,
            "system_uptime_seconds": None,
            "model": "unknown",
            "fallbacks": [],
            "input_tokens": 0,
            "output_tokens": 0,
            "estimated_cost_usd": None,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "context_tokens": None,
            "context_limit": None,
            "compactions": None,
            "session_id": "sess-1",
            "active_tasks": 2,
            "queue_mode": "queue",
            "queue_depth": 3,
        }
    )

    assert "🪽 Hermes 0.15.1" in text
    assert "⏱️ Uptime: gateway unknown · system unknown" in text
    assert "🔄 Fallbacks: none" in text
    assert "🧮 Tokens: 0 in / 0 out · 💵 Cost: unknown" in text
    assert "🗄️ Cache: 0% hit · 0 read, 0 write" in text
    assert "📚 Context: unknown · 🧹 Compactions: unknown" in text
    assert "📌 Tasks: 2 active" in text
    assert "🪢 Queue: queue (depth 3)" in text


@pytest.mark.asyncio
async def test_gateway_status_command_uses_compact_status_card(monkeypatch):
    from gateway.run import GatewayRunner
    import gateway.run as gateway_run

    source = SessionSource(
        platform=Platform.TELEGRAM,
        user_id="u1",
        chat_id="c1",
        user_name="tester",
        chat_type="dm",
    )
    session_entry = SessionEntry(
        session_key=build_session_key(source),
        session_id="20260602_xxx",
        created_at=datetime.now() - timedelta(hours=1),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
        last_prompt_tokens=42_000,
    )

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="***")}
    )
    runner.adapters = {Platform.TELEGRAM: MagicMock()}
    runner.session_store = MagicMock()
    runner.session_store.get_or_create_session.return_value = session_entry
    runner._session_db = MagicMock()
    runner._session_db.get_session_title.return_value = None
    runner._session_db.get_session.return_value = {
        "input_tokens": 64_000,
        "output_tokens": 3_000,
        "cache_read_tokens": 14_000,
        "cache_write_tokens": 0,
        "estimated_cost_usd": 0.12,
    }
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._background_tasks = set()
    runner._busy_input_mode = "steer"
    runner._queue_depth = lambda *_args, **_kwargs: 0

    monkeypatch.setattr(gateway_run, "_status_gateway_uptime_seconds", lambda: 8040)
    monkeypatch.setattr(gateway_run, "_status_system_uptime_seconds", lambda: 104400)
    monkeypatch.setattr(gateway_run, "_status_git_short_sha", lambda: "c6501c0")
    monkeypatch.setattr(
        gateway_run,
        "_load_gateway_runtime_config",
        lambda: {
            "model": {
                "provider": "azure-foundry",
                "default": "gpt-5.5-1",
                "context_length": 1_000_000,
            },
            "fallback_providers": [
                {"provider": "deepseek", "model": "deepseek-v4-pro"},
                {"provider": "deepseek", "model": "deepseek-v4-flash"},
            ],
        },
    )

    text = await runner._handle_status_command(MessageEvent(text="/status", source=source))

    assert text.splitlines() == [
        "🪽 Hermes 0.15.1 (c6501c0)",
        "⏱️ Uptime: gateway 2h 14m · system 1d 5h",
        "🧠 Model: azure-foundry/gpt-5.5-1",
        "🔄 Fallbacks: deepseek/deepseek-v4-pro, deepseek/deepseek-v4-flash",
        "🧮 Tokens: 64k in / 3k out · 💵 Cost: $0.12",
        "🗄️ Cache: 18% hit · 14k read, 0 write",
        "📚 Context: 42k/1.0m (4%) · 🧹 Compactions: 0",
        "🧵 Session: 20260602_xxx",
        "📌 Tasks: 0 active",
        "🪢 Queue: steer (depth 0)",
    ]


@pytest.mark.asyncio
async def test_gateway_status_context_does_not_use_cumulative_input_tokens(monkeypatch):
    from gateway.run import GatewayRunner
    import gateway.run as gateway_run

    source = SessionSource(
        platform=Platform.TELEGRAM,
        user_id="u1",
        chat_id="c1",
        user_name="tester",
        chat_type="dm",
    )
    session_entry = SessionEntry(
        session_key=build_session_key(source),
        session_id="20260602_xxx",
        created_at=datetime.now() - timedelta(hours=1),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
        last_prompt_tokens=0,
    )

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="***")}
    )
    runner.adapters = {Platform.TELEGRAM: MagicMock()}
    runner.session_store = MagicMock()
    runner.session_store.get_or_create_session.return_value = session_entry
    runner._session_db = MagicMock()
    runner._session_db.get_session_title.return_value = None
    runner._session_db.get_session.return_value = {
        "input_tokens": 713_600,
        "output_tokens": 26_800,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "estimated_cost_usd": 0.0,
    }
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._background_tasks = set()
    runner._busy_input_mode = "queue"
    runner._queue_depth = lambda *_args, **_kwargs: 0

    monkeypatch.setattr(gateway_run, "_status_gateway_uptime_seconds", lambda: 60)
    monkeypatch.setattr(gateway_run, "_status_system_uptime_seconds", lambda: 60)
    monkeypatch.setattr(gateway_run, "_status_git_short_sha", lambda: "c6501c0")
    monkeypatch.setattr(
        gateway_run,
        "_load_gateway_runtime_config",
        lambda: {
            "model": {
                "provider": "azure-foundry",
                "default": "gpt-5.5-1",
                "context_length": 1_000_000,
            },
            "fallback_providers": [],
        },
    )

    text = await runner._handle_status_command(MessageEvent(text="/status", source=source))

    assert "🧮 Tokens: 713.6k in / 26.8k out" in text
    assert "📚 Context: unknown · 🧹 Compactions: 0" in text
    assert "713.6k/1.0m" not in text
