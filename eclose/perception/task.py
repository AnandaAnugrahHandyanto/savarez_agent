from eclose.perception.base import BasePerceptionAgent
from eclose.events.events import PerceptionSource


class TaskPerceptionAgent(BasePerceptionAgent):
    """Perception agent that understands the current task context."""

    def __init__(self):
        super().__init__(name="TaskPerception", source=PerceptionSource.TASK)
        self.current_task = None

    def set_current_task(self, task: dict):
        """Set the current task context."""
        self.current_task = task

    async def _感知(self) -> dict:
        """Perceive task context - goal, constraints, progress."""
        if not self.current_task:
            return {"status": "no_active_task"}

        return {
            "current_task": self.current_task,
            "context": self._extract_context(),
            "constraints": self.current_task.get("constraints", {}),
            "progress": self._track_progress(),
        }

    def _extract_context(self) -> dict:
        """Extract relevant context from task."""
        return {
            "conversation_history": self.current_task.get("history", []),
            "relevant_files": self.current_task.get("files", []),
        }

    def _track_progress(self) -> dict:
        """Track task progress."""
        return {
            "completed": self.current_task.get("completed", []),
            "pending": self.current_task.get("pending", []),
            "blockers": self.current_task.get("blockers", []),
        }
