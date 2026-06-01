import json
import time
from unittest.mock import AsyncMock

import pytest

from gateway.config import Platform, PlatformConfig, load_gateway_config


def _make_adapter(require_mention=None, mention_patterns=None, free_response_chats=None,
                  dm_policy=None, allow_from=None, group_policy=None, group_allow_from=None,
                  respond_when_likely_directed=None, session_path=None):
    from gateway.platforms.whatsapp import WhatsAppAdapter

    extra = {}
    if session_path is not None:
        extra["session_path"] = str(session_path)
    if require_mention is not None:
        extra["require_mention"] = require_mention
    if mention_patterns is not None:
        extra["mention_patterns"] = mention_patterns
    if free_response_chats is not None:
        extra["free_response_chats"] = free_response_chats
    if dm_policy is not None:
        extra["dm_policy"] = dm_policy
    if allow_from is not None:
        extra["allow_from"] = allow_from
    if group_policy is not None:
        extra["group_policy"] = group_policy
    if group_allow_from is not None:
        extra["group_allow_from"] = group_allow_from
    if respond_when_likely_directed is not None:
        extra["respond_when_likely_directed"] = respond_when_likely_directed

    adapter = object.__new__(WhatsAppAdapter)
    adapter.platform = Platform.WHATSAPP
    adapter.config = PlatformConfig(enabled=True, extra=extra)
    adapter._message_handler = AsyncMock()
    adapter._dm_policy = str(extra.get("dm_policy", "open")).strip().lower()
    adapter._allow_from = WhatsAppAdapter._coerce_allow_list(extra.get("allow_from"))
    adapter._group_policy = str(extra.get("group_policy", "open")).strip().lower()
    adapter._group_allow_from = WhatsAppAdapter._coerce_allow_list(extra.get("group_allow_from"))
    adapter._mention_patterns = adapter._compile_mention_patterns()
    adapter._last_bot_reply_at_by_chat = {}
    adapter._last_bot_reply_text_by_chat = {}
    from pathlib import Path
    adapter._session_path = Path(extra.get("session_path", "/tmp/whatsapp-test-session"))
    adapter._active_threads_path = adapter._session_path / "active-threads.json"
    adapter._recent_group_messages_by_chat = {}
    adapter._free_response_chats = adapter._whatsapp_free_response_chats()
    return adapter


def _group_message(body="hello", **overrides):
    data = {
        "isGroup": True,
        "body": body,
        "chatId": "120363001234567890@g.us",
        "mentionedIds": [],
        "botIds": ["15551230000@s.whatsapp.net", "15551230000@lid"],
        "quotedParticipant": "",
    }
    data.update(overrides)
    return data


def _dm_message(body="hello", **overrides):
    data = {
        "isGroup": False,
        "body": body,
        "senderId": "6281234567890@s.whatsapp.net",
        "from": "6281234567890@s.whatsapp.net",
        "botIds": [],
        "mentionedIds": [],
    }
    data.update(overrides)
    return data


@pytest.mark.asyncio
async def test_quoted_message_body_is_included_in_processed_event(monkeypatch):
    adapter = _make_adapter(require_mention=True, mention_patterns=[r"(?i)\bwhatbot\b"])
    monkeypatch.setattr("hermes_cli.plugins.invoke_hook", lambda *args, **kwargs: [])

    event = await adapter._build_message_event(
        _group_message(
            "WhatBot, what does this mean?",
            messageId="reply-1",
            senderId="111@s.whatsapp.net",
            senderName="Alice",
            hasQuotedMessage=True,
            quotedBody="This is the attached earlier message",
            quotedType="conversation",
            quotedSenderName="Bob",
        )
    )

    assert event is not None
    assert event.text == (
        "[Quoted message from Bob]\n"
        "This is the attached earlier message\n\n"
        "[User message from Alice]\n"
        "WhatBot, what does this mean?"
    )


@pytest.mark.asyncio
async def test_quoted_media_caption_is_labeled_in_processed_event(monkeypatch):
    adapter = _make_adapter(require_mention=True, mention_patterns=[r"(?i)\bwhatbot\b"])
    monkeypatch.setattr("hermes_cli.plugins.invoke_hook", lambda *args, **kwargs: [])

    event = await adapter._build_message_event(
        _group_message(
            "WhatBot, caption?",
            messageId="reply-2",
            senderId="111@s.whatsapp.net",
            senderName="Alice",
            hasQuotedMessage=True,
            quotedBody="Photo caption from attached message",
            quotedType="imageMessage",
            quotedHasMedia=True,
            quotedSenderName="Bob",
        )
    )

    assert event is not None
    assert event.text.startswith("[Quoted image from Bob]\nPhoto caption from attached message")


