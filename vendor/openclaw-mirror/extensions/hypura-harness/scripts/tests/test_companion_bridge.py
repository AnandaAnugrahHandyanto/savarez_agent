# scripts/hypura/tests/test_companion_bridge.py
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from companion_bridge import CompanionBridge


@pytest.mark.asyncio
async def test_forward_speak_prefers_sdk_bridge() -> None:
    bridge = CompanionBridge("http://127.0.0.1:18791", repo_root=Path("C:/repo"))
    with patch.object(bridge, "_run_sdk_bridge", new=AsyncMock()) as mock_sdk:
        await bridge.forward_speak("hello", "happy")

    mock_sdk.assert_awaited_once_with(
        text="hello",
        avatar_command={"expression": "happy"},
        mic_enabled=None,
        tts_provider=None,
    )


@pytest.mark.asyncio
async def test_forward_speak_forwards_tts_provider() -> None:
    bridge = CompanionBridge("http://127.0.0.1:18791", repo_root=Path("C:/repo"))
    with patch.object(bridge, "_dispatch", new=AsyncMock()) as mock_dispatch:
        await bridge.forward_speak("hello", "happy", "web-speech")

    mock_dispatch.assert_awaited_once_with(
        text="hello",
        avatar_command={"expression": "happy"},
        tts_provider="web-speech",
    )


@pytest.mark.asyncio
async def test_forward_emotion_falls_back_to_legacy_http() -> None:
    bridge = CompanionBridge("http://127.0.0.1:18791", repo_root=Path("C:/repo"))
    with patch.object(
        bridge, "_run_sdk_bridge", new=AsyncMock(side_effect=RuntimeError("sdk failed"))
    ), patch("companion_bridge.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_cls.return_value.__aexit__.return_value = None

        await bridge.forward_emotion("neutral")

        mock_client.post.assert_awaited_once()
        call_args = mock_client.post.await_args
        assert call_args[0][0] == "http://127.0.0.1:18791/control"
        assert call_args[1]["json"] == {
            "avatarCommand": {"expression": "neutral"},
        }


@pytest.mark.asyncio
async def test_forward_speak_silently_fails_when_companion_down() -> None:
    bridge = CompanionBridge("http://127.0.0.1:18791", repo_root=Path("C:/repo"))
    with patch.object(
        bridge, "_run_sdk_bridge", new=AsyncMock(side_effect=RuntimeError("sdk failed"))
    ), patch("companion_bridge.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        req = MagicMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.ConnectError("connection refused", request=req)
        )
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_cls.return_value.__aexit__.return_value = None

        await bridge.forward_speak("hi", "neutral")


@pytest.mark.asyncio
async def test_mic_toggle_reports_sdk_failure_without_empty_legacy_fallback() -> None:
    bridge = CompanionBridge("http://127.0.0.1:18791", repo_root=Path("C:/repo"))
    with patch.object(
        bridge, "_run_sdk_bridge", new=AsyncMock(side_effect=RuntimeError("sdk failed"))
    ), patch("companion_bridge.httpx.AsyncClient") as mock_cls:
        result = await bridge.set_mic_enabled(True)

    assert result == {"ok": False, "error": "sdk failed"}
    assert not mock_cls.called


@pytest.mark.asyncio
async def test_forward_motion_uses_expected_avatar_command() -> None:
    bridge = CompanionBridge("http://127.0.0.1:18791", repo_root=Path("C:/repo"))
    with patch.object(bridge, "_dispatch", new=AsyncMock()) as mock_dispatch:
        await bridge.forward_motion("Idle", 2)

    mock_dispatch.assert_awaited_once_with(
        avatar_command={"motion": "Idle", "motionIndex": 2}
    )


@pytest.mark.asyncio
async def test_forward_load_model_uses_expected_avatar_command() -> None:
    bridge = CompanionBridge("http://127.0.0.1:18791", repo_root=Path("C:/repo"))
    with patch.object(bridge, "_dispatch", new=AsyncMock()) as mock_dispatch:
        await bridge.forward_load_model("C:/repo/assets/Hakua.fbx")

    mock_dispatch.assert_awaited_once_with(
        avatar_command={"loadModel": "C:/repo/assets/Hakua.fbx"}
    )


@pytest.mark.asyncio
async def test_state_helpers_use_sdk_bridge_only() -> None:
    bridge = CompanionBridge("http://127.0.0.1:18791", repo_root=Path("C:/repo"))
    with patch.object(
        bridge, "_run_sdk_bridge", new=AsyncMock(return_value={"ok": True})
    ) as mock_sdk:
        await bridge.set_permission("mic", "granted")
        await bridge.input_snapshot(include_camera=True, capture_camera=False)
        await bridge.window_capture()
        await bridge.get_state()

    mock_sdk.assert_any_await(permission={"capability": "mic", "decision": "granted"})
    mock_sdk.assert_any_await(
        input_snapshot={"includeCamera": True, "captureCamera": False}
    )
    mock_sdk.assert_any_await(window_capture=True)
    mock_sdk.assert_any_await(get_state=True)
