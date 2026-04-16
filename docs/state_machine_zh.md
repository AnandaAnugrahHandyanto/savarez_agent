# Agent 状态机功能文档

## 概述

Agent 状态机模块为 hermes-agent 提供了显式的状态管理能力。通过基于 Schema 的状态机引擎，Agent 可以精确跟踪和管理工作流状态，实现状态驱动的自动化操作。

### 核心特性

- **显式状态跟踪**：基于预定义 Schema 的状态空间，不再依赖对话历史猜测进度
- **状态护栏**：Schema 定义合法的状态转移，防止非法状态变更
- **定时器驱动**：支持基于超时的自动状态转移（如：30分钟无响应 → 第二次跟进）
- **持久化存储**：支持 JSON 和 SQLite 后端，完整记录状态变更历史
- **非侵入式集成**：通过 StateMachineMixin 可选启用状态机，不影响现有 Agent
- **工程层驱动**：工程层控制时机，Agent 控制内容的双模驱动
- **可观测性**：完整的状态历史记录和 CLI 查询工具

## 设计原则

### 1. Schema 即契约

状态机基于预定义的 Schema 运行，Schema 定义了：
- 状态空间（states）
- 初始状态（initial_state）
- 终止状态（final_states）
- 合法转移（transitions）
- 转移条件（conditions）

### 2. 插件化设计

新场景只需注册新的 Schema，无需修改状态机引擎：

```python
# 注册新 Schema
SchemaRegistry.register(my_custom_schema)

# Agent 使用新 Schema
agent = AIAgent(state_config=StateMachineConfig(
    enabled=True,
    schema_name="my_custom_schema"
))
```

### 3. 双模驱动

- **工程层**：控制状态转移的时机（定时器、外部触发）
- **Agent**：控制状态转移的内容（业务逻辑、上下文数据）

### 4. 前缀分层作用域

支持多层级的状态空间：

- `user:` - 用户级状态（如：用户生命周期）
- `app:` - 应用级状态（如：订单处理流程）
- `temp:` - 临时状态（如：单次对话流程）
- `system:` - 系统级状态（如：健康检查）

### 5. 事件驱动持久化

每次状态变更自动记录 StateDelta，包含：
- 时间戳
- 源状态和目标状态
- 上下文数据
- 元数据

## 核心组件

### 1. StateSchema（状态 Schema）

定义状态机的结构和约束。

```python
from agent.state_schema import StateSchema, StateTransition, StateScope

sales_schema = StateSchema(
    name="aibd_sales",
    scope=StateScope.USER,
    states={
        "idle", "querying", "analyzing", "proposing",
        "negotiating", "closing", "followup", "completed", "failed"
    },
    initial_state="idle",
    final_states={"completed", "failed"},
    transitions=[
        StateTransition("idle", "querying", action=None),
        StateTransition("querying", "analyzing", action=None),
        StateTransition("analyzing", "proposing", action=None),
        # ... 更多转移
    ],
    metadata={"description": "AIBD 销售流程"}
)
```

### 2. StateStoreBackend（状态存储）

提供状态持久化能力，支持多种后端：

```python
from agent.state_store import JSONStateStore, SQLiteStateStore

# JSON 存储
json_store = JSONStateStore(base_path="./state_data")

# SQLite 存储
sqlite_store = SQLiteStateStore(db_path="./states.db")
```

### 3. StateMachine（状态机引擎）

核心状态机引擎，负责状态转移验证和执行。

```python
from agent.state_machine import StateMachine

machine = StateMachine(
    agent_id="agent_123",
    schema_name="aibd_sales"
)

# 查询当前状态
current_state = machine.get_current_state()

# 执行状态转移
machine.transition_to("querying", context={"customer_id": "12345"})

# 设置上下文
machine.set_context("key", "value")

# 添加定时器
machine.add_timer(
    timer_id="followup",
    timeout_seconds=1800,  # 30分钟
    target_state="followup"
)
```

### 4. StateMachineMixin（状态机混入）

为 AIAgent 提供非侵入式的状态机集成。

