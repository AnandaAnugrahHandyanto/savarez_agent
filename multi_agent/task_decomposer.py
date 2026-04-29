#!/usr/bin/env python3
"""
Task Decomposer - Automatic Task Decomposition Engine

Breaks down complex tasks into parallelizable subtasks organized as a DAG (Directed Acyclic Graph).

Supports three dependency modes:
1. SERIAL: Tasks must execute in sequence
2. PARALLEL: Tasks can execute concurrently  
3. CONDITIONAL: Tasks execute based on conditions/results of other tasks

The decomposer outputs a structured task graph that the AgentPool uses to:
- Schedule task execution
- Manage dependencies
- Handle conditional branching
- Track task completion
"""

import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class DependencyType(Enum):
    """Defines how a task depends on other tasks."""
    NONE = "none"           # No dependencies, runs immediately
    SERIAL = "serial"       # Must wait for all blocking tasks to complete
    PARALLEL = "parallel"   # Can run concurrently with blocking tasks
    CONDITIONAL = "conditional"  # Runs only if condition is met


@dataclass
class TaskDependency:
    """
    Represents a dependency relationship between tasks.
    """
    task_id: str                    # ID of the task this depends on
    dependency_type: DependencyType = DependencyType.SERIAL
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None  # For CONDITIONAL type
    # For CONDITIONAL: function that receives completed task results and returns bool


@dataclass
class Task:
    """
    A single unit of work in a decomposed task graph.
    """
    task_id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    goal: str = ""                  # The objective/prompt for this task
    context: Optional[str] = None  # Additional context
    toolsets: List[str] = field(default_factory=list)  # Toolset restrictions
    depends_on: List[TaskDependency] = field(default_factory=list)
    timeout: int = 300              # Seconds before task is considered hung
    priority: int = 0                # Higher = more priority (for scheduling)
    max_retries: int = 2            # Number of retry attempts on failure
    
    # Role/specialization for the agent handling this task
    role: Optional[str] = None      # e.g., "researcher", "coder", "reviewer"
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Runtime state (set by TaskDecomposer)
    status: str = "pending"  # pending, ready, running, completed, failed, skipped
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    def __hash__(self):
        return hash(self.task_id)
    
    def __eq__(self, other):
        if not isinstance(other, Task):
            return False
        return self.task_id == other.task_id


@dataclass
class TaskGraph:
    """
    A directed acyclic graph (DAG) of tasks with their dependencies.
    """
    tasks: Dict[str, Task] = field(default_factory=dict)
    root_task_ids: List[str] = field(default_factory=list)  # Tasks with no dependencies
    
    def add_task(self, task: Task) -> None:
        """Add a task to the graph."""
        self.tasks[task.task_id] = task
        if not task.depends_on:
            self.root_task_ids.append(task.task_id)
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self.tasks.get(task_id)
    
    def get_ready_tasks(self) -> List[Task]:
        """Get tasks that are ready to execute (all dependencies complete)."""
        ready = []
        for task in self.tasks.values():
            if task.status != "pending":
                continue
            
            # Check if all dependencies are satisfied
            all_done = True
            for dep in task.depends_on:
                dep_task = self.tasks.get(dep.task_id)
                if dep_task is None:
                    # Dependency task doesn't exist - skip
                    logger.warning(f"Task {task.task_id} depends on unknown task {dep.task_id}")
                    continue
                
                if dep.dependency_type == DependencyType.NONE:
                    continue
                elif dep.dependency_type == DependencyType.SERIAL:
                    if dep_task.status != "completed":
                        all_done = False
                        break
                elif dep.dependency_type == DependencyType.PARALLEL:
                    # Parallel means it can run concurrently - no blocking
                    continue
                elif dep.dependency_type == DependencyType.CONDITIONAL:
                    if dep.condition and dep.condition(dep_task.result or {}):
                        continue  # Condition met, don't block
                    elif not dep.condition:
                        continue
                    else:
                        all_done = False
                        break
            
            if all_done:
                ready.append(task)
        
        # Sort by priority (higher first)
        ready.sort(key=lambda t: t.priority, reverse=True)
        return ready
    
    def mark_completed(self, task_id: str, result: Any) -> None:
        """Mark a task as completed with its result."""
        task = self.tasks.get(task_id)
        if task:
            task.status = "completed"
            task.result = result
    
    def mark_failed(self, task_id: str, error: str) -> None:
        """Mark a task as failed with an error."""
        task = self.tasks.get(task_id)
        if task:
            task.status = "failed"
            task.error = error
    
    def is_complete(self) -> bool:
        """Check if all non-conditional tasks are complete."""
        for task in self.tasks.values():
            if task.status not in ("completed", "failed", "skipped"):
                return False
        return True
    
    def get_execution_order(self) -> List[List[str]]:
        """
        Get tasks grouped by execution level (for visualization/debugging).
        Returns list of task ID groups, where each group can execute in parallel.
        """
        levels = []
        remaining = set(self.tasks.keys())
        completed = set()
        
        while remaining:
            # Find tasks whose dependencies are all satisfied
            current_level = []
            for task_id in list(remaining):
                task = self.tasks[task_id]
                
                # Check if all SERIAL dependencies are met
                can_execute = True
                for dep in task.depends_on:
                    if dep.dependency_type == DependencyType.SERIAL:
                        dep_task = self.tasks.get(dep.task_id)
                        if dep_task and dep_task.status != "completed":
                            can_execute = False
                            break
                    elif dep.dependency_type == DependencyType.CONDITIONAL:
                        dep_task = self.tasks.get(dep.task_id)
                        if dep_task and dep_task.status == "completed":
                            if dep.condition and not dep.condition(dep_task.result or {}):
                                can_execute = False
                                break
                
                if can_execute:
                    current_level.append(task_id)
            
            if not current_level:
                # Deadlock or circular dependency
                logger.error(f"Cannot resolve execution order. Remaining: {remaining}")
                break
            
            levels.append(current_level)
            for task_id in current_level:
                remaining.remove(task_id)
                completed.add(task_id)
        
        return levels