@pytest.mark.asyncio
async def test_quoted_body_does_not_expose_raw_whatsapp_lid_mentions(monkeypatch):
    adapter = _make_adapter(require_mention=True, mention_patterns=[r"(?i)\bwhatbot\b"])
    monkeypatch.setattr("hermes_cli.plugins.invoke_hook", lambda *args, **kwargs: [])

    event = await adapter._build_message_event(
        _group_message(
            "WhatBot, who wrote this?",
            messageId="reply-3",
            senderId="111@s.whatsapp.net",
            senderName="Alice",
            hasQuotedMessage=True,
            quotedBody="Can you unsee it @139904986148944",
            quotedType="conversation",
            quotedSenderName="Bob",
        )
    )

    assert event is not None
    assert "139904986148944" not in event.text
    assert "Can you unsee it @someone" in event.text


# --- Existing tests (unchanged logic, updated helper) ---

def test_group_messages_can_be_opened_via_config():
    adapter = _make_adapter(require_mention=False)

    assert adapter._should_process_message(_group_message("hello everyone")) is True


def test_group_messages_can_require_direct_trigger_via_config():
    adapter = _make_adapter(require_mention=True)

    assert adapter._should_process_message(_group_message("hello everyone")) is False
    assert adapter._should_process_message(
        _group_message(
            "hi there",
            mentionedIds=["15551230000@s.whatsapp.net"],
        )
    ) is True
    assert adapter._should_process_message(
        _group_message(
            "replying",
            quotedParticipant="15551230000@lid",
        )
    ) is True
    assert adapter._should_process_message(_group_message("/status")) is True


def test_regex_mention_patterns_allow_custom_wake_words():
    adapter = _make_adapter(require_mention=True, mention_patterns=[r"^\s*chompy\b"])

    assert adapter._should_process_message(_group_message("chompy status")) is True
    assert adapter._should_process_message(_group_message("   chompy help")) is True
    assert adapter._should_process_message(_group_message("hey chompy")) is False


def test_whatsapp_can_wake_on_hermes_name_without_platform_tag():
    adapter = _make_adapter(require_mention=True, mention_patterns=[r"(?i)\bhermes\b"])

    assert adapter._should_process_message(_group_message("Hermes, can you summarize this?")) is True
    assert adapter._should_process_message(_group_message("hey hermes what do you think?")) is True


def test_likely_directed_gate_accepts_high_confidence_assistant_requests():
    adapter = _make_adapter(require_mention=True, respond_when_likely_directed=True)

    assert adapter._should_process_message(_group_message("can you look up the restaurant opening hours?")) is True
    assert adapter._should_process_message(_group_message("could you summarise the plan so far?")) is True
    assert adapter._should_process_message(_group_message("please remember that dinner is at 7")) is True


def test_likely_directed_gate_rejects_normal_group_chatter():
    adapter = _make_adapter(require_mention=True, respond_when_likely_directed=True)

    assert adapter._should_process_message(_group_message("any ideas?")) is False
    assert adapter._should_process_message(_group_message("can you come over later?")) is False
    assert adapter._should_process_message(_group_message("what do you think?")) is False


def test_likely_directed_gate_rejects_ambiguous_can_you_check_without_bot_context():
    adapter = _make_adapter(require_mention=True, respond_when_likely_directed=True)

    assert adapter._should_process_message(_group_message("Can you check if it’s seen any messages from me")) is False
    assert adapter._should_process_message(_group_message("could you check whether he got the invite?")) is False
    assert adapter._should_process_message(_group_message("would you check if they are coming later?")) is False


def test_likely_directed_gate_still_accepts_bot_specific_check_requests():
    adapter = _make_adapter(
        require_mention=True,
        mention_patterns=[r"(?i)\bwhat\s*bot\b", r"(?i)\bwhatbot\b"],
        respond_when_likely_directed=True,
    )

    assert adapter._should_process_message(_group_message("WhatBot can you check if you have any reminders?")) is True
    assert adapter._should_process_message(_group_message("can you check reminders?")) is True
    assert adapter._should_process_message(_group_message("can you check todo list TL-AB12?")) is True


