# 第二阶段交付报告：Hermes 飞书多 Agent 最小工程闭环

## 1. 本次改了什么

本次按第二阶段完整需求落地了最小工程闭环，不只是 `outbound_log` 单点：

- 新增 workflow profile 读取与校验。
- 新增 workflow / task 状态记录。
- 新增 PM dispatcher，支持三类基础输入。
- 新增发送前 message validator。
- 新增用户侧 message renderer / tool log 过滤。
- 扩展 outbound_log，增加 `workflow_id`、`task_id`、`to_role`、`real_sent`。
- 接入 Feishu 真实发送链路：发送前校验，发送后记录 outbound_log，并更新 task_state。
- 接入 GatewayRunner：PM 消息先进入 dispatcher，生成 task 和独立 message event 后再发送。

## 2. 新增文件

- `gateway/workflow_profile.py`
- `gateway/task_state.py`
- `gateway/dispatcher.py`
- `gateway/message_validator.py`
- `gateway/message_renderer.py`
- `workflow_profiles/director_group/current.json`
- `workflow_state/active_workflows.json`
- `tests/gateway/test_workflow_dispatch.py`
- `docs/phase2_minimal_workflow_closure_report.md`

说明：`gateway/outbound_log.py` 和 `tests/gateway/test_outbound_log.py` 在当前工作区中已是未跟踪文件，本次是在现有文件基础上扩展字段和测试。

## 3. 修改文件

- `gateway/outbound_log.py`
- `gateway/platforms/feishu.py`
- `gateway/run.py`
- `tests/gateway/test_outbound_log.py`

注意：`gateway/platforms/feishu.py` 和 `gateway/run.py` 在本次开始前已经包含其他未提交改动。本次只在现有文件中追加第二阶段接入点，没有回滚或覆盖既有改动。

## 4. 每个模块职责

### workflow_profile

- 文件：`gateway/workflow_profile.py`
- 读取：`workflow_profiles/<profile_id>/current.json`
- 默认 profile：`director_group`
- 支持环境变量覆盖：`HERMES_WORKFLOW_PROFILE_DIR`
- 职责：校验 `profile_id`、`enabled`、`dispatcher_role`、`roles`、`message_rules`，并按 `role_id` / `capability` 查找角色。

### task_state

- 文件：`gateway/task_state.py`
- 默认状态文件：`workflow_state/active_workflows.json`
- 支持环境变量覆盖：`HERMES_WORKFLOW_STATE_PATH`
- 职责：创建 `workflow_id` / `task_id`，维护 `pending_tasks`、`completed_tasks`、`blocked_tasks`，发送成功后更新 `real_sent=true` 和 `message_id`。

### dispatcher

- 文件：`gateway/dispatcher.py`
- 职责：识别 PM 消息，生成 workflow/task/message event。
- 已支持：
  - `PM 做个恐怖片`
  - `PM 继续`
  - `PM 分别发给 wz / art / by / fx，不要写在一条信息里`

### message_validator

- 文件：`gateway/message_validator.py`
- 职责：发送前拦截错误派单。
- 已拦截：
  - 单条消息驱动多个角色。
  - 缺 `deliverable`。
  - 缺 `return_to`。
  - 目标角色不在 profile。
  - PM / dispatcher 被设为审核人。
  - draft / preview 被标记为 `real_sent`。
  - 暴露 `hermes command`、`tool.started`、`terminal args`、`python traceback`、`正在执行命令`。
  - 缺 reviewer / next_node 却标记 completed。

### message_renderer

- 文件：`gateway/message_renderer.py`
- 职责：生成用户侧协作状态文案，并过滤底层命令 / tool log 行。

### outbound_log

- 文件：`gateway/outbound_log.py`
- 职责：记录真实发送尝试和发送结果。
- 只有 `send_type=feishu_real_send`、`send_success=true` 且拿到 `feishu_message_id` 时，才会记录 `real_sent=true`。

## 5. outbound_log 表结构

当前 `outbound_log` 表包含：

- `outbound_id`
- `created_at`
- `platform`
- `chat_id`
- `chat_type`
- `source_message_id`
- `reply_to_message_id`
- `send_type`
- `workflow_id`
- `task_id`
- `to_role`
- `target_role`
- `target_profile`
- `content_hash`
- `content_preview`
- `send_success`
- `feishu_message_id`
- `real_sent`
- `error`
- `raw_response_summary`

本次新增 / 扩展的关键字段：

- `workflow_id`
- `task_id`
- `to_role`
- `real_sent`

并增加了 schema migration，旧库缺字段时会自动 `ALTER TABLE` 补齐。

## 6. 接入位置与当前调用链路

### PM dispatcher 接入

- 文件：`gateway/run.py`
- 位置：`GatewayRunner._handle_message_with_agent()`
- 行为：普通 agent 前先调用 `dispatch_pm_message()`。

当前链路：

```text
飞书消息进入 GatewayRunner
→ _handle_message_with_agent()
→ dispatch_pm_message()
→ create_workflow / create_task
→ validate_message_events()
→ adapter.send(..., metadata=workflow/task)
→ render_dispatch_result()
```

### 发送前 validator 接入

