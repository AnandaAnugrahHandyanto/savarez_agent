#!/usr/bin/env python3
"""
Agent Team System - Multi-Subagent Collaboration

Inspired by Claude Code's /agents feature. Provides a TeamLeader that coordinates
multiple TeammateAgent instances, each with a specific role, working together
on complex tasks.

Team Types:
  - code-review: [explorer, reviewer, summarizer]
  - feature-dev: [architect, coder, tester]
  - research: [searcher, analyzer, writer]

Communication:
  - Shared TeamState (in-memory, not file-based)
  - TeamMessage for inter-agent messaging
  - Broadcast support for leader → all members
  - Direct messaging for targeted communication
"""

import json
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MessageType(Enum):
    TASK = "task"
    RESULT = "result"
    BROADCAST = "broadcast"
    STATUS = "status"
    ERROR = "error"
    STOP = "stop"


@dataclass
class TeamMessage:
    """Message format for inter-agent communication."""
    msg_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    msg_type: MessageType = MessageType.TASK
    sender: str = ""
    recipient: str = ""  # "" means broadcast
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "msg_id": self.msg_id,
            "msg_type": self.msg_type.value,
            "sender": self.sender,
            "recipient": self.recipient,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TeamMessage":
        return cls(
            msg_id=d.get("msg_id", uuid.uuid4().hex[:8]),
            msg_type=MessageType(d.get("msg_type", "task")),
            sender=d.get("sender", ""),
            recipient=d.get("recipient", ""),
            content=d.get("content", ""),
            metadata=d.get("metadata", {}),
            timestamp=d.get("timestamp", time.time()),
        )


class TeamState:
    """Shared in-memory state for team communication."""

    def __init__(self, team_id: str):
        self.team_id = team_id
        self.lock = threading.RLock()
        self.messages: List[TeamMessage] = []
        self.pending_tasks: Dict[str, Dict[str, Any]] = {}
        self.completed_tasks: Dict[str, Dict[str, Any]] = {}
        self.member_states: Dict[str, Dict[str, Any]] = {}
        self.active = False
        self.created_at = time.time()

    def add_message(self, msg: TeamMessage) -> None:
        with self.lock:
            self.messages.append(msg)

    def get_messages(self, recipient: str = "", msg_type: MessageType = None) -> List[TeamMessage]:
        with self.lock:
            results = list(self.messages)
            if recipient:
                results = [m for m in results if m.recipient == recipient or m.recipient == ""]
            if msg_type:
                results = [m for m in results if m.msg_type == msg_type]
            return results

    def add_task(self, task_id: str, task: Dict[str, Any]) -> None:
        with self.lock:
            self.pending_tasks[task_id] = task

    def complete_task(self, task_id: str, result: Dict[str, Any]) -> None:
        with self.lock:
            if task_id in self.pending_tasks:
                task = self.pending_tasks.pop(task_id)
                task["result"] = result
                task["completed_at"] = time.time()
                self.completed_tasks[task_id] = task

    def get_pending_tasks(self) -> Dict[str, Dict[str, Any]]:
        with self.lock:
            return dict(self.pending_tasks)

    def get_completed_tasks(self) -> Dict[str, Dict[str, Any]]:
        with self.lock:
            return dict(self.completed_tasks)

    def update_member_state(self, member: str, state: Dict[str, Any]) -> None:
        with self.lock:
            if member not in self.member_states:
                self.member_states[member] = {}
            self.member_states[member].update(state)

    def get_member_state(self, member: str) -> Dict[str, Any]:
        with self.lock:
            return dict(self.member_states.get(member, {}))

    def get_all_member_states(self) -> Dict[str, Dict[str, Any]]:
        with self.lock:
            return dict(self.member_states)


_TEAM_REGISTRY: Dict[str, "Team"] = {}
_REGISTRY_LOCK = threading.RLock()


