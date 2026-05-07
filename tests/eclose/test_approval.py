import pytest
from eclose.evolution.approval import ApprovalWorkflow, ApprovalDecision

def test_approval_workflow_initialization():
    workflow = ApprovalWorkflow()
    assert workflow.pending_proposals == []

def test_submit_proposal_for_approval():
    workflow = ApprovalWorkflow()
    proposal = {"id": "test-1", "title": "Test Proposal"}
    workflow.pending_proposals.append(proposal)
    assert len(workflow.pending_proposals) == 1