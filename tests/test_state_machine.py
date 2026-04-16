"""
Test cases for the state machine system.

Tests cover:
- Schema registration and validation
- State machine lifecycle
- State transition validation
- Timer functionality
- Storage backends (JSON and SQLite)
- StateMachineMixin integration
- StateDrivenAutomation
"""

import pytest
import tempfile
import os
from datetime import datetime, timezone

from agent.state_schema import (
    StateSchema,
    StateTransition,
    StateScope,
    SchemaRegistry,
    StateSchemaError,
)

from agent.state_store import (
    StateDelta,
    JSONStateStore,
    SQLiteStateStore,
)

from agent.state_machine import (
    StateMachine,
    InvalidTransitionError as SMInvalidTransitionError,
    StateMachineManager,
)

from agent.state_integration import (
    StateMachineConfig,
    StateMachineMixin,
    AIBDStateIntegration,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_schema():
    """Create a sample state schema for testing."""
    return StateSchema(
        name="test_schema",
        scope=StateScope.USER,
        states={"idle", "processing", "completed", "failed"},
        initial_state="idle",
        final_states={"completed", "failed"},
        transitions=[
            StateTransition("idle", "processing", action=None),
            StateTransition("processing", "completed", action=None),
            StateTransition("processing", "failed", action=None),
            StateTransition("idle", "failed", action=None),
        ],
        metadata={"description": "Test schema"}
    )


@pytest.fixture
def complex_schema():
    """Create a more complex schema with context-based transitions."""
    def validate_success(ctx):
        return ctx.get('success', False)

    return StateSchema(
        name="complex_schema",
        scope=StateScope.USER,
        states={"start", "step1", "step2", "success", "failure"},
        initial_state="start",
        final_states={"success", "failure"},
        transitions=[
            StateTransition("start", "step1", action=None),
            StateTransition("step1", "step2", action=None),
            StateTransition("step2", "success", condition=validate_success),
            StateTransition("step2", "failure", action=None),
        ],
        metadata={"description": "Complex schema with conditions"}
    )


@pytest.fixture
def json_store(temp_dir):
    """Create a JSON state store for testing."""
    store = JSONStateStore(base_path=temp_dir)
    yield store
    # Cleanup is handled by temp_dir


@pytest.fixture
def sqlite_store(temp_dir):
    """Create a SQLite state store for testing."""
    db_path = os.path.join(temp_dir, "test_states.db")
    store = SQLiteStateStore(db_path=db_path)
    yield store
    # Cleanup is handled by temp_dir


# ============================================================================
# Schema Tests
# ============================================================================

class TestStateSchema:
    """Test StateSchema functionality."""

    def test_schema_creation(self, sample_schema):
        """Test creating a valid state schema."""
        assert sample_schema.name == "test_schema"
        assert sample_schema.scope == StateScope.USER
        assert len(sample_schema.states) == 4
        assert sample_schema.initial_state == "idle"
        assert len(sample_schema.final_states) == 2
        assert len(sample_schema.transitions) == 4

    def test_invalid_initial_state(self):
        """Test that schema with invalid initial state raises error."""
        with pytest.raises(StateSchemaError):
            StateSchema(
                name="invalid_schema",
                scope=StateScope.USER,
                states={"state1", "state2"},
                initial_state="invalid",  # Not in states
                final_states=set(),
                transitions=[]
            )

    def test_invalid_final_states(self):
        """Test that schema with invalid final states raises error."""
        with pytest.raises(StateSchemaError):
            StateSchema(
                name="invalid_schema",
                scope=StateScope.USER,
                states={"state1", "state2"},
                initial_state="state1",
                final_states={"invalid"},  # Not in states
                transitions=[]
            )

    def test_invalid_transitions(self):
        """Test that schema with invalid transitions raises error."""
        with pytest.raises(StateSchemaError):
            StateSchema(
                name="invalid_schema",
                scope=StateScope.USER,
                states={"state1", "state2"},
                initial_state="state1",
                final_states=set(),
                transitions=[
                    StateTransition("state1", "invalid", action=None)  # Invalid to_state
                ]
            )

    def test_can_transition_valid(self, sample_schema):
        """Test checking valid transitions."""
        assert sample_schema.can_transition("idle", "processing", {})
        assert sample_schema.can_transition("processing", "completed", {})
        assert sample_schema.can_transition("processing", "failed", {})

    def test_can_transition_invalid(self, sample_schema):
        """Test checking invalid transitions."""
        assert not sample_schema.can_transition("idle", "completed", {})
        assert not sample_schema.can_transition("processing", "idle", {})

    def test_can_transition_with_condition(self, complex_schema):
        """Test transitions with conditions."""
        # step2 -> success requires success=True in context
        assert complex_schema.can_transition("step2", "success", {"success": True})
        assert not complex_schema.can_transition("step2", "success", {"success": False})

    def test_get_allowed_transitions(self, sample_schema):
        """Test getting allowed transitions from a state."""
        allowed = sample_schema.get_allowed_transitions("idle")
        assert "processing" in allowed
        assert "failed" in allowed
        assert len(allowed) == 2

    def test_get_transition(self, sample_schema):
        """Test getting a specific transition."""
        transition = sample_schema.get_transition("idle", "processing")
        assert transition is not None
        assert transition.from_state == "idle"
        assert transition.to_state == "processing"


class TestSchemaRegistry:
    """Test SchemaRegistry functionality."""

    def test_register_and_get(self, sample_schema):
        """Test registering and retrieving a schema."""
        SchemaRegistry.register(sample_schema)
        retrieved = SchemaRegistry.get("test_schema")
        assert retrieved is not None
        assert retrieved.name == "test_schema"

    def test_get_nonexistent(self):
        """Test getting a non-existent schema."""
        retrieved = SchemaRegistry.get("nonexistent")
        assert retrieved is None

    def test_unregister(self, sample_schema):
        """Test unregistering a schema."""
        SchemaRegistry.register(sample_schema)
        assert SchemaRegistry.unregister("test_schema") is True
        assert SchemaRegistry.get("test_schema") is None

    def test_unregister_nonexistent(self):
        """Test unregistering a non-existent schema."""
        assert SchemaRegistry.unregister("nonexistent") is False

    def test_list_schemas(self, sample_schema):
        """Test listing all registered schemas."""
        SchemaRegistry.register(sample_schema)
        schemas = SchemaRegistry.list_schemas()
        assert "test_schema" in schemas

    def test_duplicate_registration(self, sample_schema):
        """Test that duplicate registration raises error."""
        SchemaRegistry.register(sample_schema)
        with pytest.raises(StateSchemaError):
            SchemaRegistry.register(sample_schema)

    def teardown_method(self):
        """Clean up after each test."""
        # Clear registry to avoid test interference
        SchemaRegistry._schemas.clear()


# ============================================================================
# State Store Tests
# ============================================================================

class TestStateDelta:
    """Test StateDelta functionality."""

    def test_delta_creation(self):
        """Test creating a state delta."""
        delta = StateDelta(
            agent_id="test_agent",
            schema_name="test_schema",
            timestamp=datetime.now(timezone.utc).isoformat(),
            from_state="idle",
            to_state="processing",
            context={"data": "value"},
            metadata={},
            delta_id="delta_123"
        )
        assert delta.agent_id == "test_agent"
        assert delta.from_state == "idle"
        assert delta.to_state == "processing"


class TestJSONStateStore:
    """Test JSONStateStore functionality."""

    def test_save_and_get_state(self, json_store, sample_schema):
        """Test saving and retrieving state."""
        SchemaRegistry.register(sample_schema)

        json_store.save_state(
            agent_id="test_agent",
            schema_name="test_schema",
            state="processing",
            context={"data": "value"}
        )

        state = json_store.get_state("test_agent", "test_schema")
        assert state == "processing"

    def test_save_and_get_context(self, json_store, sample_schema):
        """Test saving and retrieving context."""
        SchemaRegistry.register(sample_schema)

        json_store.save_state(
            agent_id="test_agent",
            schema_name="test_schema",
            state="processing",
            context={"key1": "value1", "key2": 123}
        )

        context = json_store.get_context("test_agent", "test_schema")
        assert context["key1"] == "value1"
        assert context["key2"] == 123

    def test_get_history(self, json_store, sample_schema):
        """Test getting state change history."""
        SchemaRegistry.register(sample_schema)

        # Make multiple transitions
        json_store.save_state("test_agent", "test_schema", "processing", {"step": 1})
        json_store.save_state("test_agent", "test_schema", "completed", {"step": 2})

        history = json_store.get_history("test_agent", "test_schema", limit=10)
        assert len(history) >= 2
        assert history[0].to_state == "completed"
        assert history[1].to_state == "processing"

    def test_delete_state(self, json_store, sample_schema):
        """Test deleting state."""
        SchemaRegistry.register(sample_schema)

        json_store.save_state("test_agent", "test_schema", "processing")
        json_store.delete_state("test_agent", "test_schema")

        state = json_store.get_state("test_agent", "test_schema")
        assert state is None

    def test_list_agents(self, json_store, sample_schema):
        """Test listing all agents for a schema."""
        SchemaRegistry.register(sample_schema)

        json_store.save_state("agent1", "test_schema", "processing")
        json_store.save_state("agent2", "test_schema", "processing")

        agents = json_store.list_agents("test_schema")
        assert "agent1" in agents
        assert "agent2" in agents

    def teardown_method(self):
        """Clean up after each test."""
        SchemaRegistry._schemas.clear()


class TestSQLiteStateStore:
    """Test SQLiteStateStore functionality."""

    def test_save_and_get_state(self, sqlite_store, sample_schema):
        """Test saving and retrieving state."""
        SchemaRegistry.register(sample_schema)

        sqlite_store.save_state(
            agent_id="test_agent",
            schema_name="test_schema",
            state="processing",
            context={"data": "value"}
        )

        state = sqlite_store.get_state("test_agent", "test_schema")
        assert state == "processing"

    def test_save_and_get_context(self, sqlite_store, sample_schema):
        """Test saving and retrieving context."""
        SchemaRegistry.register(sample_schema)

        sqlite_store.save_state(
            agent_id="test_agent",
            schema_name="test_schema",
            state="processing",
            context={"key1": "value1", "key2": 123}
        )

        context = sqlite_store.get_context("test_agent", "test_schema")
        assert context["key1"] == "value1"
        assert context["key2"] == 123

    def test_get_history(self, sqlite_store, sample_schema):
        """Test getting state change history."""
        SchemaRegistry.register(sample_schema)

        sqlite_store.save_state("test_agent", "test_schema", "processing", {"step": 1})
        sqlite_store.save_state("test_agent", "test_schema", "completed", {"step": 2})

        history = sqlite_store.get_history("test_agent", "test_schema", limit=10)
        assert len(history) >= 2
        assert history[0].to_state == "completed"
        assert history[1].to_state == "processing"

    def test_delete_state(self, sqlite_store, sample_schema):
        """Test deleting state."""
        SchemaRegistry.register(sample_schema)

        sqlite_store.save_state("test_agent", "test_schema", "processing")
        sqlite_store.delete_state("test_agent", "test_schema")

        state = sqlite_store.get_state("test_agent", "test_schema")
        assert state is None

    def test_list_agents(self, sqlite_store, sample_schema):
        """Test listing all agents for a schema."""
        SchemaRegistry.register(sample_schema)

        sqlite_store.save_state("agent1", "test_schema", "processing")
        sqlite_store.save_state("agent2", "test_schema", "processing")

        agents = sqlite_store.list_agents("test_schema")
        assert "agent1" in agents
        assert "agent2" in agents

    def teardown_method(self):
        """Clean up after each test."""
        SchemaRegistry._schemas.clear()


# ============================================================================
# State Machine Tests
# ============================================================================

class TestStateMachine:
    """Test StateMachine functionality."""

    def test_machine_initialization(self, sample_schema):
        """Test initializing a state machine."""
        SchemaRegistry.register(sample_schema)

        machine = StateMachine(
            agent_id="test_agent",
            schema_name="test_schema"
        )

        assert machine.agent_id == "test_agent"
        assert machine.schema_name == "test_schema"
        assert machine.get_current_state() == "idle"  # Initial state

    def test_valid_transition(self, sample_schema):
        """Test making a valid transition."""
        SchemaRegistry.register(sample_schema)

        machine = StateMachine(
            agent_id="test_agent",
            schema_name="test_schema"
        )

        success = machine.transition_to("processing")
        assert success is True
        assert machine.get_current_state() == "processing"

    def test_invalid_transition(self, sample_schema):
        """Test that invalid transition raises error."""
        SchemaRegistry.register(sample_schema)

        machine = StateMachine(
            agent_id="test_agent",
            schema_name="test_schema"
        )

        with pytest.raises(SMInvalidTransitionError):
            machine.transition_to("completed")  # Can't go directly from idle to completed

    def test_forced_transition(self, sample_schema):
        """Test forcing a transition."""
        SchemaRegistry.register(sample_schema)

        machine = StateMachine(
            agent_id="test_agent",
            schema_name="test_schema"
        )

        # Force invalid transition
        success = machine.transition_to("completed", force=True)
        assert success is True
        assert machine.get_current_state() == "completed"

    def test_context_management(self, sample_schema):
        """Test setting and getting context values."""
        SchemaRegistry.register(sample_schema)

        machine = StateMachine(
            agent_id="test_agent",
            schema_name="test_schema"
        )

        machine.set_context("key1", "value1")
        machine.set_context("key2", 123)

        assert machine.get_context_value("key1") == "value1"
        assert machine.get_context_value("key2") == 123
        assert machine.get_context_value("nonexistent", "default") == "default"

    def test_get_allowed_transitions(self, sample_schema):
        """Test getting allowed transitions."""
        SchemaRegistry.register(sample_schema)

        machine = StateMachine(
            agent_id="test_agent",
            schema_name="test_schema"
        )

        allowed = machine.get_allowed_transitions()
        assert "processing" in allowed
        assert "failed" in allowed

    def test_timer_addition(self, sample_schema):
        """Test adding a timer."""
        SchemaRegistry.register(sample_schema)

        machine = StateMachine(
            agent_id="test_agent",
            schema_name="test_schema"
        )

        success = machine.add_timer(
            timer_id="test_timer",
            timeout_seconds=60,
            target_state="failed"
        )

        assert success is True
        timers = machine.get_timers()
        assert len(timers) == 1
        assert timers[0].timer_id == "test_timer"

    def test_timer_removal(self, sample_schema):
        """Test removing a timer."""
        SchemaRegistry.register(sample_schema)

        machine = StateMachine(
            agent_id="test_agent",
            schema_name="test_schema"
        )

        machine.add_timer("test_timer", 60, "failed")
        success = machine.remove_timer("test_timer")

        assert success is True
        assert len(machine.get_timers()) == 0

    def test_state_history(self, sample_schema):
        """Test getting state history."""
        SchemaRegistry.register(sample_schema)

        machine = StateMachine(
            agent_id="test_agent",
            schema_name="test_schema"
        )

        machine.transition_to("processing")
        machine.transition_to("completed")

        history = machine.get_history(limit=10)
        assert len(history) >= 2

    def test_state_change_callback(self, sample_schema):
        """Test state change callbacks."""
        SchemaRegistry.register(sample_schema)

        callback_called = []
        def callback(agent_id, schema_name, event):
            callback_called.append((agent_id, schema_name, event))

        machine = StateMachine(
            agent_id="test_agent",
            schema_name="test_schema",
            state_change_callbacks=[callback]
        )

        machine.transition_to("processing")

        assert len(callback_called) == 1
        assert callback_called[0][0] == "test_agent"
        assert callback_called[0][2]['from_state'] == "idle"
        assert callback_called[0][2]['to_state'] == "processing"

    def teardown_method(self):
        """Clean up after each test."""
        SchemaRegistry._schemas.clear()
        StateMachineManager._machines.clear()


class TestStateMachineManager:
    """Test StateMachineManager functionality."""

    def test_get_machine(self, sample_schema):
        """Test getting a machine instance."""
        SchemaRegistry.register(sample_schema)

        machine = StateMachineManager.get_machine("test_agent", "test_schema")

        assert machine.agent_id == "test_agent"
        assert machine.schema_name == "test_schema"

    def test_get_same_machine(self, sample_schema):
        """Test that getting the same machine returns same instance."""
        SchemaRegistry.register(sample_schema)

        machine1 = StateMachineManager.get_machine("test_agent", "test_schema")
        machine2 = StateMachineManager.get_machine("test_agent", "test_schema")

        assert machine1 is machine2

    def test_remove_machine(self, sample_schema):
        """Test removing a machine."""
        SchemaRegistry.register(sample_schema)

        StateMachineManager.get_machine("test_agent", "test_schema")
        success = StateMachineManager.remove_machine("test_agent", "test_schema")

        assert success is True

    def test_list_machines(self, sample_schema):
        """Test listing all machines."""
        SchemaRegistry.register(sample_schema)

        StateMachineManager.get_machine("agent1", "test_schema")
        StateMachineManager.get_machine("agent2", "test_schema")

        machines = StateMachineManager.list_machines()
        assert len(machines) == 2

    def teardown_method(self):
        """Clean up after each test."""
        SchemaRegistry._schemas.clear()
        StateMachineManager._machines.clear()


# ============================================================================
# State Integration Tests
# ============================================================================

class TestStateMachineConfig:
    """Test StateMachineConfig functionality."""

    def test_default_config(self):
        """Test default configuration."""
        config = StateMachineConfig()
        assert config.enabled is False
        assert config.schema_name is None
        assert config.auto_inject_state is True
        assert config.state_inject_format == "compact"
        assert config.enable_timers is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = StateMachineConfig(
            enabled=True,
            schema_name="test_schema",
            auto_inject_state=False,
            state_inject_format="detailed"
        )
        assert config.enabled is True
        assert config.schema_name == "test_schema"
        assert config.auto_inject_state is False
        assert config.state_inject_format == "detailed"


class TestStateMachineMixin:
    """Test StateMachineMixin functionality."""

    def test_mixin_initialization(self, sample_schema):
        """Test initializing mixin with state machine."""
        SchemaRegistry.register(sample_schema)

        class TestAgent(StateMachineMixin):
            def __init__(self, session_id="test_session"):
                self.session_id = session_id
                state_config = StateMachineConfig(
                    enabled=True,
                    schema_name="test_schema"
                )
                super().__init__(state_config=state_config)

        agent = TestAgent()
        assert agent.get_current_state() == "idle"

    def test_mixin_disabled(self):
        """Test mixin when state machine is disabled."""
        class TestAgent(StateMachineMixin):
            def __init__(self):
                state_config = StateMachineConfig(enabled=False)
                super().__init__(state_config=state_config)

        agent = TestAgent()
        assert agent.get_current_state() is None

    def test_mixin_transition(self, sample_schema):
        """Test making transitions through mixin."""
        SchemaRegistry.register(sample_schema)

        class TestAgent(StateMachineMixin):
            def __init__(self):
                self.session_id = "test_session"
                state_config = StateMachineConfig(
                    enabled=True,
                    schema_name="test_schema"
                )
                super().__init__(state_config=state_config)

        agent = TestAgent()
        success = agent.transition_to("processing")

        assert success is True
        assert agent.get_current_state() == "processing"

    def test_mixin_context(self, sample_schema):
        """Test context management through mixin."""
        SchemaRegistry.register(sample_schema)

        class TestAgent(StateMachineMixin):
            def __init__(self):
                self.session_id = "test_session"
                state_config = StateMachineConfig(
                    enabled=True,
                    schema_name="test_schema"
                )
                super().__init__(state_config=state_config)

        agent = TestAgent()
        agent.set_state_context("key", "value")

        assert agent.get_state_context_value("key") == "value"

    def test_state_prompt_injection(self, sample_schema):
        """Test state prompt injection."""
        SchemaRegistry.register(sample_schema)

        class TestAgent(StateMachineMixin):
            def __init__(self):
                self.session_id = "test_session"
                state_config = StateMachineConfig(
                    enabled=True,
                    schema_name="test_schema",
                    state_inject_format="compact"
                )
                super().__init__(state_config=state_config)

        agent = TestAgent()
        injection = agent.get_state_prompt_injection()

        assert "current_state" in injection or "idle" in injection

    def teardown_method(self):
        """Clean up after each test."""
        SchemaRegistry._schemas.clear()
        StateMachineManager._machines.clear()


class TestAIBDStateIntegration:
    """Test AIBDStateIntegration functionality."""

    def test_register_aibd_schemas(self):
        """Test registering AIBD schemas."""
        AIBDStateIntegration.register_aibd_schemas()

        # Check that schemas are registered
        assert SchemaRegistry.get("aibd_sales") is not None
        assert SchemaRegistry.get("aibd_task_dispatch") is not None

    def test_get_aibd_state_config(self):
        """Test getting AIBD state config."""
        config = AIBDStateIntegration.get_aibd_state_config("aibd_sales")

        assert config.enabled is True
        assert config.schema_name == "aibd_sales"
        assert config.auto_inject_state is True

    def teardown_method(self):
        """Clean up after each test."""
        SchemaRegistry._schemas.clear()
        StateMachineManager._machines.clear()


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for the complete state machine system."""

    def test_full_workflow(self, temp_dir):
        """Test a complete workflow from schema to state machine."""
        # Create a custom schema
        schema = StateSchema(
            name="workflow_schema",
            scope=StateScope.USER,
            states={"pending", "in_progress", "review", "approved", "rejected"},
            initial_state="pending",
            final_states={"approved", "rejected"},
            transitions=[
                StateTransition("pending", "in_progress", action=None),
                StateTransition("in_progress", "review", action=None),
                StateTransition("review", "approved", action=None),
                StateTransition("review", "rejected", action=None),
                StateTransition("in_progress", "rejected", action=None),
            ]
        )

        SchemaRegistry.register(schema)

        # Create state machine
        machine = StateMachine(
            agent_id="workflow_agent",
            schema_name="workflow_schema"
        )

        # Verify initial state
        assert machine.get_current_state() == "pending"

        # Set some context
        machine.set_context("task_name", "Test Task")
        machine.set_context("assignee", "John Doe")

        # Make transitions
        machine.transition_to("in_progress")
        assert machine.get_current_state() == "in_progress"

        machine.set_context("progress", 50)

        machine.transition_to("review")
        assert machine.get_current_state() == "review"

        # Add a timer for auto-rejection
        machine.add_timer(
            timer_id="review_timeout",
            timeout_seconds=3600,
            target_state="rejected"
        )

        # Complete the workflow
        machine.transition_to("approved")
        assert machine.get_current_state() == "approved"

        # Verify history
        history = machine.get_history()
        assert len(history) >= 4

        # Verify final context
        context = machine.get_context()
        assert context["task_name"] == "Test Task"
        assert context["assignee"] == "John Doe"

    def teardown_method(self):
        """Clean up after each test."""
        SchemaRegistry._schemas.clear()
        StateMachineManager._machines.clear()
