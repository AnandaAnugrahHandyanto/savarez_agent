"""
Eclose CLI - Command-line interface for the Eclose self-evolution system.

Usage:
    python -m eclose.cli [command] [options]

Commands:
    perceive     Trigger perception from all agents
    status      Show current system status
    proposals   List pending evolution proposals
    approve     Approve a proposal
    reject      Reject a proposal
    history     Show evolution history
"""

import argparse
import sys
import json
from eclose import (
    get_event_bus,
    ProjectPerceptionAgent,
    WorldPerceptionAgent,
    SelfPerceptionAgent,
    TaskPerceptionAgent,
    GapAnalysisEngine,
    ProposalGenerator,
    ApprovalWorkflow,
    ExecutionEngine,
    VerificationLayer,
)


def cmd_perceive(args):
    """Trigger perception from all agents."""
    print("Triggering perception...")

    project_agent = ProjectPerceptionAgent(project_path=args.path)
    world_agent = WorldPerceptionAgent()
    self_agent = SelfPerceptionAgent()

    print("\n[Project Perception]")
    project_event = project_agent.perceive()
    print(f"  Source: {project_event.source.value}")
    print(f"  Confidence: {project_event.confidence}")
    print(f"  Data: {json.dumps(project_event.data, indent=2)}")

    print("\n[World Perception]")
    world_event = world_agent.perceive()
    print(f"  Source: {world_event.source.value}")
    print(f"  Confidence: {world_event.confidence}")
    print(f"  Data: {json.dumps(world_event.data, indent=2)}")

    print("\n[Self Perception]")
    self_event = self_agent.perceive()
    print(f"  Source: {self_event.source.value}")
    print(f"  Confidence: {self_event.confidence}")
    print(f"  Data: {json.dumps(self_event.data, indent=2)}")

    print("\nPerception complete!")


def cmd_status(args):
    """Show current system status."""
    print("Eclose System Status")
    print("=" * 40)

    event_bus = get_event_bus()
    print(f"Event Bus: Active")

    self_agent = SelfPerceptionAgent()
    print(f"\nSelf Perception Capabilities:")
    for cap in self_agent._get_capabilities():
        print(f"  - {cap['name']}: {cap['confidence']}")

    print(f"\nKnown Limitations:")
    for limit in self_agent._get_limitations():
        print(f"  - {limit}")


def cmd_proposals(args):
    """List pending evolution proposals."""
    approval_workflow = ApprovalWorkflow()

    pending = approval_workflow.get_pending()

    if not pending:
        print("No pending proposals.")
        return

    print(f"Pending Proposals ({len(pending)}):")
    print("=" * 40)

    for proposal in pending:
        print(f"\n[{proposal.id}] {proposal.title}")
        print(f"  Gap: {proposal.gap.description if proposal.gap else 'N/A'}")
        print(f"  Severity: {proposal.gap.severity.value if proposal.gap else 'N/A'}")
        print(f"  Approach: {proposal.solution.get('approach', 'N/A')}")


def cmd_approve(args):
    """Approve a proposal."""
    approval_workflow = ApprovalWorkflow()
    proposal_id = args.proposal_id

    if approval_workflow.approve(proposal_id):
        print(f"Proposal {proposal_id} approved!")
    else:
        print(f"Proposal {proposal_id} not found.")


def cmd_reject(args):
    """Reject a proposal."""
    approval_workflow = ApprovalWorkflow()
    proposal_id = args.proposal_id
    reason = args.reason

    if approval_workflow.reject(proposal_id, reason):
        print(f"Proposal {proposal_id} rejected!")
    else:
        print(f"Proposal {proposal_id} not found.")


def cmd_history(args):
    """Show evolution history."""
    execution_engine = ExecutionEngine()

    if not execution_engine.execution_history:
        print("No evolution history.")
        return

    print(f"Evolution History ({len(execution_engine.execution_history)} entries):")
    print("=" * 40)

    for result in execution_engine.execution_history:
        print(f"\n[{result.proposal_id}] Status: {result.status}")
        print(f"  Steps completed: {len(result.results.get('steps_completed', []))}")
        print(f"  Steps failed: {len(result.results.get('steps_failed', []))}")


def main():
    parser = argparse.ArgumentParser(
        description="Eclose - Self-Evolving AI Agent System"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # perceive command
    perceive_parser = subparsers.add_parser(
        "perceive", help="Trigger perception from all agents"
    )
    perceive_parser.add_argument(
        "--path", "-p", default=".", help="Project path to analyze"
    )

    # status command
    subparsers.add_parser("status", help="Show current system status")

    # proposals command
    subparsers.add_parser("proposals", help="List pending evolution proposals")

    # approve command
    approve_parser = subparsers.add_parser(
        "approve", help="Approve a proposal"
    )
    approve_parser.add_argument("proposal_id", help="ID of proposal to approve")

    # reject command
    reject_parser = subparsers.add_parser(
        "reject", help="Reject a proposal"
    )
    reject_parser.add_argument("proposal_id", help="ID of proposal to reject")
    reject_parser.add_argument(
        "--reason", "-r", default=None, help="Reason for rejection"
    )

    # history command
    subparsers.add_parser("history", help="Show evolution history")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    if args.command == "perceive":
        cmd_perceive(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "proposals":
        cmd_proposals(args)
    elif args.command == "approve":
        cmd_approve(args)
    elif args.command == "reject":
        cmd_reject(args)
    elif args.command == "history":
        cmd_history(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
