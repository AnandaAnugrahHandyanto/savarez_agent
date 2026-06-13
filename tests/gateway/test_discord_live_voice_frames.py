import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from plugins.platforms.discord.adapter import VoiceReceiver


pytestmark = pytest.mark.asyncio


async def test_voice_receiver_emits_decoded_frames_to_live_session_callback():
    seen = []

    async def on_frame(guild_id, user_id, pcm, timestamp):
        seen.append((guild_id, user_id, pcm, timestamp))

    vc = MagicMock()
    vc.guild = SimpleNamespace(id=111)
    vc.channel = SimpleNamespace(guild=SimpleNamespace(id=111), members=[])
    vc.user = SimpleNamespace(id=999)
    vc._connection.secret_key = [0] * 32
    vc._connection.dave_session = None
    vc._connection.ssrc = 999
    vc._connection.add_socket_listener = MagicMock()
    vc._connection.remove_socket_listener = MagicMock()
    vc._connection.hook = None

    receiver = VoiceReceiver(
        vc,
        allowed_user_ids={"444"},
        frame_callback=on_frame,
        loop=asyncio.get_running_loop(),
    )
    receiver.map_ssrc(123, 444)

    receiver._emit_pcm_frame(123, b"\0" * 3840)
    await asyncio.sleep(0)

    assert len(seen) == 1
    assert seen[0][0] == 111
    assert seen[0][1] == 444
    assert seen[0][2] == b"\0" * 3840
    assert isinstance(seen[0][3], float)


async def test_voice_receiver_skips_live_frame_when_ssrc_unknown():
    seen = []

    async def on_frame(guild_id, user_id, pcm, timestamp):
        seen.append((guild_id, user_id, pcm, timestamp))

    vc = MagicMock()
    vc.guild = SimpleNamespace(id=111)
    vc.channel = SimpleNamespace(guild=SimpleNamespace(id=111), members=[])
    vc.user = SimpleNamespace(id=999)
    vc._connection.secret_key = [0] * 32
    vc._connection.dave_session = None
    vc._connection.ssrc = 999
    vc._connection.add_socket_listener = MagicMock()
    vc._connection.remove_socket_listener = MagicMock()
    vc._connection.hook = None

    receiver = VoiceReceiver(vc, frame_callback=on_frame, loop=asyncio.get_running_loop())
    receiver._emit_pcm_frame(123, b"\0" * 3840)
    await asyncio.sleep(0)

    assert seen == []