```python
from agent.state_integration import StateMachineMixin, StateMachineConfig

class MyAgent(AIAgent, StateMachineMixin):
    def __init__(self):
        state_config = StateMachineConfig(
            enabled=True,
            schema_name="aibd_sales",
            auto_inject_state=True,  # 自动注入状态到 Prompt
            state_inject_format="compact"
        )
        super().__init__(state_config=state_config)

    # Agent 可以直接使用状态机方法
    def handle_query(self):
        self.transition_to("querying")
        self.set_state_context("query", user_query)
```

## 使用示例

### 示例 1：创建自定义 Schema

```python
from agent.state_schema import StateSchema, StateTransition, StateScope, SchemaRegistry

# 定义任务处理 Schema
task_schema = StateSchema(
    name="task_processing",
    scope=StateScope.APP,
    states={
        "pending", "assigned", "in_progress",
        "review", "approved", "rejected", "completed"
    },
    initial_state="pending",
    final_states={"completed", "rejected"},
    transitions=[
        StateTransition("pending", "assigned", action=None),
        StateTransition("assigned", "in_progress", action=None),
        StateTransition("in_progress", "review", action=None),
        StateTransition("review", "approved", action=None),
        StateTransition("review", "rejected", action=None),
        StateTransition("approved", "completed", action=None),
    ]
)

# 注册 Schema
SchemaRegistry.register(task_schema)
```

### 示例 2：带条件的转移

```python
# 定义条件函数
def is_high_priority(ctx):
    return ctx.get('priority', 0) >= 8

# 在转移中使用条件
StateTransition(
    "in_progress",
    "fast_track",
    condition=is_high_priority
)
```

### 示例 3：使用 StateMachineMixin

```python
from agent.state_integration import StateMachineMixin, StateMachineConfig

class SalesAgent(AIAgent, StateMachineMixin):
    def __init__(self, session_id):
        self.session_id = session_id
        state_config = StateMachineConfig(
            enabled=True,
            schema_name="aibd_sales",
            enable_timers=True
        )
        super().__init__(state_config=state_config)

    def process_customer_query(self, query):
        # 转移到查询状态
        self.transition_to("querying")
        self.set_state_context("query", query)

        # 处理查询...

        # 转移到分析状态
        self.transition_to("analyzing")

    def send_proposal(self, proposal):
        self.transition_to("proposing")
        self.set_state_context("proposal", proposal)

        # 添加跟进定时器
        self.add_state_timer(
            timer_id="proposal_followup",
            timeout_seconds=86400,  # 24小时
            target_state="followup"
        )
```

### 示例 4：CLI 查询状态

```bash
# 列出所有 Agent 的状态机
hermes state list

# 查看特定 Agent 的状态
hermes state get --agent-id agent_123 --schema aibd_sales

# 查看状态变更历史
hermes state history --agent-id agent_123 --schema aibd_sales --limit 20

# 重置 Agent 状态
hermes state reset --agent-id agent_123 --schema aibd_sales

# 列出所有已注册的 Schema
hermes state schemas

# 查看 Schema 详情
hermes state schema --name aibd_sales
```

## API 参考

### StateSchema

```python
@dataclass
class StateSchema:
    name: str                          # Schema 名称
    scope: StateScope                   # 作用域
    states: Set[str]                   # 状态集合
    initial_state: str                  # 初始状态
    final_states: Set[str]             # 终止状态集合
    transitions: List[StateTransition]   # 转移列表
    metadata: Dict[str, Any]            # 元数据

    def can_transition(self, from_state: str, to_state: str,
                   context: Dict[str, Any] = None) -> bool
    def get_allowed_transitions(self, from_state: str) -> List[str]
    def get_transition(self, from_state: str, to_state: str) -> Optional[StateTransition]
```

### StateMachine

