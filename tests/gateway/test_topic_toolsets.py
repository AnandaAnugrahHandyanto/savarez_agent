from gateway.config import Platform
from gateway.session import SessionSource
from gateway.topic_toolsets import resolve_channel_toolset_names, resolve_gateway_toolsets


def _source(chat_id="-1001", thread_id: str | None = "255", chat_type="group", parent_chat_id=None):
    return SessionSource(
        platform=Platform.TELEGRAM,
        chat_id=chat_id,
        chat_type=chat_type,
        thread_id=thread_id,
        parent_chat_id=parent_chat_id,
    )


def test_exact_chat_thread_toolsets_win_over_thread_and_default():
    cfg = {
        "telegram": {
            "channel_toolsets": {
                "default": ["web", "no_mcp"],
                "255": ["web", "terminal", "no_mcp"],
                "-1001:255": ["file", "lighthouse"],
            }
        },
        "mcp_servers": {
            "lighthouse": {"enabled": True},
            "plaud": {"enabled": True},
        },
        "platform_toolsets": {"telegram": ["web", "terminal"]},
    }

    names = resolve_channel_toolset_names(cfg, "telegram", _source())
    assert names == ["file", "lighthouse"]

    effective = resolve_gateway_toolsets(cfg, "telegram", _source())
    assert "file" in effective
    assert "lighthouse" in effective
    assert "plaud" not in effective
    assert "terminal" not in effective


def test_thread_toolsets_allowlist_mcp_server_without_default_mcp_surface():
    cfg = {
        "telegram": {"channel_toolsets": {"260": ["web", "lighthouse"]}},
        "mcp_servers": {
            "lighthouse": {"enabled": True},
            "plaud": {"enabled": True},
        },
        "platform_toolsets": {"telegram": ["web", "terminal"]},
    }

    effective = resolve_gateway_toolsets(cfg, "telegram", _source(thread_id="260"))
    assert "web" in effective
    assert "lighthouse" in effective
    assert "plaud" not in effective
    assert "terminal" not in effective


def test_default_channel_toolsets_can_disable_all_mcp():
    cfg = {
        "telegram": {"channel_toolsets": {"default": ["web", "no_mcp"]}},
        "mcp_servers": {
            "lighthouse": {"enabled": True},
            "plaud": {"enabled": True},
        },
        "platform_toolsets": {"telegram": ["web", "terminal"]},
    }

    effective = resolve_gateway_toolsets(cfg, "telegram", _source(thread_id="999"))
    assert "web" in effective
    assert "terminal" not in effective
    assert "lighthouse" not in effective
    assert "plaud" not in effective


def test_missing_channel_toolsets_falls_back_to_platform_toolsets():
    cfg = {
        "platform_toolsets": {"telegram": ["web", "terminal", "no_mcp"]},
        "mcp_servers": {"lighthouse": {"enabled": True}},
    }

    effective = resolve_gateway_toolsets(cfg, "telegram", _source(thread_id="999"))
    assert "web" in effective
    assert "terminal" in effective
    assert "lighthouse" not in effective


def test_telegram_general_without_thread_uses_topic_one_before_default():
    cfg = {
        "telegram": {
            "channel_toolsets": {
                "1": ["clarify", "no_mcp"],
                "default": ["web", "no_mcp"],
            }
        },
        "mcp_servers": {"lighthouse": {"enabled": True}},
    }

    effective = resolve_gateway_toolsets(
        cfg,
        "telegram",
        _source(thread_id=None, chat_type="group"),
    )
    assert "clarify" in effective
    assert "web" not in effective
    assert "lighthouse" not in effective
