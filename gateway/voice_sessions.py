from __future__ import annotations

"""Realtime voice session lifecycle primitives for gateway adapters.

This module is intentionally platform-neutral: Discord owns joining voice
channels and decoding RTP, while this backend owns session state, provider
selection, cancellation/interruption, and guardrails.  The first production
consumer is the Discord gateway `/voice live` flow.
"""

import asyncio
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, Optional, Protocol


class VoiceSessionError(RuntimeError):
    """Base class for user-visible voice session failures."""


class VoiceSessionConflict(VoiceSessionError):
    """A live session already exists for this profile/platform scope."""


class VoiceSessionUnauthorized(VoiceSessionError):
    """The caller is not authorized to create/use a voice session."""


class VoiceSessionLimitExceeded(VoiceSessionError):
    """A safe default budget or rate limit was exceeded."""


class VoiceSessionState(str, Enum):
    JOINING = "joining"
    LISTENING = "listening"
    USER_SPEAKING = "user_speaking"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    TOOL_WAIT = "tool_wait"
    DEGRADED = "degraded"
    ENDING = "ending"
    ENDED = "ended"


@dataclass(frozen=True)
class VoiceSessionConfig:
    """Safe defaults for one live voice session."""

    provider: str = "pipeline"
    mode: str = "open_mic"
    transcript_mode: str = "visible_summary"
    max_duration_seconds: int = 600
    max_input_bytes_per_minute: int = 48_000 * 2 * 2 * 60
    max_events_per_minute: int = 600
    allow_raw_audio_persistence: bool = False

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]] = None) -> "VoiceSessionConfig":
        data = dict(data or {})
        provider = str(data.get("provider") or "pipeline").strip().lower()
        mode = str(data.get("mode") or "open_mic").strip().lower()
        transcript_mode = str(data.get("transcript_mode") or "visible_summary").strip().lower()
        return cls(
            provider=provider,
            mode=mode,
            transcript_mode=transcript_mode,
            max_duration_seconds=max(30, int(data.get("max_duration_seconds", 600))),
            max_input_bytes_per_minute=max(16_000, int(data.get("max_input_bytes_per_minute", 48_000 * 2 * 2 * 60))),
            max_events_per_minute=max(30, int(data.get("max_events_per_minute", 600))),
            allow_raw_audio_persistence=bool(data.get("allow_raw_audio_persistence", False)),
        )


@dataclass(frozen=True)
class VoiceSessionRequest:
    platform: str
    guild_id: str
    channel_id: str
    text_channel_id: str
    user_id: str
    user_name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def scope_key(self) -> str:
        # One live session per platform/guild/profile scope for MVP.
        return f"{self.platform}:{self.guild_id}"


@dataclass
class VoiceSessionSnapshot:
    session_id: str
    scope_key: str
    state: VoiceSessionState
    provider: str
    mode: str
    transcript_mode: str
    started_at: float
    last_activity_at: float
    input_bytes: int = 0
    events_seen: int = 0
    interrupted_count: int = 0
    close_reason: Optional[str] = None


class RealtimeVoiceProvider(Protocol):
    name: str

    async def connect(self, session: "VoiceSession") -> None: ...
    async def send_audio(self, session: "VoiceSession", user_id: str, pcm_48k_stereo: bytes, *, timestamp: float) -> None: ...
    async def cancel_response(self, session: "VoiceSession", reason: str) -> None: ...
    async def close(self, session: "VoiceSession") -> None: ...


class PipelineVoiceProvider:
    """Fallback provider that keeps the existing STT -> text agent -> TTS path.

    The Discord adapter still emits completed utterances to the normal Hermes
    message pipeline.  This provider receives realtime frames for lifecycle,
    budgeting, and barge-in detection, but deliberately does not persist raw
    audio or call batch STT itself.
    """

    name = "pipeline"

    async def connect(self, session: "VoiceSession") -> None:
        session.set_state(VoiceSessionState.LISTENING)

    async def send_audio(self, session: "VoiceSession", user_id: str, pcm_48k_stereo: bytes, *, timestamp: float) -> None:
        session.mark_user_speaking(user_id=user_id, timestamp=timestamp)

    async def cancel_response(self, session: "VoiceSession", reason: str) -> None:
        return None

    async def close(self, session: "VoiceSession") -> None:
        return None


