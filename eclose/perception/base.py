from abc import ABC, abstractmethod
from typing import Any
from eclose.events.events import (
    PerceptionEvent,
    PerceptionSource,
    EventType,
)
from eclose.events.event_bus import get_event_bus


class BasePerceptionAgent(ABC):
    """Base class for all perception agents."""

    def __init__(self, name: str, source: PerceptionSource = PerceptionSource.PROJECT):
        self.name = name
        self.source = source
        self._event_bus = get_event_bus()

    @abstractmethod
    async def _感知(self) -> dict[str, Any]:
        """Subclasses implement their specific perception logic."""
        pass

    def perceive(self) -> PerceptionEvent:
        """Execute perception and publish event."""
        import asyncio
        data = asyncio.get_event_loop().run_until_complete(self._感知())
        event = PerceptionEvent(
            type=EventType.PERCEPTION,
            source=self.source,
            data=data,
            confidence=self._calculate_confidence(data),
        )
        self._event_bus.publish(event)
        return event

    def _calculate_confidence(self, data: dict) -> float:
        """Calculate confidence score for the perception."""
        if not data:
            return 0.0
        return 0.8  # Default confidence
