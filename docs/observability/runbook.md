# Hermes 观测可观测性快速运行清单（免费优先）

## 先决条件

- 前端依赖：`web/package.json` 与 `web/package-lock.json` 已包含 `posthog-js`。
- 后端可读写：`agent/observability.py`、`hermes_cli/web_server.py`。
- 默认配置关闭埋点（fail-open），可通过配置显式开启。

## 0. 快速开关（最小侵入）

后端配置（~/.hermes/config.yaml）可设置：

```yaml
observability:
  enabled: true
  analytics_enabled: true
  tracing_enabled: true
  structured_json_logs: true
  posthog_project_api_key: "<你的 posthog project key>"
  # 可选
  posthog_host: "https://us.i.posthog.com"
  otlp_endpoint: "http://localhost:4317"
```

说明：`enabled` 为总开关，`analytics_enabled`/`tracing_enabled` 为子开关。

## 1. 运行时验收（必须过）

1. 安装前后端依赖后，在 web 目录打包通过
   - `cd web && npm run -s build`
2. 启动服务并抓一条 `/api/observability/config`
   - 返回字段必须含：`enabled`、`posthog_host`、`posthog_project_api_key`、`env`、`service`、`version`
3. 触发一次 Dashboard API（如 `GET /api/status`），检查响应头：
   - `X-Request-Id`
   - `X-Trace-Id`
4. 前端请求路径里需有 `@/lib/analytics.ts` 和 `api.ts` 引用；非 2xx 的响应会打 `dashboard_api_error`。

## 2. 链路打通检查

- 后端：`hermes_cli/web_server.py` 全局中间件注入 request_id/correlation/trace id，并在 `/api/*` 追加 `X-Trace-Id`。
- 前端：`analytics.rememberResponse` 每次 fetch 回填本地 `trace_id/request_id`。
- 任何 dashboard 侧事件应可在日志/面板里按 request 维度关联。

## 3. 故障隔离要求（默认保持）

- 所有打点/埋点异常都需要 `try/except` 兜底，不影响主流程。
- 默认配置中 `enabled=False` 与 `analytics_enabled=False`。

## 4. 脱敏与安全

- `agent/observability.py` 内置敏感字段清洗：
  - `token/password/authorization/api key/secret/credential/phone/id card` 等。
- 禁止上报明文 `token`、`secret`、手机号/身份证号。

## 5. 推荐排障命令

- 查看当前变更内容：
  - `git status --short`
- 前端：
  - `cd web && npm run -s build`
- 后端：
  - `python -m pytest -q tests/plugins/test_disk_cleanup_plugin.py`
  - `python - <<'PY' ... TestClient(...) ...`

## 6. 里程碑（可复用）

1. 先验收 API 透传与 `dashboard_api_*` 打点
2. 再接入 PostHog/Jaeger/Tempo 的可视化看板
3. 最后补充关键页面交互打点（按钮/重试/设置保存等）
