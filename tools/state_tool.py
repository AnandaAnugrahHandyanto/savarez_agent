#!/usr/bin/env python3
"""
State Tool Module - Agent State Machine Management

Provides state management capabilities for agents with explicit state tracking.
This tool allows agents to:
- Query current state and context
- Transition to new states
- Set and retrieve state context values
- Manage state timers for timeout-driven transitions
- View state history

The state machine is based on predefined schemas that define valid states,
transitions, and associated actions. This enables explicit state tracking
instead of relying on conversation history guessing.

Design:
- Single `state` tool with action parameter: get, transition, set_context, get_context, timer, history
- State transitions are validated against the schema
- Context values are persisted with the state
- Timers enable automatic state transitions after timeout
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


# Global reference to the current agent's state machine
# This is set by the agent when the tool is loaded
_current_state_machine = None


def set_current_state_machine(state_machine):
    """Set the current agent's state machine for the tool to use"""
    global _current_state_machine
    _current_state_machine = state_machine


def get_current_state_machine():
    """Get the current agent's state machine"""
    return _current_state_machine


def state(
    action: str,
    to_state: str = None,
    context_key: str = None,
    context_value: str = None,
    timer_id: str = None,
    timeout_seconds: int = None,
    timer_target_state: str = None,
    timer_action: str = None,
    history_limit: int = 10,
) -> str:
    """
    Manage agent state machine - explicit state tracking for structured workflows.

    This tool provides explicit state management capabilities. The state machine
    is based on predefined schemas that define valid states, allowed transitions,
    and associated actions. Use this tool to:

    1. **get** - Query current state, context, and allowed transitions
    2. **transition** - Move to a new state (validated against schema)
    3. **set_context** - Store key-value data in state context
    4. **get_context** - Retrieve a value from state context
    5. **timer** - Add/remove/manage timeout-driven state transitions
    6. **history** - View state change history

    State transitions are validated - you can only move to states defined as
    valid transitions from your current state. Use 'get' action to see allowed
    transitions before attempting to transition.

    Args:
        action: Action to perform - one of: get, transition, set_context, get_context, timer, history
        to_state: Target state for 'transition' action
        context_key: Key for set_context/get_context actions
        context_value: Value for set_context action (JSON string for complex values)
        timer_id: Timer identifier for timer actions
        timeout_seconds: Timeout in seconds for 'timer' add action
        timer_target_state: State to transition to on timeout for 'timer' add action
        timer_action: Timer action - one of: add, remove, list
        history_limit: Number of history entries to return for 'history' action

    Returns:
        JSON-formatted string with action results

    Examples:
        # Get current state
        state(action="get")

        # Transition to next state
        state(action="transition", to_state="analyzing")

        # Set context value
        state(action="set_context", context_key="customer_id", context_value="12345")

        # Add a timer for automatic follow-up
        state(action="timer", timer_id="followup", timer_action="add",
              timeout_seconds=1800, timer_target_state="followup")

        # View state history
        state(action="history", history_limit=20)
    """
    machine = get_current_state_machine()

    if not machine:
        return json.dumps({
            "error": "State machine not available",
            "message": "The agent is not configured with a state machine. "
                      "Enable state machine in agent configuration."
        }, indent=2)

    try:
        if action == "get":
            return _handle_get(machine)

        elif action == "transition":
            return _handle_transition(machine, to_state)

        elif action == "set_context":
            return _handle_set_context(machine, context_key, context_value)

        elif action == "get_context":
            return _handle_get_context(machine, context_key)

        elif action == "timer":
            return _handle_timer(machine, timer_id, timeout_seconds,
                               timer_target_state, timer_action)

        elif action == "history":
            return _handle_history(machine, history_limit)

        else:
            return json.dumps({
                "error": "Invalid action",
                "message": f"Unknown action: {action}. Valid actions: "
                          f"get, transition, set_context, get_context, timer, history"
            }, indent=2)

    except Exception as e:
        logger.error(f"State tool error: {e}")
        return json.dumps({
            "error": "State tool error",
            "message": str(e)
        }, indent=2)