def test_recent_bot_reply_wakes_on_followup_question():
    adapter = _make_adapter(require_mention=True, respond_when_likely_directed=True)
    adapter._last_bot_reply_at_by_chat["120363001234567890@g.us"] = time.monotonic()
    adapter._last_bot_reply_text_by_chat["120363001234567890@g.us"] = "What part of the fish anatomy should I explain?"

    assert adapter._should_process_message(_group_message("Why don’t they have one heart for both gills?")) is True


def test_recent_non_clarification_bot_reply_does_not_wake_on_question():
    adapter = _make_adapter(require_mention=True, respond_when_likely_directed=True)
    adapter._last_bot_reply_at_by_chat["120363001234567890@g.us"] = time.monotonic()
    adapter._last_bot_reply_text_by_chat["120363001234567890@g.us"] = "No active reminders right now."

    assert adapter._should_process_message(_group_message("Why don’t they have one heart for both gills?")) is False


def test_recent_bot_reply_followup_gate_stays_conservative():
    adapter = _make_adapter(require_mention=True, respond_when_likely_directed=True)
    adapter._last_bot_reply_at_by_chat["120363001234567890@g.us"] = time.monotonic()

    assert adapter._should_process_message(_group_message("haha fair enough")) is False

    adapter._last_bot_reply_at_by_chat["120363001234567890@g.us"] = time.monotonic() - 301
    assert adapter._should_process_message(_group_message("Why don’t they have one heart?")) is False


def test_recent_bot_reply_does_not_wake_on_ambiguous_can_you_check_about_third_party():
    adapter = _make_adapter(require_mention=True, respond_when_likely_directed=True)
    adapter._last_bot_reply_at_by_chat["120363001234567890@g.us"] = time.monotonic()
    adapter._last_bot_reply_text_by_chat["120363001234567890@g.us"] = "Can you clarify?"

    assert adapter._should_process_message(_group_message("Can you check if it’s seen any messages from me")) is False
    assert adapter._should_process_message(_group_message("Can you check if you have any reminders?")) is True


def test_local_followup_classifier_can_wake_declarative_answer_to_bot_question(monkeypatch):
    adapter = _make_adapter(require_mention=True, respond_when_likely_directed=True)
    adapter._last_bot_reply_at_by_chat["120363001234567890@g.us"] = time.monotonic() - 60
    adapter._last_bot_reply_text_by_chat["120363001234567890@g.us"] = (
        "Which meal, and what exact date/time in about a month should I set it for?"
    )
    calls = []

    def fake_classifier(data, *, last_bot_reply, **kwargs):
        calls.append((data["body"], last_bot_reply))
        return True

    monkeypatch.setattr(adapter, "_classify_followup_with_local_model", fake_classifier)

    assert adapter._should_process_message(_group_message("let’s provisionally say breakfast in 30 days")) is True
    assert calls == [(
        "let’s provisionally say breakfast in 30 days",
        "Which meal, and what exact date/time in about a month should I set it for?",
    )]


def test_local_followup_classifier_does_not_run_without_pending_bot_question(monkeypatch):
    adapter = _make_adapter(require_mention=True, respond_when_likely_directed=True)
    adapter._last_bot_reply_at_by_chat["120363001234567890@g.us"] = time.monotonic() - 60
    adapter._last_bot_reply_text_by_chat["120363001234567890@g.us"] = "No active reminders right now."

    def fail_classifier(*args, **kwargs):
        raise AssertionError("classifier should not run without a bot clarification question")

    monkeypatch.setattr(adapter, "_classify_followup_with_local_model", fail_classifier)

    assert adapter._should_process_message(_group_message("breakfast in 30 days")) is False


def test_active_thread_survives_adapter_restart_and_wakes_with_context(monkeypatch, tmp_path):
    first = _make_adapter(require_mention=True, respond_when_likely_directed=True, session_path=tmp_path)
    first._record_recent_group_message(_group_message("WhatBot remind Matt and me to have breakfast in about a month"))
    first._record_bot_group_reply(
        "120363001234567890@g.us",
        "Which meal, and what exact date/time in about a month should I set it for?",
    )

    restarted = _make_adapter(require_mention=True, respond_when_likely_directed=True, session_path=tmp_path)
    calls = []

    def fake_classifier(data, *, last_bot_reply, active_thread=None, recent_messages=None):
        calls.append({
            "body": data["body"],
            "last_bot_reply": last_bot_reply,
            "active_thread": active_thread,
            "recent_messages": recent_messages,
        })
        return True

    monkeypatch.setattr(restarted, "_classify_followup_with_local_model", fake_classifier)

    assert restarted._should_process_message(_group_message("let’s provisionally say breakfast in 30 days")) is True
    assert calls[0]["last_bot_reply"] == "Which meal, and what exact date/time in about a month should I set it for?"
    assert calls[0]["active_thread"]["status"] == "awaiting_user_input"
    assert calls[0]["active_thread"]["thread_type"] == "reminder_creation"
    assert any("remind Matt" in msg["body"] for msg in calls[0]["recent_messages"])


