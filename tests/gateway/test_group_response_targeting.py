"""
Tests for gateway/group_context.py — should_respond() response-targeting logic.

Covers all four decision scenarios:
1. Explicit mention -> always respond
2. Active thread / reply to bot -> respond
3. Side conversation between others -> stay silent
4. Proactive mode + open group question -> respond
"""

import pytest
from gateway.group_context import (
    ChannelContext,
    _is_explicitly_mentioned,
    _is_reply_to_bot,
    _hermes_is_active_participant,
    _looks_like_open_group_question,
    should_respond,
)


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _asst(content, message_id=None, tool_calls=None):
    msg = {"role": "assistant", "content": content}
    if message_id:
        msg["message_id"] = message_id
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return msg


def _user(content, sender=None):
    text = f"[{sender}] {content}" if sender else content
    return {"role": "user", "content": text}


BOT_NAMES = ["Hermes", "fergus", "@hermes_bot"]


# ------------------------------------------------------------------ #
# _is_explicitly_mentioned                                            #
# ------------------------------------------------------------------ #

class TestIsExplicitlyMentioned:
    def test_at_mention_exact(self):
        assert _is_explicitly_mentioned("@Hermes what's the time?", BOT_NAMES)

    def test_at_mention_case_insensitive(self):
        assert _is_explicitly_mentioned("@hermes what's up?", BOT_NAMES)

    def test_at_hermes_bot(self):
        assert _is_explicitly_mentioned("hey @hermes_bot can you help?", BOT_NAMES)

    def test_plain_name_mention(self):
        assert _is_explicitly_mentioned("Hermes, what time is it?", BOT_NAMES)

    def test_plain_name_middle(self):
        assert _is_explicitly_mentioned("Can Hermes help with that?", BOT_NAMES)

    def test_alternate_name(self):
        assert _is_explicitly_mentioned("fergus, turn off the lights", BOT_NAMES)

    def test_no_mention(self):
        assert not _is_explicitly_mentioned("Let's meet at 5pm", BOT_NAMES)

    def test_partial_name_no_match(self):
        # "hermetic" should not trigger "hermes"
        assert not _is_explicitly_mentioned("hermetic seal needed", BOT_NAMES)

    def test_empty_text(self):
        assert not _is_explicitly_mentioned("", BOT_NAMES)

    def test_no_bot_names(self):
        assert not _is_explicitly_mentioned("Hermes!", [])

    def test_empty_bot_name_entry_skipped(self):
        assert not _is_explicitly_mentioned("test", ["", ""])


# ------------------------------------------------------------------ #
# _is_reply_to_bot                                                    #
# ------------------------------------------------------------------ #

class TestIsReplyToBot:
    def test_matches_last_message_id(self):
        assert _is_reply_to_bot("msg-99", "msg-99", [])

    def test_no_reply_id(self):
        assert not _is_reply_to_bot(None, "msg-99", [])

    def test_mismatch_no_history(self):
        assert not _is_reply_to_bot("msg-1", "msg-99", [])

    def test_found_in_history(self):
        history = [
            _user("question"),
            _asst("answer", message_id="msg-42"),
        ]
        assert _is_reply_to_bot("msg-42", None, history)

    def test_not_in_history(self):
        history = [_asst("answer", message_id="msg-99")]
        assert not _is_reply_to_bot("msg-77", None, history)

    def test_id_as_int_in_history(self):
        history = [{"role": "assistant", "content": "hi", "message_id": 42}]
        assert _is_reply_to_bot("42", None, history)


# ------------------------------------------------------------------ #
# _hermes_is_active_participant                                        #
# ------------------------------------------------------------------ #

class TestHermesIsActiveParticipant:
    def test_empty_history(self):
        assert not _hermes_is_active_participant([])

    def test_only_user_messages(self):
        history = [_user("hi"), _user("hello")]
        assert not _hermes_is_active_participant(history)

    def test_assistant_turn_present(self):
        history = [_user("question"), _asst("answer")]
        assert _hermes_is_active_participant(history)

    def test_only_tool_call_assistant_not_counted(self):
        # assistant turn that is purely a tool relay (has tool_calls, no text response)
        history = [
            _user("run a search"),
            _asst(None, tool_calls=[{"id": "c1", "function": {"name": "web_search"}}]),
        ]
        assert not _hermes_is_active_participant(history)

    def test_empty_content_not_counted(self):
        history = [{"role": "assistant", "content": ""}]
        assert not _hermes_is_active_participant(history)

    def test_multiple_turns(self):
        history = [
            _user("q1"), _asst("a1"),
            _user("q2"), _asst("a2"),
        ]
        assert _hermes_is_active_participant(history)


