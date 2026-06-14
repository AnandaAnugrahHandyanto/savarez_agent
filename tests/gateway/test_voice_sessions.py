from typing import Any

import pytest

from gateway.voice_sessions import (
    PipelineVoiceProvider,
    VoiceSessionConfig,
    VoiceSessionConflict,
    VoiceSessionLimitExceeded,
    VoiceSessionManager,
    VoiceSessionRequest,
    VoiceSessionState,
    VoiceSessionUnauthorized,
)


pytestmark = pytest.mark.asyncio


def _request(**overrides: Any):
    data: dict[str, Any] = {
        "platform": "discord",
        "guild_id": "111",
        "channel_id": "222",
        "text_channel_id": "333",
        "user_id": "444",
        "user_name": "Rob",
    }
    data.update(overrides)
    return VoiceSessionRequest(**data)


async def test_create_session_starts_provider_and_prevents_conflict():
    manager = VoiceSessionManager()

    session = await manager.create_session(_request())

    assert session.state == VoiceSessionState.LISTENING
    assert session.config.mode == "open_mic"
    with pytest.raises(VoiceSessionConflict):
        await manager.create_session(_request(channel_id="999"))


async def test_auth_checker_blocks_unauthorized_start():
    manager = VoiceSessionManager(auth_checker=lambda request: request.user_id == "allowed")

    with pytest.raises(VoiceSessionUnauthorized):
        await manager.create_session(_request(user_id="blocked"))

    session = await manager.create_session(_request(user_id="allowed"))
    assert session.state == VoiceSessionState.LISTENING


async def test_audio_budget_closes_failure_path_without_persisting_audio():
    manager = VoiceSessionManager()
    session = await manager.create_session(
        _request(),
        VoiceSessionConfig(max_input_bytes_per_minute=16_000),
    )

    with pytest.raises(VoiceSessionLimitExceeded, match="audio budget"):
        await session.receive_audio("444", b"0" * 16_001)

    # The over-budget chunk is rejected before it is counted or stored.
    assert session.input_bytes == 0
    assert not session.config.allow_raw_audio_persistence


async def test_barge_in_stops_playback_and_cancels_provider_response():
    stopped = []

    class RecordingProvider(PipelineVoiceProvider):
        name = "recording"

        def __init__(self):
            self.cancel_reasons = []

        async def cancel_response(self, session, reason):
            self.cancel_reasons.append(reason)

    provider = RecordingProvider()

    async def stop_playback(guild_id, stream_id):
        stopped.append((guild_id, stream_id))

    manager = VoiceSessionManager(
        provider_factory=lambda config: provider,
        playback_stopper=stop_playback,
    )
    session = await manager.create_session(_request())
    await session.begin_assistant_speech()

    await session.receive_audio("444", b"\0" * 3840, timestamp=session.last_activity_at + 0.1)

    assert session.state == VoiceSessionState.USER_SPEAKING
    assert session.interrupted_count == 1
    assert stopped == [("111", None)]
    assert provider.cancel_reasons == ["user_barge_in"]


async def test_close_session_releases_resources_and_removes_manager_entry():
    stopped = []

    async def stop_playback(guild_id, stream_id):
        stopped.append((guild_id, stream_id))

    manager = VoiceSessionManager(playback_stopper=stop_playback)
    session = await manager.create_session(_request())

    snapshot = await manager.close_session(session.scope_key, reason="user_leave")

    assert snapshot is not None
    assert snapshot.state == VoiceSessionState.ENDED
    assert snapshot.close_reason == "user_leave"
    assert manager.get(session.scope_key) is None
    assert stopped == [("111", None)]


async def test_event_rate_limit_rejects_excessive_stream_events():
    manager = VoiceSessionManager()
    session = await manager.create_session(
        _request(),
        VoiceSessionConfig(max_events_per_minute=30),
    )

    for _ in range(30):
        await session.receive_audio("444", b"\0")

    with pytest.raises(VoiceSessionLimitExceeded, match="event rate"):
        await session.receive_audio("444", b"\0")