def test_retroactive_bot_addressing_wakes_for_previous_group_message(tmp_path):
    adapter = _make_adapter(
        require_mention=True,
        respond_when_likely_directed=True,
        mention_patterns=[r"(?i)\bwhat\s*bot\b", r"(?i)\bwhatbot\b"],
        session_path=tmp_path,
    )
    adapter._record_recent_group_message(_group_message(
        "Summarise to Matt your new capabilities in terms of modes etc.",
        senderName="Simon W",
    ))
    adapter._record_recent_group_message(_group_message(
        "Whatbot the last message was for you",
        senderName="Simon W",
    ))

    assert adapter._should_process_message(_group_message(
        "Whatbot the last message was for you",
        senderName="Simon W",
    )) is True


def test_llm_conversation_router_can_wake_and_rewrite_retroactive_addressing(monkeypatch, tmp_path):
    adapter = _make_adapter(
        require_mention=True,
        respond_when_likely_directed=True,
        session_path=tmp_path,
    )
    adapter.config.extra["local_conversation_router"] = True
    adapter._record_recent_group_message(_group_message(
        "Summarise to Matt your new capabilities in terms of modes etc.",
        senderName="Simon W",
    ))
    calls = []

    def fake_router(data, *, recent_messages=None, active_thread=None, last_bot_reply=""):
        calls.append({"body": data["body"], "recent_messages": recent_messages, "active_thread": active_thread})
        return {
            "should_wake": True,
            "addressing_type": "retroactive_repair",
            "target_message_index": -1,
            "rewritten_user_intent": "Answer the previous group message as if it was addressed to WhatBot.",
            "reason": "user says the previous message was for the bot",
            "confidence": 0.94,
        }

    monkeypatch.setattr(adapter, "_classify_group_message_with_local_router", fake_router)

    data = _group_message("that was for you", senderName="Simon W")
    assert adapter._should_process_message(data) is True
    rewritten = adapter._rewrite_group_message_body_with_router("120363001234567890@g.us", data["body"], data)
    assert "Conversation router repair" in rewritten
    assert "Summarise to Matt your new capabilities" in rewritten
    assert calls[0]["recent_messages"]


def test_llm_conversation_router_uses_target_message_index(monkeypatch, tmp_path):
    adapter = _make_adapter(
        require_mention=True,
        respond_when_likely_directed=True,
        session_path=tmp_path,
    )
    adapter.config.extra["local_conversation_router"] = True
    adapter._record_recent_group_message(_group_message("first candidate", senderName="Alice"))
    adapter._record_recent_group_message(_group_message("second candidate", senderName="Bob"))

    monkeypatch.setattr(adapter, "_classify_group_message_with_local_router", lambda *args, **kwargs: {
        "should_wake": True,
        "addressing_type": "retroactive_repair",
        "target_message_index": -2,
        "rewritten_user_intent": "Answer the earlier target message.",
        "reason": "router selected the earlier prior message",
        "confidence": 0.9,
    })

    data = _group_message("that earlier one was for you", senderName="Simon W")
    rewritten = adapter._rewrite_group_message_body_with_router("120363001234567890@g.us", data["body"], data)

    assert "first candidate" in rewritten
    assert "second candidate" not in rewritten


def test_recent_group_message_does_not_persist_raw_sender_id_when_name_missing():
    adapter = _make_adapter(require_mention=True, respond_when_likely_directed=True)

    adapter._record_recent_group_message(_group_message("hello", senderName="", senderId="111@s.whatsapp.net"))

    recent = adapter._recent_messages_for_chat("120363001234567890@g.us")
    assert recent[-1]["sender"] == "someone"
    assert "s.whatsapp.net" not in json.dumps(recent)


