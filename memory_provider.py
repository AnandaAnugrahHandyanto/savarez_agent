"""MemoryProvider — Abstract interface for persistent memory integrations.

Hermes Agent supports pluggable memory providers (Honcho, MindGraph, Mem0, etc.)
that hook into the agent lifecycle at well-defined points. This module defines the
abstract base class, the registry, and the shared context injection helper.

Usage in AIAgent.__init__:
    from memory_provider import MemoryProviderRegistry
    self._memory = MemoryProviderRegistry()
    self._memory.register(SomeProvider())  # only activates if is_available()

Providers are called in registration order. All calls are non-fatal — exceptions
are caught and logged at debug level so the conversation continues without memory.
"""

from abc import ABC, abstractmethod
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class MemoryProvider(ABC):
    """Base class for persistent memory integrations.

    Lifecycle (called by the agent loop):
        1. on_session_start()    — first turn of a new conversation
        2. get_session_context()  — once, during system prompt assembly
        3. get_turn_context(msg)  — before each API call
        4. on_session_end(...)    — conversation expires or resets

    Implementations should be lightweight to construct. Expensive resources
    (API clients, connections) should be lazy-initialized internally.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for logging (e.g., 'honcho', 'mindgraph')."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this provider is configured and ready.

        Called once during agent init. If False, the provider is skipped.
        Should check env vars, API keys, config, etc. Must not raise.
        """
        ...

    def on_session_start(self, session_id: str, label: str = "") -> None:
        """Called on the first turn of a new conversation.

        Use for: opening sessions, initializing state, activating connections.
        """
        pass

    def get_session_context(self) -> Optional[str]:
        """Return context to bake into the system prompt (called once).

        Use for: active goals, governance policies, user profile, open
        decisions — anything visible for the entire conversation.

        Returns None or empty string to skip.
        """
        return None

    def get_turn_context(self, user_message: str) -> Optional[str]:
        """Return context relevant to this specific user message.

        Called before each API call. Results are injected ephemerally into
        the user message at API-call time (never persisted to history or
        session DB) to keep the system prompt cache stable.

        Use for: semantic retrieval, proactive recall, topic-relevant context.

        Returns None or empty string to skip.
        """
        return None

    def on_session_end(self, summary: str = "",
                       transcript: list = None,
                       session_title: str = None) -> None:
        """Called when the conversation ends or expires.

        Use for: closing sessions, ingesting transcripts, distillation.

        Args:
            summary: Brief summary of the conversation.
            transcript: List of message dicts (role/content) for ingestion.
            session_title: Optional human-friendly title for the session.
        """
        pass


class MemoryProviderRegistry:
    """Manages active memory providers for a single agent instance.

    Each AIAgent gets its own registry to avoid shared state in
    multi-user environments (e.g., the gateway serving concurrent
    Telegram conversations).
    """

    def __init__(self):
        self._providers: list[MemoryProvider] = []

    def register(self, provider: MemoryProvider) -> bool:
        """Register a provider if it's available.

        Returns True if the provider was activated, False if skipped.
        """
        try:
            if provider.is_available():
                self._providers.append(provider)
                logger.info("Memory provider activated: %s", provider.name)
                return True
            logger.debug("Memory provider not available: %s", provider.name)
            return False
        except Exception as e:
            logger.debug("Memory provider %s failed availability check: %s",
                         provider.name, e)
            return False

    @property
    def active_providers(self) -> list[MemoryProvider]:
        """List of currently active providers (in registration order)."""
        return list(self._providers)

    @property
    def has_providers(self) -> bool:
        """True if at least one provider is active."""
        return bool(self._providers)

    def on_session_start(self, session_id: str, label: str = "") -> None:
        """Notify all providers that a new session has started."""
        for p in self._providers:
            try:
                p.on_session_start(session_id, label)
            except Exception as e:
                logger.debug("%s session start failed (non-fatal): %s",
                             p.name, e)

    def get_session_context(self) -> str:
        """Collect system-prompt context from all providers.

        Returns concatenated context from all providers (in registration
        order), separated by double newlines. Returns empty string if
        no provider contributes context.
        """
        parts = []
        for p in self._providers:
            try:
                ctx = p.get_session_context()
                if ctx:
                    parts.append(ctx)
            except Exception as e:
                logger.debug("%s session context failed (non-fatal): %s",
                             p.name, e)
        return "\n\n".join(parts)

    def get_turn_context(self, user_message: str) -> str:
        """Collect per-turn context from all providers.

        Returns concatenated context (registration order), separated by
        double newlines. Returns empty string if no provider contributes.
        """
        parts = []
        for p in self._providers:
            try:
                ctx = p.get_turn_context(user_message)
                if ctx:
                    parts.append(ctx)
            except Exception as e:
                logger.debug("%s turn context failed (non-fatal): %s",
                             p.name, e)
        return "\n\n".join(parts)

    def on_session_end(self, summary: str = "", transcript: list = None,
                       session_title: str = None) -> None:
        """Notify all providers that the session has ended."""
        for p in self._providers:
            try:
                p.on_session_end(summary, transcript, session_title)
            except Exception as e:
                logger.debug("%s session end failed (non-fatal): %s",
                             p.name, e)


def create_default_registry() -> MemoryProviderRegistry:
    """Create a registry with all available providers (in priority order).

    Used by both AIAgent (per-instance) and the gateway (for session cleanup).
    Providers that aren't configured are silently skipped.

    Priority order:
        1. MindGraph (if MINDGRAPH_API_KEY is set)
        2. (Future: additional providers)
    """
    reg = MemoryProviderRegistry()
    try:
        from providers.mindgraph_provider import MindGraphProvider
        reg.register(MindGraphProvider())
    except Exception as e:
        logger.debug("MindGraph provider registration skipped: %s", e)
    return reg


def inject_provider_context(content, turn_context: str):
    """Inject memory provider context into a user message.

    Handles all content types:
    - None → returns the context string
    - str → appends context after double newline
    - list → appends a text block (multimodal messages)

    This replaces the duplicate _inject_honcho_turn_context and
    _inject_mindgraph_turn_context functions.
    """
    if not turn_context:
        return content

    if isinstance(content, list):
        return list(content) + [{"type": "text", "text": turn_context}]

    text = "" if content is None else str(content)
    if not text.strip():
        return turn_context
    return f"{text}\n\n{turn_context}"
