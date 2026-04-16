# Agent State Machine Feature Documentation

## Overview

The Agent state machine module provides explicit state management capabilities for hermes-agent. Through a Schema-based state machine engine, Agents can precisely track and manage workflow states, enabling state-driven automation.

### Core Features

- **Explicit State Tracking**: Schema-based state space, no more guessing progress from conversation history
- **State Guardrails**: Schema defines valid state transitions, preventing illegal state changes
- **Timer-Driven Transitions**: Support automatic state transitions based on timeouts (e.g., 30 minutes no response → second follow-up)
- **Persistent Storage**: Support JSON and SQLite backends with complete state change history
- **Non-Invasive Integration**: Optional state machine via StateMachineMixin, doesn't affect existing Agents
- **Engineering-Layer Driven**: Dual-mode drive where engineering controls timing, Agent controls content
- **Observability**: Complete state history and CLI query tools

## Design Principles

### 1. Schema as Contract

The state machine operates based on predefined Schemas that define:
- State space (states)
- Initial state (initial_state)
- Final states (final_states)
- Valid transitions (transitions)
- Transition conditions (conditions)

### 2. Plugin-Based Design

New scenarios only need to register a new Schema, no engine modifications required:

```python
# Register new Schema
SchemaRegistry.register(my_custom_schema)

# Agent uses new Schema
agent = AIAgent(state_config=StateMachineConfig(
    enabled=True,
    schema_name="my_custom_schema"
))
```

### 3. Dual-Mode Drive

- **Engineering Layer**: Controls when state transitions happen (timers, external triggers)
- **Agent**: Controls what happens during transitions (business logic, context data)

### 4. Prefix-Layered Scoping

Supports multi-level state spaces:

- `user:` - User-level states (e.g., user lifecycle)
- `app:` - Application-level states (e.g., order processing)
- `temp:` - Temporary states (e.g., single conversation flow)
- `system:` - System-level states (e.g., health checks)

### 5. Event-Driven Persistence

Every state change automatically records a StateDelta containing:
- Timestamp
- Source and target states
- Context data
- Metadata

## Core Components

### 1. StateSchema (State Schema)

Defines the structure and constraints of the state machine.

```python
from agent.state_schema import StateSchema, StateTransition, StateScope

sales_schema = StateSchema(
    name="aibd_sales",
    scope=StateScope.USER,
    states={
        "idle", "querying", "analyzing", "proposing",
        "negotiating", "closing", "followup", "completed", "failed"
    },
    initial_state="idle",
    final_states={"completed", "failed"},
    transitions=[
        StateTransition("idle", "querying", action=None),
        StateTransition("querying", "analyzing", action=None),
        StateTransition("analyzing", "proposing", action=None),
        # ... more transitions
    ],
    metadata={"description": "AIBD sales process"}
)
```

### 2. StateStoreBackend (State Storage)

Provides state persistence capabilities with support for multiple backends:

```python
from agent.state_store import JSONStateStore, SQLiteStateStore

# JSON storage
json_store = JSONStateStore(base_path="./state_data")

# SQLite storage
sqlite_store = SQLiteStateStore(db_path="./states.db")
```

### 3. StateMachine (State Machine Engine)

Core state machine engine responsible for state transition validation and execution.

```python
from agent.state_machine import StateMachine

machine = StateMachine(
    agent_id="agent_123",
    schema_name="aibd_sales"
)

# Query current state
current_state = machine.get_current_state()

# Execute state transition
machine.transition_to("querying", context={"customer_id": "12345"})

# Set context
machine.set_context("key", "value")

# Add timer
machine.add_timer(
    timer_id="followup",
    timeout_seconds=1800,  # 30 minutes
    target_state="followup"
)
```

### 4. StateMachineMixin (State Machine Mixin)

Provides non-invasive state machine integration for AIAgent.

