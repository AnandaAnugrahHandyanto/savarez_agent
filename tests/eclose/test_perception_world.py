import pytest
from eclose.perception.world import WorldPerceptionAgent
from eclose.events.events import PerceptionSource

def test_world_agent_initialization():
    agent = WorldPerceptionAgent()
    assert agent.source == PerceptionSource.WORLD
