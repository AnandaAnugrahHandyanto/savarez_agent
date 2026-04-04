#!/usr/bin/env python3
"""
Role Loader for Hermes Agent Pipeline.

Loads role contracts from the hearth-hermes-coord repository.
Role contracts define:
- Required inputs/outputs
- Stage transitions
- Handoff patterns
- Decision trees

Roles are self-applied constraints - Hermes follows them without external routing.
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

logger = logging.getLogger(__name__)

# Default coordination repo location
DEFAULT_COORD_REPO = Path.home() / "repos" / "hearth-hermes-coord"


class RoleContract:
    """Parsed role contract from a role definition file."""
    
    def __init__(self, role_name: str, raw_content: str):
        self.role_name = role_name
        self.raw_content = raw_content
        
        # Parsed sections
        self.position: str = ""
        self.uncertainty_removed: str = ""
        self.required_inputs: Dict[str, Any] = {}
        self.required_outputs: Dict[str, Any] = {}
        self.can_receive_from: List[str] = []
        self.can_advance_to: List[str] = []
        self.can_bounce_to: List[str] = []
        self.cannot_proceed_without: List[str] = []
        self.handoff_pattern: List[str] = []
        self.decision_tree: List[Dict[str, str]] = []
        self.communication_protocol: Dict[str, str] = {}
        self.metrics: List[str] = []
    
    def __repr__(self):
        return f"<RoleContract: {self.role_name}>"


class RoleLoader:
    """Load role contracts from the coordination repository."""
    
    def __init__(self, coord_repo_path: Path = None):
        self.coord_repo_path = coord_repo_path or self._find_coord_repo()
        self.roles_dir = self.coord_repo_path / "roles" if self.coord_repo_path else None
        self.schemas_dir = self.coord_repo_path / "packets" / "schemas" if self.coord_repo_path else None
        self._cache: Dict[str, RoleContract] = {}
    
    def _find_coord_repo(self) -> Optional[Path]:
        """Find the coordination repository."""
        # Check environment variable first
        env_path = os.environ.get("HEARTH_HERMES_COORD_PATH")
        if env_path:
            path = Path(env_path)
            if path.exists():
                return path
        
        # Check default location
        if DEFAULT_COORD_REPO.exists():
            return DEFAULT_COORD_REPO
        
        # Check for HERMES_HOME/profiles/*/coord symlink
        hermes_home = Path.home() / ".hermes"
        if hermes_home.exists():
            for profile_dir in (hermes_home / "profiles").iterdir():
                if profile_dir.is_dir():
                    coord_link = profile_dir / "coord"
                    if coord_link.exists():
                        return coord_link
        
        logger.warning("Could not find coordination repo")
        return None
    
    def list_roles(self) -> List[str]:
        """List available role contracts."""
        if self.roles_dir is None or not self.roles_dir.exists():
            return []
        
        roles = []
        for role_file in self.roles_dir.glob("*.md"):
            if role_file.name != "README.md":
                roles.append(role_file.stem)
        
        return sorted(roles)
    
    def load_role(self, role_name: str) -> Optional[RoleContract]:
        """Load a role contract by name."""
        if role_name in self._cache:
            return self._cache[role_name]
        
        if self.roles_dir is None:
            logger.error("Roles directory not found")
            return None
        
        role_file = self.roles_dir / f"{role_name}.md"
        if not role_file.exists():
            logger.error(f"Role file not found: {role_file}")
            return None
        
        try:
            content = role_file.read_text()
            contract = self._parse_role(role_name, content)
            self._cache[role_name] = contract
            return contract
        except Exception as e:
            logger.error(f"Failed to load role {role_name}: {e}")
            return None
    
    def _parse_role(self, role_name: str, content: str) -> RoleContract:
        """Parse a role definition file."""
        contract = RoleContract(role_name, content)
        
        # Parse sections using markdown headers
        sections = self._split_sections(content)
        
        # Extract position
        if "Position" in sections:
            contract.position = sections["Position"].strip()
        
        # Extract uncertainty removed
        if "Uncertainty Removed" in sections:
            contract.uncertainty_removed = sections["Uncertainty Removed"].strip()
        
        # Extract required inputs
        if "Required Inputs" in sections:
            contract.required_inputs = self._parse_yaml_block(sections["Required Inputs"])
        
        # Extract required outputs
        if "Required Outputs" in sections:
            contract.required_outputs = self._parse_yaml_block(sections["Required Outputs"])
        
        # Extract stage contract
        if "Stage Contract" in sections:
            stage_contract = self._parse_stage_contract(sections["Stage Contract"])
            contract.can_receive_from = stage_contract.get("can_receive_from", [])
            contract.can_advance_to = stage_contract.get("can_advance_to", [])
            contract.can_bounce_to = stage_contract.get("can_bounce_to", [])
            contract.cannot_proceed_without = stage_contract.get("cannot_proceed_without", [])
        
        # Extract handoff pattern
        if "Handoff Pattern" in sections:
            contract.handoff_pattern = self._parse_handoff_pattern(sections["Handoff Pattern"])
        
        # Extract decision tree
        if "Decision Tree" in sections:
            contract.decision_tree = self._parse_decision_tree(sections["Decision Tree"])
        
        return contract
    
    def _split_sections(self, content: str) -> Dict[str, str]:
        """Split markdown content into sections by h2 headers."""
        sections = {}
        current_section = None
        current_content = []
        
        for line in content.split("\n"):
            if line.startswith("## "):
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = line[3:].strip()
                current_content = []
            else:
                current_content.append(line)
        
        if current_section:
            sections[current_section] = "\n".join(current_content).strip()
        
        return sections
    
    def _parse_yaml_block(self, content: str) -> Dict[str, Any]:
        """Parse a YAML code block from markdown."""
        # Find YAML code blocks
        yaml_match = re.search(r"```ya?ml\n(.*?)\n```", content, re.DOTALL)
        if yaml_match:
            try:
                return yaml.safe_load(yaml_match.group(1))
            except yaml.YAMLError:
                pass
        
        # Fall back to key-value parsing
        result = {}
        for line in content.split("\n"):
            if ":" in line and not line.startswith("#"):
                key, value = line.split(":", 1)
                result[key.strip()] = value.strip()
        
        return result
    
    def _parse_stage_contract(self, content: str) -> Dict[str, List[str]]:
        """Parse stage contract section."""
        result = {
            "can_receive_from": [],
            "can_advance_to": [],
            "can_bounce_to": [],
            "cannot_proceed_without": [],
        }
        
        current_key = None
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("- "):
                # List item
                item = line[2:].strip()
                if current_key and current_key in result:
                    result[current_key].append(item)
            elif ":" in line and not line.startswith("-"):
                # Key definition
                key = line.split(":")[0].strip().lower().replace(" ", "_").replace("-", "_")
                if "receive" in key:
                    current_key = "can_receive_from"
                elif "advance" in key:
                    current_key = "can_advance_to"
                elif "bounce" in key:
                    current_key = "can_bounce_to"
                elif "cannot" in key:
                    current_key = "cannot_proceed_without"
                else:
                    current_key = None
        
        return result
    
    def _parse_handoff_pattern(self, content: str) -> List[str]:
        """Parse handoff pattern as a list of steps."""
        steps = []
        for line in content.split("\n"):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-")):
                # Remove leading number/list marker
                step = re.sub(r"^\d+\.\s*|^-?\s*", "", line)
                if step:
                    steps.append(step)
        return steps
    
    def _parse_decision_tree(self, content: str) -> List[Dict[str, str]]:
        """Parse decision tree into structured format."""
        decisions = []
        current_block = {}
        
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("IF"):
                if current_block:
                    decisions.append(current_block)
                current_block = {"condition": line[3:].strip()}
            elif line.startswith("→") and current_block:
                current_block["action"] = line[1:].strip()
        
        if current_block:
            decisions.append(current_block)
        
        return decisions
    
    def load_packet_schema(self, packet_type: str) -> Optional[Dict[str, Any]]:
        """Load a packet schema from the schemas directory."""
        if self.schemas_dir is None:
            return None
        
        schema_file = self.schemas_dir / f"{packet_type}.yaml"
        if not schema_file.exists():
            return None
        
        try:
            content = schema_file.read_text()
            return yaml.safe_load(content)
        except Exception as e:
            logger.error(f"Failed to load packet schema {packet_type}: {e}")
            return None
    
    def validate_packet(
        self,
        packet_type: str,
        packet_data: Dict[str, Any]
    ) -> tuple[bool, List[str]]:
        """Validate a packet against its schema.
        
        Returns:
            (is_valid, missing_fields)
        """
        schema = self.load_packet_schema(packet_type)
        if schema is None:
            return True, []
        
        required = schema.get("required", [])
        missing = []
        
        for field in required:
            if isinstance(field, str):
                if field not in packet_data:
                    missing.append(field)
            elif isinstance(field, dict):
                # Nested field
                for parent, children in field.items():
                    if parent not in packet_data:
                        missing.append(parent)
                    else:
                        for child in children:
                            if child not in packet_data.get(parent, {}):
                                missing.append(f"{parent}.{child}")
        
        return len(missing) == 0, missing
    
    def get_stage_for_role(self, role_name: str) -> Optional[str]:
        """Get the pipeline stage for a role name."""
        # Map role names to stages
        role_to_stage = {
            "research-verifier": "research-verify",
            "plan-reviewer": "plan-review",
            "scope-steward": "scope-steward",
            "architecture-verifier": "architecture-verify",
            "integration-steward": "integration-steward",
            "repo-steward": "repo-steward",
            "issue-maintainer": "issue-approve",
            "branch-steward": "branch-create",
            "delivery-manager": "delivery-manager",
            "spec-designer": "spec-design",
            "spec-verifier": "spec-verify",
            "pr-creation-agent": "pr-create",
            "red-test-builder": "red-test",
            "code-builder": "code-build",
            "cleanup-agent": "cleanup",
            "green-test-builder": "green-test",
            "tdd-refactor-agent": "tdd-refactor",
            "reviewer-improve-agent": "review-improve",
            "pr-maintainer": "pr-maintain",
            "wisdom-agent": "wisdom",
            "merger-agent": "merge",
        }
        
        # Normalize role name
        normalized = role_name.lower().replace("_", "-").replace(" ", "-")
        return role_to_stage.get(normalized)


# Singleton instance
_role_loader: Optional[RoleLoader] = None


def get_role_loader() -> RoleLoader:
    """Get the singleton RoleLoader instance."""
    global _role_loader
    if _role_loader is None:
        _role_loader = RoleLoader()
    return _role_loader


def load_role(role_name: str) -> Optional[RoleContract]:
    """Convenience function to load a role contract."""
    return get_role_loader().load_role(role_name)


def get_stage(role_name: str) -> Optional[str]:
    """Get the pipeline stage for a role name."""
    return get_role_loader().get_stage_for_role(role_name)