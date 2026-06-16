"""Tests for the dynamic_workflow tool."""

from __future__ import annotations

import json

import pytest

from tools import dynamic_workflow_tool as dwt


@pytest.fixture(autouse=True)
def _clean_workflows():
    dwt._reset_for_tests()
    yield
    dwt._reset_for_tests()


def _call(args, parent_agent=None):
    return json.loads(dwt.handle_dynamic_workflow(args, parent_agent=parent_agent))


def test_create_validates_dag_and_reports_ready_nodes():
    result = _call(
        {
            "action": "create",
            "workflow_id": "wf_demo",
            "objective": "Research a release",
            "nodes": [
                {
                    "node_id": "source_triage",
                    "phase_id": "investigate",
                    "phase_title": "Investigate",
                    "title": "Source triage",
                    "goal": "Find sources",
                },
                {
                    "node_id": "synthesis",
                    "phase": "Synthesize",
                    "goal": "Synthesize source findings",
                    "depends_on": ["source_triage"],
                },
            ],
        }
    )

    workflow = result["workflow"]
    assert workflow["workflow_id"] == "wf_demo"
    assert workflow["status"] == "ready"
    assert workflow["ready_node_ids"] == ["source_triage"]
    assert workflow["nodes"][0]["phase_id"] == "investigate"
    assert workflow["nodes"][0]["phase_title"] == "Investigate"
    assert workflow["nodes"][0]["title"] == "Source triage"
    assert workflow["nodes"][1]["phase_id"] == "synthesize"
    assert workflow["nodes"][1]["phase_title"] == "Synthesize"
    assert [node["node_id"] for node in workflow["nodes"]] == [
        "source_triage",
        "synthesis",
    ]


def test_create_rejects_cycles():
    result = _call(
        {
            "action": "create",
            "workflow_id": "wf_cycle",
            "objective": "Bad graph",
            "nodes": [
                {"node_id": "a", "goal": "A", "depends_on": ["b"]},
                {"node_id": "b", "goal": "B", "depends_on": ["a"]},
            ],
        }
    )

    assert "error" in result
    assert "cycle detected" in result["error"]


def test_dispatch_ready_uses_delegate_task_background(monkeypatch):
    calls = []

    def fake_delegate_task(**kwargs):
        calls.append(kwargs)
        return json.dumps(
            {
                "status": "dispatched",
                "delegation_id": f"deleg_{len(calls)}",
                "subagent_id": f"sa_{len(calls)}",
                "child_session_id": f"sess_{len(calls)}",
            }
        )

    from tools import delegate_tool

    monkeypatch.setattr(delegate_tool, "delegate_task", fake_delegate_task)
    parent = object()

    result = _call(
        {
            "action": "create",
            "workflow_id": "wf_dispatch",
            "objective": "Parallel source review",
            "context": "Use public docs only.",
            "dispatch_ready": True,
            "nodes": [
                {
                    "node_id": "web",
                    "phase_id": "investigate",
                    "phase_title": "Investigate",
                    "title": "Web source review",
                    "goal": "Search web sources",
                    "toolsets": ["web"],
                },
                {
                    "node_id": "files",
                    "phase_id": "investigate",
                    "phase_title": "Investigate",
                    "title": "Local note review",
                    "goal": "Inspect local notes",
                    "toolsets": ["file"],
                },
            ],
        },
        parent_agent=parent,
    )

    assert result["dispatched"] == [
        {
            "node_id": "web",
            "delegation_id": "deleg_1",
            "subagent_id": "sa_1",
            "child_session_id": "sess_1",
        },
        {
            "node_id": "files",
            "delegation_id": "deleg_2",
            "subagent_id": "sa_2",
            "child_session_id": "sess_2",
        },
    ]
    assert [call["background"] for call in calls] == [True, True]
    assert [call["parent_agent"] for call in calls] == [parent, parent]
    assert "workflow_id: wf_dispatch" in calls[0]["context"]
    assert "node_id: web" in calls[0]["context"]
    assert "phase: Investigate" in calls[0]["context"]
    assert "task_title: Web source review" in calls[0]["context"]
    assert calls[0]["toolsets"] == ["web"]
    assert calls[0]["_observability_context"] == {
        "workflow_id": "wf_dispatch",
        "workflow_node_id": "web",
        "workflow_phase_id": "investigate",
        "workflow_phase_title": "Investigate",
        "workflow_task_title": "Web source review",
        "workflow_objective": "Parallel source review",
        "task_prompt": "Search web sources",
        "task_context": "",
    }
    assert result["workflow"]["nodes"][0]["status"] == "dispatched"
    assert result["workflow"]["nodes"][0]["subagent_id"] == "sa_1"


def test_record_result_then_model_can_extend_graph_with_dependent_node():
    _call(
        {
            "action": "create",
            "workflow_id": "wf_extend",
            "objective": "Reassess after source triage",
            "nodes": [{"node_id": "source_triage", "goal": "Find source gaps"}],
        }
    )

    recorded = _call(
        {
            "action": "record_result",
            "workflow_id": "wf_extend",
            "node_id": "source_triage",
            "status": "completed",
            "summary": "Missing pricing source; add a targeted search.",
            "result": {"missing": ["pricing"]},
        }
    )
    assert recorded["workflow"]["status"] == "completed"

    extended = _call(
        {
            "action": "add_nodes",
            "workflow_id": "wf_extend",
            "nodes": [
                {
                    "node_id": "pricing_gap",
                    "goal": "Search only for pricing evidence",
                    "depends_on": ["source_triage"],
                }
            ],
        }
    )

    assert extended["workflow"]["status"] == "ready"
    assert extended["workflow"]["ready_node_ids"] == ["pricing_gap"]
    assert [node["node_id"] for node in extended["workflow"]["nodes"]] == [
        "source_triage",
        "pricing_gap",
    ]


def test_cancel_interrupts_dispatched_workflow_children(monkeypatch):
    def fake_delegate_task(**kwargs):
        return json.dumps({"status": "dispatched", "delegation_id": "deleg_a"})

    interrupted = []

    def fake_interrupt(delegation_id, reason="cancelled"):
        interrupted.append((delegation_id, reason))
        return True

    from tools import delegate_tool
    import tools.async_delegation as ad

    monkeypatch.setattr(delegate_tool, "delegate_task", fake_delegate_task)
    monkeypatch.setattr(ad, "interrupt_delegation", fake_interrupt)

    _call(
        {
            "action": "create",
            "workflow_id": "wf_cancel",
            "objective": "Cancelable",
            "dispatch_ready": True,
            "nodes": [{"node_id": "worker", "goal": "Do work"}],
        },
        parent_agent=object(),
    )

    cancelled = _call(
        {"action": "cancel", "workflow_id": "wf_cancel", "interrupt": True}
    )

    assert cancelled["interrupted_delegation_ids"] == ["deleg_a"]
    assert interrupted == [("deleg_a", "dynamic_workflow cancelled")]
    node = cancelled["workflow"]["nodes"][0]
    assert node["status"] == "dispatched"
    assert node["cancel_requested"] is True
