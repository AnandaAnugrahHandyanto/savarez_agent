"""Forward Hypura daemon actions to the Desktop Companion via the public SDK bridge."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class CompanionBridge:
    """Dispatch Desktop Companion commands through a Node SDK bridge with HTTP fallback."""

    def __init__(
        self,
        companion_url: str,
        *,
        repo_root: Path | None = None,
        state_dir: Path | None = None,
    ) -> None:
        self._base = companion_url.rstrip("/")
        self._repo_root = repo_root or Path(__file__).resolve().parents[3]
        self._state_dir = state_dir or (self._repo_root / ".openclaw-desktop")
        self._sdk_bridge_script = Path(__file__).with_name("companion_sdk_bridge.mjs")

    async def _run_sdk_bridge(
        self,
        *,
        text: str | None = None,
        avatar_command: dict[str, Any] | None = None,
        mic_enabled: bool | None = None,
        tts_provider: str | None = None,
        permission: dict[str, str] | None = None,
        input_snapshot: dict[str, bool] | None = None,
        window_capture: bool = False,
        get_state: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"stateDir": str(self._state_dir)}
        if text:
            payload["text"] = text
        if avatar_command:
            payload["avatarCommand"] = avatar_command
        if mic_enabled is not None:
            payload["micEnabled"] = mic_enabled
        if tts_provider:
            payload["ttsProvider"] = tts_provider
        if permission:
            payload["permission"] = permission
        if input_snapshot:
            payload["inputSnapshot"] = input_snapshot
        if window_capture:
            payload["windowCapture"] = True
        if get_state:
            payload["getState"] = True

        proc = await asyncio.create_subprocess_exec(
            "node",
            str(self._sdk_bridge_script),
            cwd=str(self._repo_root),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate(json.dumps(payload).encode("utf-8"))
        if proc.returncode != 0:
            raise RuntimeError(
                (
                    stderr.decode("utf-8", errors="replace")
                    or stdout.decode("utf-8", errors="replace")
                ).strip()
                or f"node bridge exited with {proc.returncode}"
            )
        if not stdout:
            return {"ok": True}
        decoded = stdout.decode("utf-8", errors="replace").strip()
        return json.loads(decoded) if decoded else {"ok": True}

    async def _post_legacy_http(
        self,
        *,
        text: str | None = None,
        avatar_command: dict[str, Any] | None = None,
    ) -> None:
        url = f"{self._base}/control"
        payload: dict[str, Any] = {}
        if text:
            payload["speakText"] = text
        if avatar_command:
            payload["avatarCommand"] = avatar_command
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(url, json=payload)

    async def _dispatch(
        self,
        *,
        text: str | None = None,
        avatar_command: dict[str, Any] | None = None,
        mic_enabled: bool | None = None,
        tts_provider: str | None = None,
    ) -> dict[str, Any]:
        try:
            return await self._run_sdk_bridge(
                text=text,
                avatar_command=avatar_command,
                mic_enabled=mic_enabled,
                tts_provider=tts_provider,
            )
        except Exception as e:  # noqa: BLE001 - preserve legacy compatibility fallback
            logger.warning("Companion SDK bridge failed, falling back to legacy HTTP: %s", e)
            if not text and not avatar_command:
                return {"ok": False, "error": str(e)}

        try:
            await self._post_legacy_http(text=text, avatar_command=avatar_command)
            return {"ok": True, "legacy_http": True}
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout, RuntimeError) as e:
            logger.warning("Companion bridge dispatch failed: %s", e)
            return {"ok": False, "error": str(e)}

    async def forward_speak(
        self, text: str, emotion: str, tts_provider: str | None = None
    ) -> dict[str, Any]:
        return await self._dispatch(
            text=text,
            avatar_command={"expression": emotion},
            tts_provider=tts_provider,
        )

    async def forward_emotion(self, emotion: str) -> dict[str, Any]:
        return await self._dispatch(avatar_command={"expression": emotion})

    async def forward_motion(self, motion: str, motion_index: int = 0) -> dict[str, Any]:
        return await self._dispatch(
            avatar_command={"motion": motion, "motionIndex": motion_index}
        )

    async def forward_expression(self, expression: str) -> dict[str, Any]:
        return await self._dispatch(avatar_command={"expression": expression})

    async def forward_look(self, x: float, y: float) -> dict[str, Any]:
        return await self._dispatch(avatar_command={"lookAt": {"x": x, "y": y}})

    async def forward_load_model(self, model_path: str) -> dict[str, Any]:
        return await self._dispatch(avatar_command={"loadModel": model_path})

    async def set_mic_enabled(self, enabled: bool) -> dict[str, Any]:
        return await self._dispatch(mic_enabled=enabled)

    async def set_permission(self, capability: str, decision: str) -> dict[str, Any]:
        return await self._run_sdk_bridge(
            permission={"capability": capability, "decision": decision}
        )

    async def input_snapshot(
        self, *, include_camera: bool = False, capture_camera: bool = False
    ) -> dict[str, Any]:
        return await self._run_sdk_bridge(
            input_snapshot={
                "includeCamera": include_camera,
                "captureCamera": capture_camera,
            }
        )

    async def window_capture(self) -> dict[str, Any]:
        return await self._run_sdk_bridge(window_capture=True)

    async def get_state(self) -> dict[str, Any]:
        return await self._run_sdk_bridge(get_state=True)