def _handle_get(machine) -> str:
    """Handle get action - return current state info"""
    current_state = machine.get_current_state()
    context = machine.get_context()
    allowed_transitions = machine.get_allowed_transitions()
    timers = machine.get_timers()

    result = {
        "current_state": current_state,
        "allowed_transitions": allowed_transitions,
        "context": context,
        "active_timers": len(timers),
        "timer_details": [
            {
                "timer_id": t.timer_id,
                "timeout_seconds": t.timeout_seconds,
                "elapsed_seconds": (datetime.utcnow() - t.start_time).total_seconds(),
                "target_state": t.target_state
            }
            for t in timers
        ]
    }

    return json.dumps(result, indent=2)


def _handle_transition(machine, to_state: str) -> str:
    """Handle transition action - move to new state"""
    if not to_state:
        return json.dumps({
            "error": "Missing to_state parameter",
            "message": "The 'to_state' parameter is required for transition action"
        }, indent=2)

    # Check if transition is allowed
    if not machine.can_transition(to_state):
        allowed = machine.get_allowed_transitions()
        return json.dumps({
            "error": "Invalid transition",
            "message": f"Cannot transition from '{machine.get_current_state()}' "
                      f"to '{to_state}'. Allowed transitions: {allowed}"
        }, indent=2)

    # Perform transition
    success = machine.transition_to(to_state)

    if success:
        return json.dumps({
            "success": True,
            "from_state": machine.get_context().get('_last_from_state'),
            "to_state": to_state,
            "message": f"Successfully transitioned to state: {to_state}"
        }, indent=2)
    else:
        return json.dumps({
            "error": "Transition failed",
            "message": f"Failed to transition to state: {to_state}"
        }, indent=2)


def _handle_set_context(machine, context_key: str, context_value: str) -> str:
    """Handle set_context action - store value in context"""
    if not context_key:
        return json.dumps({
            "error": "Missing context_key parameter",
            "message": "The 'context_key' parameter is required for set_context action"
        }, indent=2)

    if context_value is None:
        return json.dumps({
            "error": "Missing context_value parameter",
            "message": "The 'context_value' parameter is required for set_context action"
        }, indent=2)

    # Try to parse as JSON for complex values
    try:
        value = json.loads(context_value)
    except json.JSONDecodeError:
        value = context_value  # Use as plain string

    machine.set_context(context_key, value)

    return json.dumps({
        "success": True,
        "key": context_key,
        "value": value,
        "message": f"Context value set: {context_key} = {value}"
    }, indent=2)


def _handle_get_context(machine, context_key: str) -> str:
    """Handle get_context action - retrieve value from context"""
    if not context_key:
        return json.dumps({
            "error": "Missing context_key parameter",
            "message": "The 'context_key' parameter is required for get_context action"
        }, indent=2)

    value = machine.get_context_value(context_key)

    return json.dumps({
        "key": context_key,
        "value": value,
        "found": value is not None
    }, indent=2)