class Team:
    """Manages a team of agents working collaboratively."""

    TEAM_TYPES = {
        "code-review": ["explorer", "reviewer", "summarizer"],
        "feature-dev": ["architect", "coder", "tester"],
        "research": ["searcher", "analyzer", "writer"],
    }

    ROLE_SYSTEM_PROMPTS = {
        "explorer": "You are a code explorer. Find and analyze relevant files, understand project structure, and identify key components related to the task.",
        "reviewer": "You are a code reviewer. Analyze code quality, identify issues, suggest improvements, and ensure best practices are followed.",
        "summarizer": "You are a summarizer. Synthesize findings from team members into clear, concise summaries and final reports.",
        "architect": "You are a software architect. Design system structures, make technology decisions, and plan implementation approaches.",
        "coder": "You are a coder. Implement features, write clean code, and handle technical details of the implementation.",
        "tester": "You are a tester. Design and write tests, verify functionality, and ensure code quality meets standards.",
        "searcher": "You are a researcher. Search for information, gather data, and compile findings on the given topic.",
        "analyzer": "You are an analyzer. Analyze data and information, identify patterns, and provide insights.",
        "writer": "You are a writer. Create clear, well-structured written content based on research and analysis.",
    }

    def __init__(self, team_type: str, team_id: str = None):
        if team_type not in self.TEAM_TYPES:
            raise ValueError(f"Unknown team type: {team_type}. Available: {list(self.TEAM_TYPES.keys())}")

        self.team_id = team_id or f"team-{uuid.uuid4().hex[:8]}"
        self.team_type = team_type
        self.state = TeamState(self.team_id)
        self.members: Dict[str, "TeammateAgent"] = {}
        self.leader: Optional["TeamLeader"] = None
        self.state.active = True

    def add_member(self, role: str, agent: "TeammateAgent") -> None:
        with _REGISTRY_LOCK:
            self.members[role] = agent
            self.state.update_member_state(role, {"status": "ready", "added_at": time.time()})

    def remove_member(self, role: str) -> None:
        with _REGISTRY_LOCK:
            if role in self.members:
                del self.members[role]
                self.state.update_member_state(role, {"status": "removed", "removed_at": time.time()})

    def get_member(self, role: str) -> Optional["TeammateAgent"]:
        return self.members.get(role)

    def get_active_roles(self) -> List[str]:
        return list(self.members.keys())

    def broadcast(self, msg: TeamMessage) -> None:
        """Send a message to all team members."""
        msg.recipient = ""  # broadcast
        self.state.add_message(msg)
        for member in self.members.values():
            member.receive_message(msg)

    def send_to(self, recipient: str, msg: TeamMessage) -> bool:
        """Send a message to a specific member."""
        if recipient not in self.members:
            return False
        msg.recipient = recipient
        self.state.add_message(msg)
        self.members[recipient].receive_message(msg)
        return True

    def stop(self) -> None:
        """Stop the entire team."""
        self.state.active = False
        stop_msg = TeamMessage(msg_type=MessageType.STOP, sender="team-leader",
                               content="Team is shutting down.")
        for member in self.members.values():
            member.receive_message(stop_msg)

    def get_status(self) -> Dict[str, Any]:
        """Get team status."""
        return {
            "team_id": self.team_id,
            "team_type": self.team_type,
            "active": self.state.active,
            "members": {
                role: {
                    "status": self.state.get_member_state(role).get("status", "unknown"),
                    "tasks_completed": len([t for t in self.state.completed_tasks.values()
                                           if t.get("assigned_to") == role]),
                }
                for role in self.members
            },
            "pending_tasks": len(self.state.pending_tasks),
            "completed_tasks": len(self.state.completed_tasks),
            "uptime_seconds": time.time() - self.state.created_at,
        }


def _get_team_prompt(role: str, task: str, team_type: str) -> str:
    """Build a system prompt for a teammate agent."""
    role_desc = Team.ROLE_SYSTEM_PROMPTS.get(role, f"You are a {role} agent.")
    return f"""{role_desc}

TEAM CONTEXT:
- Your role: {role}
- Team type: {team_type}
- Your task: {task}

You are part of a team collaborating to solve a complex task.
Use your specialized role to contribute to the team's overall goal.
When done, report your findings/results back to the team leader.

Important: Work autonomously on your assigned task and communicate results clearly."""