- 文件：`gateway/platforms/feishu.py`
- 位置：`FeishuAdapter.send()`
- 行为：真实调用飞书 API 前，若 metadata 中包含 workflow/task 信息，则调用 `_validate_workflow_outbound()`。

当前链路：

```text
FeishuAdapter.send()
→ _validate_workflow_outbound()
→ validate_message_event()
→ 通过后继续 _feishu_send_with_retry()
→ 未通过则 record_outbound(send_type=blocked_by_validator, real_sent=false)
```

### 发送后 outbound_log / task_state 接入

- 文件：`gateway/platforms/feishu.py`
- 位置：`_record_feishu_send_outbound()`
- 行为：记录 outbound_log；若飞书成功返回 `message_id`，则调用 `mark_task_sent()`。

当前链路：

```text
_feishu_send_with_retry()
→ _finalize_send_result()
→ _record_feishu_send_outbound()
→ record_outbound()
→ mark_task_sent(real_sent=true, message_id=...)
```

### tool log 展示过滤接入

- 文件：`gateway/run.py`
- 位置：agent progress callback
- 行为：进度消息进入飞书前先调用 `sanitize_user_visible_message()`。

## 7. 三个测试用例结果

执行命令：

```bash
venv/bin/pytest -q tests/gateway/test_workflow_dispatch.py tests/gateway/test_outbound_log.py
```

结果：

```text
10 passed, 8 warnings in 4.26s
```

覆盖：

- 测试 1：`PM 做个恐怖片`
  - `intent=rough_creative_request`
  - `matched_capability=direction_decision`
  - `matched_role=dd`
  - `task_count=1`
  - `message_event_count=1`
  - `next_state=waiting_for_dd`
  - `validator=pass`

- 测试 2：`PM 继续`
  - 无 active workflow：返回 `need_judgement`
  - 有 active workflow：返回 `continue_dispatch`

- 测试 3：`PM 分别发给 wz / art / by / fx，不要写在一条信息里`
  - `target_roles=["wz", "art", "by", "fx"]`
  - `task_objects=4`
  - `message_events=4`
  - `merged_message=false`
  - `validator=pass`

额外覆盖：

- Feishu 真实发送成功后记录 `feishu_message_id`。
- Feishu 真实发送成功后 `task_state.real_sent=true`。
- Feishu 发送失败时 `real_sent=false`。
- outbound_log 写入失败不影响原始发送结果。
- renderer 能过滤 `tool.started` / `hermes -p ...`。

## 8. 是否已实现关键能力

- `workflow profile`：已实现最小读取与校验。
- `task_state`：已实现最小 workflow/task 状态。
- `dispatcher`：已实现三类基础 PM 输入。
- `message_validator`：已实现发送前最小强校验。
- `message_renderer`：已实现用户侧最小过滤。
- `outbound_log / real_sent`：已实现，`real_sent` 以飞书 `message_id` 为准。
- 多角色“分别发”：已实现为多个独立 `message_event`，dispatcher 生成 4 个 event，Gateway 逐条调用 `adapter.send()`。
- PM 越权审核：validator 已拦截 dispatcher 作为 reviewer / final_reviewer 的情况。
- 底层命令隐藏：renderer 已过滤核心内部命令 / tool log 行。

## 9. 还没闭环的项目

本次没有做：

- HTML 配置页。
- Template registry。
- Obsidian 自动写入。
- MemOS 自动写入。
- 大型 publisher。
- rollback 发布回滚系统。
- 可视化流程图。
- 复杂权限后台。
- 完整多团队模板市场。

仍需后续加强：

- task_state 当前是 JSON 文件，尚未实现并发锁和恢复策略。
- dispatcher 当前只覆盖三条基础测试输入，尚未覆盖完整工作流决策。
- validator 是最小规则集，尚未支持复杂 profile rule DSL。
- renderer 是最小行级过滤，尚未做完整展示分层。
- role 返回识别只保留了 `mark_task_returned()` 能力，尚未接入真实 inbound return event。
- 多角色发送当前逐条调用 adapter，尚未做失败重试、部分成功补偿和确认汇总。

## 10. 风险与注意事项

- `gateway/platforms/feishu.py` 和 `gateway/run.py` 当前存在其他未提交改动，合并时需要按功能块审查，避免把无关改动混入第二阶段提交。
- JSON task_state 适合最小闭环，不适合高并发生产写入。
- `real_sent=true` 已绑定 `message_id`，但多 chunk 消息目前只记录最后一个 `message_id`。
- 发送前校验只在 metadata 包含 workflow/task 信息时启用，不影响普通飞书消息发送。
- 当前 dispatcher 使用默认 `director_group` profile，后续需要把 profile selection 从入口配置化。

## 11. 下一步建议

建议第三阶段按最小测试发布闭环推进：

1. 给 `task_state` 增加文件锁或迁移到现有 `SessionDB` / SQLite，避免并发写入覆盖。
2. 接入角色返回识别，把真实 inbound return event 更新到 `completed_tasks`。
3. 给多角色逐条发送增加部分失败记录、重试和用户侧确认摘要。
4. 把 profile selection 从硬默认 `director_group` 改为 group profile / chat config 驱动。
5. 增加 simulator，用同一套 dispatcher / validator / renderer 跑离线沙盒测试。
6. 暂缓 HTML 配置页、publisher、rollback、template registry，先把真实收发闭环跑稳。
