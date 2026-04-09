"""Integration layer — delegation chains, orchestration, and cross-profile coordination."""

from hierarchy.core.integration.chain_store import ChainStore
from hierarchy.core.integration.delegation import (
    ChainStatus,
    DelegationChain,
    DelegationHop,
    HopStatus,
)
from hierarchy.core.integration.exceptions import (
    ChainAlreadyComplete,
    ChainNotFound,
    CircularDelegation,
    DelegationTimeout,
    IntegrationError,
    InvalidDelegation,
)
from hierarchy.core.integration.orchestrator import ChainOrchestrator
from hierarchy.core.integration.result_propagation import ResultCollector

__all__ = [
    # Models
    "DelegationChain",
    "DelegationHop",
    "ChainStatus",
    "HopStatus",
    # Persistence
    "ChainStore",
    # Orchestration
    "ChainOrchestrator",
    "ResultCollector",
    # Exceptions
    "IntegrationError",
    "ChainNotFound",
    "InvalidDelegation",
    "ChainAlreadyComplete",
    "DelegationTimeout",
    "CircularDelegation",
]