class TeammateAgent:
    """A sub-agent with a specific role in a team."""

    def __init__(self, role: str, team: Team, parent_agent=None):
        self.role = role
        self.team = team
        self.parent_agent = parent_agent
        self.agent = None
        self.message_history: List[TeamMessage] = []
        self.current_task: Optional[Dict[str, Any]] = None
        self.task_result: Optional[Dict[str, Any]] = None
        self._running = False
        self._lock = threading.Lock()

    def assign_task(self, task: Dict[str, Any]) -> str:
        """Assign a task to this teammate."""
        task_id = task.get("task_id") or f"task-{uuid.uuid4().hex[:8]}"
        task["assigned_to"] = self.role
        task["assigned_at"] = time.time()
        self.current_task = task
        self.team.state.add_task(task_id, task)

        msg = TeamMessage(
            msg_type=MessageType.TASK,
            sender="team-leader",
            recipient=self.role,
            content=task.get("goal", ""),
            metadata={"task_id": task_id, "task": task}
        )
        self.team.state.add_message(msg)
        self.receive_message(msg)
        return task_id

    def receive_message(self, msg: TeamMessage) -> None:
        """Receive a message from the team."""
        with self._lock:
            self.message_history.append(msg)

        if msg.msg_type == MessageType.STOP:
            self._running = False
            return

        if msg.msg_type == MessageType.TASK:
            self._execute_task(msg)

    def _execute_task(self, msg: TeamMessage) -> None:
        """Execute the assigned task using delegate_task."""
        self._running = True
        task = msg.metadata.get("task", {})
        task_id = msg.metadata.get("task_id", "unknown")
        goal = msg.content

        self.team.state.update_member_state(self.role, {"status": "working", "current_task": task_id})

        try:
            from tools.delegate_tool import delegate_task

            context = task.get("context", "")
            toolsets = task.get("toolsets")

            # Build role-specific prompt
            system_prompt = _get_team_prompt(self.role, goal, self.team.team_type)

            # Use delegate_task to run the subagent
            result_str = delegate_task(
                goal=f"{system_prompt}\n\nUSER TASK:\n{goal}",
                context=context,
                toolsets=toolsets,
                parent_agent=self.parent_agent,
            )

            # Parse result
            try:
                result = json.loads(result_str) if result_str.startswith("{") else {"result": result_str}
            except json.JSONDecodeError:
                result = {"result": result_str}

            self.task_result = {
                "role": self.role,
                "task_id": task_id,
                "status": "completed",
                "result": result,
                "completed_at": time.time(),
            }

            # Report back to team leader
            result_msg = TeamMessage(
                msg_type=MessageType.RESULT,
                sender=self.role,
                recipient="team-leader",
                content=json.dumps(result, ensure_ascii=False),
                metadata={"task_id": task_id, "result": self.task_result}
            )
            self.team.state.add_message(result_msg)
            self.team.state.complete_task(task_id, self.task_result)

            if self.team.leader:
                self.team.leader.receive_message(result_msg)

        except Exception as exc:
            logger.exception(f"[{self.role}] Task execution failed")
            self.task_result = {
                "role": self.role,
                "task_id": task_id,
                "status": "error",
                "error": str(exc),
                "completed_at": time.time(),
            }

            error_msg = TeamMessage(
                msg_type=MessageType.ERROR,
                sender=self.role,
                recipient="team-leader",
                content=str(exc),
                metadata={"task_id": task_id, "error": str(exc)}
            )
            self.team.state.add_message(error_msg)
            if self.team.leader:
                self.team.leader.receive_message(error_msg)

        finally:
            self.team.state.update_member_state(self.role, {"status": "idle", "current_task": None})
            self._running = False

    def get_history(self) -> List[TeamMessage]:
        """Get message history for this teammate."""
        with self._lock:
            return list(self.message_history)

    def is_busy(self) -> bool:
        """Check if teammate is currently working."""
        return self._running


