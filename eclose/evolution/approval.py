from enum import Enum
from eclose.evolution.proposal import EvolutionProposal


class ApprovalDecision(Enum):
    APPROVE = "approve"
    REJECT = "reject"
    DEFER = "defer"
    APPROVE_WITH_CHANGES = "approve_with_changes"


class ApprovalWorkflow:
    """Handles human approval for evolution proposals."""

    def __init__(self):
        self.pending_proposals: list[EvolutionProposal] = []
        self.approved_proposals: list[EvolutionProposal] = []
        self.rejected_proposals: list[EvolutionProposal] = []

    def submit_for_approval(self, proposal: EvolutionProposal):
        """Submit a proposal for human approval."""
        if proposal.requires_approval:
            self.pending_proposals.append(proposal)

    def approve(self, proposal_id: str) -> bool:
        """Approve a proposal."""
        for proposal in self.pending_proposals:
            if proposal.id == proposal_id:
                self.pending_proposals.remove(proposal)
                self.approved_proposals.append(proposal)
                return True
        return False

    def reject(self, proposal_id: str, reason: str = None):
        """Reject a proposal."""
        for proposal in self.pending_proposals:
            if proposal.id == proposal_id:
                proposal.metadata["rejection_reason"] = reason
                self.pending_proposals.remove(proposal)
                self.rejected_proposals.append(proposal)
                return True
        return False

    def get_pending(self) -> list[EvolutionProposal]:
        """Get all pending proposals."""
        return self.pending_proposals.copy()