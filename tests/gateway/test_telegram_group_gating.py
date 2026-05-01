import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig, load_gateway_config


def _make_adapter(
    require_mention=None,
    free_response_chats=None,
    mention_patterns=None,
    ignored_threads=None,
    allow_from=None,
    group_allow_from=None,
    allow_bots=None,
    hq_aliases=None,
    hq_bot_id=None,
    hq_assignment=None,
    hq_escalation=None,
):
    from gateway.platforms.telegram import TelegramAdapter

    extra = {}
    if require_mention is not None:
        extra["require_mention"] = require_mention
    if free_response_chats is not None:
        extra["free_response_chats"] = free_response_chats
    if mention_patterns is not None:
        extra["mention_patterns"] = mention_patterns
    if ignored_threads is not None:
        extra["ignored_threads"] = ignored_threads
    if allow_from is not None:
        extra["allow_from"] = allow_from
    if group_allow_from is not None:
        extra["group_allow_from"] = group_allow_from
    if allow_bots is not None:
        extra["allow_bots"] = allow_bots
    if hq_aliases is not None:
        extra["hq_aliases"] = hq_aliases
    if hq_bot_id is not None:
        extra["hq_bot_id"] = hq_bot_id
    extra["hq_assignment"] = hq_assignment or {}
    extra["hq_escalation"] = hq_escalation or {}

    adapter = object.__new__(TelegramAdapter)
    adapter.platform = Platform.TELEGRAM
    adapter.config = PlatformConfig(enabled=True, token="***", extra=extra)
    adapter._bot = SimpleNamespace(id=999, username="hermes_bot")
    adapter._message_handler = AsyncMock()
    adapter._pending_text_batches = {}
    adapter._pending_text_batch_tasks = {}
    adapter._text_batch_delay_seconds = 0.01
    adapter._mention_patterns = adapter._compile_mention_patterns()
    return adapter


def _group_message(
    text="hello",
    *,
    chat_id=-100,
    from_user_id=111,
    from_user_username=None,
    from_user_is_bot=False,
    thread_id=None,
    reply_to_bot=False,
    entities=None,
    caption=None,
    caption_entities=None,
):
    reply_to_message = None
    if reply_to_bot:
        reply_to_message = SimpleNamespace(from_user=SimpleNamespace(id=999))
    return SimpleNamespace(
        text=text,
        caption=caption,
        entities=entities or [],
        caption_entities=caption_entities or [],
        message_thread_id=thread_id,
        chat=SimpleNamespace(id=chat_id, type="group"),
        from_user=SimpleNamespace(id=from_user_id, username=from_user_username, is_bot=from_user_is_bot),
        reply_to_message=reply_to_message,
    )


def _dm_message(text="hello", *, from_user_id=111):
    return SimpleNamespace(
        text=text,
        caption=None,
        entities=[],
        caption_entities=[],
        message_thread_id=None,
        chat=SimpleNamespace(id=from_user_id, type="private"),
        from_user=SimpleNamespace(id=from_user_id),
        reply_to_message=None,
    )


def _mention_entity(text, mention="@hermes_bot"):
    offset = text.index(mention)
    return SimpleNamespace(type="mention", offset=offset, length=len(mention))


def _bot_command_entity(text, command):
    """Entity Telegram emits for a ``/cmd`` or ``/cmd@botname`` token.

    Telegram parses slash commands server-side. For ``/cmd@botname`` the
    client does NOT emit a separate ``mention`` entity — the whole span
    is a single ``bot_command`` entity.
    """
    offset = text.index(command)
    return SimpleNamespace(type="bot_command", offset=offset, length=len(command))


def test_group_messages_can_be_opened_via_config():
    adapter = _make_adapter(require_mention=False)

    assert adapter._should_process_message(_group_message("hello everyone")) is True


