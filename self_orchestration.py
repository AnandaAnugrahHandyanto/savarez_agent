#!/usr/bin/env python3
"""
Self-Orchestration for Hermes Agent Pipeline.

Hermes routes itself. This module provides:
- Stage determination
- Role contract application
- Artifact collection
- Transition validation
- Self-advancement

No external orchestrator needed. Hermes checks itself, advances itself.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from pipeline_state import (
    PipelineStateDB,
    STAGE_TRANSITIONS,
    create_blocker_packet,
    create_completion_packet,
    create_escalation_packet,
)
from role_loader import RoleLoader, RoleContract
from transition_checker import TransitionChecker, TransitionError, MissingArtifactError

logger = logging.getLogger(__name__)


class SelfOrchestrator:
    """
    Self-orchestration for Hermes work items.
    
    Hermes determines its own stage, applies role contracts,
    collects artifacts, and advances itself through the pipeline.
    
    No external routing. Self-contained state machine.
    """
    
    def __init__(
        self,
        state_db: PipelineStateDB = None,
        role_loader: RoleLoader = None,
        checker: TransitionChecker = None
    ):
        self.state_db = state_db or PipelineStateDB()
        self.role_loader = role_loader or RoleLoader()
        self.checker = checker or TransitionChecker(self.state_db, self.role_loader)
    
    # =========================================================================
    # Stage Determination
    # =========================================================================
    
    def get_current_stage(self, work_item_id: str) -> Optional[str]:
        """Get the current stage for a work item."""
        work_item = self.state_db.get_work_item(work_item_id)
        if work_item is None:
            return None
        return work_item["current_stage"]
    
    def get_next_stage(self, work_item_id: str) -> Optional[str]:
        """Get the next stage for a work item."""
        current = self.get_current_stage(work_item_id)
        if current is None:
            return None
        transition = STAGE_TRANSITIONS.get(current)
        return transition.get("next") if transition else None
    
    def get_stage_info(self, work_item_id: str) -> Dict[str, Any]:
        """Get full stage information for a work item."""
        work_item = self.state_db.get_work_item(work_item_id)
        if work_item is None:
            return {"error": "Work item not found"}
        
        current_stage = work_item["current_stage"]
        transition = STAGE_TRANSITIONS.get(current_stage, {})
        
        # Get collected artifacts
        artifacts = self.state_db.get_all_artifacts(work_item_id)
        
        # Get packet history
        packets = self.state_db.get_packet_history(work_item_id)
        
        return {
            "work_item_id": work_item_id,
            "title": work_item.get("title"),
            "github_issue_url": work_item.get("github_issue_url"),
            "github_issue_number": work_item.get("github_issue_number"),
            "current_stage": current_stage,
            "stage_entered_at": work_item.get("stage_entered_at"),
            "next_stage": transition.get("next"),
            "required_artifacts": transition.get("required_artifacts", []),
            "uncertainty_removed": transition.get("uncertainty_removed"),
            "collected_artifacts": list(artifacts.keys()),
            "packet_count": len(packets),
        }
    
    # =========================================================================
    # Role Contract Application
    # =========================================================================
    
    def get_role_contract(self, stage: str) -> Optional[RoleContract]:
        """Get the role contract for a stage."""
        # Map stages to role files
        stage_to_role = {
            "research-verify": "research-verifier",
            "plan-review": "plan-reviewer",
            "scope-steward": "scope-steward",
            "architecture-verify": "architecture-verifier",
            "integration-steward": "integration-steward",
            "repo-steward": "repo-steward",
            "issue-approve": "issue-maintainer",
            "branch-create": "branch-steward",
            "delivery-manager": "delivery-manager",
            "spec-design": "spec-designer",
            "spec-verify": "spec-verifier",
            "pr-create": "pr-creation-agent",
            "red-test": "red-test-builder",
            "code-build": "code-builder",
            "cleanup": "cleanup-agent",
            "green-test": "green-test-builder",
            "tdd-refactor": "tdd-refactor-agent",
            "review-improve": "reviewer-improve-agent",
            "pr-maintain": "pr-maintainer",
            "wisdom": "wisdom-agent",
            "merge": "merger-agent",
        }
        
        role_name = stage_to_role.get(stage)
        if role_name is None:
            return None
        
        return self.role_loader.load_role(role_name)
    
    def apply_role_contract(self, work_item_id: str) -> Dict[str, Any]:
        """Apply the current role contract to understand what's needed."""
        current_stage = self.get_current_stage(work_item_id)
        if current_stage is None:
            return {"error": "Cannot determine current stage"}
        
        role_contract = self.get_role_contract(current_stage)
        transition = STAGE_TRANSITIONS.get(current_stage, {})
        
        # Get missing artifacts
        required = transition.get("required_artifacts", [])
        has_all, missing = self.state_db.has_artifacts(work_item_id, required)
        
        return {
            "stage": current_stage,
            "role_contract": role_contract.__dict__ if role_contract else None,
            "required_artifacts": required,
            "has_all_artifacts": has_all,
            "missing_artifacts": missing,
            "uncertainty_to_remove": transition.get("uncertainty_removed"),
            "can_advance": has_all,
            "next_stage": transition.get("next"),
        }
    
    # =========================================================================
    # Artifact Collection
    # =========================================================================
    
    def store_artifact(
        self,
        work_item_id: str,
        artifact_type: str,
        artifact_data: Dict[str, Any]
    ) -> int:
        """Store an artifact for a work item."""
        return self.state_db.store_artifact(work_item_id, artifact_type, artifact_data)
    
    def store_github_issue(
        self,
        work_item_id: str,
        issue_url: str,
        issue_number: int
    ) -> bool:
        """Link a work item to a GitHub issue."""
        return self.state_db.link_github_issue(work_item_id, issue_url, issue_number)
    
    def store_branch_artifact(
        self,
        work_item_id: str,
        branch_name: str,
        head_sha: str,
        workspace_path: str = None
    ) -> Tuple[int, int]:
        """Store branch creation artifacts."""
        branch_id = self.state_db.store_artifact(
            work_item_id,
            "branch_name",
            {"value": branch_name}
        )
        sha_id = self.state_db.store_artifact(
            work_item_id,
            "head_sha",
            {"value": head_sha, "workspace": workspace_path}
        )
        return branch_id, sha_id
    
    def store_pr_artifact(
        self,
        work_item_id: str,
        pr_url: str,
        pr_number: int,
        draft: bool = False
    ) -> int:
        """Store PR creation artifact."""
        return self.state_db.store_artifact(
            work_item_id,
            "pr_url",
            {
                "value": pr_url,
                "pr_number": pr_number,
                "draft": draft,
            }
        )
    
    def store_merge_artifact(
        self,
        work_item_id: str,
        merge_sha: str,
        merged_at: str
    ) -> int:
        """Store merge completion artifact."""
        return self.state_db.store_artifact(
            work_item_id,
            "merge_sha",
            {
                "value": merge_sha,
                "merged_at": merged_at,
            }
        )
    
    # =========================================================================
    # Packet Emission
    # =========================================================================
    
    def emit_blocker(
        self,
        work_item_id: str,
        agent_id: str,
        error_class: str,
        exact_command: str,
        env_snapshot: Dict[str, Any],
        resolution_hint: str,
        context: str = None,
    ) -> int:
        """Emit a blocker packet when cannot proceed."""
        packet = create_blocker_packet(
            agent_id=agent_id,
            stage=self.get_current_stage(work_item_id),
            error_class=error_class,
            exact_command=exact_command,
            env_snapshot=env_snapshot,
            resolution_hint=resolution_hint,
            context=context,
        )
        return self.state_db.emit_packet(work_item_id, "blocker", packet)
    
    def emit_completion(
        self,
        work_item_id: str,
        agent_id: str,
        summary: str,
        evidence_bundle: Dict[str, Any] = None,
        lessons_learned: List[str] = None,
    ) -> int:
        """Emit a completion packet when stage is done."""
        work_item = self.state_db.get_work_item(work_item_id)
        packet = create_completion_packet(
            agent_id=agent_id,
            stage=work_item["current_stage"] if work_item else "unknown",
            issue_url=work_item.get("github_issue_url") if work_item else None,
            summary=summary,
            evidence_bundle=evidence_bundle,
            lessons_learned=lessons_learned,
            next_stage=self.get_next_stage(work_item_id),
        )
        return self.state_db.emit_packet(work_item_id, "completion", packet)
    
    def emit_escalation(
        self,
        work_item_id: str,
        agent_id: str,
        blocker_type: str,
        exact_block: str,
        attempted_solutions: List[str],
        recommended_path: str,
        context: str = None,
        steven_requested: bool = False,
    ) -> int:
        """
        Emit an escalation packet.
        
        ESCALATION IS RARE. Use only when:
        - Steven explicitly asked to be involved
        - Literally cannot proceed (external authorization, permission, access)
        - Something genuinely broken (service down, credential invalid)
        
        For everything else - reason through it yourself.
        """
        work_item = self.state_db.get_work_item(work_item_id)
        packet = create_escalation_packet(
            agent_id=agent_id,
            stage=work_item["current_stage"] if work_item else "unknown",
            context=context or f"Work item: {work_item_id}",
            blocker_type=blocker_type,
            exact_block=exact_block,
            attempted_solutions=attempted_solutions,
            recommended_path=recommended_path,
            steven_requested=steven_requested,
        )
        return self.state_db.emit_packet(work_item_id, "escalation", packet)
    
    # =========================================================================
    # Self-Advancement
    # =========================================================================
    
    def can_advance(self, work_item_id: str) -> Tuple[bool, str, Dict[str, Any]]:
        """Check if this work item can advance to the next stage."""
        return self.checker.check_transition(work_item_id)
    
    def advance(
        self,
        work_item_id: str,
        notes: str = None
    ) -> Tuple[bool, str]:
        """
        Attempt to advance to the next stage.
        
        Returns:
            (success, message)
        """
        # Can we advance?
        can_advance, reason, details = self.can_advance(work_item_id)
        if not can_advance:
            return False, f"Cannot advance: {reason}"
        
        # Advance
        success, message = self.state_db.advance(work_item_id, notes=notes)
        return success, message
    
    def advance_with_artifact(
        self,
        work_item_id: str,
        artifact_type: str,
        artifact_data: Dict[str, Any],
        notes: str = None,
    ) -> Tuple[bool, str]:
        """
        Store an artifact and attempt to advance.
        
        This is the common pattern: produce artifact, check if ready, advance.
        """
        # Store the artifact
        self.store_artifact(work_item_id, artifact_type, artifact_data)
        
        # Try to advance
        return self.advance(work_item_id, notes=notes)
    
    # =========================================================================
    # Delegation Helper
    # =========================================================================
    
    def get_delegation_context(
        self,
        work_item_id: str,
        goal: str = None
    ) -> Dict[str, Any]:
        """
        Get the context needed to delegate a stage to a subagent.
        
        Use this when spawning a subagent for a specific stage.
        Returns role contract, current state, artifacts, and goal.
        """
        stage_info = self.get_stage_info(work_item_id)
        role_contract = self.get_role_contract(stage_info["current_stage"])
        artifacts = self.state_db.get_all_artifacts(work_item_id)
        
        return {
            "work_item_id": work_item_id,
            "stage": stage_info["current_stage"],
            "goal": goal,
            "role_contract": role_contract.__dict__ if role_contract else None,
            "required_artifacts": stage_info.get("required_artifacts", []),
            "collected_artifacts": artifacts,
            "uncertainty_to_remove": stage_info.get("uncertainty_removed"),
            "github_issue_url": stage_info.get("github_issue_url"),
            "github_issue_number": stage_info.get("github_issue_number"),
            "next_stage": stage_info.get("next_stage"),
        }


# Singleton instance
_orchestrator: Optional[SelfOrchestrator] = None


def get_orchestrator() -> SelfOrchestrator:
    """Get the singleton orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SelfOrchestrator()
    return _orchestrator


# Convenience functions

def current_stage(work_item_id: str) -> Optional[str]:
    """Get the current stage for a work item."""
    return get_orchestrator().get_current_stage(work_item_id)


def can_advance(work_item_id: str) -> Tuple[bool, str]:
    """Check if a work item can advance."""
    can, reason, _ = get_orchestrator().can_advance(work_item_id)
    return can, reason


def advance(work_item_id: str, notes: str = None) -> Tuple[bool, str]:
    """Advance a work item to the next stage."""
    return get_orchestrator().advance(work_item_id, notes=notes)


def status(work_item_id: str) -> str:
    """Get a human-readable status for a work item."""
    return get_orchestrator().checker.describe_transition(work_item_id)