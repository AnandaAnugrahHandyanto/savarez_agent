"""
Typed Message Protocol — agent/ 子系统之间的消息类型定义。

设计参考：autogen 的 BaseAgent 协议
- 所有跨 agent 的消息都用 dataclass，不用裸 dict
- 消息分为 3 类：AgentMessage（内容）、TaskResult（结果）、ControlMessage（控制）
- ControlMessage 用于 pause/resume/cancel/reset 等生命周期控制

用法：
    from agent.messages import AgentMessage, TaskResult, ControlMessage

    msg = AgentMessage(role="assistant", content="分析完毕", sender="analyzer")
    result = TaskResult(task_id="t1", status=TaskStatus.SUCCESS, result={"summary": "..."})
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal, Optional


class MessageType(enum.Enum):
    TEXT = "text"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    SYSTEM = "system"


class TaskStatus(enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    MAX_ITERATIONS = "max_iterations"


class ControlType(enum.Enum):
    PAUSE = "pause"
    RESUME = "resume"
    CANCEL = "cancel"
    RESET = "reset"
    INTERRUPT = "interrupt"


# ---------------------------------------------------------------------------
# Core message types
# ---------------------------------------------------------------------------


@dataclass
class AgentMessage:
    """跨 agent 传递的内容消息。"""
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    message_type: MessageType = MessageType.TEXT
    sender: Optional[str] = None           # agent name that produced this
    task_id: Optional[str] = None           # associated task
    tool_name: Optional[str] = None         # for TOOL_CALL / TOOL_RESULT
    tool_call_id: Optional[str] = None      # correlate call with result
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "message_type": self.message_type.value,
            "sender": self.sender,
            "task_id": self.task_id,
            "tool_name": self.tool_name,
            "tool_call_id": self.tool_call_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AgentMessage:
        return cls(
            role=d["role"],
            content=d["content"],
            message_type=MessageType(d.get("message_type", "text")),
            sender=d.get("sender"),
            task_id=d.get("task_id"),
            tool_name=d.get("tool_name"),
            tool_call_id=d.get("tool_call_id"),
            metadata=d.get("metadata", {}),
        )


@dataclass
class ToolTraceEntry:
    """单次工具调用的完整追踪记录。"""
    tool: str
    args_bytes: int = 0
    result_bytes: int = 0
    status: Literal["ok", "error"] = "ok"
    started_at: float = field(default_factory=time.time)
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "args_bytes": self.args_bytes,
            "result_bytes": self.result_bytes,
            "status": self.status,
            "started_at": self.started_at,
            "duration_ms": self.duration_ms,
        }


@dataclass
class TaskResult:
    """子任务完成后的结构化结果。"""
    task_id: str
    status: TaskStatus
    result: Any = None                       # the summary / final content
    error: Optional[str] = None
    exit_reason: Optional[Literal["completed", "interrupted", "max_iterations"]] = None
    tool_trace: list[ToolTraceEntry] = field(default_factory=list)
    tokens: dict[str, int] = field(default_factory=dict)  # input / output
    duration_seconds: float = 0.0
    model: Optional[str] = None
    api_calls: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "exit_reason": self.exit_reason,
            "tool_trace": [e.to_dict() for e in self.tool_trace],
            "tokens": self.tokens,
            "duration_seconds": self.duration_seconds,
            "model": self.model,
            "api_calls": self.api_calls,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TaskResult:
        tool_trace = []
        for e in d.get("tool_trace", []):
            if isinstance(e, dict):
                tool_trace.append(ToolTraceEntry(
                    tool=e.get("tool", ""),
                    args_bytes=e.get("args_bytes", 0),
                    result_bytes=e.get("result_bytes", 0),
                    status=e.get("status", "ok"),
                    started_at=e.get("started_at", 0),
                    duration_ms=e.get("duration_ms", 0),
                ))
            else:
                tool_trace.append(e)

        status_str = d.get("status", "failed")
        if isinstance(status_str, str):
            status = TaskStatus(status_str)
        else:
            status = status_str

        return cls(
            task_id=d["task_id"],
            status=status,
            result=d.get("result"),
            error=d.get("error"),
            exit_reason=d.get("exit_reason"),
            tool_trace=tool_trace,
            tokens=d.get("tokens", {}),
            duration_seconds=d.get("duration_seconds", 0.0),
            model=d.get("model"),
            api_calls=d.get("api_calls", 0),
            metadata=d.get("metadata", {}),
        )

    @property
    def is_success(self) -> bool:
        return self.status == TaskStatus.SUCCESS

    @property
    def is_retriable(self) -> bool:
        return self.status in (TaskStatus.FAILED, TaskStatus.MAX_ITERATIONS)


@dataclass
class ControlMessage:
    """生命周期控制消息（pause / resume / cancel / reset）。"""
    control_type: ControlType
    source: str = "parent"
    task_id: Optional[str] = None
    reason: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "control_type": self.control_type.value,
            "source": self.source,
            "task_id": self.task_id,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ControlMessage:
        return cls(
            control_type=ControlType(d["control_type"]),
            source=d.get("source", "parent"),
            task_id=d.get("task_id"),
            reason=d.get("reason"),
            timestamp=d.get("timestamp", time.time()),
            metadata=d.get("metadata", {}),
        )


@dataclass
class AgentInfo:
    """注册到 coordinator 的 agent 元信息。"""
    name: str
    role: str
    description: str = ""
    capabilities: list[str] = field(default_factory=list)
    task_id: Optional[str] = None        # current active task

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "description": self.description,
            "capabilities": self.capabilities,
            "task_id": self.task_id,
        }


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def new_message_id() -> str:
    return str(uuid.uuid4())[:8]


def make_error_message(content: str, sender: str = "system") -> AgentMessage:
    return AgentMessage(
        role="system",
        content=content,
        message_type=MessageType.ERROR,
        sender=sender,
    )


def make_tool_result(
    content: str,
    tool_call_id: str,
    sender: str = "tool",
) -> AgentMessage:
    return AgentMessage(
        role="tool",
        content=content,
        message_type=MessageType.TOOL_RESULT,
        sender=sender,
        tool_call_id=tool_call_id,
    )


def make_control(type_: ControlType, **kw) -> ControlMessage:
    return ControlMessage(control_type=type_, **kw)
