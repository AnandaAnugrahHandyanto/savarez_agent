"""Abstract base for provider transports.

A transport owns the data path for one api_mode:
  convert_messages → convert_tools → build_kwargs → normalize_response

It does NOT own: client construction, streaming, credential refresh,
prompt caching, interrupt handling, or retry logic.  Those stay on AIAgent.
"""

import copy
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set

from agent.transports.types import NormalizedResponse


def _is_valid_json(s: str) -> bool:
    """Return True if *s* is valid JSON."""
    try:
        json.loads(s)
        return True
    except (json.JSONDecodeError, ValueError, TypeError):
        return False


def sanitize_tool_calls_in_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sanitize messages by dropping malformed tool_calls and orphan tool results.

    If a streamed assistant response is cut off mid ``input_json_delta``, the
    resulting ``tool_call.arguments`` can be a truncated (non-JSON) string.
    Re-sending that history to Anthropic-compatible proxies (LiteLLM, etc.)
    causes a deterministic 400 that retries cannot recover from.

    This function:

    1. Drops assistant messages whose ``tool_calls`` contain malformed
       ``function.arguments`` (not valid JSON).
    2. Drops ``tool`` result messages whose ``tool_call_id`` no longer has a
       matching assistant tool_call (orphaned results).

    Dropping (rather than repairing to ``{}``) is intentional — a ``{}``-arg
    tool call would execute a garbage edit; dropping lets the model re-attempt
    on the next turn.

    Returns a shallow copy of the list when mutations are needed; returns the
    original list when no sanitization is required.
    """
    # First pass: collect valid tool_call_ids and detect malformed tool_calls
    valid_tool_call_ids: Set[str] = set()
    needs_sanitize = False

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "assistant":
            continue
        tool_calls = msg.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        valid_tcs = []
        for tc in tool_calls:
            if not isinstance(tc, dict):
                needs_sanitize = True
                continue
            fn = tc.get("function", {}) if isinstance(tc.get("function"), dict) else {}
            args = fn.get("arguments", "{}")
            if isinstance(args, str) and not _is_valid_json(args):
                needs_sanitize = True
                continue
            valid_tcs.append(tc)
            tc_id = tc.get("id")
            if isinstance(tc_id, str):
                valid_tool_call_ids.add(tc_id)
        if len(valid_tcs) != len(tool_calls):
            needs_sanitize = True
        # Also mark for sanitize if assistant message has no valid tool_calls
        # but originally had some (all were malformed)
        if tool_calls and not valid_tcs:
            needs_sanitize = True

    if not needs_sanitize:
        return messages

    # Second pass: rebuild messages, dropping malformed assistant messages
    # and orphan tool results
    sanitized = []
    for msg in messages:
        if not isinstance(msg, dict):
            sanitized.append(msg)
            continue

        if msg.get("role") == "assistant":
            tool_calls = msg.get("tool_calls")
            if isinstance(tool_calls, list):
                valid_tcs = []
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    fn = tc.get("function", {}) if isinstance(tc.get("function"), dict) else {}
                    args = fn.get("arguments", "{}")
                    if isinstance(args, str) and not _is_valid_json(args):
                        continue
                    valid_tcs.append(tc)
                if valid_tcs:
                    new_msg = copy.copy(msg)
                    new_msg["tool_calls"] = valid_tcs
                    sanitized.append(new_msg)
                else:
                    # All tool_calls malformed — drop the whole assistant msg
                    pass
                continue

        if msg.get("role") == "tool":
            tc_id = msg.get("tool_call_id")
            if isinstance(tc_id, str) and tc_id not in valid_tool_call_ids:
                # Orphan tool result — drop it
                continue

        sanitized.append(msg)

    return sanitized


class ProviderTransport(ABC):
    """Base class for provider-specific format conversion and normalization."""

    @property
    @abstractmethod
    def api_mode(self) -> str:
        """The api_mode string this transport handles (e.g. 'anthropic_messages')."""
        ...

    @abstractmethod
    def convert_messages(self, messages: List[Dict[str, Any]], **kwargs) -> Any:
        """Convert OpenAI-format messages to provider-native format.

        Returns provider-specific structure (e.g. (system, messages) for Anthropic,
        or the messages list unchanged for chat_completions).
        """
        ...

    @abstractmethod
    def convert_tools(self, tools: List[Dict[str, Any]]) -> Any:
        """Convert OpenAI-format tool definitions to provider-native format.

        Returns provider-specific tool list (e.g. Anthropic input_schema format).
        """
        ...

    @abstractmethod
    def build_kwargs(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **params,
    ) -> Dict[str, Any]:
        """Build the complete API call kwargs dict.

        This is the primary entry point — it typically calls convert_messages()
        and convert_tools() internally, then adds model-specific config.

        Returns a dict ready to be passed to the provider's SDK client.
        """
        ...

    @abstractmethod
    def normalize_response(self, response: Any, **kwargs) -> NormalizedResponse:
        """Normalize a raw provider response to the shared NormalizedResponse type.

        This is the only method that returns a transport-layer type.
        """
        ...

    def validate_response(self, response: Any) -> bool:
        """Optional: check if the raw response is structurally valid.

        Returns True if valid, False if the response should be treated as invalid.
        Default implementation always returns True.
        """
        return True

    def extract_cache_stats(self, response: Any) -> Optional[Dict[str, int]]:
        """Optional: extract provider-specific cache hit/creation stats.

        Returns dict with 'cached_tokens' and 'creation_tokens', or None.
        Default returns None.
        """
        return None

    def map_finish_reason(self, raw_reason: str) -> str:
        """Optional: map provider-specific stop reason to OpenAI equivalent.

        Default returns the raw reason unchanged.  Override for providers
        with different stop reason vocabularies.
        """
        return raw_reason
