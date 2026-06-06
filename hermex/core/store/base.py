from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Session:
    session_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PatternRecord:
    pattern_key: tuple[str, ...]
    count: int
    session_ids: list[str]


@dataclass
class TelemetryEvent:
    session_id: str
    summary: str
    embedding: list[float]
    tool_name: str | None = None
    success: bool = True
    failure_reason: str | None = None
    source_accuracy: float = 1.0


@dataclass
class TelemetryHit:
    session_id: str
    summary: str
    score: float
    source_accuracy: float = 1.0
    tool_name: str | None = None
    success: bool = True
    failure_reason: str | None = None


@dataclass
class CrystallizedSkill:
    pattern_key: tuple[str, ...]
    tool_name: str
    description: str
    input_schema: dict[str, Any]
    execution_plan: list[dict[str, Any]] = field(default_factory=list)


class AbstractPatternStore(ABC):
    @abstractmethod
    async def increment(self, pattern: tuple[str, ...], session_id: str) -> int:
        raise NotImplementedError

    @abstractmethod
    async def get_above_threshold(self, threshold: int) -> list[PatternRecord]:
        raise NotImplementedError


class AbstractTelemetryStore(ABC):
    @abstractmethod
    async def emit(self, trace: TelemetryEvent) -> None:
        raise NotImplementedError

    @abstractmethod
    async def search_similar(
        self,
        embedding: list[float],
        top_k: int,
        exclude_session: str | None = None,
    ) -> list[TelemetryHit]:
        raise NotImplementedError

    @abstractmethod
    async def search_failures(self, embedding: list[float], top_k: int) -> list[TelemetryHit]:
        raise NotImplementedError


class AbstractSessionStore(ABC):
    @abstractmethod
    async def load_or_create(self, session_id: str) -> Session:
        raise NotImplementedError

    @abstractmethod
    async def save(self, session: Session) -> None:
        raise NotImplementedError


class AbstractSkillRegistry(ABC):
    @abstractmethod
    async def list_all(self) -> list[CrystallizedSkill]:
        raise NotImplementedError

    @abstractmethod
    async def register_if_absent(self, pattern_key: tuple[str, ...], skill: Any) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def exists_for_pattern(self, pattern_key: tuple[str, ...]) -> bool:
        raise NotImplementedError


@dataclass
class CoreStore:
    patterns: AbstractPatternStore
    telemetry: AbstractTelemetryStore
    sessions: AbstractSessionStore
    skills: AbstractSkillRegistry
