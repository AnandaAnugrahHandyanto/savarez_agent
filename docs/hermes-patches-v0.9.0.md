# Hermes-Agent v0.9.0 补丁状态报告

> 生成日期: 2026-04-14
> 基于版本: v0.9.0 (commit 5621fc44)
> 目标用途: GLM-5.1 (智谱 AI) 兼容性

---

## 补丁状态总览

| # | 补丁名称 | 状态 | 说明 |
|---|----------|------|------|
| 1 | 自定义 Provider max_tokens | **已应用** | 为通用自定义 provider 添加 max_tokens 回退 |
| 2 | 空内容响应重试 | **上游已修复** | v0.9.0 已内置重试 + fallback 机制 |
| 3 | 工具循环死连接清理 | **已应用** | 每次 API 调用前清理死连接 |
| 4 | API 429 重试次数 | **已应用** | max_retries 3 → 10 |
| 5 | Stream stale 超时 vs 思考模型 | **已应用** | 按 max_tokens 缩放超时 |
| 6 | httpx 读超时 vs 思考模型 | **已应用** | 按 max_tokens 缩放读超时 |
| 7 | 凭证池 429 冷却时间 | **已应用** | 1 小时 → 3 分钟 |
| 8 | Gateway 中断修复 | **已应用** | 5 个子修复中 3 个已应用 |

---

## 补丁 1: 自定义 Provider 未设置 max_tokens

**状态**: 已应用

**文件**: `run_agent.py` (约第 6293 行)

**原问题**: hermes 调用自定义 OpenAI 兼容 API（如 GLM-5.1）时不传 `max_tokens` 参数。
API 使用默认值（约 4096），思考模式与实际内容共享此预算，模型推理耗光 token 后 `content` 为空。

**已应用修复**: 在 `elif` 链末尾添加了自定义 provider 分支：
```python
elif self.api_mode == "chat_completions" and not self._is_direct_openai_url():
    _ctx_len = getattr(getattr(self, "context_compressor", None), "context_length", 0) or 0
    if _ctx_len > 0:
        _default_output = min(max(_ctx_len // 3, 32768), 131072)
        api_kwargs.update(self._max_tokens_param(_default_output))
```

**效果**: GLM-5.1 context_length=204800 → max_tokens=68266

**升级检查**: 搜索 `_is_direct_openai_url` 和 `_is_qwen_portal`，检查 elif 链是否已包含通用自定义 provider 处理。

---

## 补丁 2: 空内容响应不重试

**状态**: 上游已修复 (v0.9.0)

**原问题**: 当 GLM-5.1 在工具调用后返回纯推理内容（无可见文本）时，原代码直接设 `"(empty)"` 并退出。

**当前版本**: v0.9.0 已内置完整重试机制：
- `_empty_content_retries` 计数器，最多重试 3 次
- 重试失败后尝试 fallback provider 切换
- 完整的日志和状态通知

**无需操作**。

---

## 补丁 3: 工具循环中 API 调用间未清理死连接

**状态**: 已应用

**文件**: `run_agent.py` (约第 8064 行)

**原问题**: `_cleanup_dead_connections()` 只在 `run_conversation()` 开头调用一次。
在工具循环中多次 API 调用之间，HTTP 连接可能进入 CLOSE-WAIT 状态，导致下一次 API 调用挂起。

**已应用修复**: 在每次 API 调用计数后添加清理：
```python
if api_call_count > 1 and self.api_mode != "anthropic_messages":
    try:
        if self._cleanup_dead_connections():
            self._vprint(...)
    except Exception:
        pass
```

**升级检查**: 搜索 `starting API call #`，检查 `api_call_count` 递增后是否有 `_cleanup_dead_connections` 调用。

---

## 补丁 4: API 429 重试次数过少

**状态**: 已应用

**文件**: `run_agent.py` (约第 8260 行)

**修复**: `max_retries = 3` → `max_retries = 10`

**升级检查**: 搜索 `max_retries = `，确认值 >= 10。

---

## 补丁 5: Stream stale 超时未考虑思考模型

**状态**: 已应用

**文件**: `run_agent.py` (约第 5475 行)