def test_llm_conversation_router_cache_key_changes_with_recent_context(monkeypatch, tmp_path):
    adapter = _make_adapter(
        require_mention=True,
        respond_when_likely_directed=True,
        session_path=tmp_path,
    )
    adapter.config.extra["local_conversation_router"] = True
    calls = []

    def fake_router(data, *, recent_messages=None, active_thread=None, last_bot_reply=""):
        calls.append([item.get("body") for item in (recent_messages or [])])
        return {
            "should_wake": len(calls) == 1,
            "addressing_type": "human_chatter" if len(calls) > 1 else "retroactive_repair",
            "reason": "context-sensitive decision",
        }

    monkeypatch.setattr(adapter, "_classify_group_message_with_local_router", fake_router)
    data = _group_message("that was for you", messageId="same-message")
    adapter._record_recent_group_message(_group_message("first context", senderName="Alice"))
    first = adapter._conversation_router_decision(data)
    adapter._record_recent_group_message(_group_message("different context", senderName="Bob"))
    second = adapter._conversation_router_decision(data)

    assert first is not None
    assert second is not None
    assert first["should_wake"] is True
    assert second["should_wake"] is False
    assert len(calls) == 2


def test_local_router_refuses_non_local_base_url_without_explicit_opt_in(monkeypatch, tmp_path):
    adapter = _make_adapter(require_mention=True, respond_when_likely_directed=True, session_path=tmp_path)
    adapter.config.extra["local_conversation_router"] = True
    adapter.config.extra["local_conversation_router_base_url"] = "https://example.com"

    def fail_urlopen(*args, **kwargs):
        raise AssertionError("non-local router URL should not be called")

    monkeypatch.setattr("urllib.request.urlopen", fail_urlopen)

    assert adapter._classify_group_message_with_local_router(_group_message("that was for you")) is None


def test_llm_conversation_router_can_reject_ambiguous_group_chatter(monkeypatch, tmp_path):
    adapter = _make_adapter(
        require_mention=True,
        respond_when_likely_directed=True,
        session_path=tmp_path,
    )
    adapter.config.extra["local_conversation_router"] = True

    monkeypatch.setattr(adapter, "_classify_group_message_with_local_router", lambda *args, **kwargs: {
        "should_wake": False,
        "addressing_type": "human_chatter",
        "reason": "ordinary human-to-human message",
        "confidence": 0.88,
    })

    assert adapter._should_process_message(_group_message("can you check if it saw me?")) is False


def test_retroactive_bot_addressing_wakes_without_fresh_bot_mention(tmp_path):
    adapter = _make_adapter(
        require_mention=True,
        respond_when_likely_directed=True,
        mention_patterns=[r"(?i)\bwhat\s*bot\b", r"(?i)\bwhatbot\b"],
        session_path=tmp_path,
    )
    adapter._record_recent_group_message(_group_message(
        "Summarise to Matt your new capabilities in terms of modes etc.",
        senderName="Simon W",
    ))
    adapter._record_recent_group_message(_group_message(
        "the last message was for you",
        senderName="Simon W",
    ))

    assert adapter._should_process_message(_group_message(
        "the last message was for you",
        senderName="Simon W",
    )) is True


@pytest.mark.asyncio
async def test_retroactive_bot_addressing_injects_previous_message_into_event(monkeypatch, tmp_path):
    adapter = _make_adapter(
        require_mention=True,
        respond_when_likely_directed=True,
        mention_patterns=[r"(?i)\bwhat\s*bot\b", r"(?i)\bwhatbot\b"],
        session_path=tmp_path,
    )
    monkeypatch.setattr("hermes_cli.plugins.invoke_hook", lambda *args, **kwargs: [])

    # First message is not directly addressed to the bot, but it is persisted
    # in the recent group slice by the bridge before the wake gate runs.
    first = await adapter._build_message_event(_group_message(
        "Summarise to Matt your new capabilities in terms of modes etc.",
        messageId="m1",
        senderId="111@s.whatsapp.net",
        senderName="Simon W",
    ))
    assert first is None

    event = await adapter._build_message_event(_group_message(
        "Whatbot the last message was for you",
        messageId="m2",
        senderId="111@s.whatsapp.net",
        senderName="Simon W",
    ))

    assert event is not None
    assert "The user is now directing this prior group message at WhatBot" in event.text
    assert "Summarise to Matt your new capabilities" in event.text
    assert "Whatbot the last message was for you" in event.text


def test_non_clarification_bot_reply_closes_persisted_active_thread(tmp_path):
    adapter = _make_adapter(require_mention=True, respond_when_likely_directed=True, session_path=tmp_path)
    adapter._record_bot_group_reply(
        "120363001234567890@g.us",
        "Which meal, and what exact date/time in about a month should I set it for?",
    )
    assert adapter._load_active_thread("120363001234567890@g.us") is not None

    adapter._record_bot_group_reply("120363001234567890@g.us", "Done — I set the reminder.")

    assert adapter._load_active_thread("120363001234567890@g.us") is None


