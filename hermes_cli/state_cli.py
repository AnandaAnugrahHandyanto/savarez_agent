"""
State CLI Commands - Agent State Machine Management

Provides CLI commands for managing agent state machines:
- hermes state list: List all active state machines
- hermes state get <agent_id>: Get state machine details
- hermes state history <agent_id>: View state change history
- hermes state reset <agent_id>: Reset state machine to initial state
- hermes state schemas: List registered state schemas
- hermes state schema <name>: Show schema details
"""

import argparse
import json
from pathlib import Path
from typing import Optional

from hermes_cli.colors import Colors, color
from hermes_constants import get_hermes_home

# Import state machine components
try:
    from agent.state_machine import StateMachineManager, StateMachineError
    from agent.state_schema import SchemaRegistry, StateSchema
    from agent.state_integration import AIBDStateIntegration
    STATE_MACHINE_AVAILABLE = True
except ImportError:
    STATE_MACHINE_AVAILABLE = False


def check_mark(ok: bool) -> str:
    """Return checkmark or cross based on boolean."""
    if ok:
        return color("✓", Colors.GREEN)
    return color("✗", Colors.RED)


def ensure_state_machine():
    """Ensure state machine is available."""
    if not STATE_MACHINE_AVAILABLE:
        print(color("Error: State machine module not available", Colors.RED))
        print("Please ensure the agent.state_machine module is properly installed.")
        return False
    return True


# ============================================================================
# Command: hermes state list
# ============================================================================

def cmd_state_list(args):
    """List all active state machines."""
    if not ensure_state_machine():
        return 1

    print()
    print(color("┌─────────────────────────────────────────────────────────┐", Colors.CYAN))
    print(color("│              Active State Machines                     │", Colors.CYAN))
    print(color("└─────────────────────────────────────────────────────────┘", Colors.CYAN))
    print()

    machines = StateMachineManager.list_machines()

    if not machines:
        print(color("  No active state machines found", Colors.DIM))
        print()
        return 0

    # Group by schema
    by_schema = {}
    for m in machines:
        schema = m['schema_name']
        if schema not in by_schema:
            by_schema[schema] = []
        by_schema[schema].append(m)

    for schema_name, schema_machines in sorted(by_schema.items()):
        print(color(f"◆ Schema: {schema_name}", Colors.CYAN, Colors.BOLD))
        print(f"  Active machines: {len(schema_machines)}")
        print()

        for m in schema_machines:
            print(f"    Agent ID:    {m['agent_id']}")
            print(f"    Current:      {color(m['current_state'], Colors.YELLOW)}")
            print(f"    Timers:       {m['timers']}")
            if m['context']:
                ctx_preview = json.dumps(m['context'], ensure_ascii=False)[:100]
                if len(ctx_preview) >= 100:
                    ctx_preview += "..."
                print(f"    Context:      {ctx_preview}")
            print()

    print()
    print(f"Total: {len(machines)} active state machine(s)")
    print()
    return 0


# ============================================================================
# Command: hermes state get
# ============================================================================

def cmd_state_get(args):
    """Get state machine details for a specific agent."""
    if not ensure_state_machine():
        return 1

    agent_id = args.agent_id
    schema_name = args.schema

    print()
    print(color("┌─────────────────────────────────────────────────────────┐", Colors.CYAN))
    print(color(f"│         State Machine: {agent_id[:30]:<30} │", Colors.CYAN))
    print(color("└─────────────────────────────────────────────────────────┘", Colors.CYAN))
    print()

    status = StateMachineManager.get_machine_status(agent_id, schema_name)

    if not status:
        print(color(f"  State machine not found: {agent_id}", Colors.RED))
        if schema_name:
            print(f"  Schema: {schema_name}")
        print()
        return 1

    print(color("◆ Basic Info", Colors.CYAN, Colors.BOLD))
    print(f"  Agent ID:     {status['agent_id']}")
    print(f"  Schema:       {status['schema_name']}")
    print(f"  Current:      {color(status['current_state'], Colors.YELLOW)}")
    print()

    print(color("◆ Allowed Transitions", Colors.CYAN, Colors.BOLD))
    if status['allowed_transitions']:
        for t in status['allowed_transitions']:
            print(f"  - {t}")
    else:
        print(color("  (none - final state)", Colors.DIM))
    print()

    print(color("◆ State Context", Colors.CYAN, Colors.BOLD))
    if status['context']:
        for key, value in sorted(status['context'].items()):
            # Truncate long values
            value_str = json.dumps(value, ensure_ascii=False)
            if len(value_str) > 80:
                value_str = value_str[:80] + "..."
            print(f"  {key}: {value_str}")
    else:
        print(color("  (empty)", Colors.DIM))
    print()

    if status['timers']:
        print(color("◆ Active Timers", Colors.CYAN, Colors.BOLD))
        for t in status['timers']:
            elapsed = t['elapsed_seconds']
            timeout = t['timeout_seconds']
            remaining = max(0, timeout - elapsed)
            progress_pct = int((elapsed / timeout) * 100) if timeout > 0 else 0

            # Progress bar
            bar_length = 20
            filled = int((elapsed / timeout) * bar_length) if timeout > 0 else 0
            bar = "█" * filled + "░" * (bar_length - filled)

            print(f"  Timer:        {t['timer_id']}")
            print(f"  Progress:     [{bar}] {progress_pct}%")
            print(f"  Elapsed:      {elapsed:.1f}s / {timeout}s")
            print(f"  Remaining:    {remaining:.1f}s")
            if t['target_state']:
                print(f"  Target:       {color(t['target_state'], Colors.YELLOW)}")
            print()

    print()
    return 0