def test_group_messages_can_require_direct_trigger_via_config():
    adapter = _make_adapter(require_mention=True)

    assert adapter._should_process_message(_group_message("hello everyone")) is False
    assert adapter._should_process_message(_group_message("hi @hermes_bot", entities=[_mention_entity("hi @hermes_bot")])) is True
    assert adapter._should_process_message(_group_message("replying", reply_to_bot=True)) is True
    # Commands must also respect require_mention when it is enabled
    assert adapter._should_process_message(_group_message("/status"), is_command=True) is False
    # Telegram's group command menu sends ``/cmd@botname`` as a single
    # ``bot_command`` entity spanning the whole token (no separate mention
    # entity). We must accept it so the menu works when require_mention is on.
    assert adapter._should_process_message(
        _group_message(
            "/status@hermes_bot",
            entities=[_bot_command_entity("/status@hermes_bot", "/status@hermes_bot")],
        ),
        is_command=True,
    ) is True
    # A bot_command entity addressed at a different bot must not satisfy
    # the mention gate — Telegram groups can host multiple bots that
    # register the same command name.
    assert adapter._should_process_message(
        _group_message(
            "/status@other_bot",
            entities=[_bot_command_entity("/status@other_bot", "/status@other_bot")],
        ),
        is_command=True,
    ) is False
    # Bare ``/status`` (no @botname) must still be dropped in groups with
    # require_mention=True — Telegram delivers it only when the bot's
    # privacy mode is off, and even then we should not respond unless the
    # user explicitly addressed the bot.
    assert adapter._should_process_message(
        _group_message("/status", entities=[_bot_command_entity("/status", "/status")]),
        is_command=True,
    ) is False
    # And commands still pass unconditionally when require_mention is disabled
    adapter_no_mention = _make_adapter(require_mention=False)
    assert adapter_no_mention._should_process_message(_group_message("/status"), is_command=True) is True


def test_free_response_chats_bypass_mention_requirement():
    adapter = _make_adapter(require_mention=True, free_response_chats=["-200"])

    assert adapter._should_process_message(_group_message("hello everyone", chat_id=-200)) is True
    assert adapter._should_process_message(_group_message("hello everyone", chat_id=-201)) is False


def test_ignored_threads_drop_group_messages_before_other_gates():
    adapter = _make_adapter(require_mention=False, free_response_chats=["-200"], ignored_threads=[31, "42"])

    assert adapter._should_process_message(_group_message("hello everyone", chat_id=-200, thread_id=31)) is False
    assert adapter._should_process_message(_group_message("hello everyone", chat_id=-200, thread_id=42)) is False
    assert adapter._should_process_message(_group_message("hello everyone", chat_id=-200, thread_id=99)) is True


def test_regex_mention_patterns_allow_custom_wake_words():
    adapter = _make_adapter(require_mention=True, mention_patterns=[r"^\s*chompy\b"])

    assert adapter._should_process_message(_group_message("chompy status")) is True
    assert adapter._should_process_message(_group_message("   chompy help")) is True
    assert adapter._should_process_message(_group_message("hey chompy")) is False


def test_invalid_regex_patterns_are_ignored():
    adapter = _make_adapter(require_mention=True, mention_patterns=[r"(", r"^\s*chompy\b"])

    assert adapter._should_process_message(_group_message("chompy status")) is True
    assert adapter._should_process_message(_group_message("hello everyone")) is False


def test_config_bridges_telegram_group_settings(monkeypatch, tmp_path):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        "telegram:\n"
        "  require_mention: true\n"
        "  mention_patterns:\n"
        "    - \"^\\\\s*chompy\\\\b\"\n"
        "  free_response_chats:\n"
        "    - \"-123\"\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.delenv("TELEGRAM_REQUIRE_MENTION", raising=False)
    monkeypatch.delenv("TELEGRAM_MENTION_PATTERNS", raising=False)
    monkeypatch.delenv("TELEGRAM_FREE_RESPONSE_CHATS", raising=False)

    config = load_gateway_config()

    assert config is not None
    assert __import__("os").environ["TELEGRAM_REQUIRE_MENTION"] == "true"
    assert json.loads(__import__("os").environ["TELEGRAM_MENTION_PATTERNS"]) == [r"^\s*chompy\b"]
    assert __import__("os").environ["TELEGRAM_FREE_RESPONSE_CHATS"] == "-123"


