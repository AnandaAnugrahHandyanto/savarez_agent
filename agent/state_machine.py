"""
Agent State Machine - 状态机引擎核心

实现状态机引擎，负责：
1. 状态转移验证和执行
2. 自动触发状态关联动作
3. 与状态存储集成
4. 支持定时器驱动的状态转移
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any, Set
from enum import Enum

from agent.state_schema import StateSchema, StateTransition, SchemaRegistry, StateScope
from agent.state_store import StateStoreBackend, get_state_store, StateDelta

logger = logging.getLogger(__name__)


class StateMachineError(Exception):
    """状态机错误基类"""
    pass


class InvalidStateError(StateMachineError):
    """无效状态错误"""
    pass


class InvalidTransitionError(StateMachineError):
    """无效转移错误"""
    pass


class SchemaNotRegisteredError(StateMachineError):
    """Schema未注册错误"""
    pass


@dataclass
class Timer:
    """定时器定义"""
    timer_id: str
    agent_id: str
    schema_name: str
    trigger_state: str              # 触发定时器的状态
    target_state: str              # 超时后转移到的状态
    timeout_seconds: int           # 超时时间（秒）
    start_time: datetime           # 定时器开始时间
    action: Optional[Callable[[Dict[str, Any]], None]] = None  # 超时触发的动作
    context: Dict[str, Any] = field(default_factory=dict)  # 附加上下文
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StateMachine:
    """
    状态机引擎 - Schema即契约的核心实现

    功能：
    1. 状态转移验证（基于Schema的allowedTransitions）
    2. 自动触发状态关联动作
    3. 与StateStore集成进行持久化
    4. 定时器驱动的自动状态转移
    5. 状态变更事件通知
    """

    agent_id: str
    schema_name: str
    store: StateStoreBackend = field(default_factory=get_state_store)
    state_change_callbacks: List[Callable[[str, str, Dict[str, Any]], None]] = field(default_factory=list)

    # 内部状态
    _current_state: Optional[str] = None
    _schema: Optional[StateSchema] = None
    _context: Dict[str, Any] = field(default_factory=dict)
    _timers: Dict[str, Timer] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _initialized: bool = False

    def __post_init__(self):
        """初始化状态机"""
        self._load_schema()
        self._load_current_state()
        self._initialized = True
        logger.info(f"状态机已初始化: {self.agent_id} @ {self.schema_name} = {self._current_state}")

    def _load_schema(self):
        """加载Schema"""
        self._schema = SchemaRegistry.get(self.schema_name)
        if self._schema is None:
            raise SchemaNotRegisteredError(f"Schema '{self.schema_name}' 未注册")

    def _load_current_state(self):
        """从存储加载当前状态"""
        self._current_state = self.store.get_state(self.agent_id, self.schema_name)
        self._context = self.store.get_context(self.agent_id, self.schema_name)

        # 如果没有状态，使用初始状态
        if self._current_state is None:
            self._current_state = self._schema.initial_state
            self._save_state(self._current_state, context={"initialized": True})

    def _save_state(self, new_state: str, context: Dict[str, Any] = None):
        """保存状态到存储"""
        # 更新上下文
        if context:
            self._context.update(context)

        # 保存到存储
        self.store.save_state(
            agent_id=self.agent_id,
            schema_name=self.schema_name,
            state=new_state,
            context=self._context.copy()
        )

    def _notify_state_change(self, from_state: str, to_state: str, context: Dict[str, Any]):
        """通知状态变更监听器"""
        for callback in self.state_change_callbacks:
            try:
                callback(self.agent_id, self.schema_name, {
                    'from_state': from_state,
                    'to_state': to_state,
                    'context': context,
                    'timestamp': datetime.utcnow().isoformat()
                })
            except Exception as e:
                logger.error(f"状态变更通知失败: {e}")

    def _execute_transition_action(self, transition: StateTransition, context: Dict[str, Any]):
        """执行转移关联的动作"""
        if transition.action:
            try:
                # 合并当前上下文和转移上下文
                full_context = {**self._context, **context}
                transition.action(full_context)
                logger.debug(f"执行转移动作: {transition.from_state} -> {transition.to_state}")
            except Exception as e:
                logger.error(f"转移动作执行失败: {e}")

    def _check_timers(self):
        """检查并触发超时的定时器"""
        now = datetime.utcnow()
        expired_timers = []

        with self._lock:
            for timer_id, timer in self._timers.items():
                if timer.trigger_state != self._current_state:
                    continue  # 定时器只在特定状态下生效

                elapsed = (now - timer.start_time).total_seconds()
                if elapsed >= timer.timeout_seconds:
                    expired_timers.append(timer)

        # 触发过期的定时器
        for timer in expired_timers:
            logger.info(f"定时器触发: {timer.timer_id} (超时 {timer.timeout_seconds}s)")
            try:
                # 执行定时器动作
                if timer.action:
                    timer.action({**self._context, **timer.context})

                # 自动状态转移
                self.transition_to(timer.target_state, context={
                    'trigger': f'timer:{timer.timer_id}',
                    'timeout_elapsed': elapsed
                })

                # 移除定时器
                with self._lock:
                    if timer.timer_id in self._timers:
                        del self._timers[timer.timer_id]
            except Exception as e:
                logger.error(f"定时器触发失败: {e}")

    def get_current_state(self) -> Optional[str]:
        """获取当前状态"""
        return self._current_state

    def get_context(self) -> Dict[str, Any]:
        """获取当前上下文"""
        return self._context.copy()

    def set_context(self, key: str, value: Any):
        """设置上下文值"""
        with self._lock:
            self._context[key] = value
            # 保存到存储
            self._save_state(self._current_state)

    def get_context_value(self, key: str, default: Any = None) -> Any:
        """获取上下文值"""
        with self._lock:
            return self._context.get(key, default)

    def can_transition(self, to_state: str, context: Dict[str, Any] = None) -> bool:
        """检查是否允许转移到目标状态"""
        if self._current_state is None:
            return False

        full_context = {**self._context, **(context or {})}
        return self._schema.can_transition(self._current_state, to_state, full_context)

    def get_allowed_transitions(self) -> List[str]:
        """获取当前状态允许转移到的所有状态"""
        if self._current_state is None:
            return []
        return self._schema.get_allowed_transitions(self._current_state)

    def transition_to(self, to_state: str, context: Dict[str, Any] = None, force: bool = False) -> bool:
        """
        执行状态转移

        Args:
            to_state: 目标状态
            context: 转移时的上下文数据
            force: 是否强制转移（跳过验证）

        Returns:
            是否转移成功

        Raises:
            InvalidTransitionError: 转移不被允许且未强制
        """
        with self._lock:
            from_state = self._current_state

            # 验证转移
            if not force and not self.can_transition(to_state, context):
                allowed = self.get_allowed_transitions()
                raise InvalidTransitionError(
                    f"不允许从 '{from_state}' 转移到 '{to_state}'。"
                    f"允许的转移: {allowed}"
                )

            # 执行转移
            full_context = {**self._context, **(context or {})}
            transition = self._schema.get_transition(from_state, to_state)

            # 执行转移前的动作
            if transition:
                self._execute_transition_action(transition, full_context)

            # 更新状态
            self._current_state = to_state
            self._save_state(to_state, context)

            # 通知状态变更
            self._notify_state_change(from_state, to_state, full_context)

            logger.info(f"状态转移: {self.agent_id} {from_state} -> {to_state}")

            # 检查是否到达终止状态
            if to_state in self._schema.final_states:
                logger.info(f"到达终止状态: {to_state}")

            return True

    def add_timer(self, timer_id: str, timeout_seconds: int,
                 target_state: str = None, action: Callable = None,
                 context: Dict[str, Any] = None) -> bool:
        """
        添加定时器

        Args:
            timer_id: 定时器唯一标识
            timeout_seconds: 超时时间（秒）
            target_state: 超时后转移到的状态（可选）
            action: 超时触发的动作（可选）
            context: 附加上下文（可选）

        Returns:
            是否添加成功
        """
        if self._current_state is None:
            return False

        with self._lock:
            self._timers[timer_id] = Timer(
                timer_id=timer_id,
                agent_id=self.agent_id,
                schema_name=self.schema_name,
                trigger_state=self._current_state,  # 在当前状态下触发
                target_state=target_state,
                timeout_seconds=timeout_seconds,
                start_time=datetime.utcnow(),
                action=action,
                context=context or {},
                metadata={}
            )

        logger.debug(f"定时器已添加: {timer_id} (超时 {timeout_seconds}s)")
        return True

    def remove_timer(self, timer_id: str) -> bool:
        """移除定时器"""
        with self._lock:
            if timer_id in self._timers:
                del self._timers[timer_id]
                logger.debug(f"定时器已移除: {timer_id}")
                return True
            return False

    def get_timers(self) -> List[Timer]:
        """获取所有活跃定时器"""
        with self._lock:
            return list(self._timers.values())

    def check_and_trigger_timers(self) -> int:
        """检查并触发超时的定时器，返回触发的数量"""
        self._check_timers()

    def get_history(self, limit: int = 100) -> List[StateDelta]:
        """获取状态变更历史"""
        return self.store.get_history(self.agent_id, self.schema_name, limit)

    def reset(self, force: bool = False):
        """重置到初始状态"""
        with self._lock:
            # 清除所有定时器
            self._timers.clear()

            # 重置状态
            self._current_state = self._schema.initial_state
            self._context = {}
            self._save_state(self._current_state, context={'reset': True})

            logger.info(f"状态机已重置: {self.agent_id} -> {self._current_state}")

    def cleanup(self):
        """清理资源"""
        with self._lock:
            self._timers.clear()


# =============================================================================
# 状态机管理器 - 管理多个状态机实例
# =============================================================================

class StateMachineManager:
    """状态机管理器 - 管理所有Agent的状态机实例"""

    _machines: Dict[str, StateMachine] = {}
    _lock: threading.Lock = threading.Lock()
    _timer_thread: Optional[threading.Thread] = None
    _timer_running: bool = False

    @classmethod
    def get_machine(cls, agent_id: str, schema_name: str) -> StateMachine:
        """获取或创建状态机实例"""
        key = f"{agent_id}:{schema_name}"

        with cls._lock:
            if key not in cls._machines:
                cls._machines[key] = StateMachine(
                    agent_id=agent_id,
                    schema_name=schema_name
                )
            return cls._machines[key]

    @classmethod
    def remove_machine(cls, agent_id: str, schema_name: str = None) -> bool:
        """移除状态机实例"""
        removed = False

        with cls._lock:
            if schema_name:
                key = f"{agent_id}:{schema_name}"
                if key in cls._machines:
                    cls._machines[key].cleanup()
                    del cls._machines[key]
                    removed = True
            else:
                # 移除该agent的所有状态机
                keys_to_remove = [k for k in cls._machines.keys() if k.startswith(f"{agent_id}:")]
                for key in keys_to_remove:
                    cls._machines[key].cleanup()
                    del cls._machines[key]
                    removed = True

        if removed:
            logger.info(f"状态机已移除: {agent_id}")

        return removed

    @classmethod
    def start_timer_thread(cls, check_interval: float = 1.0):
        """启动定时器检查线程"""
        if cls._timer_running:
            return

        cls._timer_running = True

        def timer_loop():
            while cls._timer_running:
                try:
                    with cls._lock:
                        machines = list(cls._machines.values())

                    for machine in machines:
                        machine.check_and_trigger_timers()

                    time.sleep(check_interval)
                except Exception as e:
                    logger.error(f"定时器检查线程错误: {e}")

        cls._timer_thread = threading.Thread(target=timer_loop, daemon=True)
        cls._timer_thread.start()
        logger.info("定时器检查线程已启动")

    @classmethod
    def stop_timer_thread(cls):
        """停止定时器检查线程"""
        cls._timer_running = False
        if cls._timer_thread:
            cls._timer_thread.join(timeout=5)
            cls._timer_thread = None
            logger.info("定时器检查线程已停止")

    @classmethod
    def list_machines(cls) -> List[Dict[str, Any]]:
        """列出所有活跃的状态机"""
        with cls._lock:
            return [
                {
                    'agent_id': m.agent_id,
                    'schema_name': m.schema_name,
                    'current_state': m.get_current_state(),
                    'context': m.get_context(),
                    'timers': len(m.get_timers())
                }
                for m in cls._machines.values()
            ]

    @classmethod
    def get_machine_status(cls, agent_id: str, schema_name: str = None) -> Optional[Dict[str, Any]]:
        """获取特定状态机的状态"""
        with cls._lock:
            if schema_name:
                key = f"{agent_id}:{schema_name}"
                if key in cls._machines:
                    m = cls._machines[key]
                    return {
                        'agent_id': m.agent_id,
                        'schema_name': m.schema_name,
                        'current_state': m.get_current_state(),
                        'context': m.get_context(),
                        'allowed_transitions': m.get_allowed_transitions(),
                        'timers': [
                            {
                                'timer_id': t.timer_id,
                                'timeout_seconds': t.timeout_seconds,
                                'elapsed_seconds': (datetime.utcnow() - t.start_time).total_seconds(),
                                'target_state': t.target_state
                            }
                            for t in m.get_timers()
                        ]
                    }
            else:
                # 返回该agent的所有状态机
                results = []
                for key, m in cls._machines.items():
                    if key.startswith(f"{agent_id}:"):
                        results.append({
                            'schema_name': m.schema_name,
                            'current_state': m.get_current_state(),
                            'context': m.get_context()
                        })
                return results if results else None
        return None