def test_local_followup_classifier_prompt_includes_thread_and_recent_context(monkeypatch, tmp_path):
    adapter = _make_adapter(require_mention=True, respond_when_likely_directed=True, session_path=tmp_path)
    adapter.config.extra["local_followup_classifier"] = True
    adapter.config.extra["local_followup_classifier_base_url"] = "http://localhost:11434"
    adapter._record_recent_group_message(_group_message("WhatBot create a BBQ plan for Saturday", senderName="Simon"))
    active_thread = {
        "thread_id": "T-TEST",
        "thread_type": "plan_creation",
        "status": "awaiting_user_input",
        "last_bot_reply": "What date should I put on the BBQ plan?",
    }
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return json.dumps({"message": {"content": json.dumps({"should_wake": True, "reason": "answers plan date", "confidence": 0.9})}}).encode()

    def fake_urlopen(req, timeout):
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert adapter._classify_followup_with_local_model(
        _group_message("second Saturday in June"),
        last_bot_reply="What date should I put on the BBQ plan?",
        active_thread=active_thread,
        recent_messages=adapter._recent_group_messages_by_chat["120363001234567890@g.us"],
    ) is True
    prompt = captured["payload"]["messages"][0]["content"]
    assert "Active WhatBot thread" in prompt
    assert "plan_creation" in prompt
    assert "Recent group messages" in prompt
    assert "WhatBot create a BBQ plan" in prompt
    assert captured["payload"]["think"] is False


@pytest.mark.asyncio
async def test_ignored_group_message_still_fires_observed_hook(monkeypatch):
    adapter = _make_adapter(require_mention=True, respond_when_likely_directed=True)
    calls = []

    def fake_invoke_hook(name, **kwargs):
        calls.append((name, kwargs))
        return []

    monkeypatch.setattr("hermes_cli.plugins.invoke_hook", fake_invoke_hook)

    event = await adapter._build_message_event(
        _group_message(
            "ordinary group chatter",
            messageId="casual-1",
            senderId="111@s.whatsapp.net",
            senderName="Alice",
        )
    )

    assert event is None
    observed = [kwargs for name, kwargs in calls if name == "platform_message_observed"]
    assert len(observed) == 1
    assert observed[0]["will_process"] is False
    assert observed[0]["event"].text == "ordinary group chatter"


@pytest.mark.asyncio
async def test_unallowlisted_group_activation_request_is_not_observed_or_persisted(monkeypatch, tmp_path):
    adapter = _make_adapter(
        require_mention=True,
        group_policy="allowlist",
        group_allow_from=["allowed@g.us"],
        session_path=tmp_path,
    )
    calls = []

    def fake_invoke_hook(name, **kwargs):
        calls.append((name, kwargs))
        return []

    monkeypatch.setattr("hermes_cli.plugins.invoke_hook", fake_invoke_hook)

    event = await adapter._build_message_event(
        _group_message(
            "Hermes activate",
            chatId="unknown@g.us",
            chatName="Unknown Group",
            messageId="activate-1",
            senderId="111@s.whatsapp.net",
            senderName="Alice",
        )
    )

    assert event is None
    assert [name for name, _kwargs in calls if name == "platform_message_observed"] == []
    assert adapter._recent_messages_for_chat("unknown@g.us") == []


def test_invalid_regex_patterns_are_ignored():
    adapter = _make_adapter(require_mention=True, mention_patterns=[r"(", r"^\s*chompy\b"])

    assert adapter._should_process_message(_group_message("chompy status")) is True
    assert adapter._should_process_message(_group_message("hello everyone")) is False


def test_config_bridges_whatsapp_group_settings(monkeypatch, tmp_path):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        "whatsapp:\n"
        "  require_mention: true\n"
        "  mention_patterns:\n"
        "    - \"^\\\\s*chompy\\\\b\"\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.delenv("WHATSAPP_REQUIRE_MENTION", raising=False)
    monkeypatch.delenv("WHATSAPP_MENTION_PATTERNS", raising=False)

    config = load_gateway_config()

    assert config is not None
    assert config.platforms[Platform.WHATSAPP].extra["require_mention"] is True
    assert config.platforms[Platform.WHATSAPP].extra["mention_patterns"] == [r"^\s*chompy\b"]
    assert __import__("os").environ["WHATSAPP_REQUIRE_MENTION"] == "true"
    assert json.loads(__import__("os").environ["WHATSAPP_MENTION_PATTERNS"]) == [r"^\s*chompy\b"]