def test_config_bridges_telegram_user_allowlists(monkeypatch, tmp_path):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        "telegram:\n"
        "  allow_from:\n"
        "    - \"111\"\n"
        "    - \"222\"\n"
        "  group_allow_from:\n"
        "    - \"333\"\n"
        "  group_allowed_chats:\n"
        "    - \"-100\"\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.delenv("TELEGRAM_ALLOWED_USERS", raising=False)
    monkeypatch.delenv("TELEGRAM_GROUP_ALLOWED_USERS", raising=False)
    monkeypatch.delenv("TELEGRAM_GROUP_ALLOWED_CHATS", raising=False)

    config = load_gateway_config()

    assert config is not None
    assert __import__("os").environ["TELEGRAM_ALLOWED_USERS"] == "111,222"
    assert __import__("os").environ["TELEGRAM_GROUP_ALLOWED_USERS"] == "333"
    assert __import__("os").environ["TELEGRAM_GROUP_ALLOWED_CHATS"] == "-100"


def test_config_env_overrides_telegram_user_allowlists(monkeypatch, tmp_path):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        "telegram:\n"
        "  allow_from: \"111\"\n"
        "  group_allow_from: \"222\"\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("TELEGRAM_ALLOWED_USERS", "999")
    monkeypatch.setenv("TELEGRAM_GROUP_ALLOWED_USERS", "888")

    config = load_gateway_config()

    assert config is not None
    assert __import__("os").environ["TELEGRAM_ALLOWED_USERS"] == "999"
    assert __import__("os").environ["TELEGRAM_GROUP_ALLOWED_USERS"] == "888"


def test_dm_allow_from_is_enforced_by_gateway_authorization_not_trigger_gate():
    adapter = _make_adapter(allow_from=["111", "222"])

    assert adapter._should_process_message(_dm_message("hello", from_user_id=111)) is True
    assert adapter._should_process_message(_dm_message("hello", from_user_id=333)) is True


def test_group_allow_from_is_enforced_by_gateway_authorization_not_trigger_gate():
    adapter = _make_adapter(group_allow_from=["111"])

    assert adapter._should_process_message(_group_message("hello", from_user_id=333)) is True


def test_config_bridges_telegram_ignored_threads(monkeypatch, tmp_path):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        "telegram:\n"
        "  ignored_threads:\n"
        "    - 31\n"
        "    - \"42\"\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.delenv("TELEGRAM_IGNORED_THREADS", raising=False)

    config = load_gateway_config()

    assert config is not None
    assert __import__("os").environ["TELEGRAM_IGNORED_THREADS"] == "31,42"

def _trusted_assignment_config(**overrides):
    config = {
        "enabled": True,
        "allowed_chat_ids": ["-5166431570"],
        "trusted_sender_usernames": ["Awoo999_bot"],
        "max_turns_default": 1,
        "max_turns_max": 3,
        "strip_header": True,
    }
    config.update(overrides)
    return config

def test_bot_senders_are_ignored_by_default():
    adapter = _make_adapter(require_mention=True)

    assert adapter._should_process_message(
        _group_message(
            "hi @hermes_bot",
            entities=[_mention_entity("hi @hermes_bot")],
            from_user_id=222,
            from_user_is_bot=True,
        )
    ) is False

def test_bot_senders_can_be_opted_in_for_mentions():
    adapter = _make_adapter(require_mention=True, allow_bots="mentions")

    assert adapter._should_process_message(
        _group_message(
            "hi @hermes_bot",
            entities=[_mention_entity("hi @hermes_bot")],
            from_user_id=222,
            from_user_is_bot=True,
        )
    ) is True
    assert adapter._should_process_message(
        _group_message("hello everyone", from_user_id=222, from_user_is_bot=True)
    ) is False

def test_own_bot_sender_is_never_processed():
    adapter = _make_adapter(require_mention=True, allow_bots="all")

    assert adapter._should_process_message(
        _group_message(
            "hi @hermes_bot",
            entities=[_mention_entity("hi @hermes_bot")],
            from_user_id=999,
            from_user_is_bot=True,
        )
    ) is False

def test_hq_aliases_trigger_this_bot_when_require_mention_enabled():
    adapter = _make_adapter(require_mention=True, hq_aliases=["小礫", "rubble"])

    assert adapter._should_process_message(_group_message("小礫 盤查 gateway")) is True
    assert adapter._should_process_message(_group_message("rubble 盤查 gateway")) is True
    assert adapter._should_process_message(_group_message("小礫：盤查 gateway")) is True