class TaskDecomposer:
    """
    Decomposes complex tasks into parallelizable subtask graphs.
    
    Uses LLM-based decomposition to:
    1. Analyze the input task
    2. Identify subtasks that can run in parallel
    3. Determine dependencies between subtasks
    4. Output a structured TaskGraph
    
    Supports manual decomposition via direct Task creation as well.
    """
    
    def __init__(self, parent_agent: Any = None):
        """
        Initialize the TaskDecomposer.
        
        Args:
            parent_agent: Optional AIAgent instance for LLM-based decomposition
        """
        self.parent_agent = parent_agent
    
    def decompose(
        self,
        task: str,
        mode: str = "auto",
        context: Optional[str] = None,
        max_parallel: int = 5,
    ) -> TaskGraph:
        """
        Decompose a complex task into a task graph.
        
        Args:
            task: The high-level task description
            mode: Decomposition mode - "auto" (LLM), "manual", or "template"
            context: Additional context for decomposition
            max_parallel: Maximum number of tasks that can run in parallel
            
        Returns:
            TaskGraph with decomposed subtasks
        """
        if mode == "auto":
            return self._llm_decompose(task, context, max_parallel)
        elif mode == "manual":
            return self._manual_decompose(task, context)
        elif mode == "template":
            return self._template_decompose(task, context)
        else:
            raise ValueError(f"Unknown decomposition mode: {mode}")
    
    def _llm_decompose(
        self,
        task: str,
        context: Optional[str],
        max_parallel: int,
    ) -> TaskGraph:
        """
        Use LLM to intelligently decompose the task.
        
        This method constructs a prompt that asks the LLM to analyze the task
        and produce a structured decomposition.
        """
        # If no parent agent, fall back to simple decomposition
        if not self.parent_agent:
            logger.warning("No parent agent available for LLM decomposition, using simple mode")
            return self._simple_decompose(task, context)
        
        prompt = self._build_decomposition_prompt(task, context, max_parallel)
        
        # Call LLM for decomposition
        try:
            # Use delegate_task-like approach to get decomposition
            # For now, fall back to simple decomposition
            logger.info("LLM decomposition requested but using simple fallback")
            return self._simple_decompose(task, context)
        except Exception as e:
            logger.error(f"LLM decomposition failed: {e}")
            return self._simple_decompose(task, context)
    
    def _build_decomposition_prompt(
        self,
        task: str,
        context: Optional[str],
        max_parallel: int,
    ) -> str:
        """Build the prompt for LLM-based decomposition."""
        return f"""Analyze this complex task and decompose it into parallelizable subtasks:

TASK: {task}

CONTEXT: {context or 'No additional context provided'}

Please decompose this into subtasks following these rules:
1. Identify independent subtasks that can run in PARALLEL
2. Identify sequential subtasks that must run in SERIAL
3. Identify conditional subtasks that depend on results of other tasks
4. Keep each subtask focused and atomic
5. Maximum {max_parallel} tasks should run in parallel

Output your decomposition as a JSON structure:
{{
  "tasks": [
    {{
      "task_id": "unique_id",
      "goal": "subtask description",
      "context": "optional context for this subtask",
      "toolsets": ["toolset1", "toolset2"],
      "depends_on": [
        {{"task_id": "dep_id", "type": "serial|parallel|conditional", "condition": "optional condition expression"}}
      ],
      "role": "optional role specialization"
    }}
  ]
}}
"""
    
    def _simple_decompose(self, task: str, context: Optional[str]) -> TaskGraph:
        """
        Simple decomposition that creates a single task or parallel tasks
        based on obvious breaks in the task description.
        """
        graph = TaskGraph()
        
        # Create a single root task with the full goal
        root = Task(
            goal=task,
            context=context,
            role="generalist",
        )
        graph.add_task(root)
        
        return graph
    
    def _manual_decompose(self, task: str, context: Optional[str]) -> TaskGraph:
        """
        Manual decomposition - allows direct Task creation via API.
        """
        # This would be called programmatically to add tasks
        graph = TaskGraph()
        
        # Create a placeholder root
        root = Task(
            goal=task,
            context=context,
        )
        graph.add_task(root)
        
        return graph
    
    def _template_decompose(self, task: str, context: Optional[str]) -> TaskGraph:
        """
        Template-based decomposition using predefined patterns.
        """
        # Check for common patterns
        task_lower = task.lower()
        
        graph = TaskGraph()
        
        # Research + Execute pattern
        if any(kw in task_lower for kw in ["research", "find", "search", "investigate"]):
            if any(kw in task_lower for kw in ["implement", "create", "build", "write", "code"]):
                return self._create_research_execute_graph(task, context)
        
        # Parallel exploration pattern
        if any(kw in task_lower for kw in ["compare", "evaluate", "analyze", "review"]):
            if " vs " in task_lower or " or " in task_lower:
                return self._create_comparison_graph(task, context)
        
        # Default: single task
        root = Task(goal=task, context=context)
        graph.add_task(root)
        return graph
    
    def _create_research_execute_graph(self, task: str, context: Optional[str]) -> TaskGraph:
        """Create a research -> execute dependency graph."""
        graph = TaskGraph()
        
        research = Task(
            task_id="research",
            goal=f"Research and gather information for: {task}",
            context=context,
            role="researcher",
            depends_on=[],
        )
        
        execute = Task(
            task_id="execute",
            goal=f"Implement/action based on: {task}",
            context=context,
            role="coder",
            depends_on=[
                TaskDependency(task_id="research", dependency_type=DependencyType.SERIAL)
            ],
        )
        
        graph.add_task(research)
        graph.add_task(execute)
        
        return graph
    
    def _create_comparison_graph(self, task: str, context: Optional[str]) -> TaskGraph:
        """Create a parallel comparison graph."""
        graph = TaskGraph()
        
        # Split task by " vs " or " or "
        parts = []
        if " vs " in task:
            parts = [p.strip() for p in task.split(" vs ")]
        elif " or " in task:
            parts = [p.strip() for p in task.split(" or ")]
        
        if len(parts) >= 2:
            for i, part in enumerate(parts):
                sub_task = Task(
                    task_id=f"option_{i}",
                    goal=f"Analyze and evaluate: {part}",
                    context=context,
                    role="analyst",
                    depends_on=[],
                    priority=i,
                )
                graph.add_task(sub_task)
            
            # Add synthesis task
            synthesis = Task(
                task_id="synthesize",
                goal=f"Compare and synthesize results from all options for: {task}",
                context=context,
                role="reviewer",
                depends_on=[TaskDependency(task_id=f"option_{i}") for i in range(len(parts))],
            )
            graph.add_task(synthesis)
        else:
            # Fallback to single task
            root = Task(goal=task, context=context)
            graph.add_task(root)
        
        return graph
    
    @staticmethod
    def create_parallel_tasks(
        goals: List[str],
        context: Optional[str] = None,
        toolsets: Optional[List[str]] = None,
    ) -> TaskGraph:
        """
        Create a task graph with multiple parallel tasks.
        
        Args:
            goals: List of task goals
            context: Shared context for all tasks
            toolsets: Shared toolsets for all tasks
            
        Returns:
            TaskGraph with parallel tasks
        """
        graph = TaskGraph()
        
        for i, goal in enumerate(goals):
            task = Task(
                task_id=f"parallel_{i}",
                goal=goal,
                context=context,
                toolsets=toolsets or [],
                depends_on=[],
                priority=i,
            )
            graph.add_task(task)
        
        return graph
    
    @staticmethod
    def create_serial_tasks(
        goals: List[str],
        context: Optional[str] = None,
        toolsets: Optional[List[str]] = None,
    ) -> TaskGraph:
        """
        Create a task graph with sequential tasks.
        
        Args:
            goals: List of task goals in execution order
            context: Shared context for all tasks
            toolsets: Shared toolsets for all tasks
            
        Returns:
            TaskGraph with serial tasks
        """
        graph = TaskGraph()
        prev_task_id = None
        
        for i, goal in enumerate(goals):
            depends_on = []
            if prev_task_id:
                depends_on.append(
                    TaskDependency(task_id=prev_task_id, dependency_type=DependencyType.SERIAL)
                )
            
            task = Task(
                task_id=f"serial_{i}",
                goal=goal,
                context=context,
                toolsets=toolsets or [],
                depends_on=depends_on,
            )
            graph.add_task(task)
            prev_task_id = task.task_id
        
        return graph
