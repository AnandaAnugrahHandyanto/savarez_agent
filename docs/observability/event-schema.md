# Hermes 观测打点事件与字段说明

> 与 `agent/observability.py`、`web/src/lib/analytics.ts`、`web/src/lib/api.ts` 中的字段约定保持一致。

## 1. 通用字段（全局通用属性）

以下字段会在前后端上报时尽量补充（若可得）：

- `trace_id`: 同一次链路的 `trace_id`
- `request_id`: 前端每次请求的唯一 ID
- `span_id`: 当前 span id（仅后端 tracing 开启时）
- `user_id`: 会话用户/会话标识（可为空）
- `session_id`: 会话 ID
- `env`: 运行环境（local / prod）
- `service`: `hermes-agent`
- `version`: build/version 字段
- `source`: 事件来源，当前固定值 `dashboard` / `agent`

## 2. 后端事件

### `agent_turn_started`
会话回合开始。

- `session_id`
- `model`
- `provider`
- `platform`
- `history_count`

### `llm_call_completed`
LLM API 调用成功返回。

- `session_id`
- `api_call_count`
- `model`
- `provider`
- `duration_ms`

### `api_error`
`run_conversation` 外层异常（不中断主链路）。

- `session_id`
- `api_call_count`
- `model`
- `provider`
- `error`

### `agent_turn_completed`
会话回合结束。

- `session_id`
- `model`
- `provider`
- `api_calls`
- `completed`
- `failed`
- `interrupted`
- `turn_exit_reason`
- `input_tokens`
- `output_tokens`
- `total_tokens`

### `tool_used`
工具调用完成。

- `tool_name`
- `task_id`
- `session_id`
- `tool_call_id`
- `duration_ms`

### `dashboard_api_request`
HTTP API 成功返回（`/api/*`，状态码 < 400）。

- `method`
- `path`
- `status_code`
- `duration_ms`
- `request_id`
- `correlation_id`

### `dashboard_api_error`
API 异常/返回错误。

- `method`
- `path`
- `status_code`（有响应时）
- `duration_ms`（有响应时）
- `request_id`
- `correlation_id`
- `error`（异常时）

### `gateway_restart_requested`
Dashboard 触发网关重启。

- `pid`

### `hermes_update_requested`
Dashboard 触发版本更新。

- `pid`

### `model_set`
模型配置变更。

- `scope`
- `provider`
- `model` / `reset`

### `config_saved`
配置保存。

- `mode`: `structured` 或 `raw_yaml`

### `session_deleted`
会话删除。

- `session_id`

### `plugin_enabled` / `plugin_disabled`
插件开关。

- `name`

## 3. 前端事件

### `dashboard_api_error`
前端 fetch 封装里对非 2xx 的接口请求。

- `url`
- `status`
- `request_id`
- `trace_id`

## 4. 追踪透传字段

- 后端通过 `X-Request-Id` 回传给前端。
- 后端会为每次 `/api/*` 响应回传 `X-Trace-Id`。
- 前端 `analytics.rememberResponse()` 会从响应头更新本地上下文，作为后续打点的默认 `request_id/trace_id`。