class TeamLeader:
    """Main agent that coordinates a team of teammates."""

    def __init__(self, team_type: str, parent_agent=None, team_id: str = None):
        self.team = Team(team_type, team_id)
        self.team.leader = self
        self.parent_agent = parent_agent
        self.pending_results: Dict[str, TeamMessage] = {}
        self._lock = threading.Lock()

        # Register in global registry
        with _REGISTRY_LOCK:
            _TEAM_REGISTRY[self.team.team_id] = self.team

    def start(self) -> Dict[str, Any]:
        """Initialize team members and start the team."""
        roles = self.team.TEAM_TYPES.get(self.team.team_type, [])

        for role in roles:
            teammate = TeammateAgent(role=role, team=self.team, parent_agent=self.parent_agent)
            self.team.add_member(role, teammate)

        return {
            "team_id": self.team.team_id,
            "team_type": self.team.team_type,
            "roles": roles,
            "status": "started"
        }

    def add_member(self, role: str) -> Dict[str, Any]:
        """Add a new member to the team."""
        if role in self.team.members:
            return {"error": f"Role '{role}' already exists in team"}

        teammate = TeammateAgent(role=role, team=self.team, parent_agent=self.parent_agent)
        self.team.add_member(role, teammate)

        return {
            "role": role,
            "status": "added",
            "team_id": self.team.team_id
        }

    def delegate_task(self, goal: str, context: str = "", toolsets: List[str] = None,
                     roles: List[str] = None) -> str:
        """Delegate a task to one or more team members."""
        if not self.team.state.active:
            return json.dumps({"error": "Team is not active"})

        # If no specific roles, use all members
        if not roles:
            roles = self.team.get_active_roles()

        task_id = f"task-{uuid.uuid4().hex[:8]}"
        results = []

        def run_for_role(role):
            teammate = self.team.get_member(role)
            if not teammate:
                return {"role": role, "status": "error", "error": "Member not found"}

            task = {
                "task_id": task_id,
                "goal": goal,
                "context": context,
                "toolsets": toolsets,
            }
            tid = teammate.assign_task(task)
            return {"role": role, "task_id": tid, "status": "delegated"}

        # Run in parallel
        if len(roles) == 1:
            results.append(run_for_role(roles[0]))
        else:
            with ThreadPoolExecutor(max_workers=len(roles)) as executor:
                futures = {executor.submit(run_for_role, role): role for role in roles}
                for future in as_completed(futures):
                    try:
                        results.append(future.result())
                    except Exception as exc:
                        role = futures[future]
                        results.append({"role": role, "status": "error", "error": str(exc)})

        return json.dumps({
            "task_id": task_id,
            "delegated_to": roles,
            "results": results
        })

    def receive_message(self, msg: TeamMessage) -> None:
        """Receive a message from a teammate."""
        with self._lock:
            if msg.msg_type == MessageType.RESULT:
                self.pending_results[msg.metadata.get("task_id", msg.msg_id)] = msg
            elif msg.msg_type == MessageType.ERROR:
                self.pending_results[msg.metadata.get("task_id", msg.msg_id)] = msg

    def collect_results(self, task_id: str = None, timeout: float = 60.0) -> Dict[str, Any]:
        """Collect results from teammates."""
        start = time.time()
        target_task_id = task_id

        while time.time() - start < timeout:
            with self._lock:
                if target_task_id and target_task_id in self.pending_results:
                    msg = self.pending_results.pop(target_task_id)
                    return {
                        "task_id": target_task_id,
                        "result": msg.content,
                        "metadata": msg.metadata
                    }

                # Check if all teammates are idle (no pending work)
                busy = [r for r, m in self.team.members.items() if m.is_busy()]
                if not busy and self.pending_results:
                    # Return all pending results
                    all_results = dict(self.pending_results)
                    self.pending_results.clear()
                    return {
                        "results": {k: v.content for k, v in all_results.items()},
                        "count": len(all_results)
                    }

            time.sleep(0.5)

        return {"error": "Timeout waiting for results", "task_id": target_task_id}

    def get_status(self) -> Dict[str, Any]:
        """Get team status."""
        return self.team.get_status()

    def stop(self) -> Dict[str, Any]:
        """Stop the team."""
        self.team.stop()
        with _REGISTRY_LOCK:
            if self.team.team_id in _TEAM_REGISTRY:
                del _TEAM_REGISTRY[self.team.team_id]

        return {
            "team_id": self.team.team_id,
            "status": "stopped"
        }

    def get_team(self) -> Team:
        """Get the team instance."""
        return self.team