```python
from agent.state_integration import StateMachineMixin, StateMachineConfig

class MyAgent(AIAgent, StateMachineMixin):
    def __init__(self):
        state_config = StateMachineConfig(
            enabled=True,
            schema_name="aibd_sales",
            auto_inject_state=True,  # Auto-inject state to Prompt
            state_inject_format="compact"
        )
        super().__init__(state_config=state_config)

    # Agent can directly use state machine methods
    def handle_query(self):
        self.transition_to("querying")
        self.set_state_context("query", user_query)
```

## Usage Examples

### Example 1: Creating Custom Schema

```python
from agent.state_schema import StateSchema, StateTransition, StateScope, SchemaRegistry

# Define task processing Schema
task_schema = StateSchema(
    name="task_processing",
    scope=StateScope.APP,
    states={
        "pending", "assigned", "in_progress",
        "review", "approved", "rejected", "completed"
    },
    initial_state="pending",
    final_states={"completed", "rejected"},
    transitions=[
        StateTransition("pending", "assigned", action=None),
        StateTransition("assigned", "in_progress", action=None),
        StateTransition("in_progress", "review", action=None),
        StateTransition("review", "approved", action=None),
        StateTransition("review", "rejected", action=None),
        StateTransition("approved", "completed", action=None),
    ]
)

# Register Schema
SchemaRegistry.register(task_schema)
```

### Example 2: Conditional Transitions

```python
# Define condition function
def is_high_priority(ctx):
    return ctx.get('priority', 0) >= 8

# Use condition in transition
StateTransition(
    "in_progress",
    "fast_track",
    condition=is_high_priority
)
```

### Example 3: Using StateMachineMixin

```python
from agent.state_integration import StateMachineMixin, StateMachineConfig

class SalesAgent(AIAgent, StateMachineMixin):
    def __init__(self, session_id):
        self.session_id = session_id
        state_config = StateMachineConfig(
            enabled=True,
            schema_name="aibd_sales",
            enable_timers=True
        )
        super().__init__(state_config=state_config)

    def process_customer_query(self, query):
        # Transition to querying state
        self.transition_to("querying")
        self.set_state_context("query", query)

        # Process query...

        # Transition to analyzing state
        self.transition_to("analyzing")

    def send_proposal(self, proposal):
        self.transition_to("proposing")
        self.set_state_context("proposal", proposal)

        # Add follow-up timer
        self.add_state_timer(
            timer_id="proposal_followup",
            timeout_seconds=86400,  # 24 hours
            target_state="followup"
        )
```

### Example 4: CLI State Queries

```bash
# List all Agent state machines
hermes state list

# View specific Agent state
hermes state get --agent-id agent_123 --schema aibd_sales

# View state change history
hermes state history --agent-id agent_123 --schema aibd_sales --limit 20

# Reset Agent state
hermes state reset --agent-id agent_123 --schema aibd_sales

# List all registered Schemas
hermes state schemas

# View Schema details
hermes state schema --name aibd_sales
```

## API Reference

### StateSchema

```python
@dataclass
class StateSchema:
    name: str                          # Schema name
    scope: StateScope                   # Scope
    states: Set[str]                   # State set
    initial_state: str                  # Initial state
    final_states: Set[str]             # Final state set
    transitions: List[StateTransition]   # Transition list
    metadata: Dict[str, Any]            # Metadata

    def can_transition(self, from_state: str, to_state: str,
                   context: Dict[str, Any] = None) -> bool
    def get_allowed_transitions(self, from_state: str) -> List[str]
    def get_transition(self, from_state: str, to_state: str) -> Optional[StateTransition]
```

### StateMachine