class OpenAIRealtimeVoiceProvider(PipelineVoiceProvider):
    """Readiness gate for the selected realtime model path.

    Full websocket event translation lands behind this interface.  Until then,
    selecting provider="openai_realtime" verifies credentials and then runs in
    degraded pipeline mode rather than silently pretending raw audio is being
    streamed to OpenAI.
    """

    name = "openai_realtime"

    async def connect(self, session: "VoiceSession") -> None:
        if not (os.getenv("OPENAI_API_KEY") or os.getenv("VOICE_TOOLS_OPENAI_KEY")):
            session.set_state(VoiceSessionState.DEGRADED)
            session.degraded_reason = "OpenAI realtime credentials missing; using pipeline voice fallback"
        else:
            session.set_state(VoiceSessionState.DEGRADED)
            session.degraded_reason = "OpenAI realtime websocket adapter not enabled yet; using pipeline voice fallback"


ProviderFactory = Callable[[VoiceSessionConfig], RealtimeVoiceProvider]
AuthChecker = Callable[[VoiceSessionRequest], bool | Awaitable[bool]]
PlaybackStopper = Callable[[str, Optional[str]], Awaitable[None]]


def default_provider_factory(config: VoiceSessionConfig) -> RealtimeVoiceProvider:
    if config.provider in {"openai", "openai_realtime", "realtime"}:
        return OpenAIRealtimeVoiceProvider()
    return PipelineVoiceProvider()


