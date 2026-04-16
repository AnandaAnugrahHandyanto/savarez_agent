"""Agent internals -- extracted modules from run_agent.py.

These modules contain pure utility functions and self-contained classes
that were previously embedded in the 3,600-line run_agent.py. Extracting
them makes run_agent.py focused on the AIAgent orchestrator class.
"""

# State machine integration
from agent.state_schema import (
    StateSchema,
    StateTransition,
    StateScope,
    SchemaRegistry,
    StateSchemaError,
    InvalidStateError,
    InvalidTransitionError,
)

from agent.state_store import (
    StateStoreBackend,
    StateDelta,
    JSONStateStore,
    SQLiteStateStore,
    get_state_store,
)

from agent.state_machine import (
    StateMachine,
    StateMachineError,
    InvalidStateError as SMInvalidStateError,
    InvalidTransitionError as SMInvalidTransitionError,
    Timer,
    StateMachineManager,
)

from agent.state_integration import (
    StateMachineConfig,
    StateMachineMixin,
    StateDrivenAutomation,
    AIBDStateIntegration,
)

__all__ = [
    # State schema
    "StateSchema",
    "StateTransition",
    "StateScope",
    "SchemaRegistry",
    "StateSchemaError",
    "InvalidStateError",
    "InvalidTransitionError",
    # State store
    "StateStoreBackend",
    "StateDelta",
    "JSONStateStore",
    "SQLiteStateStore",
    "get_state_store",
    # State machine
    "StateMachine",
    "StateMachineError",
    "SMInvalidStateError",
    "SMInvalidTransitionError",
    "Timer",
    "StateMachineManager",
    # State integration
    "StateMachineConfig",
    "StateMachineMixin",
    "StateDrivenAutomation",
    "AIBDStateIntegration",
]