def test_free_response_chats_bypass_mention_gating():
    adapter = _make_adapter(
        require_mention=True,
        free_response_chats=["120363001234567890@g.us"],
    )

    assert adapter._should_process_message(_group_message("hello everyone")) is True


def test_free_response_chats_does_not_bypass_other_groups():
    adapter = _make_adapter(
        require_mention=True,
        free_response_chats=["999999999999@g.us"],
    )

    assert adapter._should_process_message(_group_message("hello everyone")) is False


def test_dm_passes_with_default_open_policy():
    adapter = _make_adapter(require_mention=True)

    dm = _dm_message("hello")
    assert adapter._should_process_message(dm) is True


def test_mention_stripping_removes_bot_phone_from_body():
    adapter = _make_adapter(require_mention=True)

    data = _group_message("@15551230000 what is the weather?")
    cleaned = adapter._clean_bot_mention_text(data["body"], data)
    assert "15551230000" not in cleaned
    assert "weather" in cleaned


def test_mention_stripping_preserves_body_when_no_mention():
    adapter = _make_adapter(require_mention=True)

    data = _group_message("just a normal message")
    cleaned = adapter._clean_bot_mention_text(data["body"], data)
    assert cleaned == "just a normal message"


# --- New dm_policy tests ---

def test_dm_policy_disabled_blocks_all_dms():
    adapter = _make_adapter(dm_policy="disabled")

    assert adapter._should_process_message(_dm_message("hello")) is False


def test_dm_policy_disabled_still_allows_groups():
    adapter = _make_adapter(dm_policy="disabled", require_mention=False)

    assert adapter._should_process_message(_group_message("hello")) is True


def test_dm_policy_allowlist_blocks_unlisted_sender():
    adapter = _make_adapter(dm_policy="allowlist", allow_from=["6289999999999@s.whatsapp.net"])

    assert adapter._should_process_message(_dm_message("hello")) is False


def test_dm_policy_allowlist_allows_listed_sender():
    adapter = _make_adapter(dm_policy="allowlist", allow_from=["6281234567890@s.whatsapp.net"])

    assert adapter._should_process_message(_dm_message("hello")) is True


def test_dm_policy_open_allows_all_dms():
    adapter = _make_adapter(dm_policy="open")

    assert adapter._should_process_message(_dm_message("hello")) is True


# --- New group_policy tests ---

def test_group_policy_disabled_blocks_all_groups():
    adapter = _make_adapter(group_policy="disabled", require_mention=False)

    assert adapter._should_process_message(_group_message("hello")) is False


def test_group_policy_disabled_still_allows_dms():
    adapter = _make_adapter(group_policy="disabled")

    assert adapter._should_process_message(_dm_message("hello")) is True


def test_group_policy_allowlist_blocks_unlisted_group():
    adapter = _make_adapter(group_policy="allowlist", group_allow_from=["999999999999@g.us"])

    assert adapter._should_process_message(_group_message("agus test")) is False


def test_group_policy_allowlist_allows_listed_group():
    adapter = _make_adapter(
        group_policy="allowlist",
        group_allow_from=["120363001234567890@g.us"],
        require_mention=True,
        mention_patterns=[r"^\s*(?:(?:@)?(?:agus|Augustus))\b"],
    )

    # Listed group — passes the allowlist gate, mention still required
    assert adapter._should_process_message(_group_message("hello")) is False
    assert adapter._should_process_message(_group_message("agus test")) is True


def test_group_policy_open_allows_all_groups():
    adapter = _make_adapter(group_policy="open", require_mention=True)

    # Open policy — all groups pass the gate (mention still needed)
    assert adapter._should_process_message(_group_message("hello")) is False
    assert adapter._should_process_message(_group_message("/status")) is True


# --- Config bridging tests ---

def test_config_bridges_whatsapp_dm_and_group_policy(monkeypatch, tmp_path):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        "whatsapp:\n"
        "  dm_policy: disabled\n"
        "  group_policy: allowlist\n"
        "  group_allow_from:\n"
        "    - \"120363001234567890@g.us\"\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.delenv("WHATSAPP_DM_POLICY", raising=False)
    monkeypatch.delenv("WHATSAPP_GROUP_POLICY", raising=False)
    monkeypatch.delenv("WHATSAPP_GROUP_ALLOWED_USERS", raising=False)

    config = load_gateway_config()

    assert config is not None
    assert config.platforms[Platform.WHATSAPP].extra["dm_policy"] == "disabled"
    assert config.platforms[Platform.WHATSAPP].extra["group_policy"] == "allowlist"
    assert config.platforms[Platform.WHATSAPP].extra["group_allow_from"] == ["120363001234567890@g.us"]
    assert __import__("os").environ["WHATSAPP_DM_POLICY"] == "disabled"
    assert __import__("os").environ["WHATSAPP_GROUP_POLICY"] == "allowlist"
    assert __import__("os").environ["WHATSAPP_GROUP_ALLOWED_USERS"] == "120363001234567890@g.us"