# ------------------------------------------------------------------ #
# _looks_like_open_group_question                                     #
# ------------------------------------------------------------------ #

class TestLooksLikeOpenGroupQuestion:
    def test_question_mark(self):
        assert _looks_like_open_group_question("Anyone free later?")

    def test_can_anyone(self):
        assert _looks_like_open_group_question("Can anyone help me deploy this?")

    def test_does_anyone(self):
        assert _looks_like_open_group_question("Does anyone know how to fix this?")

    def test_any_ideas(self):
        assert _looks_like_open_group_question("Any ideas on the design?")

    def test_any_thoughts(self):
        assert _looks_like_open_group_question("Any thoughts on this approach?")

    def test_who_knows(self):
        assert _looks_like_open_group_question("Who knows the deploy steps?")

    def test_how_do_we(self):
        assert _looks_like_open_group_question("how do we reset the server")

    def test_plain_statement(self):
        assert not _looks_like_open_group_question("See you at 5pm")

    def test_i_am_done(self):
        assert not _looks_like_open_group_question("I'm done with the PR")

    def test_empty(self):
        assert not _looks_like_open_group_question("")


# ------------------------------------------------------------------ #
# should_respond — Scenario 1: Explicit mention                       #
# ------------------------------------------------------------------ #

class TestShouldRespondExplicitMention:
    """Rule 1: Hermes is directly addressed -> always respond."""

    def _ctx(self, **kwargs):
        defaults = dict(bot_names=BOT_NAMES, history=[], proactive=False)
        defaults.update(kwargs)
        return ChannelContext(**defaults)

    def test_at_mention_empty_history(self):
        assert should_respond("@Hermes what time is it?", self._ctx())

    def test_plain_name_empty_history(self):
        assert should_respond("Hermes, help please", self._ctx())

    def test_alternate_bot_name(self):
        assert should_respond("fergus turn off the lights", self._ctx())

    def test_mention_overrides_no_active_thread(self):
        # Even with no prior Hermes messages in session, mention wins
        history = [_user("Alice: hello"), _user("Bob: yeah")]
        assert should_respond("@Hermes are you there?", self._ctx(history=history))


# ------------------------------------------------------------------ #
# should_respond — Scenario 1b: Reply to Hermes message              #
# ------------------------------------------------------------------ #

class TestShouldRespondReplyToBot:
    """Rule 1b: Direct reply to a Hermes message -> always respond."""

    def _ctx(self, **kwargs):
        defaults = dict(bot_names=BOT_NAMES, history=[], proactive=False)
        defaults.update(kwargs)
        return ChannelContext(**defaults)

    def test_reply_to_last_bot_message(self):
        ctx = self._ctx(reply_to_message_id="msg-5", bot_last_message_id="msg-5")
        assert should_respond("Yeah that makes sense", ctx)

    def test_reply_to_bot_via_history(self):
        history = [_asst("Try rebooting the server", message_id="msg-10")]
        ctx = self._ctx(reply_to_message_id="msg-10", history=history)
        assert should_respond("Rebooting didn't help", ctx)

    def test_reply_to_other_user_no_respond(self):
        # replying to someone else, no mention, empty session
        ctx = self._ctx(reply_to_message_id="msg-3", bot_last_message_id="msg-7")
        assert not should_respond("Good point Alice", ctx)


# ------------------------------------------------------------------ #
# should_respond — Scenario 2: Active thread continuation            #
# ------------------------------------------------------------------ #

class TestShouldRespondActiveThread:
    """Rule 2: Hermes is already participating -> respond to continue thread."""

    def _ctx(self, history, **kwargs):
        defaults = dict(bot_names=BOT_NAMES, proactive=False)
        defaults.update(kwargs)
        return ChannelContext(history=history, **defaults)

    def test_hermes_already_replied(self):
        history = [
            _user("What database should we use?", sender="Alice"),
            _asst("PostgreSQL is a solid choice for your use case."),
        ]
        ctx = self._ctx(history)
        assert should_respond("Alice: yeah postgres sounds good", ctx)

    def test_side_chat_mid_active_thread(self):
        # Even a side-chat comment gets a response because Hermes is active
        history = [
            _user("Deploy help?", sender="Bob"),
            _asst("Sure, run kubectl apply -f deployment.yaml"),
        ]
        ctx = self._ctx(history)
        assert should_respond("Bob: already did", ctx)

    def test_no_prior_hermes_turn_no_respond(self):
        history = [
            _user("Let's do lunch", sender="Alice"),
            _user("Sounds good", sender="Bob"),
        ]
        ctx = self._ctx(history)
        assert not should_respond("Cool, 12:30 then", ctx)


