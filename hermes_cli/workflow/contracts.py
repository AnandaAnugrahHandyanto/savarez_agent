"""Canonical workflow API contract fixtures shared with WebUI tests.

These static fixtures pin the browser-facing JSON shape for the workflow
control surface. Core owns the field names; WebUI should consume these shapes
instead of inferring workflow state from prose or Kanban task bodies.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

WORKFLOW_API_CONTRACT_VERSION = "workflow-api-v1"

_WORKFLOW = {
    "id": "wf_contract",
    "title": "Workflow Contract Fixture",
    "description": "Canonical workflow API shape for Core/WebUI contract tests.",
    "workspacePath": "/tmp/workflow-contract",
    "board": "workflow-system",
    "scale": "large",
    "status": "running",
    "currentGate": "gate_contract_review",
    "policyPath": ".hermes/workflow.yaml",
    "policySnapshot": {"version": 1},
    "createdAt": 1.0,
    "updatedAt": 2.0,
    "createdBy": "hermes-agent",
    "metadata": {"contractVersion": WORKFLOW_API_CONTRACT_VERSION},
}

_NODES = [
    {
        "id": "shape-plan",
        "title": "Shape implementation plan",
        "role": "planner",
        "profile": "planner",
        "status": "done",
        "parents": [],
        "children": ["build-slice"],
        "gateLevel": 1,
        "gateType": None,
        "kanbanTaskId": "task_shape_plan",
        "workspace": {
            "kind": "worktree",
            "branch": "workflow/wf_contract/shape-plan",
            "worktreePath": "/tmp/worktrees/wf_contract-shape-plan",
            "baseRef": "origin/main",
        },
        "definitionOfDone": ["Plan reviewed."],
        "scope": {"summary": "Turn the request into a concrete workflow plan."},
        "evidence": {"tests": ["contract"]},
        "metadata": {"contractNode": True},
        "createdAt": 1.0,
        "updatedAt": 2.0,
    },
    {
        "id": "build-slice",
        "title": "Build first slice",
        "role": "engineer",
        "profile": "engineer",
        "status": "running",
        "parents": ["shape-plan"],
        "children": [],
        "gateLevel": 2,
        "gateType": "review",
        "kanbanTaskId": "task_build_slice",
        "workspace": {"kind": "scratch", "branch": None, "worktreePath": None, "baseRef": None},
        "definitionOfDone": ["Targeted tests pass."],
        "scope": {"summary": "Implement the first independently useful workflow slice."},
        "evidence": {},
        "metadata": {},
        "createdAt": 1.0,
        "updatedAt": 2.0,
    },
]

_EDGES = [{"source": "shape-plan", "target": "build-slice", "kind": "depends_on"}]

_GATE = {
    "id": "gate_contract_review",
    "workflowId": "wf_contract",
    "nodeId": "build-slice",
    "gateType": "review",
    "level": 2,
    "status": "pending",
    "verdict": None,
    "requiredActor": "reviewer",
    "resolvedBy": None,
    "resolvedAt": None,
    "artifactId": "art_contract_handoff",
    "reason": "Contract fixture gate awaiting review.",
    "metadata": {"contractGate": True},
}

_ARTIFACT = {
    "id": "art_contract_handoff",
    "workflowId": "wf_contract",
    "kind": "handoff",
    "path": "/tmp/workflow-contract/handoff.md",
    "sha256": "0" * 64,
    "mimeType": "text/markdown",
    "schemaVersion": 1,
    "status": "active",
    "createdAt": 2.0,
    "createdBy": "hermes-agent",
    "metadata": {"contractArtifact": True},
}

_EVENT = {
    "id": "evt_contract_seeded",
    "workflowId": "wf_contract",
    "nodeId": "shape-plan",
    "eventType": "workflow_contract_seeded",
    "actorType": "system",
    "actorId": "workflow-contract",
    "message": "Seeded workflow API contract fixture.",
    "data": {"contractVersion": WORKFLOW_API_CONTRACT_VERSION},
    "createdAt": 3.0,
}

_CONTROL_ACTION = {
    "id": "approve-gate:gate_contract_review",
    "type": "resolve_gate",
    "label": "Approve review gate",
    "method": "POST",
    "endpoint": "/api/workflows/wf_contract/gates/gate_contract_review/resolve",
    "gateId": "gate_contract_review",
    "status": "approved",
    "verdict": "approved",
    "enabled": True,
}

_INBOX_ITEM = {
    "id": "inbox_contract",
    "title": "Contract inbox item",
    "body": "Shape this inbox item into a workflow.",
    "source": "webui_chat",
    "status": "triaged",
    "classification": "decomposition_worthy",
    "workspacePath": "/tmp/workflow-contract",
    "assignedWorkflowId": None,
    "createdAt": 1.0,
    "updatedAt": 1.0,
    "createdBy": "webui",
    "metadata": {"contractVersion": WORKFLOW_API_CONTRACT_VERSION},
}

_DRAFT_DAG = {
    "schema_version": 1,
    "workflow_id": "wf_contract",
    "name": "Workflow Contract Fixture",
    "scale": "large",
    "nodes": [
        {"id": "shape-plan", "title": "Shape implementation plan", "role": "planner", "profile": "planner", "scope": {"summary": "Shape the contract request."}},
        {"id": "build-slice", "title": "Build first slice", "role": "engineer", "profile": "engineer", "parents": ["shape-plan"], "definition_of_done": ["Targeted tests pass."], "scope": {"summary": "Build the contract request."}},
    ],
    "edges": _EDGES,
}


def _response(facts: dict[str, Any]) -> dict[str, Any]:
    return {"facts": facts, "insights": None}


def workflow_api_contract_fixture() -> dict[str, Any]:
    """Return the canonical workflow API fixture for cross-repo tests."""

    fixture = {
        "contractVersion": WORKFLOW_API_CONTRACT_VERSION,
        "envelope": {"facts": {}, "insights": None},
        "fixtures": {
            "workflowList": _response({"workflows": [_WORKFLOW], "count": 1}),
            "workflowDag": _response({"workflow": _WORKFLOW, "nodes": _NODES, "edges": _EDGES, "gates": [_GATE], "artifacts": [_ARTIFACT], "controlActions": [_CONTROL_ACTION]}),
            "workflowNode": _response({"workflowId": "wf_contract", "node": _NODES[1], "gates": [_GATE], "events": [_EVENT], "artifacts": [_ARTIFACT]}),
            "workflowEvents": _response({"workflowId": "wf_contract", "events": [_EVENT], "count": 1}),
            "workflowArtifacts": _response({"workflowId": "wf_contract", "artifacts": [_ARTIFACT], "count": 1}),
            "inboxList": _response({"inboxItems": [_INBOX_ITEM], "count": 1}),
            "inboxItem": _response({"inboxItem": _INBOX_ITEM}),
            "inboxShape": _response({"inboxItem": _INBOX_ITEM, "draftWorkflow": {"id": "wf_contract", "title": "Workflow Contract Fixture", "description": _INBOX_ITEM["body"], "workspacePath": "/tmp/workflow-contract", "board": "workflow-system", "scale": "large", "sourceInboxItemId": "inbox_contract"}, "draftDag": _DRAFT_DAG}),
            "inboxPromote": _response({"workflow": {**_WORKFLOW, "status": "dag_draft"}, "inboxItem": {**_INBOX_ITEM, "status": "promoted", "assignedWorkflowId": "wf_contract"}, "dag": _DRAFT_DAG}),
        },
    }
    return deepcopy(fixture)
