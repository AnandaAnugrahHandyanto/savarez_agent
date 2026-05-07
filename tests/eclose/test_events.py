import pytest
from eclose.events.events import (
    PerceptionEvent,
    GapEvent,
    ProposalEvent,
    ExecutionEvent,
    EventType,
    PerceptionSource,
    GapType,
    Severity,
)

def test_perception_event_creation():
    event = PerceptionEvent(
        type=EventType.PERCEPTION,
        source=PerceptionSource.PROJECT,
        data={"project_path": "/test"},
        confidence=0.9,
    )
    assert event.type == EventType.PERCEPTION
    assert event.source == PerceptionSource.PROJECT
    assert event.data["project_path"] == "/test"
    assert event.confidence == 0.9
    assert event.timestamp is not None
