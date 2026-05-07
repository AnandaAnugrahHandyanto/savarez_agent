import pytest
from eclose.perception.base import BasePerceptionAgent
from eclose.events.events import PerceptionSource, PerceptionEvent

class TestAgent(BasePerceptionAgent):
    async def _感知(self) -> dict:
        return {"test": True}

def test_base_agent_initialization():
    agent = TestAgent(name="TestAgent")
    assert agent.name == "TestAgent"
    assert agent.source == PerceptionSource.PROJECT  # Default

def test_base_agent_perceive():
    agent = TestAgent(name="TestAgent")
    event = agent.perceive()
    assert isinstance(event, PerceptionEvent)
    assert event.data["test"] is True
