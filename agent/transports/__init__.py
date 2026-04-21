"""Transport layer types and registry for provider response normalization.

Usage:
    from agent.transports import get_transport
    transport = get_transport("anthropic_messages")
    result = transport.normalize_response(raw_response)
"""

import importlib

from agent.transports.types import NormalizedResponse, ToolCall, Usage, build_tool_call, map_finish_reason  # noqa: F401

_REGISTRY: dict = {}

_TRANSPORT_MODULES = {
    "anthropic_messages": ("agent.transports.anthropic", "AnthropicTransport"),
    "codex_responses": ("agent.transports.codex", "ResponsesApiTransport"),
    "chat_completions": ("agent.transports.chat_completions", "ChatCompletionsTransport"),
    "bedrock_converse": ("agent.transports.bedrock", "BedrockTransport"),
}


def register_transport(api_mode: str, transport_cls: type) -> None:
    """Register a transport class for an api_mode string."""
    _REGISTRY[api_mode] = transport_cls


def get_transport(api_mode: str):
    """Get a transport instance for the given api_mode.

    Returns None if no transport is registered for this api_mode.
    This allows gradual migration — call sites can check for None
    and fall back to the legacy code path.
    """
    if not _REGISTRY:
        _discover_transports()
    cls = _REGISTRY.get(api_mode)
    if cls is None:
        _discover_transport(api_mode)
        cls = _REGISTRY.get(api_mode)
    if cls is None:
        return None
    return cls()


def _discover_transport(api_mode: str) -> None:
    """Import the module for a single transport mode if it is known."""
    module_info = _TRANSPORT_MODULES.get(api_mode)
    if module_info is None:
        return
    module_name, class_name = module_info
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        return
    if api_mode in _REGISTRY:
        return
    transport_cls = getattr(module, class_name, None)
    if transport_cls is not None:
        register_transport(api_mode, transport_cls)


def _discover_transports() -> None:
    """Import all transport modules to trigger auto-registration."""
    for api_mode in _TRANSPORT_MODULES:
        _discover_transport(api_mode)
