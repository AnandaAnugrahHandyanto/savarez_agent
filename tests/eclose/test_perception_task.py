import pytest
from eclose.perception.task import TaskPerceptionAgent
from eclose.events.events import PerceptionSource

def test_task_agent_initialization():
    agent = TaskPerceptionAgent()
    assert agent.source == PerceptionSource.TASK