def test_other_bot_alias_does_not_trigger_this_bot():
    adapter = _make_adapter(require_mention=True, hq_aliases=["小礫", "rubble"])

    assert adapter._should_process_message(_group_message("阿奇 盤查 gateway")) is False
    assert adapter._should_process_message(_group_message("rubblefish 盤查 gateway")) is False

def test_hq_assignment_for_this_bot_is_processed():
    adapter = _make_adapter(require_mention=True, hq_bot_id="rubble")

    assert adapter._should_process_message(
        _group_message("[HQ_ASSIGN target=rubble max_turns=1]\n盤查 gateway")
    ) is True
    assert adapter._should_process_message(
        _group_message("[HQ_ASSIGN target=RUBBLE max_turns=1]\n盤查 gateway")
    ) is True
    assert adapter._should_process_message(
        _group_message("[HQ_ASSIGN target=chase max_turns=1]\n盤查 gateway")
    ) is False

def test_hq_assignment_from_bot_still_hits_loop_guard():
    adapter = _make_adapter(require_mention=True, hq_bot_id="rubble")

    assert adapter._should_process_message(
        _group_message(
            "[HQ_ASSIGN target=rubble max_turns=1]\n盤查 gateway",
            from_user_id=222,
            from_user_is_bot=True,
        )
    ) is False

def test_trusted_architect_bot_assignment_is_processed_when_enabled():
    adapter = _make_adapter(
        require_mention=True,
        hq_bot_id="rubble",
        hq_assignment=_trusted_assignment_config(),
    )

    assert adapter._should_process_message(
        _group_message(
            "[HQ_ASSIGN target=rubble max_turns=1]\n盤查 gateway",
            chat_id=-5166431570,
            from_user_id=999001,
            from_user_username="Awoo999_bot",
            from_user_is_bot=True,
        )
    ) is True

def test_bot_assignment_still_ignored_when_hq_assignment_disabled():
    adapter = _make_adapter(require_mention=True, hq_bot_id="rubble")

    assert adapter._should_process_message(
        _group_message(
            "[HQ_ASSIGN target=rubble max_turns=1]\n盤查 gateway",
            chat_id=-5166431570,
            from_user_id=999001,
            from_user_username="Awoo999_bot",
            from_user_is_bot=True,
        )
    ) is False

def test_untrusted_bot_assignment_is_ignored():
    adapter = _make_adapter(
        require_mention=True,
        hq_bot_id="rubble",
        hq_assignment=_trusted_assignment_config(),
    )

    assert adapter._should_process_message(
        _group_message(
            "[HQ_ASSIGN target=rubble max_turns=1]\n盤查 gateway",
            chat_id=-5166431570,
            from_user_id=123,
            from_user_username="RandomBot",
            from_user_is_bot=True,
        )
    ) is False

def test_trusted_bot_assignment_in_wrong_chat_is_ignored():
    adapter = _make_adapter(
        require_mention=True,
        hq_bot_id="rubble",
        hq_assignment=_trusted_assignment_config(),
    )

    assert adapter._should_process_message(
        _group_message(
            "[HQ_ASSIGN target=rubble max_turns=1]\n盤查 gateway",
            chat_id=-111,
            from_user_id=999001,
            from_user_username="Awoo999_bot",
            from_user_is_bot=True,
        )
    ) is False

def test_trusted_bot_assignment_for_other_target_is_ignored():
    adapter = _make_adapter(
        require_mention=True,
        hq_bot_id="rubble",
        hq_assignment=_trusted_assignment_config(),
    )

    assert adapter._should_process_message(
        _group_message(
            "[HQ_ASSIGN target=zuma max_turns=1]\n做圖",
            chat_id=-5166431570,
            from_user_id=999001,
            from_user_username="Awoo999_bot",
            from_user_is_bot=True,
        )
    ) is False

def test_own_bot_assignment_is_never_processed_even_if_trusted():
    adapter = _make_adapter(
        require_mention=True,
        hq_bot_id="rubble",
        hq_assignment=_trusted_assignment_config(trusted_sender_usernames=["hermes_bot"]),
    )

    assert adapter._should_process_message(
        _group_message(
            "[HQ_ASSIGN target=rubble max_turns=1]\n盤查 gateway",
            chat_id=-5166431570,
            from_user_id=999,
            from_user_username="hermes_bot",
            from_user_is_bot=True,
        )
    ) is False

