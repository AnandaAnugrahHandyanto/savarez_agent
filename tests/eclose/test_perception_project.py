import pytest
from eclose.perception.project import ProjectPerceptionAgent
from eclose.events.events import PerceptionSource

def test_project_agent_initialization():
    agent = ProjectPerceptionAgent(project_path="/test/path")
    assert agent.source == PerceptionSource.PROJECT
    assert agent.project_path == "/test/path"

def test_project_agent_default_path():
    agent = ProjectPerceptionAgent()
    assert agent.project_path is not None