class VoiceSession:
    def __init__(
        self,
        request: VoiceSessionRequest,
        config: VoiceSessionConfig,
        provider: RealtimeVoiceProvider,
        *,
        playback_stopper: Optional[PlaybackStopper] = None,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self.request = request
        self.config = config
        self.provider = provider
        self.session_id = f"vs_{uuid.uuid4().hex[:12]}"
        self.scope_key = request.scope_key
        self._now = now
        self.started_at = now()
        self.last_activity_at = self.started_at
        self.state = VoiceSessionState.JOINING
        self.input_bytes = 0
        self.events_seen = 0
        self.interrupted_count = 0
        self.close_reason: Optional[str] = None
        self.degraded_reason: Optional[str] = None
        self._window_started_at = self.started_at
        self._window_input_bytes = 0
        self._window_events = 0
        self._playback_stopper = playback_stopper
        self._closed = False
        self._lock = asyncio.Lock()

    def set_state(self, state: VoiceSessionState) -> None:
        self.state = state
        self.last_activity_at = self._now()

    def snapshot(self) -> VoiceSessionSnapshot:
        return VoiceSessionSnapshot(
            session_id=self.session_id,
            scope_key=self.scope_key,
            state=self.state,
            provider=self.provider.name,
            mode=self.config.mode,
            transcript_mode=self.config.transcript_mode,
            started_at=self.started_at,
            last_activity_at=self.last_activity_at,
            input_bytes=self.input_bytes,
            events_seen=self.events_seen,
            interrupted_count=self.interrupted_count,
            close_reason=self.close_reason,
        )

    async def start(self) -> None:
        await self.provider.connect(self)
        if self.state == VoiceSessionState.JOINING:
            self.set_state(VoiceSessionState.LISTENING)

    def _check_limits(self, byte_count: int, now: float) -> None:
        if now - self.started_at > self.config.max_duration_seconds:
            raise VoiceSessionLimitExceeded("voice session duration limit exceeded")
        if now - self._window_started_at >= 60:
            self._window_started_at = now
            self._window_input_bytes = 0
            self._window_events = 0
        if self._window_events + 1 > self.config.max_events_per_minute:
            raise VoiceSessionLimitExceeded("voice session event rate limit exceeded")
        if self._window_input_bytes + byte_count > self.config.max_input_bytes_per_minute:
            raise VoiceSessionLimitExceeded("voice session audio budget exceeded")

    def mark_user_speaking(self, *, user_id: str, timestamp: Optional[float] = None) -> None:
        if self.state == VoiceSessionState.SPEAKING:
            # The async cancel is done in receive_audio; this synchronous state
            # update keeps provider callbacks simple.
            self.state = VoiceSessionState.INTERRUPTED
        else:
            self.state = VoiceSessionState.USER_SPEAKING
        self.last_activity_at = timestamp or self._now()

    async def receive_audio(self, user_id: str, pcm_48k_stereo: bytes, *, timestamp: Optional[float] = None) -> None:
        if self._closed:
            return
        now = timestamp or self._now()
        async with self._lock:
            self._check_limits(len(pcm_48k_stereo), now)
            self.input_bytes += len(pcm_48k_stereo)
            self.events_seen += 1
            self._window_input_bytes += len(pcm_48k_stereo)
            self._window_events += 1
            was_speaking = self.state == VoiceSessionState.SPEAKING
            if was_speaking:
                await self.interrupt(reason="user_barge_in")
            await self.provider.send_audio(self, user_id, pcm_48k_stereo, timestamp=now)

    async def begin_assistant_speech(self) -> None:
        if not self._closed:
            self.set_state(VoiceSessionState.SPEAKING)

    async def interrupt(self, *, reason: str = "interrupted") -> None:
        if self._closed:
            return
        self.interrupted_count += 1
        self.set_state(VoiceSessionState.INTERRUPTED)
        if self._playback_stopper is not None:
            await self._playback_stopper(self.request.guild_id, None)
        await self.provider.cancel_response(self, reason)

    async def close(self, *, reason: str = "closed") -> None:
        if self._closed:
            return
        self._closed = True
        self.close_reason = reason
        self.set_state(VoiceSessionState.ENDING)
        try:
            if self._playback_stopper is not None:
                await self._playback_stopper(self.request.guild_id, None)
        finally:
            await self.provider.close(self)
            self.set_state(VoiceSessionState.ENDED)


class VoiceSessionManager:
    def __init__(
        self,
        *,
        provider_factory: ProviderFactory = default_provider_factory,
        auth_checker: Optional[AuthChecker] = None,
        playback_stopper: Optional[PlaybackStopper] = None,
    ) -> None:
        self._provider_factory = provider_factory
        self._auth_checker = auth_checker
        self._playback_stopper = playback_stopper
        self._sessions: Dict[str, VoiceSession] = {}
        self._lock = asyncio.Lock()

    @property
    def sessions(self) -> Dict[str, VoiceSession]:
        return dict(self._sessions)

    async def _authorized(self, request: VoiceSessionRequest) -> bool:
        if self._auth_checker is None:
            return True
        allowed = self._auth_checker(request)
        if asyncio.iscoroutine(allowed):
            allowed = await allowed
        return bool(allowed)

    async def create_session(self, request: VoiceSessionRequest, config: Optional[VoiceSessionConfig] = None) -> VoiceSession:
        if not await self._authorized(request):
            raise VoiceSessionUnauthorized("not authorized to start a voice session")
        config = config or VoiceSessionConfig()
        async with self._lock:
            existing = self._sessions.get(request.scope_key)
            if existing and existing.state is not VoiceSessionState.ENDED:
                raise VoiceSessionConflict(f"voice session already active for {request.scope_key}")
            provider = self._provider_factory(config)
            session = VoiceSession(
                request,
                config,
                provider,
                playback_stopper=self._playback_stopper,
            )
            self._sessions[request.scope_key] = session
        try:
            await session.start()
        except Exception:
            async with self._lock:
                self._sessions.pop(request.scope_key, None)
            raise
        return session

    def get(self, scope_key: str) -> Optional[VoiceSession]:
        return self._sessions.get(scope_key)

    async def receive_audio(self, scope_key: str, user_id: str, pcm_48k_stereo: bytes, *, timestamp: Optional[float] = None) -> bool:
        session = self._sessions.get(scope_key)
        if not session:
            return False
        await session.receive_audio(user_id, pcm_48k_stereo, timestamp=timestamp)
        return True

    async def close_session(self, scope_key: str, *, reason: str = "closed") -> Optional[VoiceSessionSnapshot]:
        session = self._sessions.get(scope_key)
        if not session:
            return None
        await session.close(reason=reason)
        async with self._lock:
            self._sessions.pop(scope_key, None)
        return session.snapshot()