def test_hq_assignment_header_is_stripped_and_metadata_attached():
    from gateway.platforms.base import MessageEvent, MessageType

    adapter = _make_adapter(
        require_mention=True,
        hq_bot_id="rubble",
        hq_assignment=_trusted_assignment_config(),
    )
    msg = _group_message(
        "[HQ_ASSIGN target=rubble max_turns=2 trace_id=smoke-001]\n盤查 gateway",
        chat_id=-5166431570,
        from_user_id=999001,
        from_user_username="Awoo999_bot",
        from_user_is_bot=True,
    )
    event = MessageEvent(text=msg.text, message_type=MessageType.TEXT)

    updated = adapter._apply_hq_assignment_to_event(msg, event)

    assert updated.text == "盤查 gateway"
    assert updated.metadata["hq_assignment"]["target"] == "rubble"
    assert updated.metadata["hq_assignment"]["max_turns"] == 2
    assert updated.metadata["hq_assignment"]["trace_id"] == "smoke-001"

def test_hq_assignment_max_turns_is_clamped_to_config_cap():
    adapter = _make_adapter(
        require_mention=True,
        hq_bot_id="rubble",
        hq_assignment=_trusted_assignment_config(max_turns_max=3),
    )
    msg = _group_message(
        "[HQ_ASSIGN target=rubble max_turns=99]\n盤查 gateway",
        chat_id=-5166431570,
        from_user_id=999001,
        from_user_username="Awoo999_bot",
        from_user_is_bot=True,
    )

    assignment = adapter._parse_hq_assignment(msg)

    assert assignment["max_turns"] == 3

def test_gateway_runner_uses_assignment_max_turns_when_lower_than_default():
    from gateway.platforms.base import MessageEvent
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    event = MessageEvent(text="task", metadata={"hq_assignment": {"max_turns": 1}})

    assert runner._effective_max_iterations_for_event(event, 90) == 1

def test_gateway_runner_does_not_raise_iterations_above_default():
    from gateway.platforms.base import MessageEvent
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    event = MessageEvent(text="task", metadata={"hq_assignment": {"max_turns": 999}})

    assert runner._effective_max_iterations_for_event(event, 90) == 90

def _architect_escalation_config(**overrides):
    config = {
        "enabled": True,
        "allowed_chat_ids": ["-5166431570"],
        "trusted_worker_usernames": ["Awoo008_bot", "Awoo001_bot"],
        "accepted_types": ["HQ_ESCALATE", "HQ_RESULT"],
        "statuses": ["done", "blocked", "failed", "needs_human"],
        "max_turns_default": 1,
        "max_turns_max": 3,
        "strip_header": True,
    }
    config.update(overrides)
    return config


def test_trusted_worker_escalation_to_architect_is_processed_when_enabled():
    adapter = _make_adapter(
        require_mention=True,
        allow_bots="none",
        hq_bot_id="architect",
        hq_escalation=_architect_escalation_config(),
    )

    assert adapter._should_process_message(
        _group_message(
            "[HQ_ESCALATE target=architect from=rubble ticket=T20260502-rubble-smoke severity=urgent max_turns=2]\n卡點內容",
            chat_id=-5166431570,
            from_user_id=999008,
            from_user_username="Awoo008_bot",
            from_user_is_bot=True,
        )
    ) is True

def test_hq_escalation_rejects_wrong_chat_untrusted_sender_wrong_target_and_human_bypass():
    adapter = _make_adapter(
        require_mention=True,
        allow_bots="none",
        hq_bot_id="architect",
        hq_escalation=_architect_escalation_config(),
    )

    assert adapter._should_process_message(
        _group_message(
            "[HQ_ESCALATE target=architect from=rubble ticket=T20260502-rubble-smoke]\n卡點內容",
            chat_id=-1,
            from_user_username="Awoo008_bot",
            from_user_is_bot=True,
        )
    ) is False
    assert adapter._should_process_message(
        _group_message(
            "[HQ_ESCALATE target=architect from=rubble ticket=T20260502-rubble-smoke]\n卡點內容",
            chat_id=-5166431570,
            from_user_username="untrusted_bot",
            from_user_is_bot=True,
        )
    ) is False
    assert adapter._should_process_message(
        _group_message(
            "[HQ_ESCALATE target=rubble from=rubble ticket=T20260502-rubble-smoke]\n卡點內容",
            chat_id=-5166431570,
            from_user_username="Awoo008_bot",
            from_user_is_bot=True,
        )
    ) is False
    assert adapter._should_process_message(
        _group_message(
            "[HQ_ESCALATE target=architect from=rubble ticket=T20260502-rubble-smoke]\n卡點內容",
            chat_id=-5166431570,
            from_user_username="human_user",
            from_user_is_bot=False,
        )
    ) is False

