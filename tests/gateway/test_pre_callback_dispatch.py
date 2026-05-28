"""Tests for the pre_callback_dispatch plugin hook.

The hook fires at the TOP of ``TelegramAdapter._handle_callback_query`` for
every inbound callback-query (inline-keyboard button click), BEFORE any of
the built-in prefix branches (model picker, gmail triage, exec approval,
slash confirm, clarify, …) run. Plugins may return action dicts mirroring
``pre_gateway_dispatch``:
    {"action": "skip",    "reason": "..."}    -> drop click, no upstream branches run
    {"action": "rewrite", "data":   "..."}    -> replace query.data, continue dispatch
    {"action": "allow"}   /   None            -> normal dispatch
Failure modes (hook raises, returns garbage, etc.) MUST fall through to the
normal prefix dispatch — never break inline keyboard clicks.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig


@pytest.fixture
def telegram_adapter():
    """Construct a minimal TelegramAdapter with no real Bot/Application.

    We exercise only ``_handle_callback_query``; the rest of the adapter
    surface stays untouched.
    """
    from gateway.platforms.telegram import TelegramAdapter

    config = PlatformConfig(enabled=True)
    adapter = TelegramAdapter(config)
    # Real bot/app not needed for these tests.
    adapter._app = MagicMock()
    adapter._bot = MagicMock()
    return adapter


def _make_callback_query(data="mp:gpt"):
    """Stand-in for a python-telegram-bot CallbackQuery — only the fields
    ``_handle_callback_query`` reads."""
    return SimpleNamespace(
        data=data,
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
        from_user=SimpleNamespace(id=12345, first_name="tester"),
        message=SimpleNamespace(
            chat_id=-1001234567890,
            chat=SimpleNamespace(type="group"),
            message_thread_id=5,
        ),
    )


def _make_update(query):
    return SimpleNamespace(callback_query=query)


@pytest.mark.asyncio
async def test_pre_callback_dispatch_skip_short_circuits(monkeypatch, telegram_adapter):
    """{'action': 'skip'} drops the click before built-in prefix branches run."""
    called_model_picker = AsyncMock()
    monkeypatch.setattr(telegram_adapter, "_handle_model_picker_callback", called_model_picker)

    def _fake_hook(name, **kwargs):
        if name == "pre_callback_dispatch":
            return [{"action": "skip", "reason": "legacy-prefix"}]
        return []

    monkeypatch.setattr("hermes_cli.plugins.invoke_hook", _fake_hook)

    query = _make_callback_query(data="mp:gpt")
    await telegram_adapter._handle_callback_query(_make_update(query), context=object())

    # Model-picker branch must NOT have run.
    called_model_picker.assert_not_awaited()


@pytest.mark.asyncio
async def test_pre_callback_dispatch_rewrite_replaces_data(monkeypatch, telegram_adapter):
    """{'action': 'rewrite', 'data': ...} mutates the in-flight ``data``."""
    called_model_picker = AsyncMock()
    monkeypatch.setattr(telegram_adapter, "_handle_model_picker_callback", called_model_picker)

    def _fake_hook(name, **kwargs):
        if name == "pre_callback_dispatch":
            return [{"action": "rewrite", "data": "mp:claude"}]
        return []

    monkeypatch.setattr("hermes_cli.plugins.invoke_hook", _fake_hook)

    query = _make_callback_query(data="mp:gpt")
    await telegram_adapter._handle_callback_query(_make_update(query), context=object())

    # Model-picker received the REWRITTEN data, not the original.
    called_model_picker.assert_awaited_once()
    _, args, kwargs = called_model_picker.mock_calls[0]
    assert args[1] == "mp:claude" or kwargs.get("data") == "mp:claude"


@pytest.mark.asyncio
async def test_pre_callback_dispatch_allow_falls_through(monkeypatch, telegram_adapter):
    """{'action': 'allow'} continues to the normal prefix branches."""
    called_model_picker = AsyncMock()
    monkeypatch.setattr(telegram_adapter, "_handle_model_picker_callback", called_model_picker)

    def _fake_hook(name, **kwargs):
        if name == "pre_callback_dispatch":
            return [{"action": "allow"}]
        return []

    monkeypatch.setattr("hermes_cli.plugins.invoke_hook", _fake_hook)

    query = _make_callback_query(data="mp:gpt")
    await telegram_adapter._handle_callback_query(_make_update(query), context=object())

    called_model_picker.assert_awaited_once()


@pytest.mark.asyncio
async def test_pre_callback_dispatch_none_return_falls_through(monkeypatch, telegram_adapter):
    """No return from any hook → normal dispatch."""
    called_model_picker = AsyncMock()
    monkeypatch.setattr(telegram_adapter, "_handle_model_picker_callback", called_model_picker)

    def _fake_hook(name, **kwargs):
        return []

    monkeypatch.setattr("hermes_cli.plugins.invoke_hook", _fake_hook)

    query = _make_callback_query(data="mp:gpt")
    await telegram_adapter._handle_callback_query(_make_update(query), context=object())

    called_model_picker.assert_awaited_once()


@pytest.mark.asyncio
async def test_pre_callback_dispatch_exception_falls_through(monkeypatch, telegram_adapter):
    """A raising hook layer must not break inline keyboard clicks."""
    called_model_picker = AsyncMock()
    monkeypatch.setattr(telegram_adapter, "_handle_model_picker_callback", called_model_picker)

    def _fake_hook(name, **kwargs):
        raise RuntimeError("plugin blew up")

    monkeypatch.setattr("hermes_cli.plugins.invoke_hook", _fake_hook)

    query = _make_callback_query(data="mp:gpt")
    await telegram_adapter._handle_callback_query(_make_update(query), context=object())

    called_model_picker.assert_awaited_once()


@pytest.mark.asyncio
async def test_pre_callback_dispatch_garbage_return_falls_through(monkeypatch, telegram_adapter):
    """Non-dict / unknown action returns are ignored — normal dispatch."""
    called_model_picker = AsyncMock()
    monkeypatch.setattr(telegram_adapter, "_handle_model_picker_callback", called_model_picker)

    def _fake_hook(name, **kwargs):
        return ["not a dict", {"action": "unknown-verb"}, 42]

    monkeypatch.setattr("hermes_cli.plugins.invoke_hook", _fake_hook)

    query = _make_callback_query(data="mp:gpt")
    await telegram_adapter._handle_callback_query(_make_update(query), context=object())

    called_model_picker.assert_awaited_once()


@pytest.mark.asyncio
async def test_pre_callback_dispatch_kwargs_match_contract(monkeypatch, telegram_adapter):
    """Hook receives query / data / gateway / source kwargs as documented."""
    seen_kwargs = {}

    def _fake_hook(name, **kwargs):
        if name == "pre_callback_dispatch":
            seen_kwargs.update(kwargs)
        return []

    monkeypatch.setattr("hermes_cli.plugins.invoke_hook", _fake_hook)
    # Bind a fake gateway ref so the kwarg is non-None.
    sentinel_gateway = object()
    telegram_adapter.set_gateway_ref(sentinel_gateway)

    query = _make_callback_query(data="ea:once:7")
    await telegram_adapter._handle_callback_query(_make_update(query), context=object())

    assert set(seen_kwargs) == {"query", "data", "gateway", "source"}
    assert seen_kwargs["query"] is query
    assert seen_kwargs["data"] == "ea:once:7"
    assert seen_kwargs["gateway"] is sentinel_gateway
    from gateway.session import SessionSource
    assert isinstance(seen_kwargs["source"], SessionSource)
    assert seen_kwargs["source"].platform == Platform.TELEGRAM
    assert seen_kwargs["source"].user_id == "12345"
    assert seen_kwargs["source"].chat_id == "-1001234567890"
    assert seen_kwargs["source"].chat_type == "group"
    assert seen_kwargs["source"].thread_id == "5"


@pytest.mark.asyncio
async def test_pre_callback_dispatch_runs_before_auth_check(monkeypatch, telegram_adapter):
    """The hook fires for unauthorized users so legacy-button retirement
    plugins can answer without an Unauthorized toast."""
    seen = {"called": False}

    def _fake_hook(name, **kwargs):
        if name == "pre_callback_dispatch":
            seen["called"] = True
            return [{"action": "skip", "reason": "legacy"}]
        return []

    monkeypatch.setattr("hermes_cli.plugins.invoke_hook", _fake_hook)
    # Force the per-branch auth check to refuse — if the hook fires AFTER
    # auth, the test would never see seen["called"] = True for an ea: click.
    monkeypatch.setattr(telegram_adapter, "_is_callback_user_authorized", lambda *a, **kw: False)

    query = _make_callback_query(data="ea:once:7")
    await telegram_adapter._handle_callback_query(_make_update(query), context=object())

    assert seen["called"] is True


@pytest.mark.asyncio
async def test_pre_callback_dispatch_skip_with_answer_text_awaits_answer(monkeypatch, telegram_adapter):
    """{'action': 'skip', 'answer_text': '...'} → core awaits
    query.answer(text=...) so a sync plugin hook can answer a callback
    without needing to be async itself."""
    called_model_picker = AsyncMock()
    monkeypatch.setattr(telegram_adapter, "_handle_model_picker_callback", called_model_picker)

    def _fake_hook(name, **kwargs):
        if name == "pre_callback_dispatch":
            return [{"action": "skip", "reason": "legacy", "answer_text": "↩️ retired"}]
        return []

    monkeypatch.setattr("hermes_cli.plugins.invoke_hook", _fake_hook)

    query = _make_callback_query(data="fq:x:abc")
    await telegram_adapter._handle_callback_query(_make_update(query), context=object())

    query.answer.assert_awaited_once_with(text="↩️ retired")
    called_model_picker.assert_not_awaited()


@pytest.mark.asyncio
async def test_pre_callback_dispatch_skip_answer_failure_does_not_break_dispatch(monkeypatch, telegram_adapter):
    """If query.answer raises during the skip-answer path, the click must
    still be DROPPED (the plugin asked for skip); failure is logged."""
    called_model_picker = AsyncMock()
    monkeypatch.setattr(telegram_adapter, "_handle_model_picker_callback", called_model_picker)

    def _fake_hook(name, **kwargs):
        if name == "pre_callback_dispatch":
            return [{"action": "skip", "reason": "legacy", "answer_text": "notice"}]
        return []

    monkeypatch.setattr("hermes_cli.plugins.invoke_hook", _fake_hook)

    query = _make_callback_query(data="fq:x:abc")
    query.answer = AsyncMock(side_effect=RuntimeError("telegram blip"))
    await telegram_adapter._handle_callback_query(_make_update(query), context=object())

    called_model_picker.assert_not_awaited()


@pytest.mark.asyncio
async def test_pre_callback_dispatch_skip_without_answer_text_does_not_call_answer(monkeypatch, telegram_adapter):
    """answer_text is OPTIONAL — without it, skip just drops the click."""
    called_model_picker = AsyncMock()
    monkeypatch.setattr(telegram_adapter, "_handle_model_picker_callback", called_model_picker)

    def _fake_hook(name, **kwargs):
        if name == "pre_callback_dispatch":
            return [{"action": "skip", "reason": "drop"}]
        return []

    monkeypatch.setattr("hermes_cli.plugins.invoke_hook", _fake_hook)

    query = _make_callback_query(data="fq:x:abc")
    await telegram_adapter._handle_callback_query(_make_update(query), context=object())

    query.answer.assert_not_awaited()
    called_model_picker.assert_not_awaited()


@pytest.mark.asyncio
async def test_pre_callback_dispatch_first_actionable_result_wins(monkeypatch, telegram_adapter):
    """Multi-plugin: first skip/rewrite/allow wins; later results ignored."""
    called_model_picker = AsyncMock()
    monkeypatch.setattr(telegram_adapter, "_handle_model_picker_callback", called_model_picker)

    def _fake_hook(name, **kwargs):
        if name == "pre_callback_dispatch":
            return [
                {"action": "allow"},                           # first wins
                {"action": "skip", "reason": "later-skip"},    # ignored
                {"action": "rewrite", "data": "mp:other"},     # ignored
            ]
        return []

    monkeypatch.setattr("hermes_cli.plugins.invoke_hook", _fake_hook)

    query = _make_callback_query(data="mp:gpt")
    await telegram_adapter._handle_callback_query(_make_update(query), context=object())

    called_model_picker.assert_awaited_once()
    _, args, kwargs = called_model_picker.mock_calls[0]
    assert args[1] == "mp:gpt" or kwargs.get("data") == "mp:gpt"


@pytest.mark.asyncio
async def test_pre_callback_dispatch_rewrite_into_model_picker_is_permitted(monkeypatch, telegram_adapter):
    """Regression: rewrite into the un-auth-checked model-picker branch
    DOES route to the model picker. The plugins.py doc-block documents
    this footgun; this test pins behavior so a future allow-list change
    is opt-in and explicit, not silent."""
    called_model_picker = AsyncMock()
    monkeypatch.setattr(telegram_adapter, "_handle_model_picker_callback", called_model_picker)

    def _fake_hook(name, **kwargs):
        if name == "pre_callback_dispatch":
            return [{"action": "rewrite", "data": "mp:adversary"}]
        return []

    monkeypatch.setattr("hermes_cli.plugins.invoke_hook", _fake_hook)

    query = _make_callback_query(data="fq:legacy:1")
    await telegram_adapter._handle_callback_query(_make_update(query), context=object())

    called_model_picker.assert_awaited_once()
    _, args, kwargs = called_model_picker.mock_calls[0]
    assert args[1] == "mp:adversary" or kwargs.get("data") == "mp:adversary"


@pytest.mark.asyncio
async def test_pre_callback_dispatch_skip_log_handles_data_with_no_colon(monkeypatch, telegram_adapter, caplog):
    """The skip log uses a bounded data_prefix that does NOT leak the whole
    callback payload when no colon is present."""
    called_model_picker = AsyncMock()
    monkeypatch.setattr(telegram_adapter, "_handle_model_picker_callback", called_model_picker)

    def _fake_hook(name, **kwargs):
        if name == "pre_callback_dispatch":
            return [{"action": "skip", "reason": "drop"}]
        return []

    monkeypatch.setattr("hermes_cli.plugins.invoke_hook", _fake_hook)

    query = _make_callback_query(data="opaque-id-1234567890")
    with caplog.at_level("INFO"):
        await telegram_adapter._handle_callback_query(_make_update(query), context=object())

    # The full opaque id MUST NOT appear in the log; placeholder is logged instead
    assert "opaque-id-1234567890" not in caplog.text
    assert "<no-prefix>" in caplog.text