def _handle_timer(machine, timer_id: str, timeout_seconds: int,
                 timer_target_state: str, timer_action: str) -> str:
    """Handle timer action - manage state timers"""
    if not timer_action:
        return json.dumps({
            "error": "Missing timer_action parameter",
            "message": "The 'timer_action' parameter is required. "
                      "Valid actions: add, remove, list"
        }, indent=2)

    if timer_action == "add":
        if not timer_id:
            return json.dumps({
                "error": "Missing timer_id parameter",
                "message": "The 'timer_id' parameter is required for adding a timer"
            }, indent=2)
        if not timeout_seconds:
            return json.dumps({
                "error": "Missing timeout_seconds parameter",
                "message": "The 'timeout_seconds' parameter is required for adding a timer"
            }, indent=2)

        success = machine.add_timer(
            timer_id=timer_id,
            timeout_seconds=timeout_seconds,
            target_state=timer_target_state
        )

        if success:
            return json.dumps({
                "success": True,
                "timer_id": timer_id,
                "timeout_seconds": timeout_seconds,
                "target_state": timer_target_state,
                "message": f"Timer added: {timer_id} (timeout: {timeout_seconds}s)"
            }, indent=2)
        else:
            return json.dumps({
                "error": "Failed to add timer",
                "message": f"Could not add timer: {timer_id}"
            }, indent=2)

    elif timer_action == "remove":
        if not timer_id:
            return json.dumps({
                "error": "Missing timer_id parameter",
                "message": "The 'timer_id' parameter is required for removing a timer"
            }, indent=2)

        success = machine.remove_timer(timer_id)

        if success:
            return json.dumps({
                "success": True,
                "timer_id": timer_id,
                "message": f"Timer removed: {timer_id}"
            }, indent=2)
        else:
            return json.dumps({
                "error": "Timer not found",
                "message": f"Timer not found: {timer_id}"
            }, indent=2)

    elif timer_action == "list":
        timers = machine.get_timers()

        timer_list = [
            {
                "timer_id": t.timer_id,
                "timeout_seconds": t.timeout_seconds,
                "elapsed_seconds": (datetime.utcnow() - t.start_time).total_seconds(),
                "target_state": t.target_state
            }
            for t in timers
        ]

        return json.dumps({
            "active_timers": len(timer_list),
            "timers": timer_list
        }, indent=2)

    else:
        return json.dumps({
            "error": "Invalid timer_action",
            "message": f"Unknown timer_action: {timer_action}. Valid actions: add, remove, list"
        }, indent=2)


def _handle_history(machine, history_limit: int) -> str:
    """Handle history action - return state change history"""
    history = machine.get_history(history_limit)

    history_list = []
    for delta in history:
        history_list.append({
            "timestamp": delta.timestamp,
            "from_state": delta.from_state,
            "to_state": delta.to_state,
            "delta_id": delta.delta_id
        })

    return json.dumps({
        "current_state": machine.get_current_state(),
        "history_count": len(history_list),
        "history": history_list
    }, indent=2)


# Tool schema for registration
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "state",
        "description": "Manage agent state machine - explicit state tracking for structured workflows. "
                      "Query current state, transition to new states, manage context values, "
                      "and set up timeout-driven automatic transitions.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "action",
                    "description": "Action to perform. Use 'get' to query current state and allowed transitions, "
                                 "'transition' to move to a new state, 'set_context' to store data, "
                                 "'get_context' to retrieve data, 'timer' to manage timeout timers, "
                                 "'history' to view state change history.",
                    "enum": ["get", "transition", "set_context", "get_context", "timer", "history"]
                },
                "to_state": {
                    "type": "string",
                    "description": "Target state for 'transition' action. Must be one of the allowed transitions "
                                 "from the current state. Use 'get' action first to see allowed transitions."
                },
                "context_key": {
                    "type": "string",
                    "description": "Key name for set_context or get_context actions. Used to store/retrieve "
                                 "values in the state context."
                },
                "context_value": {
                    "type": "string",
                    "description": "Value to store for set_context action. Can be a plain string or JSON for "
                                 "complex objects (lists, dicts, etc.)."
                },
                "timer_id": {
                    "type": "string",
                    "description": "Unique identifier for the timer. Used for add, remove, and list timer actions."
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Timeout duration in seconds for timer add action. After this time elapses, "
                                 "the timer will trigger and optionally transition to the target state."
                },
                "timer_target_state": {
                    "type": "string",
                    "description": "Optional target state for timer. If specified, the timer will automatically "
                                 "transition to this state when it times out."
                },
                "timer_action": {
                    "type": "string",
                    "description": "Timer sub-action: 'add' to create a new timer, 'remove' to delete a timer, "
                                 "'list' to show all active timers.",
                    "enum": ["add", "remove", "list"]
                },
                "history_limit": {
                    "type": "integer",
                    "description": "Maximum number of history entries to return for 'history' action. Default: 10.",
                    "default": 10
                }
            },
            "required": ["action"]
        }
    }
}


def get_tool_schema() -> Dict[str, Any]:
    """Return the tool schema for registration"""
    return TOOL_SCHEMA


def get_tool_function() -> callable:
    """Return the tool function for registration"""
    return state
