"""Tests for Slack clarify Block Kit button rendering and resolution.

Slack counterpart to tests/gateway/test_discord_clarify_buttons.py and
test_telegram_clarify_buttons.py for the ``send_clarify`` override.

Slack renders clarify via Block Kit ``actions`` blocks (buttons, or a
``static_select`` for long choice lists) and dispatches clicks through
``_handle_clarify_action``. The auth + resolution path mirrors the other
adapters:

  · numeric choice → resolve_gateway_clarify(clarify_id, canonical_text)
  · "Other" button → mark_awaiting_text(clarify_id) so the text-intercept
    captures the next in-thread message
  · unauthorized / malformed → ignored, no resolve, no message rewrite
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure the repo root is importable
# ---------------------------------------------------------------------------
_repo = str(Path(__file__).resolve().parents[2])
if _repo not in sys.path:
    sys.path.insert(0, _repo)


# ---------------------------------------------------------------------------
# Minimal Slack SDK mock so SlackAdapter can be imported (mirrors
# test_slack_approval_buttons.py)
# ---------------------------------------------------------------------------
def _ensure_slack_mock():
    """Wire up the minimal mocks required to import SlackAdapter."""
    if "slack_bolt" in sys.modules:
        return
    slack_bolt = MagicMock()
    slack_bolt.async_app.AsyncApp = MagicMock
    sys.modules["slack_bolt"] = slack_bolt
    sys.modules["slack_bolt.async_app"] = slack_bolt.async_app
    handler_mod = MagicMock()
    handler_mod.AsyncSocketModeHandler = MagicMock
    sys.modules["slack_bolt.adapter"] = MagicMock()
    sys.modules["slack_bolt.adapter.socket_mode"] = MagicMock()
    sys.modules["slack_bolt.adapter.socket_mode.async_handler"] = handler_mod
    sdk_mod = MagicMock()
    sdk_mod.web = MagicMock()
    sdk_mod.web.async_client = MagicMock()
    sdk_mod.web.async_client.AsyncWebClient = MagicMock
    sys.modules["slack_sdk"] = sdk_mod
    sys.modules["slack_sdk.web"] = sdk_mod.web
    sys.modules["slack_sdk.web.async_client"] = sdk_mod.web.async_client


_ensure_slack_mock()

from gateway.platforms.slack import SlackAdapter  # noqa: E402
from gateway.config import PlatformConfig  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_adapter():
    """Create a SlackAdapter with mocked internals (mirror approval tests)."""
    config = PlatformConfig(enabled=True, token="***")
    adapter = SlackAdapter(config)
    adapter._app = MagicMock()
    adapter._bot_user_id = "U_BOT"
    adapter._team_clients = {"T1": AsyncMock()}
    adapter._team_bot_user_ids = {"T1": "U_BOT"}
    adapter._channel_team = {"C1": "T1"}
    return adapter


class _AuthRunner:
    def __init__(self, auth_fn=None):
        self._auth_fn = auth_fn or (lambda _source: True)
        self.seen_sources = []

    async def handle(self, event):
        return None

    def _is_user_authorized(self, source):
        self.seen_sources.append(source)
        return self._auth_fn(source)


def _attach_auth_runner(adapter, auth_fn=None):
    runner = _AuthRunner(auth_fn=auth_fn)
    adapter.set_message_handler(runner.handle)
    return runner


def _clear_clarify_state():
    from tools import clarify_gateway as cm

    with cm._lock:
        cm._entries.clear()
        cm._session_index.clear()
        cm._notify_cbs.clear()


def _click_body(*, msg_ts="111.222",
                section_text=":question: *Clarification Needed*\nPick a color",
                user_name="norbert", user_id="U_NORBERT"):
    """A Block Kit action body as Bolt delivers it to the handler."""
    return {
        "message": {
            "ts": msg_ts,
            "blocks": [
                {"type": "section",
                 "text": {"type": "mrkdwn", "text": section_text}},
                {"type": "actions", "elements": []},
            ],
        },
        "channel": {"id": "C1"},
        "user": {"name": user_name, "id": user_id},
    }


# ===========================================================================
# send_clarify — block rendering
# ===========================================================================

class TestSlackSendClarify:
    def setup_method(self):
        _clear_clarify_state()

    @pytest.mark.asyncio
    async def test_multi_choice_renders_buttons_with_encoded_values(self):
        adapter = _make_adapter()
        client = adapter._team_clients["T1"]
        client.chat_postMessage = AsyncMock(return_value={"ts": "1.1"})

        result = await adapter.send_clarify(
            chat_id="C1",
            question="Pick a color",
            choices=["red", "green", "blue"],
            clarify_id="cidM",
            session_key="sk-M",
        )

        assert result.success is True
        assert result.message_id == "1.1"
        client.chat_postMessage.assert_called_once()
        blocks = client.chat_postMessage.call_args[1]["blocks"]
        assert len(blocks) == 2
        assert blocks[0]["type"] == "section"
        section_text = blocks[0]["text"]["text"]
        # Mirrors send_exec_approval: bold role title, then the question beneath.
        assert "*Clarification Needed*" in section_text
        assert "Pick a color" in section_text
        assert blocks[1]["type"] == "actions"
        elements = blocks[1]["elements"]
        # 3 choice buttons + 1 Other
        assert len(elements) == 4
        assert [e["action_id"] for e in elements] == [
            "hermes_clarify_0",
            "hermes_clarify_1",
            "hermes_clarify_2",
            "hermes_clarify_other",
        ]
        # Values encode clarify_id|idx (and |other for the trailing button)
        assert elements[0]["value"] == "cidM|0"
        assert elements[1]["value"] == "cidM|1"
        assert elements[2]["value"] == "cidM|2"
        assert elements[3]["value"] == "cidM|other"
        # Button labels are the bare choice text — no numeric prefix (tappable,
        # so the "1./2." numbering from the text fallback is dropped).
        assert elements[0]["text"]["text"] == "red"
        assert elements[1]["text"]["text"] == "green"
        assert "Other" in elements[3]["text"]["text"]

    @pytest.mark.asyncio
    async def test_open_ended_renders_section_only_no_actions(self):
        adapter = _make_adapter()
        client = adapter._team_clients["T1"]
        client.chat_postMessage = AsyncMock(return_value={"ts": "2.2"})

        result = await adapter.send_clarify(
            chat_id="C1",
            question="What is your name?",
            choices=None,
            clarify_id="cidOE",
            session_key="sk-OE",
        )

        assert result.success is True
        blocks = client.chat_postMessage.call_args[1]["blocks"]
        # Open-ended → section only, NO actions block (text-intercept resolves)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "section"
        assert all(b["type"] != "actions" for b in blocks)

    @pytest.mark.asyncio
    async def test_many_choices_degrade_to_static_select(self):
        adapter = _make_adapter()
        client = adapter._team_clients["T1"]
        client.chat_postMessage = AsyncMock(return_value={"ts": "3.3"})

        choices = [f"opt-{i}" for i in range(8)]  # > _CLARIFY_BUTTON_LIMIT (4)
        await adapter.send_clarify(
            chat_id="C1",
            question="Pick one",
            choices=choices,
            clarify_id="cidS",
            session_key="sk-S",
        )

        blocks = client.chat_postMessage.call_args[1]["blocks"]
        actions = blocks[1]
        assert actions["type"] == "actions"
        element = actions["elements"][0]
        assert element["type"] == "static_select"
        assert element["action_id"] == "hermes_clarify_select"
        # One option per choice, each value-encoded clarify_id|idx
        assert len(element["options"]) == 8
        assert element["options"][0]["value"] == "cidS|0"
        assert element["options"][7]["value"] == "cidS|7"

    @pytest.mark.asyncio
    async def test_long_question_stays_under_section_cap(self):
        adapter = _make_adapter()
        client = adapter._team_clients["T1"]
        client.chat_postMessage = AsyncMock(return_value={"ts": "4.4"})

        await adapter.send_clarify(
            chat_id="C1",
            question="Q" * 3000,
            choices=["a", "b"],
            clarify_id="cidL",
            session_key="sk-L",
        )

        blocks = client.chat_postMessage.call_args[1]["blocks"]
        section_text = blocks[0]["text"]["text"]
        # Must stay under Slack's 3000-char section-block cap (no invalid_blocks)
        assert len(section_text) <= 3000

    @pytest.mark.asyncio
    async def test_thread_ts_from_metadata_posts_in_thread(self):
        adapter = _make_adapter()
        client = adapter._team_clients["T1"]
        client.chat_postMessage = AsyncMock(return_value={"ts": "5.5"})

        await adapter.send_clarify(
            chat_id="C1",
            question="Pick",
            choices=["a"],
            clarify_id="cidT",
            session_key="sk-T",
            metadata={"thread_id": "9999.0000"},
        )

        assert client.chat_postMessage.call_args[1].get("thread_ts") == "9999.0000"

    @pytest.mark.asyncio
    async def test_not_connected_returns_failure(self):
        adapter = _make_adapter()
        adapter._app = None
        result = await adapter.send_clarify(
            chat_id="C1",
            question="?",
            choices=["a"],
            clarify_id="cidNC",
            session_key="sk-NC",
        )
        assert result.success is False
        assert "Not connected" in (result.error or "")


# ===========================================================================
# _handle_clarify_action — numeric resolve
# ===========================================================================

class TestSlackClarifyResolve:
    def setup_method(self):
        _clear_clarify_state()

    @pytest.mark.asyncio
    async def test_numeric_click_resolves_with_canonical_choice_text(self):
        from tools import clarify_gateway as cm

        cm.register("cidA", "sk-A", "Pick", ["red", "green", "blue"])

        adapter = _make_adapter()
        _attach_auth_runner(adapter)
        client = adapter._team_clients["T1"]
        client.chat_update = AsyncMock()

        ack = AsyncMock()
        body = _click_body()
        action = {"action_id": "hermes_clarify_1", "value": "cidA|1"}

        await adapter._handle_clarify_action(ack, body, action)

        ack.assert_called_once()
        # Resolved through the clarify primitive with the canonical text,
        # not the button label.
        with cm._lock:
            entry = cm._entries.get("cidA")
        assert entry is not None
        assert entry.response == "green"
        assert entry.event.is_set()
        # Message rewritten with "Answered by" footer
        client.chat_update.assert_called_once()
        update_kwargs = client.chat_update.call_args[1]
        assert "Answered by norbert" in update_kwargs["text"]
        assert "green" in update_kwargs["text"]

    @pytest.mark.asyncio
    async def test_static_select_uses_selected_option_value(self):
        from tools import clarify_gateway as cm

        cm.register("cidSel", "sk-Sel", "Pick", [f"opt-{i}" for i in range(8)])

        adapter = _make_adapter()
        _attach_auth_runner(adapter)
        client = adapter._team_clients["T1"]
        client.chat_update = AsyncMock()

        ack = AsyncMock()
        body = _click_body()
        # static_select carries the chosen value under selected_option, not value
        action = {
            "action_id": "hermes_clarify_select",
            "selected_option": {"value": "cidSel|5"},
        }

        await adapter._handle_clarify_action(ack, body, action)

        with cm._lock:
            entry = cm._entries.get("cidSel")
        assert entry is not None
        assert entry.response == "opt-5"
        assert entry.event.is_set()

    @pytest.mark.asyncio
    async def test_numeric_click_falls_back_to_index_when_entry_missing(self):
        """If the entry vanished (race/stale prompt), resolve with the raw
        index token rather than crashing."""
        adapter = _make_adapter()
        _attach_auth_runner(adapter)
        client = adapter._team_clients["T1"]
        client.chat_update = AsyncMock()

        ack = AsyncMock()
        body = _click_body()
        action = {"action_id": "hermes_clarify_0", "value": "cidGone|0"}

        # No cm.register() — entry intentionally absent. Must not raise.
        await adapter._handle_clarify_action(ack, body, action)

        ack.assert_called_once()
        # Footer falls back to the raw token
        update_kwargs = client.chat_update.call_args[1]
        assert "Answered by norbert" in update_kwargs["text"]

    @pytest.mark.asyncio
    async def test_dirty_choices_index_stays_aligned_with_rendered_buttons(self):
        """Regression: send_clarify filters empty/whitespace choices before
        rendering, so the encoded button index is into the FILTERED list. The
        handler must apply the identical filter to entry.choices before
        indexing — otherwise a dirty input list desyncs the two index spaces
        and resolves the wrong (or empty) value.

        Entry stores the raw list ["", "  ", "real-choice", None]; the rendered
        button for the only real choice carries index 0 (filtered view). Clicking
        it must resolve to "real-choice", not entry.choices[0] == "".
        """
        from tools import clarify_gateway as cm

        # Deliberately dirty input (empties, whitespace, None) — build at runtime
        # so the static type checker doesn't reject the intentional None.
        dirty_choices = ["", "  ", "real-choice", None]
        cm.register("cidDirty", "sk-Dirty", "Pick", dirty_choices)

        adapter = _make_adapter()
        _attach_auth_runner(adapter)
        client = adapter._team_clients["T1"]
        client.chat_update = AsyncMock()

        ack = AsyncMock()
        body = _click_body()
        # send_clarify would render "real-choice" as button index 0.
        action = {"action_id": "hermes_clarify_0", "value": "cidDirty|0"}

        await adapter._handle_clarify_action(ack, body, action)

        with cm._lock:
            entry = cm._entries.get("cidDirty")
        assert entry is not None
        assert entry.response == "real-choice"
        assert entry.event.is_set()
        assert "real-choice" in client.chat_update.call_args[1]["text"]


# ===========================================================================
# _handle_clarify_action — "Other" → text-capture
# ===========================================================================

class TestSlackClarifyOther:
    def setup_method(self):
        _clear_clarify_state()

    @pytest.mark.asyncio
    async def test_other_flips_entry_to_awaiting_text_no_resolve(self):
        from tools import clarify_gateway as cm

        cm.register("cidD", "sk-D", "Pick", ["x", "y"])

        adapter = _make_adapter()
        _attach_auth_runner(adapter)
        client = adapter._team_clients["T1"]
        client.chat_update = AsyncMock()

        ack = AsyncMock()
        body = _click_body()
        action = {"action_id": "hermes_clarify_other", "value": "cidD|other"}

        await adapter._handle_clarify_action(ack, body, action)

        # Entry flipped to awaiting_text, still pending (not resolved)
        pending = cm.get_pending_for_session("sk-D")
        assert pending is not None
        assert pending.clarify_id == "cidD"
        assert pending.awaiting_text is True
        with cm._lock:
            entry = cm._entries.get("cidD")
        assert entry is not None
        assert not entry.event.is_set()
        # Message rewritten to prompt for the typed answer
        client.chat_update.assert_called_once()
        assert "type a custom answer" in client.chat_update.call_args[1]["text"]


# ===========================================================================
# _handle_clarify_action — auth + safety
# ===========================================================================

class TestSlackClarifyAuthSafety:
    def setup_method(self):
        _clear_clarify_state()

    @pytest.mark.asyncio
    async def test_unauthorized_click_ignored_no_resolve_no_update(self):
        from tools import clarify_gateway as cm

        cm.register("cidU", "sk-U", "Pick", ["x"])

        adapter = _make_adapter()
        # Auth runner denies everyone
        _attach_auth_runner(adapter, auth_fn=lambda _s: False)
        client = adapter._team_clients["T1"]
        client.chat_update = AsyncMock()

        ack = AsyncMock()
        body = _click_body(user_name="mallory", user_id="U_ATTACKER")
        action = {"action_id": "hermes_clarify_0", "value": "cidU|0"}

        await adapter._handle_clarify_action(ack, body, action)

        # Acked (so Slack doesn't retry) but no resolve, no message rewrite
        ack.assert_called_once()
        client.chat_update.assert_not_called()
        with cm._lock:
            entry = cm._entries.get("cidU")
        assert entry is not None
        assert not entry.event.is_set()

    @pytest.mark.asyncio
    async def test_malformed_value_no_crash_no_resolve(self):
        adapter = _make_adapter()
        _attach_auth_runner(adapter)
        client = adapter._team_clients["T1"]
        client.chat_update = AsyncMock()

        ack = AsyncMock()
        body = _click_body()
        # No "|" separator
        action = {"action_id": "hermes_clarify_0", "value": "garbage-no-pipe"}

        with patch(
            "tools.clarify_gateway.resolve_gateway_clarify"
        ) as mock_resolve:
            await adapter._handle_clarify_action(ack, body, action)

        ack.assert_called_once()
        mock_resolve.assert_not_called()
        client.chat_update.assert_not_called()
