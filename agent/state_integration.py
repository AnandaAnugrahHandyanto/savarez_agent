"""
Agent State Machine Integration - 状态机与AIAgent集成

提供状态机与AIAgent的无缝集成：
1. StateMachineMixin - 可混入AIAgent的状态机功能
2. 状态感知的Prompt注入
3. 状态变更事件钩子
4. 工程层状态驱动能力
"""

import logging
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass

from agent.state_machine import StateMachine, StateMachineManager, Timer
from agent.state_schema import StateSchema, SchemaRegistry, StateTransition

logger = logging.getLogger(__name__)


@dataclass
class StateMachineConfig:
    """状态机配置"""
    enabled: bool = False
    schema_name: Optional[str] = None
    auto_inject_state: bool = True  # 是否自动注入状态到Prompt
    state_inject_format: str = "compact"  # compact, detailed, custom
    custom_state_template: Optional[str] = None  # 自定义状态注入模板
    enable_timers: bool = True  # 是否启用定时器
    on_state_change: Optional[Callable] = None  # 状态变更回调


class StateMachineMixin:
    """
    状态机混入类 - 为AIAgent添加状态管理能力

    设计原则：
    - 非侵入式集成：AIAgent可选择启用状态机
    - 双模驱动：Agent控制内容，工程层控制时机
    - 可观测性：状态变更自动记录和通知
    """

    def __init__(self, *args, **kwargs):
        # 先调用父类初始化
        super().__init__(*args, **kwargs)

        # 状态机配置
        self._state_config: StateMachineConfig = kwargs.get('state_config', StateMachineConfig())
        self._state_machine: Optional[StateMachine] = None

        # 如果启用了状态机，进行初始化
        if self._state_config.enabled and self._state_config.schema_name:
            self._init_state_machine()

    def _init_state_machine(self):
        """初始化状态机"""
        try:
            # 使用session_id作为agent_id
            agent_id = getattr(self, 'session_id', 'unknown')

            # 从StateMachineManager获取或创建状态机实例
            self._state_machine = StateMachineManager.get_machine(
                agent_id=agent_id,
                schema_name=self._state_config.schema_name
            )

            # 注册状态变更回调
            if self._state_config.on_state_change:
                self._state_machine.state_change_callbacks.append(
                    self._state_config.on_state_change
                )

            # 添加内部状态变更回调（用于日志和监控）
            self._state_machine.state_change_callbacks.append(
                self._on_state_changed
            )

            logger.info(
                f"状态机已初始化: {agent_id} @ {self._state_config.schema_name} "
                f"= {self._state_machine.get_current_state()}"
            )

        except Exception as e:
            logger.error(f"状态机初始化失败: {e}")
            self._state_machine = None

    def _on_state_changed(self, agent_id: str, schema_name: str, event: Dict[str, Any]):
        """内部状态变更回调"""
        from_state = event.get('from_state')
        to_state = event.get('to_state')
        logger.info(f"状态变更: {agent_id} {from_state} -> {to_state}")

    # ========================================================================
    # 公共API - 状态管理
    # ========================================================================

    def get_current_state(self) -> Optional[str]:
        """获取当前状态"""
        if not self._state_machine:
            return None
        return self._state_machine.get_current_state()

    def get_state_context(self) -> Dict[str, Any]:
        """获取状态上下文"""
        if not self._state_machine:
            return {}
        return self._state_machine.get_context()

    def get_allowed_transitions(self) -> List[str]:
        """获取允许的转移状态"""
        if not self._state_machine:
            return []
        return self._state_machine.get_allowed_transitions()

    def can_transition_to(self, to_state: str, context: Dict[str, Any] = None) -> bool:
        """检查是否可以转移到目标状态"""
        if not self._state_machine:
            return False
        return self._state_machine.can_transition(to_state, context)

    def transition_to(self, to_state: str, context: Dict[str, Any] = None, force: bool = False) -> bool:
        """
        执行状态转移

        Args:
            to_state: 目标状态
            context: 转移时的上下文数据
            force: 是否强制转移（跳过验证）

        Returns:
            是否转移成功
        """
        if not self._state_machine:
            logger.warning("状态机未启用，无法执行状态转移")
            return False

        try:
            return self._state_machine.transition_to(to_state, context, force)
        except Exception as e:
            logger.error(f"状态转移失败: {e}")
            return False

    def set_state_context(self, key: str, value: Any):
        """设置状态上下文值"""
        if self._state_machine:
            self._state_machine.set_context(key, value)

    def get_state_context_value(self, key: str, default: Any = None) -> Any:
        """获取状态上下文值"""
        if self._state_machine:
            return self._state_machine.get_context_value(key, default)
        return default

    # ========================================================================
    # 定时器管理
    # ========================================================================

    def add_state_timer(self, timer_id: str, timeout_seconds: int,
                       target_state: str = None, action: Callable = None,
                       context: Dict[str, Any] = None) -> bool:
        """
        添加状态定时器

        Args:
            timer_id: 定时器唯一标识
            timeout_seconds: 超时时间（秒）
            target_state: 超时后转移到的状态（可选）
            action: 超时触发的动作（可选）
            context: 附加上下文（可选）

        Returns:
            是否添加成功
        """
        if not self._state_machine or not self._state_config.enable_timers:
            logger.warning("状态机或定时器未启用")
            return False

        return self._state_machine.add_timer(
            timer_id=timer_id,
            timeout_seconds=timeout_seconds,
            target_state=target_state,
            action=action,
            context=context
        )

    def remove_state_timer(self, timer_id: str) -> bool:
        """移除状态定时器"""
        if not self._state_machine:
            return False
        return self._state_machine.remove_timer(timer_id)

    def get_state_timers(self) -> List[Timer]:
        """获取所有活跃的状态定时器"""
        if not self._state_machine:
            return []
        return self._state_machine.get_timers()

    # ========================================================================
    # Prompt注入
    # ========================================================================

    def get_state_prompt_injection(self) -> str:
        """
        获取状态信息的Prompt注入

        根据配置返回不同格式的状态信息，用于注入到系统提示词中
        """
        if not self._state_machine or not self._state_config.auto_inject_state:
            return ""

        current_state = self._state_machine.get_current_state()
        if not current_state:
            return ""

        context = self._state_machine.get_context()
        allowed_transitions = self._state_machine.get_allowed_transitions()

        # 使用自定义模板
        if self._state_config.custom_state_template:
            return self._state_config.custom_state_template.format(
                current_state=current_state,
                context=context,
                allowed_transitions=allowed_transitions
            )

        # 根据格式选择注入方式
        if self._state_config.state_inject_format == "compact":
            return self._format_compact_state(current_state, allowed_transitions)
        elif self._state_config.state_inject_format == "detailed":
            return self._format_detailed_state(current_state, context, allowed_transitions)
        else:  # minimal
            return self._format_minimal_state(current_state)

    def _format_compact_state(self, current_state: str, allowed_transitions: List[str]) -> str:
        """紧凑格式状态注入"""
        transitions_str = ", ".join(allowed_transitions[:5])  # 最多显示5个
        if len(allowed_transitions) > 5:
            transitions_str += f" (+{len(allowed_transitions) - 5} more)"

        return f"\n[当前状态: {current_state} | 可转移至: {transitions_str}]"

    def _format_detailed_state(self, current_state: str, context: Dict[str, Any],
                               allowed_transitions: List[str]) -> str:
        """详细格式状态注入"""
        state_info = f"\n--- Agent 运行状态 ---\n"
        state_info += f"当前状态: {current_state}\n"

        if allowed_transitions:
            state_info += f"允许的转移: {', '.join(allowed_transitions)}\n"

        if context:
            state_info += "状态上下文:\n"
            for key, value in context.items():
                if not key.startswith('_'):  # 跳过内部字段
                    state_info += f"  - {key}: {value}\n"

        state_info += "---\n"
        return state_info

    def _format_minimal_state(self, current_state: str) -> str:
        """最小格式状态注入"""
        return f"[状态: {current_state}]"

    # ========================================================================
    # 状态历史和诊断
    # ========================================================================

    def get_state_history(self, limit: int = 100):
        """获取状态变更历史"""
        if not self._state_machine:
            return []
        return self._state_machine.get_history(limit)

    def get_state_machine_status(self) -> Optional[Dict[str, Any]]:
        """获取状态机完整状态"""
        if not self._state_machine:
            return None

        return {
            'schema_name': self._state_machine.schema_name,
            'current_state': self._state_machine.get_current_state(),
            'context': self._state_machine.get_context(),
            'allowed_transitions': self._state_machine.get_allowed_transitions(),
            'timers': [
                {
                    'timer_id': t.timer_id,
                    'timeout_seconds': t.timeout_seconds,
                    'elapsed_seconds': (t.start_time - t.start_time).total_seconds() if hasattr(t, 'start_time') else 0,
                    'target_state': t.target_state
                }
                for t in self._state_machine.get_timers()
            ]
        }

    def reset_state_machine(self, force: bool = False):
        """重置状态机到初始状态"""
        if self._state_machine:
            self._state_machine.reset(force)
            logger.info("状态机已重置")

    def cleanup_state_machine(self):
        """清理状态机资源"""
        if self._state_machine:
            agent_id = getattr(self, 'session_id', 'unknown')
            StateMachineManager.remove_machine(agent_id, self._state_config.schema_name)
            logger.info(f"状态机已清理: {agent_id}")


