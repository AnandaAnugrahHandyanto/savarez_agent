"""
Eclose Approval TUI - Simple terminal UI for viewing and approving evolution proposals.

A simple text-based TUI for reviewing pending evolution proposals
and approving/rejecting them.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eclose.evolution import ApprovalWorkflow, ExecutionEngine
from eclose.evolution.proposal import EvolutionProposal


class ApprovalTUI:
    """Simple text-based TUI for proposal approval."""

    def __init__(self):
        self.approval_workflow = ApprovalWorkflow()
        self.execution_engine = ExecutionEngine()
        self.running = True

    def clear_screen(self):
        """Clear the terminal screen."""
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_header(self):
        """Print the TUI header."""
        print("=" * 60)
        print("  Eclose - Evolution Proposal Approval")
        print("=" * 60)
        print()

    def print_menu(self):
        """Print the main menu."""
        print("Options:")
        print("  [1] View pending proposals")
        print("  [2] Approve a proposal")
        print("  [3] Reject a proposal")
        print("  [4] View history")
        print("  [5] Run evolution cycle")
        print("  [q] Quit")
        print()

    def view_pending(self):
        """View pending proposals."""
        self.clear_screen()
        self.print_header()

        pending = self.approval_workflow.get_pending()

        if not pending:
            print("No pending proposals.")
            print()
            return

        print(f"Pending Proposals ({len(pending)}):")
        print("-" * 60)

        for i, proposal in enumerate(pending, 1):
            print(f"\n[{i}] {proposal.title}")
            print(f"    ID: {proposal.id}")
            if proposal.gap:
                print(f"    Gap: {proposal.gap.description}")
                print(f"    Severity: {proposal.gap.severity.value}")
            print(f"    Approach: {proposal.solution.get('approach', 'N/A')}")
            print(f"    Steps: {len(proposal.solution.get('steps', []))}")

        print()

    def approve_proposal(self):
        """Approve a proposal."""
        self.clear_screen()
        self.print_header()

        pending = self.approval_workflow.get_pending()

        if not pending:
            print("No pending proposals to approve.")
            print()
            return

        print("Pending Proposals:")
        for i, proposal in enumerate(pending, 1):
            print(f"  [{i}] {proposal.id}: {proposal.title}")

        print()
        choice = input("Enter proposal number to approve (or Enter to cancel): ")

        if not choice:
            return

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(pending):
                proposal = pending[idx]
                if self.approval_workflow.approve(proposal.id):
                    print(f"\n✓ Proposal {proposal.id} approved!")
                    print("\nExecuting evolution...")

                    # Execute the proposal
                    result = self.execution_engine.execute(proposal)
                    print(f"\nExecution result: {result.status}")
                    print(f"Steps completed: {len(result.results.get('steps_completed', []))}")

                    if result.results.get('steps_failed'):
                        print(f"Steps failed: {len(result.results.get('steps_failed', []))}")
                else:
                    print(f"Failed to approve proposal.")
            else:
                print("Invalid selection.")
        except ValueError:
            print("Invalid input.")

        print()

    def reject_proposal(self):
        """Reject a proposal."""
        self.clear_screen()
        self.print_header()

        pending = self.approval_workflow.get_pending()

        if not pending:
            print("No pending proposals to reject.")
            print()
            return

        print("Pending Proposals:")
        for i, proposal in enumerate(pending, 1):
            print(f"  [{i}] {proposal.id}: {proposal.title}")

        print()
        choice = input("Enter proposal number to reject (or Enter to cancel): ")

        if not choice:
            return

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(pending):
                proposal = pending[idx]
                reason = input("Enter rejection reason (optional): ")
                if self.approval_workflow.reject(proposal.id, reason):
                    print(f"\n✓ Proposal {proposal.id} rejected!")
                else:
                    print(f"Failed to reject proposal.")
            else:
                print("Invalid selection.")
        except ValueError:
            print("Invalid input.")

        print()

    def view_history(self):
        """View evolution history."""
        self.clear_screen()
        self.print_header()

        history = self.execution_engine.execution_history

        if not history:
            print("No evolution history.")
            print()
            return

        print(f"Evolution History ({len(history)} entries):")
        print("-" * 60)

        for result in history:
            print(f"\n[{result.proposal_id}] Status: {result.status}")
            print(f"  Steps completed: {len(result.results.get('steps_completed', []))}")
            print(f"  Steps failed: {len(result.results.get('steps_failed', []))}")
            print(f"  Verification: {'PASSED' if result.verification.get('passed') else 'FAILED'}")

        print()

    def run_evolution_cycle(self):
        """Run the evolution cycle (placeholder - would integrate with full system)."""
        self.clear_screen()
        self.print_header()

        print("Evolution Cycle")
        print("-" * 60)
        print("This would trigger:")
        print("  1. Perception from all agents")
        print("  2. Gap analysis")
        print("  3. Proposal generation")
        print()
        print("Note: Full integration with Hermes AIAgent required.")
        print()

    def run(self):
        """Run the main TUI loop."""
        while self.running:
            self.clear_screen()
            self.print_header()
            self.print_menu()

            choice = input("Select option: ").strip().lower()

            if choice == '1':
                self.view_pending()
            elif choice == '2':
                self.approve_proposal()
            elif choice == '3':
                self.reject_proposal()
            elif choice == '4':
                self.view_history()
            elif choice == '5':
                self.run_evolution_cycle()
            elif choice == 'q':
                self.running = False
                print("Goodbye!")
            else:
                print("Invalid option.")
                print()

            if self.running:
                input("Press Enter to continue...")


def main():
    """Main entry point."""
    tui = ApprovalTUI()
    tui.run()


if __name__ == "__main__":
    main()