```python
@dataclass
class StateMachine:
    agent_id: str
    schema_name: str
    store: StateStoreBackend
    state_change_callbacks: List[Callable]

    def get_current_state(self) -> Optional[str]
    def get_context(self) -> Dict[str, Any]
    def set_context(self, key: str, value: Any)
    def get_context_value(self, key: str, default: Any = None) -> Any
    def can_transition(self, to_state: str, context: Dict[str, Any] = None) -> bool
    def get_allowed_transitions(self) -> List[str]
    def transition_to(self, to_state: str, context: Dict[str, Any] = None,
                   force: bool = False) -> bool
    def add_timer(self, timer_id: str, timeout_seconds: int,
                 target_state: str = None, action: Callable = None,
                 context: Dict[str, Any] = None) -> bool
    def remove_timer(self, timer_id: str) -> bool
    def get_timers(self) -> List[Timer]
    def get_history(self, limit: int = 100) -> List[StateDelta]
    def reset(self, force: bool = False)
```

### StateMachineMixin

```python
class StateMachineMixin:
    def get_current_state(self) -> Optional[str]
    def get_state_context(self) -> Dict[str, Any]
    def get_allowed_transitions(self) -> List[str]
    def can_transition_to(self, to_state: str, context: Dict[str, Any] = None) -> bool
    def transition_to(self, to_state: str, context: Dict[str, Any] = None,
                   force: bool = False) -> bool
    def set_state_context(self, key: str, value: Any)
    def get_state_context_value(self, key: str, default: Any = None) -> Any
    def add_state_timer(self, timer_id: str, timeout_seconds: int,
                      target_state: str = None, action: Callable = None,
                      context: Dict[str, Any] = None) -> bool
    def remove_state_timer(self, timer_id: str) -> bool
    def get_state_timers(self) -> List[Timer]
    def get_state_history(self, limit: int = 100)
    def get_state_prompt_injection(self) -> str
    def reset_state_machine(self, force: bool = False)
    def cleanup_state_machine(self)
```

### StateMachineConfig

```python
@dataclass
class StateMachineConfig:
    enabled: bool = False                      # Enable state machine
    schema_name: Optional[str] = None          # Schema name
    auto_inject_state: bool = True            # Auto-inject state to Prompt
    state_inject_format: str = "compact"      # Inject format: compact, detailed, minimal
    custom_state_template: Optional[str] = None  # Custom inject template
    enable_timers: bool = True                # Enable timers
    on_state_change: Optional[Callable] = None  # State change callback
```

## Pre-built Schemas

### aibd_sales (AIBD Sales Process)

State tracking for AIBD sales scenarios:

```
idle → querying → analyzing → proposing → negotiating → closing → followup → completed
                                                              ↓
                                                            failed
```

### aibd_task_dispatch (AIBD Task Dispatch)

State tracking for AIBD task distribution scenarios:

```
pending → assigned → in_progress → review → approved → completed
                                        ↓
                                      rejected
```

## Best Practices

### 1. Schema Design

- Keep state space simple, avoid over-segmentation
- Clearly define initial and final states
- Use meaningful transition conditions
- Record Schema purpose in metadata

### 2. Context Management

- Use context to store business-related data
- Avoid storing large amounts of data in context
- Use meaningful key names

### 3. Timer Usage

- Use clear IDs for timers
- Set reasonable timeout durations
- Clean up timers when no longer needed

### 4. Error Handling

- Catch and log state transition errors
- Perform necessary cleanup in final states
- Use force parameter carefully for exceptional cases

## Troubleshooting

### State Machine Not Initialized

```
Error: Schema 'xxx' not registered
Solution: Ensure Schema is registered via SchemaRegistry.register()
```

### Invalid State Transition

```
Error: Cannot transition from 'A' to 'B'
Solution: Check if transition is defined in Schema, or use force=True
```

### Storage Issues

```
Error: Unable to save state
Solution: Check storage path permissions, ensure JSON/SQLite files are writable
```

## Related Files

- `agent/state_schema.py` - Schema definitions and registry
- `agent/state_store.py` - State storage backends
- `agent/state_machine.py` - State machine engine
- `agent/state_integration.py` - Agent integration layer
- `tools/state_tool.py` - Agent state management tool
- `hermes_cli/state_cli.py` - CLI state management commands
- `tests/test_state_machine.py` - Test cases
