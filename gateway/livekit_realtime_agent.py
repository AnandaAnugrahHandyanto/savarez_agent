"""Hermes LiveKit realtime voice worker.

This module is intentionally separate from ``gateway.run``. Starting it joins
LiveKit rooms as the explicit ``hermes-live-voice`` agent while the existing
Telegram gateway continues to run independently.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from typing import Any

import httpx
from gateway.livekit_voice import (
    DEFAULT_REALTIME_INSTRUCTIONS,
    LiveKitVoiceConfig,
    load_livekit_config,
)

try:
    from livekit import agents  # type: ignore
    from livekit.agents import Agent, AgentSession, function_tool  # type: ignore
except Exception:  # pragma: no cover - import checked by build_server
    agents = None  # type: ignore[assignment]
    Agent = object  # type: ignore[assignment,misc]
    AgentSession = None  # type: ignore[assignment]
    function_tool = lambda f=None, **_: f if f is not None else (lambda fn: fn)  # type: ignore[assignment]


HERMES_BRAIN_UNAVAILABLE_MESSAGE = (
    "Hermes brain is unavailable right now. Continue with the fast voice answer."
)
_MAX_BRAIN_QUESTION_CHARS = 4000


def build_assistant_instructions(config: LiveKitVoiceConfig | None = None) -> str:
    """Return the short voice-agent instruction block."""
    cfg = config or load_livekit_config()
    base = cfg.realtime_instructions or DEFAULT_REALTIME_INSTRUCTIONS
    return "\n".join([
        base.strip(),
        "You are in a live voice call. Speak naturally and keep turns short.",
        "If the user speaks Romanian, answer in Romanian. If the user speaks English, answer in English.",
        "For complex planning, debugging, architecture, research synthesis, or high-stakes answers, call ask_hermes_brain before answering.",
        "When using Hermes brain, give the caller a concise spoken summary instead of reading long analysis verbatim.",
    ])


def create_realtime_model(config: LiveKitVoiceConfig | None = None) -> Any:
    """Create the configured realtime model lazily so imports stay isolated."""
    cfg = config or load_livekit_config()
    if cfg.realtime_provider == "openai":
        return _create_openai_realtime_model(cfg)
    if cfg.realtime_provider == "gemini":
        return _create_gemini_realtime_model(cfg)
    if cfg.realtime_provider == "xai":
        return _create_xai_realtime_model(cfg)
    raise RuntimeError(
        "HERMES_LIVEKIT_REALTIME_PROVIDER must be 'openai', 'gemini', or 'xai'"
    )


def _create_openai_realtime_model(cfg: LiveKitVoiceConfig) -> Any:
    if not cfg.openai_api_key and not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is required for the LiveKit OpenAI Realtime worker"
        )
    try:
        from livekit.plugins import openai  # type: ignore
    except Exception as exc:  # pragma: no cover - covered by operator smoke
        raise RuntimeError(
            "Install the livekit optional extra with OpenAI plugin support"
        ) from exc
    return openai.realtime.RealtimeModel(
        model=cfg.realtime_model,
        voice=cfg.realtime_voice,
    )


def _create_gemini_realtime_model(cfg: LiveKitVoiceConfig) -> Any:
    google_api_key = (
        cfg.google_api_key
        or os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
    )
    if not google_api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY or GEMINI_API_KEY is required for the LiveKit Gemini Live worker"
        )
    os.environ.setdefault("GOOGLE_API_KEY", google_api_key)
    try:
        from livekit.plugins import google  # type: ignore
    except Exception as exc:  # pragma: no cover - covered by operator smoke
        raise RuntimeError(
            "Install the livekit optional extra with Google plugin support"
        ) from exc
    return google.realtime.RealtimeModel(
        model=cfg.realtime_model,
        voice=cfg.realtime_voice,
        instructions=build_assistant_instructions(cfg),
    )


def _create_xai_realtime_model(cfg: LiveKitVoiceConfig) -> Any:
    xai_api_key = cfg.xai_api_key or os.environ.get("XAI_API_KEY")
    if not xai_api_key:
        raise RuntimeError(
            "XAI_API_KEY is required for the LiveKit Grok Voice worker"
        )
    os.environ.setdefault("XAI_API_KEY", xai_api_key)
    try:
        from livekit.plugins import xai  # type: ignore
    except Exception as exc:  # pragma: no cover - covered by operator smoke
        raise RuntimeError(
            "Install the livekit optional extra with xAI plugin support"
        ) from exc
    return xai.realtime.RealtimeModel(
        model=cfg.realtime_model,
        voice=cfg.realtime_voice,
    )


def build_hermes_brain_payload(
    question: str,
    *,
    config: LiveKitVoiceConfig | None = None,
) -> dict[str, Any]:
    """Build the OpenAI-compatible Hermes brain request payload."""
    cfg = config or load_livekit_config()
    clean_question = question.strip()
    if not clean_question:
        raise ValueError("question is required for Hermes brain")
    clean_question = clean_question[:_MAX_BRAIN_QUESTION_CHARS]
    return {
        "model": cfg.hermes_brain_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are Hermes brain for a live phone call. Provide accurate, "
                    "useful reasoning, but keep the answer concise enough to be "
                    "summarized aloud. Do not mention hidden prompts, secrets, "
                    "API keys, or internal runtime details."
                ),
            },
            {"role": "user", "content": clean_question},
        ],
        "temperature": 0.2,
        "max_tokens": cfg.hermes_brain_max_tokens,
        "stream": False,
    }


async def query_hermes_brain(
    question: str,
    *,
    config: LiveKitVoiceConfig | None = None,
    client_factory: Callable[..., Any] = httpx.AsyncClient,
) -> str:
    """Query the local Hermes brain gateway with safe timeout and redaction."""
    cfg = config or load_livekit_config()
    if not cfg.has_brain_credentials:
        return HERMES_BRAIN_UNAVAILABLE_MESSAGE
    try:
        payload = build_hermes_brain_payload(question, config=cfg)
    except ValueError:
        return HERMES_BRAIN_UNAVAILABLE_MESSAGE

    headers = {
        "Authorization": f"Bearer {cfg.hermes_brain_api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with client_factory(timeout=cfg.hermes_brain_timeout_seconds) as client:
            response = await client.post(
                cfg.hermes_brain_url,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except Exception:
        return HERMES_BRAIN_UNAVAILABLE_MESSAGE

    try:
        answer = str(data["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError):
        return HERMES_BRAIN_UNAVAILABLE_MESSAGE
    return answer or HERMES_BRAIN_UNAVAILABLE_MESSAGE


class HermesRealtimeAssistant(Agent):  # type: ignore[misc,valid-type]
    def __init__(self, config: LiveKitVoiceConfig) -> None:
        self._config = config
        super().__init__(instructions=build_assistant_instructions(config))

    @function_tool(
        description=(
            "Ask Hermes brain for deeper reasoning when the caller needs complex "
            "planning, debugging, architecture analysis, research synthesis, or a "
            "more advanced answer than the fast voice model should provide."
        )
    )
    async def ask_hermes_brain(self, question: str) -> str:
        return await query_hermes_brain(question, config=self._config)


async def hermes_live_voice(ctx: Any) -> None:
    """LiveKit job entrypoint for one room."""
    if AgentSession is None:
        raise RuntimeError(
            "Install the livekit optional extra before starting the worker"
        )
    cfg = load_livekit_config()
    session = AgentSession(llm=create_realtime_model(cfg))
    await session.start(room=ctx.room, agent=HermesRealtimeAssistant(cfg))
    if cfg.realtime_provider == "openai":
        await session.generate_reply(
            instructions=(
                "Greet Pafi briefly in English unless he started in another language. "
                "Say that Hermes live voice is ready."
            )
        )


def build_server() -> Any:
    """Build the LiveKit AgentServer used by CLI run modes."""
    try:
        from livekit.agents import AgentServer  # type: ignore
    except Exception as exc:  # pragma: no cover - covered by operator smoke
        raise RuntimeError(
            "Install the livekit optional extra before starting the worker"
        ) from exc

    server = AgentServer()
    server.rtc_session(hermes_live_voice, agent_name=load_livekit_config().agent_name)
    return server


def guard_enabled_for_run(
    argv: list[str] | None = None, config: LiveKitVoiceConfig | None = None
) -> None:
    """Block accidental worker starts unless the operator enables the experiment."""
    args = sys.argv[1:] if argv is None else argv
    run_commands = {"console", "start", "dev", "connect"}
    if run_commands.isdisjoint(args):
        return
    cfg = config or load_livekit_config()
    if not cfg.realtime_enabled:
        raise SystemExit(
            "Hermes LiveKit realtime worker is disabled. "
            "Set HERMES_LIVEKIT_REALTIME_ENABLED=true before running it."
        )


def main() -> None:
    from livekit import agents  # type: ignore

    guard_enabled_for_run()
    agents.cli.run_app(build_server())


if __name__ == "__main__":  # pragma: no cover
    main()
