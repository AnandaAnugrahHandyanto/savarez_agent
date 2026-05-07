import pytest
from eclose.perception.self_agent import SelfPerceptionAgent
from eclose.events.events import PerceptionSource

def test_self_agent_initialization():
    agent = SelfPerceptionAgent()
    assert agent.source == PerceptionSource.SELF