# ========================================================================
# 工程层状态驱动工具
# ========================================================================

class StateDrivenAutomation:
    """
    工程层状态驱动自动化

    提供基于状态的外部触发能力，实现"工程层控制时机，Agent控制内容"的双模驱动
    """

    @staticmethod
    def register_automation(schema_name: str, state: str,
                          action: Callable[[Dict[str, Any]], None],
                          condition: Callable[[Dict[str, Any]], bool] = None) -> bool:
        """
        注册状态驱动的自动化动作

        Args:
            schema_name: Schema名称
            state: 触发状态
            action: 执行的动作函数
            condition: 触发条件函数（可选）

        Returns:
            是否注册成功
        """
        try:
            # 获取Schema并添加自动化转移动作
            schema = SchemaRegistry.get(schema_name)
            if not schema:
                logger.error(f"Schema '{schema_name}' 未注册")
                return False

            # 创建自动化转移动作
            def automation_wrapper(ctx: Dict[str, Any]):
                if condition is None or condition(ctx):
                    action(ctx)

            # 添加到Schema的转移动作中
            # 注意：这里需要在Schema层面支持自动化注册
            # 当前实现需要扩展StateSchema来支持自动化注册
            logger.info(f"自动化动作已注册: {schema_name}.{state}")
            return True

        except Exception as e:
            logger.error(f"注册自动化动作失败: {e}")
            return False

    @staticmethod
    def trigger_automation(agent_id: str, schema_name: str,
                         check_state: bool = True) -> int:
        """
        触发自动化动作

        Args:
            agent_id: Agent ID
            schema_name: Schema名称
            check_state: 是否检查当前状态

        Returns:
            触发的动作数量
        """
        try:
            machine = StateMachineManager.get_machine(agent_id, schema_name)
            current_state = machine.get_current_state()

            # 这里需要实现自动化触发逻辑
            # 当前版本为简化实现
            logger.debug(f"触发自动化检查: {agent_id} @ {current_state}")
            return 0

        except Exception as e:
            logger.error(f"触发自动化失败: {e}")
            return 0