def test_trusted_worker_result_to_architect_requires_from_ticket_and_allowed_status():
    adapter = _make_adapter(
        require_mention=True,
        allow_bots="none",
        hq_bot_id="architect",
        hq_escalation=_architect_escalation_config(),
    )

    assert adapter._should_process_message(
        _group_message(
            "[HQ_RESULT target=architect from=factory ticket=T20260502-rubble-smoke status=done max_turns=2]\n已查完",
            chat_id=-5166431570,
            from_user_username="Awoo001_bot",
            from_user_is_bot=True,
        )
    ) is True
    assert adapter._should_process_message(
        _group_message(
            "[HQ_RESULT target=architect ticket=T20260502-rubble-smoke status=done]\nmissing from",
            chat_id=-5166431570,
            from_user_username="Awoo001_bot",
            from_user_is_bot=True,
        )
    ) is False
    assert adapter._should_process_message(
        _group_message(
            "[HQ_RESULT target=architect from=factory status=done]\nmissing ticket",
            chat_id=-5166431570,
            from_user_username="Awoo001_bot",
            from_user_is_bot=True,
        )
    ) is False
    assert adapter._should_process_message(
        _group_message(
            "[HQ_RESULT target=architect from=factory ticket=T20260502-rubble-smoke status=lol]\nbad status",
            chat_id=-5166431570,
            from_user_username="Awoo001_bot",
            from_user_is_bot=True,
        )
    ) is False

def test_hq_escalation_event_strips_header_and_attaches_metadata():
    from gateway.platforms.base import MessageEvent, MessageType

    adapter = _make_adapter(
        require_mention=True,
        hq_bot_id="architect",
        hq_escalation=_architect_escalation_config(),
    )
    msg = _group_message(
        "[HQ_ESCALATE target=architect from=rubble ticket=T20260502-rubble-smoke severity=urgent max_turns=9 trace_id=t3]\n卡點內容",
        chat_id=-5166431570,
        from_user_username="Awoo008_bot",
        from_user_is_bot=True,
    )
    event = MessageEvent(text=msg.text, message_type=MessageType.TEXT)

    updated = adapter._apply_hq_escalation_to_event(msg, event)

    assert updated.text == "卡點內容"
    assert updated.metadata["hq_escalation"]["type"] == "HQ_ESCALATE"
    assert updated.metadata["hq_escalation"]["target"] == "architect"
    assert updated.metadata["hq_escalation"]["from"] == "rubble"
    assert updated.metadata["hq_escalation"]["ticket"] == "T20260502-rubble-smoke"
    assert updated.metadata["hq_escalation"]["severity"] == "urgent"
    assert updated.metadata["hq_escalation"]["max_turns"] == 3
    assert updated.metadata["hq_escalation"]["trace_id"] == "t3"

def test_gateway_runner_clamps_hq_escalation_max_turns():
    from gateway.platforms.base import MessageEvent
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    assert runner._effective_max_iterations_for_event(
        MessageEvent(text="task", metadata={"hq_escalation": {"max_turns": 2}}),
        90,
    ) == 2
    assert runner._effective_max_iterations_for_event(
        MessageEvent(text="task", metadata={"hq_escalation": {"max_turns": 999}}),
        90,
    ) == 90


