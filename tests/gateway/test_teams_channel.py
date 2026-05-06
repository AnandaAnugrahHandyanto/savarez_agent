import pytest
from unittest.mock import AsyncMock, MagicMock

try:
    from gateway.config import PlatformConfig
    from plugins.platforms.teams.adapter import TeamsAdapter
except ImportError:
    TeamsAdapter = None

pytestmark = pytest.mark.skipif(TeamsAdapter is None, reason="Teams plugin not available")

def _make_config(**extra):
    return PlatformConfig(enabled=True, extra=extra)

def _make_activity(conversation_type="channel", conv_id="19:abc", conv_name="Test Channel", mentions=None, text="Hello", aad_object_id="user1"):
    activity = MagicMock(); activity.type = "message"
    activity.conversation = MagicMock()
    activity.conversation.conversation_type = conversation_type
    activity.conversation.id = conv_id
    activity.conversation.name = conv_name
    activity.text = text
    activity.mentions = mentions or []
    activity.entities = mentions or []
    activity.from_ = MagicMock()
    activity.from_.aad_object_id = aad_object_id
    activity.from_.properties = {}
    return activity

def _make_ctx(activity):
    ctx = MagicMock()
    ctx.activity = activity
    return ctx

@pytest.mark.asyncio
async def test_allowed_channels_dropped_if_not_in_list():
    cfg = _make_config(allowed_channels=["19:allowed"])
    adapter = TeamsAdapter(cfg)
    adapter._app = MagicMock()
    adapter.handle_message = AsyncMock()
    
    act = _make_activity(conv_id="19:disallowed", conv_name="Disallowed", text="<at>Bot</at> hello")
    await adapter._on_message(_make_ctx(act))
    adapter.handle_message.assert_not_called()

@pytest.mark.asyncio
async def test_allowed_channels_passed_if_in_list():
    cfg = _make_config(allowed_channels=["19:allowed"])
    adapter = TeamsAdapter(cfg)
    adapter._app = MagicMock()
    adapter.handle_message = AsyncMock()
    
    act = _make_activity(conv_id="19:allowed", conv_name="Allowed", text="<at>Bot</at> hello")
    await adapter._on_message(_make_ctx(act))
    adapter.handle_message.assert_awaited_once()

@pytest.mark.asyncio
async def test_allowed_channels_passed_by_name():
    cfg = _make_config(allowed_channels=["Allowed Name"])
    adapter = TeamsAdapter(cfg)
    adapter._app = MagicMock()
    adapter.handle_message = AsyncMock()
    
    act = _make_activity(conv_id="19:allowed", conv_name="Allowed Name", text="<at>Bot</at> hello")
    await adapter._on_message(_make_ctx(act))
    adapter.handle_message.assert_awaited_once()

@pytest.mark.asyncio
async def test_unmentioned_dropped_in_channel():
    cfg = _make_config()
    adapter = TeamsAdapter(cfg)
    adapter._app = MagicMock()
    adapter.handle_message = AsyncMock()
    
    act = _make_activity(text="hello without mention")
    await adapter._on_message(_make_ctx(act))
    adapter.handle_message.assert_not_called()

@pytest.mark.asyncio
async def test_unmentioned_passed_if_free_response():
    cfg = _make_config(free_response_channels=["19:free"])
    adapter = TeamsAdapter(cfg)
    adapter._app = MagicMock()
    adapter.handle_message = AsyncMock()
    
    act = _make_activity(conv_id="19:free", text="hello without mention")
    await adapter._on_message(_make_ctx(act))
    adapter.handle_message.assert_awaited_once()

@pytest.mark.asyncio
async def test_dm_bypasses_channel_checks():
    cfg = _make_config(allowed_channels=["19:allowed"])
    adapter = TeamsAdapter(cfg)
    adapter._app = MagicMock()
    adapter.handle_message = AsyncMock()
    
    act = _make_activity(conversation_type="personal", conv_id="dm123", text="hello")
    await adapter._on_message(_make_ctx(act))
    adapter.handle_message.assert_awaited_once()