# ============================================================================
# Command: hermes state history
# ============================================================================

def cmd_state_history(args):
    """View state change history for an agent."""
    if not ensure_state_machine():
        return 1

    agent_id = args.agent_id
    schema_name = args.schema
    limit = args.limit

    print()
    print(color("┌─────────────────────────────────────────────────────────┐", Colors.CYAN))
    print(color(f"│      State History: {agent_id[:30]:<30} │", Colors.CYAN))
    print(color("└─────────────────────────────────────────────────────────┘", Colors.CYAN))
    print()

    try:
        machine = StateMachineManager.get_machine(agent_id, schema_name)
        history = machine.get_history(limit)

        if not history:
            print(color("  No state history found", Colors.DIM))
            print()
            return 0

        print(f"Showing {len(history)} most recent state changes:")
        print()

        for i, delta in enumerate(history, 1):
            from_state = delta.from_state or "(initial)"
            to_state = delta.to_state

            # Format transition
            if i == 1:
                # Initial state
                print(f"{i}. {color(to_state, Colors.GREEN, Colors.BOLD)} (initial)")
            else:
                print(f"{i}. {from_state} → {color(to_state, Colors.YELLOW, Colors.BOLD)}")

            print(f"   Time:     {delta.timestamp}")
            print(f"   Delta ID: {delta.delta_id}")

            if delta.context:
                ctx_preview = json.dumps(delta.context, ensure_ascii=False)[:100]
                if len(ctx_preview) >= 100:
                    ctx_preview += "..."
                print(f"   Context:  {ctx_preview}")
            print()

        print()
        return 0

    except Exception as e:
        print(color(f"Error: {e}", Colors.RED))
        print()
        return 1


# ============================================================================
# Command: hermes state reset
# ============================================================================

def cmd_state_reset(args):
    """Reset state machine to initial state."""
    if not ensure_state_machine():
        return 1

    agent_id = args.agent_id
    schema_name = args.schema
    force = args.force

    print()
    print(color("┌─────────────────────────────────────────────────────────┐", Colors.CYAN))
    print(color(f"│         Reset State Machine: {agent_id[:25]:<25} │", Colors.CYAN))
    print(color("└─────────────────────────────────────────────────────────┘", Colors.CYAN))
    print()

    try:
        machine = StateMachineManager.get_machine(agent_id, schema_name)

        current_state = machine.get_current_state()
        print(f"Current state: {color(current_state, Colors.YELLOW)}")
        print()

        if not force:
            response = input("Are you sure you want to reset this state machine? (yes/no): ")
            if response.lower() not in ("yes", "y"):
                print("Reset cancelled.")
                print()
                return 0

        machine.reset(force=True)

        new_state = machine.get_current_state()
        print()
        print(color(f"✓ State machine reset to: {new_state}", Colors.GREEN))
        print()
        return 0

    except Exception as e:
        print(color(f"Error: {e}", Colors.RED))
        print()
        return 1


# ============================================================================
# Command: hermes state schemas
# ============================================================================

def cmd_state_schemas(args):
    """List all registered state schemas."""
    if not ensure_state_machine():
        return 1

    print()
    print(color("┌─────────────────────────────────────────────────────────┐", Colors.CYAN))
    print(color("│              Registered State Schemas                  │", Colors.CYAN))
    print(color("└─────────────────────────────────────────────────────────┘", Colors.CYAN))
    print()

    schemas = SchemaRegistry.list_schemas()

    if not schemas:
        print(color("  No schemas registered", Colors.DIM))
        print()
        return 0

    for schema_name, schema in sorted(schemas.items()):
        print(color(f"◆ {schema_name}", Colors.CYAN, Colors.BOLD))
        print(f"  Scope:        {schema.scope.value}")
        print(f"  States:       {len(schema.states)}")
        print(f"  Initial:      {schema.initial_state}")
        print(f"  Final:        {', '.join(sorted(schema.final_states))}")
        print(f"  Transitions:  {len(schema.transitions)}")

        if schema.metadata:
            desc = schema.metadata.get('description', '')
            if desc:
                print(f"  Description:  {desc}")
        print()

    print(f"Total: {len(schemas)} schema(s) registered")
    print()
    return 0


# ============================================================================
# Command: hermes state schema
# ============================================================================