@pytest.mark.asyncio
async def test_hq_escalation_metadata_bypasses_human_user_allowlist(monkeypatch):
    from gateway.platforms.base import MessageEvent
    from gateway.run import GatewayRunner
    from gateway.session import SessionSource

    monkeypatch.setenv("TELEGRAM_ALLOWED_USERS", "1926710271")
    monkeypatch.delenv("TELEGRAM_GROUP_ALLOWED_USERS", raising=False)
    monkeypatch.delenv("TELEGRAM_GROUP_ALLOWED_CHATS", raising=False)
    monkeypatch.delenv("TELEGRAM_ALLOW_ALL_USERS", raising=False)

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(platforms={Platform.TELEGRAM: PlatformConfig(enabled=True)})
    runner.adapters = {Platform.TELEGRAM: SimpleNamespace(send=AsyncMock())}
    runner.pairing_store = MagicMock()
    runner.pairing_store.is_approved.return_value = False
    runner.session_store = MagicMock()
    runner._running_agents = {}
    runner._update_prompt_pending = {}

    async def _capture(event, source, _quick_key, _run_generation=None):
        return f"processed:{event.metadata['hq_escalation']['ticket']}"

    runner._handle_message_with_agent = _capture

    event = MessageEvent(
        text="smoke",
        source=SessionSource(
            platform=Platform.TELEGRAM,
            chat_id="-5166431570",
            chat_name="HQ",
            chat_type="group",
            user_id="8761586079",
            user_name="小礫",
            is_bot=True,
        ),
        metadata={"hq_escalation": {"ticket": "T20260502-rubble-smoke"}},
    )

    assert await runner._handle_message(event) == "processed:T20260502-rubble-smoke"

def test_config_bridges_telegram_allow_bots(monkeypatch, tmp_path):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        "telegram:\n"
        "  allow_bots: mentions\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.delenv("TELEGRAM_ALLOW_BOTS", raising=False)

    config = load_gateway_config()

    assert config is not None
    assert __import__("os").environ["TELEGRAM_ALLOW_BOTS"] == "mentions"

def test_config_bridges_telegram_hq_aliases(monkeypatch, tmp_path):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        "telegram:\n"
        "  hq_aliases:\n"
        "    - 小礫\n"
        "    - rubble\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.delenv("TELEGRAM_HQ_ALIASES", raising=False)

    config = load_gateway_config()

    assert config is not None
    assert __import__("os").environ["TELEGRAM_HQ_ALIASES"] == "小礫,rubble"

def test_config_bridges_telegram_hq_bot_id(monkeypatch, tmp_path):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        "telegram:\n"
        "  hq_bot_id: Rubble\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.delenv("TELEGRAM_HQ_BOT_ID", raising=False)

    config = load_gateway_config()

    assert config is not None
    assert __import__("os").environ["TELEGRAM_HQ_BOT_ID"] == "rubble"

def test_config_bridges_telegram_hq_escalation(monkeypatch, tmp_path):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        "telegram:\n"
        "  hq_escalation:\n"
        "    enabled: true\n"
        "    allowed_chat_ids:\n"
        "      - \"-5166431570\"\n"
        "    trusted_worker_usernames:\n"
        "      - Awoo008_bot\n"
        "    accepted_types:\n"
        "      - HQ_ESCALATE\n"
        "      - HQ_RESULT\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.delenv("TELEGRAM_HQ_ESCALATION", raising=False)

    config = load_gateway_config()

    assert config is not None
    payload = json.loads(__import__("os").environ["TELEGRAM_HQ_ESCALATION"])
    assert payload["enabled"] is True
    assert payload["allowed_chat_ids"] == ["-5166431570"]
    assert payload["trusted_worker_usernames"] == ["Awoo008_bot"]
    assert payload["accepted_types"] == ["HQ_ESCALATE", "HQ_RESULT"]

def test_config_bridges_telegram_hq_assignment(monkeypatch, tmp_path):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        "telegram:\n"
        "  hq_assignment:\n"
        "    enabled: true\n"
        "    allowed_chat_ids:\n"
        "      - \"-5166431570\"\n"
        "    trusted_sender_usernames:\n"
        "      - Awoo999_bot\n"
        "    max_turns_default: 1\n"
        "    max_turns_max: 3\n"
        "    strip_header: true\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.delenv("TELEGRAM_HQ_ASSIGNMENT", raising=False)

    config = load_gateway_config()

    assert config is not None
    bridged = json.loads(__import__("os").environ["TELEGRAM_HQ_ASSIGNMENT"])
    assert bridged["enabled"] is True
    assert bridged["allowed_chat_ids"] == ["-5166431570"]
    assert bridged["trusted_sender_usernames"] == ["Awoo999_bot"]
    assert bridged["max_turns_max"] == 3
