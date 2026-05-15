"""Adapter registry for one-model API passthrough protocols."""

from __future__ import annotations

from typing import Any, Mapping

from .adapters.base import PassthroughProtocolAdapter
from .adapters.codex_responses import CodexResponsesAdapter
from .adapters.openai_chat import OpenAIChatAdapter

_ADAPTERS: tuple[type[PassthroughProtocolAdapter], ...] = (
    CodexResponsesAdapter,
    OpenAIChatAdapter,
)


def get_passthrough_adapter(runtime: Mapping[str, Any]) -> PassthroughProtocolAdapter | None:
    """Return the protocol adapter for a Hermes-resolved runtime.

    The registry key is protocol/api_mode only. It intentionally does not look
    at account metadata or credentials; those belong to Hermes' runtime layer.
    """

    for adapter_cls in _ADAPTERS:
        if adapter_cls.supports_runtime(runtime):
            return adapter_cls()
    return None


def supported_api_modes() -> set[str]:
    modes: set[str] = set()
    for adapter_cls in _ADAPTERS:
        modes.update(adapter_cls.api_modes)
    return modes