def cmd_state_schema(args):
    """Show details for a specific schema."""
    if not ensure_state_machine():
        return 1

    schema_name = args.name

    print()
    print(color("┌─────────────────────────────────────────────────────────┐", Colors.CYAN))
    print(color(f"│         Schema Details: {schema_name[:30]:<30} │", Colors.CYAN))
    print(color("└─────────────────────────────────────────────────────────┘", Colors.CYAN))
    print()

    schema = SchemaRegistry.get(schema_name)

    if not schema:
        print(color(f"  Schema not found: {schema_name}", Colors.RED))
        print()
        return 1

    print(color("◆ Basic Info", Colors.CYAN, Colors.BOLD))
    print(f"  Name:         {schema.name}")
    print(f"  Scope:        {schema.scope.value}")
    print(f"  Initial:      {color(schema.initial_state, Colors.GREEN)}")
    print(f"  Final:        {', '.join(sorted(schema.final_states))}")
    print()

    print(color("◆ States", Colors.CYAN, Colors.BOLD))
    for state in sorted(schema.states):
        if state in schema.final_states:
            marker = color(" (final)", Colors.DIM)
        elif state == schema.initial_state:
            marker = color(" (initial)", Colors.DIM)
        else:
            marker = ""
        print(f"  - {state}{marker}")
    print()

    print(color("◆ Transitions", Colors.CYAN, Colors.BOLD))
    # Group transitions by from_state
    by_from = {}
    for t in schema.transitions:
        if t.from_state not in by_from:
            by_from[t.from_state] = []
        by_from[t.from_state].append(t.to_state)

    for from_state in sorted(by_from.keys()):
        to_states = sorted(by_from[from_state])
        print(f"  {color(from_state, Colors.YELLOW)} → {', '.join(to_states)}")
    print()

    if schema.metadata:
        print(color("◆ Metadata", Colors.CYAN, Colors.BOLD))
        for key, value in schema.metadata.items():
            print(f"  {key}: {value}")
        print()

    print()
    return 0


# ============================================================================
# Command: hermes state init
# ============================================================================

def cmd_state_init(args):
    """Initialize AIBD state schemas."""
    if not ensure_state_machine():
        return 1

    print()
    print(color("┌─────────────────────────────────────────────────────────┐", Colors.CYAN))
    print(color("│         Initialize AIBD State Schemas                │", Colors.CYAN))
    print(color("└─────────────────────────────────────────────────────────┘", Colors.CYAN))
    print()

    try:
        AIBDStateIntegration.register_aibd_schemas()

        print(color("✓ AIBD state schemas registered successfully", Colors.GREEN))
        print()
        print("Available schemas:")
        print("  - aibd_sales: Sales workflow state machine")
        print("  - aibd_task_dispatch: Task dispatch state machine")
        print()
        return 0

    except Exception as e:
        print(color(f"Error: {e}", Colors.RED))
        print()
        return 1


# ============================================================================
# Argument Parser Setup
# ============================================================================

def setup_state_parser(subparsers):
    """Setup state CLI commands."""
    state_parser = subparsers.add_parser(
        "state",
        help="Manage agent state machines",
        description="View and manage agent state machines for explicit state tracking"
    )
    state_subparsers = state_parser.add_subparsers(dest="state_command")

    # state list
    list_parser = state_subparsers.add_parser(
        "list",
        help="List all active state machines"
    )
    list_parser.set_defaults(func=cmd_state_list)

    # state get
    get_parser = state_subparsers.add_parser(
        "get",
        help="Get state machine details"
    )
    get_parser.add_argument(
        "agent_id",
        help="Agent ID (session ID)"
    )
    get_parser.add_argument(
        "--schema", "-s",
        help="Schema name (optional)"
    )
    get_parser.set_defaults(func=cmd_state_get)

    # state history
    history_parser = state_subparsers.add_parser(
        "history",
        help="View state change history"
    )
    history_parser.add_argument(
        "agent_id",
        help="Agent ID (session ID)"
    )
    history_parser.add_argument(
        "--schema", "-s",
        help="Schema name (optional)"
    )
    history_parser.add_argument(
        "--limit", "-n",
        type=int,
        default=10,
        help="Number of history entries to show (default: 10)"
    )
    history_parser.set_defaults(func=cmd_state_history)

    # state reset
    reset_parser = state_subparsers.add_parser(
        "reset",
        help="Reset state machine to initial state"
    )
    reset_parser.add_argument(
        "agent_id",
        help="Agent ID (session ID)"
    )
    reset_parser.add_argument(
        "--schema", "-s",
        help="Schema name (optional)"
    )
    reset_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Skip confirmation prompt"
    )
    reset_parser.set_defaults(func=cmd_state_reset)

    # state schemas
    schemas_parser = state_subparsers.add_parser(
        "schemas",
        help="List all registered state schemas"
    )
    schemas_parser.set_defaults(func=cmd_state_schemas)

    # state schema
    schema_parser = state_subparsers.add_parser(
        "schema",
        help="Show details for a specific schema"
    )
    schema_parser.add_argument(
        "name",
        help="Schema name"
    )
    schema_parser.set_defaults(func=cmd_state_schema)

    # state init
    init_parser = state_subparsers.add_parser(
        "init",
        help="Initialize AIBD state schemas"
    )
    init_parser.set_defaults(func=cmd_state_init)

    return state_parser
