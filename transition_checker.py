#!/usr/bin/env python3
"""
Transition Checker for Hermes Agent Pipeline.

Validates that required artifacts exist before allowing stage transitions.
This is the enforcement layer - Hermes checks itself, not external routing.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any

from pipeline_state import PipelineStateDB, STAGE_TRANSITIONS
from role_loader import RoleLoader, RoleContract

logger = logging.getLogger(__name__)


class TransitionChecker:
    """Validate stage transitions based on required artifacts."""
    
    def __init__(self, state_db: PipelineStateDB, role_loader: RoleLoader):
        self.state_db = state_db
        self.role_loader = role_loader
    
    def check_transition(
        self,
        work_item_id: str,
        target_stage: str = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Check if a work item can transition to the target stage.
        
        Returns:
            (can_transition, reason, details)
            - can_transition: True if transition is allowed
            - reason: Human-readable explanation
            - details: Structured details for logging/debugging
        """
        # Get current work item state
        work_item = self.state_db.get_work_item(work_item_id)
        if work_item is None:
            return False, "Work item not found", {"error": "work_item_not_found"}
        
        current_stage = work_item["current_stage"]
        
        # Get transition definition
        transition = STAGE_TRANSITIONS.get(current_stage)
        if transition is None:
            return False, f"Unknown current stage: {current_stage}", {
                "error": "unknown_stage",
                "stage": current_stage
            }
        
        # Determine target stage
        next_stage = target_stage or transition.get("next")
        if next_stage is None:
            return False, "No next stage (terminal)", {
                "error": "terminal_stage",
                "stage": current_stage
            }
        
        # Validate next stage exists
        if next_stage not in STAGE_TRANSITIONS and next_stage != "complete":
            return False, f"Unknown target stage: {next_stage}", {
                "error": "invalid_target",
                "target": next_stage
            }
        
        # Check required artifacts
        required_artifacts = transition.get("required_artifacts", [])
        has_all, missing = self.state_db.has_artifacts(work_item_id, required_artifacts)
        
        if not has_all:
            return False, f"Missing artifacts: {missing}", {
                "error": "missing_artifacts",
                "required": required_artifacts,
                "missing": missing,
                "current_stage": current_stage,
                "target_stage": next_stage,
            }
        
        # Check stage-specific requirements
        stage_specific_check = self._check_stage_specific(work_item_id, current_stage, next_stage)
        if not stage_specific_check[0]:
            return stage_specific_check
        
        # All checks passed
        return True, f"Can transition from {current_stage} to {next_stage}", {
            "current_stage": current_stage,
            "target_stage": next_stage,
            "artifacts_present": required_artifacts,
        }
    
    def _check_stage_specific(
        self,
        work_item_id: str,
        current_stage: str,
        next_stage: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Check stage-specific requirements."""
        
        # GitHub issue required after issue-approve
        if current_stage == "issue-approve":
            work_item = self.state_db.get_work_item(work_item_id)
            if work_item and not work_item.get("github_issue_url"):
                return False, "GitHub issue URL required for issue approval", {
                    "error": "missing_github_issue",
                    "stage": current_stage,
                }
        
        # Branch name required after branch-create
        if current_stage == "branch-create":
            branch_artifact = self.state_db.get_artifact(work_item_id, "branch_name")
            if not branch_artifact:
                return False, "Branch name artifact required for branch creation", {
                    "error": "missing_branch_name",
                    "stage": current_stage,
                }
        
        # HEAD SHA required after branch-create
        if current_stage == "branch-create":
            sha_artifact = self.state_db.get_artifact(work_item_id, "head_sha")
            if not sha_artifact:
                return False, "HEAD SHA artifact required for branch creation", {
                    "error": "missing_head_sha",
                    "stage": current_stage,
                }
        
        # Merge SHA required for completion
        if next_stage == "complete":
            merge_artifact = self.state_db.get_artifact(work_item_id, "merge_sha")
            if not merge_artifact:
                return False, "Merge SHA artifact required for completion", {
                    "error": "missing_merge_sha",
                    "stage": current_stage,
                }
        
        return True, "Stage-specific checks passed", {}
    
    def validate_artifact(
        self,
        work_item_id: str,
        artifact_type: str,
        artifact_data: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Validate an artifact against its expected schema.
        
        Returns:
            (is_valid, missing_fields)
        """
        # Map artifact types to packet schemas
        artifact_to_schema = {
            "verification_packet": "blocker",  # Could be completion too
            "review_packet": "completion",
            "branch_name": None,  # Simple string
            "head_sha": None,
            "pr_url": None,
            "merge_sha": None,
        }
        
        # For simple string artifacts
        if artifact_type in ("branch_name", "head_sha", "pr_url", "merge_sha"):
            if not artifact_data:
                return False, ["value"]
            if not isinstance(artifact_data.get("value"), str):
                return False, ["value"]
            return True, []
        
        # For complex artifacts, validate against schema
        schema_name = artifact_to_schema.get(artifact_type)
        if schema_name:
            return self.role_loader.validate_packet(schema_name, artifact_data)
        
        # Default: artifact exists is sufficient
        return True, []
    
    def get_next_stage(self, work_item_id: str) -> Optional[str]:
        """Get the next stage for a work item."""
        work_item = self.state_db.get_work_item(work_item_id)
        if work_item is None:
            return None
        
        current_stage = work_item["current_stage"]
        transition = STAGE_TRANSITIONS.get(current_stage)
        
        if transition is None:
            return None
        
        return transition.get("next")
    
    def get_required_artifacts(self, work_item_id: str) -> List[str]:
        """Get the required artifacts for the next transition."""
        work_item = self.state_db.get_work_item(work_item_id)
        if work_item is None:
            return []
        
        current_stage = work_item["current_stage"]
        transition = STAGE_TRANSITIONS.get(current_stage)
        
        if transition is None:
            return []
        
        return transition.get("required_artifacts", [])
    
    def get_missing_artifacts(self, work_item_id: str) -> List[str]:
        """Get the artifacts missing for the next transition."""
        required = self.get_required_artifacts(work_item_id)
        has_all, missing = self.state_db.has_artifacts(work_item_id, required)
        return missing
    
    def describe_transition(self, work_item_id: str) -> str:
        """Describe the current state and next steps for a work item."""
        work_item = self.state_db.get_work_item(work_item_id)
        if work_item is None:
            return f"Work item {work_item_id} not found"
        
        current_stage = work_item["current_stage"]
        transition = STAGE_TRANSITIONS.get(current_stage)
        
        if transition is None:
            return f"Work item is at stage '{current_stage}' (unknown stage)"
        
        next_stage = transition.get("next")
        required = transition.get("required_artifacts", [])
        uncertainty = transition.get("uncertainty_removed", "")
        
        has_all, missing = self.state_db.has_artifacts(work_item_id, required)
        
        parts = [
            f"Current stage: {current_stage}",
        ]
        
        if uncertainty:
            parts.append(f"Uncertainty to remove: {uncertainty}")
        
        if next_stage:
            parts.append(f"Next stage: {next_stage}")
        
        if required:
            if has_all:
                parts.append(f"Required artifacts: {required} (all present)")
            else:
                parts.append(f"Required artifacts: {required}")
                parts.append(f"Missing: {missing}")
        
        if has_all and next_stage:
            parts.append("Ready to advance")
        elif missing:
            parts.append(f"Need to produce: {missing}")
        
        return "\n".join(parts)


class TransitionError(Exception):
    """Raised when a stage transition cannot proceed."""
    
    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(message)
        self.details = details or {}
    
    def __str__(self):
        base = super().__str__()
        if self.details:
            return f"{base} (details: {self.details})"
        return base


class MissingArtifactError(TransitionError):
    """Raised when required artifacts are missing."""
    
    def __init__(self, missing: List[str], stage: str):
        super().__init__(
            f"Missing artifacts for stage '{stage}': {missing}",
            {"missing": missing, "stage": stage}
        )
        self.missing = missing
        self.stage = stage


class InvalidTransitionError(TransitionError):
    """Raised when attempting an invalid stage transition."""
    
    def __init__(self, from_stage: str, to_stage: str, reason: str):
        super().__init__(
            f"Cannot transition from '{from_stage}' to '{to_stage}': {reason}",
            {"from": from_stage, "to": to_stage, "reason": reason}
        )
        self.from_stage = from_stage
        self.to_stage = to_stage


# Convenience functions

def check_stage(
    work_item_id: str,
    state_db: PipelineStateDB = None,
    role_loader: RoleLoader = None
) -> Tuple[bool, str, Dict[str, Any]]:
    """Check if a work item can advance to the next stage.
    
    Convenience function that creates necessary instances if not provided.
    """
    if state_db is None:
        from pipeline_state import PipelineStateDB
        state_db = PipelineStateDB()
    
    if role_loader is None:
        role_loader = RoleLoader()
    
    checker = TransitionChecker(state_db, role_loader)
    return checker.check_transition(work_item_id)


def get_status(
    work_item_id: str,
    state_db: PipelineStateDB = None,
    role_loader: RoleLoader = None
) -> str:
    """Get a human-readable status for a work item."""
    if state_db is None:
        from pipeline_state import PipelineStateDB
        state_db = PipelineStateDB()
    
    if role_loader is None:
        role_loader = RoleLoader()
    
    checker = TransitionChecker(state_db, role_loader)
    return checker.describe_transition(work_item_id)