# ========================================================================
# AIBD特定集成
# ========================================================================

class AIBDStateIntegration:
    """
    AIBD场景的状态机集成

    提供AIBD业务场景的预设Schema和自动化
    """

    @staticmethod
    def register_aibd_schemas():
        """注册AIBD相关的状态Schema"""
        from agent.state_schema import (
            StateSchema, StateTransition, StateScope, SchemaRegistry
        )

        # AIBD销售流程Schema
        aibd_sales_schema = StateSchema(
            name="aibd_sales",
            scope=StateScope.USER,
            states={
                "idle", "querying", "analyzing", "proposing", "negotiating",
                "closing", "followup", "completed", "failed"
            },
            initial_state="idle",
            final_states={"completed", "failed"},
            transitions=[
                StateTransition("idle", "querying", action=None),
                StateTransition("querying", "analyzing", action=None),
                StateTransition("analyzing", "proposing", action=None),
                StateTransition("proposing", "negotiating", action=None),
                StateTransition("negotiating", "closing", action=None),
                StateTransition("closing", "followup", action=None),
                StateTransition("followup", "completed", action=None),
                StateTransition("followup", "negotiating", action=None),
                # 异常流程
                StateTransition("querying", "failed", action=None),
                StateTransition("analyzing", "failed", action=None),
                StateTransition("proposing", "failed", action=None),
                StateTransition("negotiating", "failed", action=None),
            ],
            metadata={"description": "AIBD销售流程状态机"}
        )

        # AIBD任务调度Schema
        aibd_task_schema = StateSchema(
            name="aibd_task_dispatch",
            scope=StateScope.USER,
            states={
                "pending", "assigned", "in_progress", "review", "approved",
                "rejected", "completed", "cancelled"
            },
            initial_state="pending",
            final_states={"completed", "cancelled"},
            transitions=[
                StateTransition("pending", "assigned", action=None),
                StateTransition("assigned", "in_progress", action=None),
                StateTransition("in_progress", "review", action=None),
                StateTransition("review", "approved", action=None),
                StateTransition("review", "rejected", action=None),
                StateTransition("approved", "completed", action=None),
                StateTransition("rejected", "in_progress", action=None),
                # 异常流程
                StateTransition("pending", "cancelled", action=None),
                StateTransition("assigned", "cancelled", action=None),
            ],
            metadata={"description": "AIBD任务调度状态机"}
        )

        # 注册Schema
        SchemaRegistry.register(aibd_sales_schema)
        SchemaRegistry.register(aibd_task_schema)

        logger.info("AIBD状态Schema已注册")

    @staticmethod
    def get_aibd_state_config(schema_name: str = "aibd_sales") -> StateMachineConfig:
        """获取AIBD场景的状态机配置"""
        return StateMachineConfig(
            enabled=True,
            schema_name=schema_name,
            auto_inject_state=True,
            state_inject_format="compact",
            enable_timers=True
        )