**原问题**: 流式响应的 stale 超时默认 180s，只根据上下文大小缩放。
思考模型即使上下文很小，也可能在推理阶段花费数分钟。

**已应用修复**: 增加 `max_tokens` 维度的缩放：
```python
_output_budget = api_kwargs.get("max_tokens", 0) or 0
if _output_budget > 65536:
    _stream_stale_timeout = max(_stream_stale_timeout_base, 420.0)  # 7 min
elif _output_budget > 32768:
    _stream_stale_timeout = max(_stream_stale_timeout_base, 300.0)  # 5 min
elif _est_tokens > 100_000:
    ...
```

**效果**: GLM-5.1 max_tokens=68266 → 420s（7分钟）超时

**升级检查**: 搜索 `HERMES_STREAM_STALE_TIMEOUT`，检查是否有 `_output_budget` 或 `max_tokens` 相关的缩放逻辑。

---

## 补丁 6: httpx 逐块读取超时未适配思考模型

**状态**: 已应用

**文件**: `run_agent.py` (约第 5064 行)

**原问题**: httpx 流式客户端的 socket 级 `read_timeout` 默认 120 秒。
思考模型在推理阶段可能超过 120 秒不发任何 chunk。

**已应用修复**: 根据 `max_tokens` 缩放：
```python
_output_budget = api_kwargs.get("max_tokens", 0) or 0
if _output_budget > 32768:
    _stream_read_timeout = max(_stream_read_timeout, 180.0)  # 3 min per-chunk
```

**升级检查**: 搜索 `HERMES_STREAM_READ_TIMEOUT`，检查是否有 `max_tokens` 相关的缩放逻辑。

---

## 补丁 7: 凭证池 429 冷却时间过长

**状态**: 已应用

**文件**: `agent/credential_pool.py` (第 74 行)

**修复**: `EXHAUSTED_TTL_429_SECONDS = 60 * 60` → `60 * 3`（3 分钟）

**升级检查**: 搜索 `EXHAUSTED_TTL_429_SECONDS`，确认值 <= `60 * 3`。

---

## 补丁 8: Agent 对话无故中断（Gateway 模式）

**状态**: 部分已应用（3/5 子修复）

### Fix 1: 生产端 — `gateway/run.py` ✅ 已应用

搜索 `response["already_sent"] = True`，已添加失败守卫：
```python
if not response.get("failed"):
    response["already_sent"] = True
```

### Fix 2: 消费端 — `gateway/run.py` ✅ 上游已修复

v0.9.0 已包含 `if agent_result.get("already_sent") and not agent_result.get("failed"):` 检查。

### Fix 3: SSE 事件 — `gateway/platforms/api_server.py` ⚠️ 未检查

SSE 事件中的 `failed` 和 `error` 字段。当前版本可能已改进，但未逐一验证。

### Fix 4: catch-all 异常 — `gateway/platforms/api_server.py` ⚠️ 未检查

SSE 流处理外层异常捕获。当前版本可能已改进，但未逐一验证。

### Fix 5: 降低并发上限 — `gateway/platforms/api_server.py` ✅ 已应用

`_MAX_CONCURRENT_RUNS = 10` → `3`

---

## 快速升级检查命令

升级官方版后，依次运行以下命令快速检查：

```bash
# 补丁 1: 自定义 provider max_tokens
grep -n "_is_direct_openai_url" run_agent.py | head -5

# 补丁 3: 工具循环死连接清理
grep -n "_cleanup_dead_connections" run_agent.py

# 补丁 4: 429 重试次数
grep -n "max_retries = " run_agent.py

# 补丁 5: Stream stale 超时
grep -n "HERMES_STREAM_STALE_TIMEOUT" run_agent.py

# 补丁 6: httpx 读超时
grep -n "HERMES_STREAM_READ_TIMEOUT" run_agent.py

# 补丁 7: 凭证池冷却
grep -n "EXHAUSTED_TTL_429_SECONDS" agent/credential_pool.py

# 补丁 8: Gateway 并发
grep -n "_MAX_CONCURRENT_RUNS" gateway/platforms/api_server.py
```

如果以上命令的输出显示补丁已包含在新版本中，则无需重新应用。
