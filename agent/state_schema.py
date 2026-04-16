"""
Agent State Schema - 状态护栏系统的契约定义

基于Harness Engineering方法论，为Agent提供受控的状态空间。
状态空间严格定义，转移必须在allowedTransitions内。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Optional, Callable, Any
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class StateScope(str, Enum):
    """状态作用域 - 类似ADK的前缀分层设计"""
    USER = "user"       # 用户相关状态（长期）
    APP = "app"         # 应用/业务状态（会话级）
    TEMP = "temp"        # 临时状态（单次任务）
    SYSTEM = "system"     # 系统级状态（运行时）


@dataclass
class StateTransition:
    """状态转移定义"""
    from_state: str
    to_state: str
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None  # 转移条件函数
    action: Optional[Callable[[Dict[str, Any]], None]] = None  # 转移时自动触发的动作
    metadata: Dict[str, Any] = field(default_factory=dict)  # 附加元数据


@dataclass
class StateSchema:
    """
    状态Schema定义 - Schema即契约

    定义一个场景的完整状态空间：
    - states: 允许的所有状态
    - initial_state: 初始状态
    - final_states: 终止状态
    - transitions: 允许的状态转移
    - scope: 状态作用域
    """
    name: str                          # Schema名称（如：aibd_sales作业）
    scope: StateScope                  # 作用域
    states: Set[str]                   # 所有允许的状态
    initial_state: str                 # 初始状态
    final_states: Set[str]             # 终止状态（到达后自动结束）
    transitions: List[StateTransition]  # 允许的状态转移
    metadata: Dict[str, Any] = field(default_factory=dict)  # Schema元数据

    def __post_init__(self):
        """验证Schema定义的完整性"""
        # 验证初始状态是否在states中
        if self.initial_state not in self.states:
            raise ValueError(f"初始状态 '{self.initial_state}' 不在状态空间中")

        # 验证终止状态是否在states中
        for fs in self.final_states:
            if fs not in self.states:
                raise ValueError(f"终止状态 '{fs}' 不在状态空间中")

        # 验证所有转移的状态都在states中
        for trans in self.transitions:
            if trans.from_state not in self.states:
                raise ValueError(f"转移源状态 '{trans.from_state}' 不在状态空间中")
            if trans.to_state not in self.states:
                raise ValueError(f"转移目标状态 '{trans.to_state}' 不在状态空间中")

        # 构建转移查找表
        self._transition_map: Dict[str, List[StateTransition]] = {}
        for state in self.states:
            self._transition_map[state] = []
        for trans in self.transitions:
            self._transition_map[trans.from_state].append(trans)

        logger.info(f"Schema '{self.name}' 初始化完成: {len(self.states)}个状态, {len(self.transitions)}个转移")

    def can_transition(self, from_state: str, to_state: str, context: Dict[str, Any] = None) -> bool:
        """检查是否允许从from_state转移到to_state"""
        if from_state not in self._transition_map:
            return False

        for trans in self._transition_map[from_state]:
            if trans.to_state == to_state:
                # 检查条件（如果有）
                if trans.condition:
                    try:
                        return trans.condition(context or {})
                    except Exception as e:
                        logger.error(f"状态转移条件检查失败: {e}")
                        return False
                return True
        return False

    def get_allowed_transitions(self, from_state: str) -> List[str]:
        """获取从from_state可以转移到的所有目标状态"""
        if from_state not in self._transition_map:
            return []
        return [t.to_state for t in self._transition_map[from_state]]

    def get_transition(self, from_state: str, to_state: str) -> Optional[StateTransition]:
        """获取特定的状态转移对象"""
        if from_state not in self._transition_map:
            return None
        for trans in self._transition_map[from_state]:
            if trans.to_state == to_state:
                return trans
        return None


# =============================================================================
# 预定义的Schema示例
# =============================================================================

def create_aibd_sales_schema() -> StateSchema:
    """
    AIBD销售作业Schema示例

    状态流转：
    idle -> engaged -> link_sent -> waiting_confirm -> confirmed/completed
    """
    transitions = [
        # 从空闲开始
        StateTransition(
            from_state="idle",
            to_state="engaged",
            metadata={"trigger": "用户首次互动"}
        ),

        # 发送链接
        StateTransition(
            from_state="engaged",
            to_state="link_sent",
            action=lambda ctx: logger.info(f"链接已发送: {ctx.get('link_url')}")
        ),

        # 等待确认
        StateTransition(
            from_state="link_sent",
            to_state="waiting_confirm",
            metadata={"trigger": "等待用户确认"}
        ),

        # 用户确认
        StateTransition(
            from_state="waiting_confirm",
            to_state="confirmed",
            action=lambda ctx: logger.info(f"用户已确认: {ctx.get('user_id')}")
        ),

        # 用户拒绝/无响应
        StateTransition(
            from_state="waiting_confirm",
            to_state="completed",
            condition=lambda ctx: ctx.get('no_response', False) or ctx.get('rejected', False),
            metadata={"trigger": "超时或拒绝"}
        ),

        # 直接完成
        StateTransition(
            from_state="engaged",
            to_state="completed",
            condition=lambda ctx: ctx.get('immediate_complete', False)
        ),
    ]

    return StateSchema(
        name="aibd_sales作业",
        scope=StateScope.APP,
        states={"idle", "engaged", "link_sent", "waiting_confirm", "confirmed", "completed"},
        initial_state="idle",
        final_states={"completed", "confirmed"},
        transitions=transitions,
        metadata={"description": "AIBD销售作业标准流程"}
    )


def create_aibd_task_schema() -> StateSchema:
    """
    AIBD任务下发Schema示例

    状态流转：
    pending -> dispatching -> dispatched -> monitoring -> completed/failed
    """
    transitions = [
        StateTransition(from_state="pending", to_state="dispatching"),
        StateTransition(from_state="dispatching", to_state="dispatched"),
        StateTransition(from_state="dispatched", to_state="monitoring"),
        StateTransition(from_state="monitoring", to_state="completed"),
        StateTransition(from_state="monitoring", to_state="failed"),
        StateTransition(from_state="failed", to_state="pending",  # 重试
            condition=lambda ctx: ctx.get('retry_count', 0) < 3
        ),
    ]

    return StateSchema(
        name="aibd_task下发",
        scope=StateScope.APP,
        states={"pending", "dispatching", "dispatched", "monitoring", "completed", "failed"},
        initial_state="pending",
        final_states={"completed"},
        transitions=transitions,
        metadata={"description": "AIBD任务下发流程"}
    )


# =============================================================================
# Schema注册表 - 插件化设计
# =============================================================================

class SchemaRegistry:
    """Schema注册表 - 支持插件化注册新Schema"""

    _schemas: Dict[str, StateSchema] = {}

    @classmethod
    def register(cls, schema: StateSchema) -> None:
        """注册一个新的Schema"""
        if schema.name in cls._schemas:
            logger.warning(f"Schema '{schema.name}' 已存在，将被覆盖")
        cls._schemas[schema.name] = schema
        logger.info(f"Schema已注册: {schema.name}")

    @classmethod
    def get(cls, name: str) -> Optional[StateSchema]:
        """获取已注册的Schema"""
        return cls._schemas.get(name)

    @classmethod
    def list_schemas(cls) -> List[str]:
        """列出所有已注册的Schema名称"""
        return list(cls._schemas.keys())

    @classmethod
    def unregister(cls, name: str) -> bool:
        """注销Schema"""
        if name in cls._schemas:
            del cls._schemas[name]
            logger.info(f"Schema已注销: {name}")
            return True
        return False


# 注册默认Schema
SchemaRegistry.register(create_aibd_sales_schema())
SchemaRegistry.register(create_aibd_task_schema())