# Global helpers

def get_team(team_id: str) -> Optional[Team]:
    """Get a team by ID."""
    with _REGISTRY_LOCK:
        return _TEAM_REGISTRY.get(team_id)


def list_teams() -> List[Dict[str, Any]]:
    """List all active teams."""
    with _REGISTRY_LOCK:
        return [
            {
                "team_id": t.team_id,
                "team_type": t.team_type,
                "active": t.state.active,
                "members": t.get_active_roles(),
            }
            for t in _TEAM_REGISTRY.values()
        ]


def stop_all_teams() -> None:
    """Stop all active teams."""
    with _REGISTRY_LOCK:
        for team in list(_TEAM_REGISTRY.values()):
            team.stop()
        _TEAM_REGISTRY.clear()


# Command handlers for /team command

def handle_team_command(args: List[str], parent_agent=None) -> str:
    """Handle /team command arguments."""
    if not args:
        return json.dumps({"error": "No subcommand provided", "help": "/team start|status|add|stop"})

    subcommand = args[0].lower()

    if subcommand == "start":
        if len(args) < 2:
            return json.dumps({"error": "Usage: /team start <type>", "types": list(Team.TEAM_TYPES.keys())})
        team_type = args[1].lower()
        if team_type not in Team.TEAM_TYPES:
            return json.dumps({"error": f"Unknown type: {team_type}", "types": list(Team.TEAM_TYPES.keys())})

        leader = TeamLeader(team_type=team_type, parent_agent=parent_agent)
        result = leader.start()
        return json.dumps(result)

    elif subcommand == "status":
        teams = list_teams()
        if not teams:
            return json.dumps({"teams": [], "message": "No active teams"})
        return json.dumps({"teams": teams})

    elif subcommand == "add":
        if len(args) < 2:
            return json.dumps({"error": "Usage: /team add <role>"})
        role = args[1].lower()
        # Find active team or use most recent
        with _REGISTRY_LOCK:
            active_teams = [t for t in _TEAM_REGISTRY.values() if t.state.active]
        if not active_teams:
            return json.dumps({"error": "No active team. Use /team start <type> first."})
        team = active_teams[0]
        leader = team.leader
        if not leader:
            return json.dumps({"error": "Team has no leader"})
        result = leader.add_member(role)
        return json.dumps(result)

    elif subcommand == "stop":
        with _REGISTRY_LOCK:
            active_teams = [t for t in _TEAM_REGISTRY.values() if t.state.active]
        if not active_teams:
            return json.dumps({"message": "No active teams to stop"})
        results = []
        for team in active_teams:
            if team.leader:
                results.append(team.leader.stop())
        return json.dumps({"stopped": results})

    elif subcommand == "delegate":
        if len(args) < 2:
            return json.dumps({"error": "Usage: /team delegate <goal>"})
        goal = " ".join(args[1:])
        with _REGISTRY_LOCK:
            active_teams = [t for t in _TEAM_REGISTRY.values() if t.state.active]
        if not active_teams:
            return json.dumps({"error": "No active team. Use /team start <type> first."})
        team = active_teams[0]
        leader = team.leader
        if not leader:
            return json.dumps({"error": "Team has no leader"})
        result = leader.delegate_task(goal)
        return result

    else:
        return json.dumps({"error": f"Unknown subcommand: {subcommand}", "help": "/team start|status|add|stop|delegate"})