# ------------------------------------------------------------------ #
# should_respond — Scenario 3: Side conversation (stay silent)       #
# ------------------------------------------------------------------ #

class TestShouldRespondSideConversation:
    """Rule 3: Conversation between others with no Hermes stake -> silent."""

    def _ctx(self, **kwargs):
        defaults = dict(bot_names=BOT_NAMES, history=[], proactive=False)
        defaults.update(kwargs)
        return ChannelContext(**defaults)

    def test_casual_chat_silent(self):
        assert not should_respond("See you at 5pm Alice!", self._ctx())

    def test_users_discussing_without_bot(self):
        assert not should_respond("Bob: I think we should ship on Friday", self._ctx())

    def test_lgtm_comment_silent(self):
        assert not should_respond("LGTM, merging now", self._ctx())

    def test_statement_no_question(self):
        assert not should_respond("The build passed", self._ctx())

    def test_proactive_off_with_statement(self):
        # proactive=False: plain statement, no mention, no history -> silent
        ctx = self._ctx(proactive=False)
        assert not should_respond("I finished the PR", ctx)


# ------------------------------------------------------------------ #
# should_respond — Scenario 4: Proactive mode open question          #
# ------------------------------------------------------------------ #

class TestShouldRespondProactive:
    """Rule 4: proactive=True + unresolved group question -> respond."""

    def _ctx(self, proactive, **kwargs):
        defaults = dict(bot_names=BOT_NAMES, history=[])
        defaults.update(kwargs)
        return ChannelContext(proactive=proactive, **defaults)

    def test_proactive_on_question(self):
        ctx = self._ctx(proactive=True)
        assert should_respond("Does anyone know how to restart nginx?", ctx)

    def test_proactive_on_any_ideas(self):
        ctx = self._ctx(proactive=True)
        assert should_respond("Any ideas on the best approach here?", ctx)

    def test_proactive_off_question(self):
        ctx = self._ctx(proactive=False)
        assert not should_respond("Does anyone know how to restart nginx?", ctx)

    def test_proactive_on_plain_statement(self):
        # question marker absent -> stay silent even with proactive=True
        ctx = self._ctx(proactive=True)
        assert not should_respond("I finished the report", ctx)

    def test_proactive_on_who_question(self):
        ctx = self._ctx(proactive=True)
        assert should_respond("Who has access to the prod database?", ctx)


# ------------------------------------------------------------------ #
# Integration: combined scenarios                                     #
# ------------------------------------------------------------------ #

class TestShouldRespondIntegration:
    """End-to-end scenarios mixing rules."""

    def test_mention_beats_no_history(self):
        ctx = ChannelContext(bot_names=BOT_NAMES, history=[], proactive=False)
        assert should_respond("hey @Hermes can you check the logs?", ctx)

    def test_no_mention_no_history_proactive_off(self):
        ctx = ChannelContext(bot_names=BOT_NAMES, history=[], proactive=False)
        assert not should_respond("Let's ship this tomorrow", ctx)

    def test_active_thread_no_mention_needed(self):
        history = [_user("q", sender="Eirik"), _asst("a")]
        ctx = ChannelContext(bot_names=BOT_NAMES, history=history, proactive=False)
        # No mention needed once Hermes is active
        assert should_respond("[Sonia] sounds good to me", ctx)

    def test_three_participant_side_chat_silent(self):
        """Core scenario: three-person chat with no bot involvement -> silent."""
        history = [
            _user("Let's do standup at 10", sender="Alice"),
            _user("Works for me", sender="Bob"),
            _user("I'll be 5 min late", sender="Charlie"),
        ]
        ctx = ChannelContext(bot_names=BOT_NAMES, history=history, proactive=False)
        assert not should_respond("[Alice] ok see you then", ctx)

    def test_group_question_with_proactive_enabled(self):
        """When proactive is on, an open group question triggers a response."""
        history = [
            _user("Let's discuss the architecture", sender="Eirik"),
            _user("Ok I'm ready", sender="Sonia"),
        ]
        ctx = ChannelContext(bot_names=BOT_NAMES, history=history, proactive=True)
        assert should_respond("Any thoughts on the new microservice design?", ctx)

    def test_reply_to_hermes_no_mention_needed(self):
        """Reply to Hermes message needs no @mention."""
        history = [_asst("Try checking the pods.", message_id="m-5")]
        ctx = ChannelContext(
            bot_names=BOT_NAMES,
            history=history,
            reply_to_message_id="m-5",
            proactive=False,
        )
        assert should_respond("I did, still failing", ctx)
