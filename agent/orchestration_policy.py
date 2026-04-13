"""Pure orchestration policy for SDAO phase 1.

This module intentionally contains no runtime wiring. It only decides the
preferred orchestration mode from a small set of task-shape signals.
"""

from typing import Literal, Optional

ComplexityBand = Literal["simple", "medium", "complex"]
OrchestrationMode = Literal["solo", "sequential", "parallel"]


def decide_orchestration_mode(
    *,
    task_count_estimate: int,
    has_dependencies: bool,
    complexity: ComplexityBand,
    subtasks_independent: Optional[bool],
    explicit_no_subagents: bool,
) -> OrchestrationMode:
    """Return the preferred SDAO orchestration mode.

    Tie-break policy:
    - prefer solo when signals are weak or ambiguous
    - if not solo, prefer sequential over parallel
    """
    if explicit_no_subagents:
        return "solo"

    if task_count_estimate <= 1:
        if complexity == "complex" and has_dependencies:
            return "sequential"
        return "solo"

    if has_dependencies:
        return "sequential" if complexity == "complex" else "solo"

    if complexity == "complex" and subtasks_independent is True and task_count_estimate >= 2:
        return "parallel"

    return "solo"
