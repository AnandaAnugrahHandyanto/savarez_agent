from eclose.events import get_event_bus
from eclose.perception import (
    ProjectPerceptionAgent,
    WorldPerceptionAgent,
    SelfPerceptionAgent,
    TaskPerceptionAgent,
)
from eclose.evolution import (
    GapAnalysisEngine,
    ProposalGenerator,
    ApprovalWorkflow,
    ExecutionEngine,
    VerificationLayer,
)


class EcloseIntegration:
    """Integration layer connecting Eclose system with Hermes AIAgent."""

    def __init__(self, hermes_state=None, tool_registry=None):
        """
        Initialize Eclose integration with Hermes.

        Args:
            hermes_state: Optional Hermes session state (SessionDB instance)
            tool_registry: Optional Hermes tool registry
        """
        self.hermes_state = hermes_state
        self.tool_registry = tool_registry
        self.event_bus = get_event_bus()

        # Initialize perception agents with Hermes context
        self.project_agent = ProjectPerceptionAgent()
        self.world_agent = WorldPerceptionAgent()
        self.self_agent = SelfPerceptionAgent()
        self.task_agent = TaskPerceptionAgent()

        # Initialize evolution system
        self.gap_engine = GapAnalysisEngine()
        self.proposal_gen = ProposalGenerator()
        self.approval_workflow = ApprovalWorkflow()
        self.execution_engine = ExecutionEngine()
        self.verification = VerificationLayer()

        # Subscribe to events
        self._setup_event_subscriptions()

    def _setup_event_subscriptions(self):
        """Subscribe to perception events for gap analysis."""
        from eclose.events.events import EventType

        self.event_bus.subscribe(EventType.PERCEPTION, self._on_perception)

    def _on_perception(self, event):
        """Handle perception events and trigger gap analysis."""
        # Analyze perception data for gaps
        needs = self._extract_needs(event)
        capabilities = self._get_capabilities()

        gaps = self.gap_engine.identify_gaps(needs, capabilities)

        # Generate proposals for identified gaps
        for gap in gaps:
            proposal = self.proposal_gen.generate_proposal(gap)
            self.approval_workflow.submit_for_approval(proposal)

    def _extract_needs(self, event):
        """Extract needs from perception events."""
        # Task needs from current task context
        needs = []

        if event.source.value == "task":
            task_data = event.data.get("current_task", {})
            if task_data:
                # Extract needs from task requirements
                task_type = task_data.get("type", "")
                if task_type:
                    needs.append(task_type)

        return needs

    def _get_capabilities(self):
        """Get current capabilities from Hermes tool registry."""
        capabilities = []

        # Base capabilities
        base_caps = self.self_agent._get_capabilities()
        capabilities.extend([c["name"] for c in base_caps])

        # Add Hermes tools if available
        if self.tool_registry:
            # TODO: Integrate with actual Hermes tool registry
            pass

        return capabilities

    def perceive_all(self):
        """Trigger perception from all agents."""
        self.project_agent.perceive()
        self.world_agent.perceive()
        self.self_agent.perceive()

    def set_task_context(self, task: dict):
        """Set the current task context for task perception."""
        self.task_agent.set_current_task(task)
        self.task_agent.perceive()

    def get_pending_approvals(self) -> list:
        """Get proposals pending approval."""
        return self.approval_workflow.get_pending()

    def run_evolution_cycle(self):
        """Run a complete evolution cycle: perceive -> analyze -> propose."""
        print("Starting evolution cycle...")

        # 1. Perceive
        print("\n[1/3] Perception...")
        self.perceive_all()

        # 2. Analyze (handled via event subscription)
        print("\n[2/3] Analysis...")

        # 3. Proposals
        print("\n[3/3] Proposals generated")
        pending = self.get_pending_approvals()
        print(f"  {len(pending)} proposals pending approval")

        return pending