```python
@dataclass
class StateMachine:
    agent_id: str
    schema_name: str
    store: StateStoreBackend
    state_change_callbacks: List[Callable]

    def get_current_state(self) -> Optional[str]
    def get_context(self) -> Dict[str, Any]
    def set_context(self, key: str, value: Any)
    def get_context_value(self, key: str, default: Any = None) -> Any
    def can_transition(self, to_state: str, context: Dict[str, Any] = None) -> bool
    def get_allowed_transitions(self) -> List[str]
    def transition_to(self, to_state: str, context: Dict[str, Any] = None,
                   force: bool = False) -> bool
    def add_timer(self, timer_id: str, timeout_seconds: int,
                 target_state: str = None, action: Callable = None,
                 context: Dict[str, Any] = None) -> bool
    def remove_timer(self, timer_id: str) -> bool
    def get_timers(self) -> List[Timer]
    def get_history(self, limit: int = 100) -> List[StateDelta]
    def reset(self, force: bool = False)
```

### StateMachineMixin

```python
class StateMachineMixin:
    def get_current_state(self) -> Optional[str]
    def get_state_context(self) -> Dict[str, Any]
    def get_allowed_transitions(self) -> List[str]
    def can_transition_to(self, to_state: str, context: Dict[str, Any] = None) -> bool
    def transition_to(self, to_state: str, context: Dict[str, Any] = None,
                   force: bool = False) -> bool
    def set_state_context(self, key: str, value: Any)
    def get_state_context_value(self, key: str, default: Any = None) -> Any
    def add_state_timer(self, timer_id: str, timeout_seconds: int,
                      target_state: str = None, action: Callable = None,
                      context: Dict[str, Any] = None) -> bool
    def remove_state_timer(self, timer_id: str) -> bool
    def get_state_timers(self) -> List[Timer]
    def get_state_history(self, limit: int = 100)
    def get_state_prompt_injection(self) -> str
    def reset_state_machine(self, force: bool = False)
    def cleanup_state_machine(self)
```

### StateMachineConfig

```python
@dataclass
class StateMachineConfig:
    enabled: bool = False                      # 是否启用状态机
    schema_name: Optional[str] = None          # Schema 名称
    auto_inject_state: bool = True            # 是否自动注入状态到 Prompt
    state_inject_format: str = "compact"      # 注入格式: compact, detailed, minimal
    custom_state_template: Optional[str] = None  # 自定义注入模板
    enable_timers: bool = True                # 是否启用定时器
    on_state_change: Optional[Callable] = None  # 状态变更回调
```

## 预置 Schema

### aibd_sales（AIBD 销售流程）

用于 AIBD 销售场景的状态跟踪：

```
idle → querying → analyzing → proposing → negotiating → closing → followup → completed
                                                              ↓
                                                            failed
```

### aibd_task_dispatch（AIBD 任务调度）

用于 AIBD 任务分发场景的状态跟踪：

```
pending → assigned → in_progress → review → approved → completed
                                        ↓
                                      rejected
```

## 最佳实践

### 1. Schema 设计

- 保持状态空间简洁，避免过度细分
- 明确定义初始状态和终止状态
- 使用有意义的转移条件
- 在 metadata 中记录 Schema 用途

### 2. 上下文管理

- 使用上下文存储业务相关数据
- 避免在上下文中存储大量数据
- 使用有意义的键名

### 3. 定时器使用

- 为定时器使用清晰的 ID
- 合理设置超时时间
- 及时清理不再需要的定时器

### 4. 错误处理

- 捕获并记录状态转移错误
- 在终止状态进行必要的清理
- 使用 force 参数谨慎处理异常情况

## 故障排查

### 状态机未初始化

```
错误：Schema 'xxx' 未注册
解决：确保 Schema 已通过 SchemaRegistry.register() 注册
```

### 非法状态转移

```
错误：不允许从 'A' 转移到 'B'
解决：检查 Schema 中是否定义了该转移，或使用 force=True 强制转移
```

### 存储问题

```
错误：无法保存状态
解决：检查存储路径权限，确保 JSON/SQLite 文件可写
```

## 相关文件

- `agent/state_schema.py` - Schema 定义和注册
- `agent/state_store.py` - 状态存储后端
- `agent/state_machine.py` - 状态机引擎
- `agent/state_integration.py` - Agent 集成层
- `tools/state_tool.py` - Agent 状态管理工具
- `hermes_cli/state_cli.py` - CLI 状态管理命令
- `tests/test_state_machine.py` - 测试用例
