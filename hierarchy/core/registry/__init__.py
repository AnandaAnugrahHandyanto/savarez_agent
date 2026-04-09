"""Profile registry — manages agent profiles and hierarchy."""

from hierarchy.core.registry.exceptions import (
    DuplicateProfile,
    InvalidHierarchy,
    InvalidProfileName,
    ProfileNotFound,
    RegistryError,
)
from hierarchy.core.registry.integrity import IntegrityIssue, Severity, scan_integrity
from hierarchy.core.registry.models import Profile, Role, Status, validate_profile_name
from hierarchy.core.registry.profile_registry import ProfileRegistry

__all__ = [
    "ProfileRegistry",
    "Profile",
    "Role",
    "Status",
    "validate_profile_name",
    "RegistryError",
    "ProfileNotFound",
    "InvalidHierarchy",
    "DuplicateProfile",
    "InvalidProfileName",
    "scan_integrity",
    "IntegrityIssue",
    "Severity",
]