def test_config_bridges_whatsapp_allow_from(monkeypatch, tmp_path):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        "whatsapp:\n"
        "  dm_policy: allowlist\n"
        "  allow_from:\n"
        "    - \"6281234567890@s.whatsapp.net\"\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.delenv("WHATSAPP_DM_POLICY", raising=False)
    monkeypatch.delenv("WHATSAPP_ALLOWED_USERS", raising=False)

    config = load_gateway_config()

    assert config is not None
    assert config.platforms[Platform.WHATSAPP].extra["dm_policy"] == "allowlist"
    assert config.platforms[Platform.WHATSAPP].extra["allow_from"] == ["6281234567890@s.whatsapp.net"]
    assert __import__("os").environ["WHATSAPP_DM_POLICY"] == "allowlist"
    assert __import__("os").environ["WHATSAPP_ALLOWED_USERS"] == "6281234567890@s.whatsapp.net"


# --- Broadcast / status / newsletter pseudo-chats are always dropped ---


def test_status_broadcast_chats_are_always_dropped():
    """Felipe's gateway.log showed the agent replying to status@broadcast
    (a contact's WhatsApp Story update). These pseudo-chats aren't real
    conversations and the adapter must drop them regardless of dm_policy.
    """
    from gateway.platforms.whatsapp import WhatsAppAdapter

    # Even on the most permissive config — open DMs, no allowlist — Stories
    # and Channel posts must not reach the agent.
    adapter = _make_adapter(dm_policy="open")

    # Classic Story update — what Felipe was seeing in production.
    status_msg = _dm_message(
        body="[video received]",
        chatId="status@broadcast",
        senderId="34612345678@s.whatsapp.net",
    )
    assert adapter._should_process_message(status_msg) is False

    # Channel / Newsletter broadcast posts.
    newsletter_msg = _dm_message(
        body="check out our latest post",
        chatId="120363999999999999@newsletter",
        senderId="120363999999999999@newsletter",
    )
    assert adapter._should_process_message(newsletter_msg) is False


def test_broadcast_filter_runs_before_allowlist():
    """A status@broadcast message from an allowlisted sender still drops —
    we never want to reply to Stories, even from authorized contacts.
    """
    adapter = _make_adapter(
        dm_policy="allowlist",
        allow_from=["34612345678@s.whatsapp.net"],
    )

    msg = _dm_message(
        body="[image received]",
        chatId="status@broadcast",
        senderId="34612345678@s.whatsapp.net",
    )
    assert adapter._should_process_message(msg) is False


def test_real_dm_still_processed_after_broadcast_filter():
    """Sanity check: the broadcast filter doesn't accidentally drop real DMs."""
    adapter = _make_adapter(dm_policy="open")

    msg = _dm_message(
        body="hello",
        chatId="34612345678@s.whatsapp.net",
        senderId="34612345678@s.whatsapp.net",
    )
    assert adapter._should_process_message(msg) is True


def test_is_broadcast_chat_helper_recognizes_common_jids():
    from gateway.platforms.whatsapp import WhatsAppAdapter

    assert WhatsAppAdapter._is_broadcast_chat("status@broadcast") is True
    assert WhatsAppAdapter._is_broadcast_chat("STATUS@BROADCAST") is True
    assert WhatsAppAdapter._is_broadcast_chat("  status@broadcast  ") is True
    assert WhatsAppAdapter._is_broadcast_chat("120363999999999999@newsletter") is True
    assert WhatsAppAdapter._is_broadcast_chat("1234@broadcast") is True  # broadcast list
    # Real chats must not match.
    assert WhatsAppAdapter._is_broadcast_chat("34612345678@s.whatsapp.net") is False
    assert WhatsAppAdapter._is_broadcast_chat("120363001234567890@g.us") is False
    assert WhatsAppAdapter._is_broadcast_chat("") is False
    assert WhatsAppAdapter._is_broadcast_chat(None) is False  # type: ignore[arg-type]
