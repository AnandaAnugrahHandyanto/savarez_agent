# Hermes-Agent 官方版补丁指南

> 安装全新官方版 hermes-agent 后，使用 GLM-5.1 (智谱 AI) 需要手动应用的补丁。
> 每次升级官方版后，检查以下补丁是否已被上游修复；未修复则需重新应用。

---

## 配置

编辑 `~/.hermes/config.yaml`：

```yaml
model:
  default: glm-5.1
  provider: custom
  base_url: https://open.bigmodel.cn/api/coding/paas/v4
  api_key: <your-key>
  context_length: 204800    # GLM-5.1 实际支持 200K 上下文

agent:
  max_turns: 90             # 工具调用最大轮次
  gateway_timeout: 1800     # 30 分钟超时
```

---

## 补丁 1: 自定义 Provider 未设置 max_tokens

**文件**: `run_agent.py`

**问题**: hermes 调用自定义 OpenAI 兼容 API（如 GLM-5.1）时不传 `max_tokens` 参数。
API 使用默认值（约 4096），思考模式（reasoning_content）与实际内容共享此预算。
模型推理耗光 token 后，`content` 字段为空，导致 "(empty)" 响应。

**定位**: 搜索 `self._is_openrouter_url()`，找到 `if self.max_tokens is not None` 附近的 `elif` 链。

**修复**: 在 `elif` 链末尾添加：
```python
elif self.api_mode == "chat_completions" and not self._is_direct_openai_url():
    # Custom OpenAI-compatible providers (Zhipu/GLM, Moonshot, etc.)
    # often have low default max_tokens (e.g. 4096). When the model
    # uses thinking/reasoning mode, reasoning tokens share the same
    # output budget — the model exhausts tokens on reasoning and
    # produces no visible content.  Set a generous default (16K)
    # based on context_length to prevent this.
    _ctx_len = getattr(getattr(self, "context_compressor", None), "context_length", 0) or 0
    if _ctx_len > 0:
        _default_output = min(max(_ctx_len // 3, 32768), 131072)
        api_kwargs["max_tokens"] = _default_output
```

**效果**: GLM-5.1 context_length=204800 → max_tokens=68266

---

## 补丁 2: 空内容响应不重试

**文件**: `run_agent.py`

**问题**: 当 GLM-5.1 在工具调用后返回纯推理内容（无可见文本）时，
原代码直接设 `"(empty)"` 并退出循环，不进行任何重试。
注释写 "No retries needed" 是错误的。

**定位**: 搜索 `"No retries needed"` 或 `"(empty)"`，找到 reasoning-only 分支。

**修复**: 替换为带重试的逻辑：
```python
# Reasoning-only or empty response: the model produced
# thinking but no visible content.  When this happens
# after tool calls (model was actively working), retry
# with a continuation prompt instead of giving up.
reasoning_text = self._extract_reasoning(assistant_message)
if not hasattr(self, '_empty_content_retries'):
    self._empty_content_retries = 0

_has_prior_tool_calls = any(
    msg.get("role") == "assistant" and msg.get("tool_calls")
    for msg in messages[-10:]
)

if _has_prior_tool_calls and self._empty_content_retries < 2:
    self._empty_content_retries += 1
    if reasoning_text:
        reasoning_preview = reasoning_text[:300] + "..." if len(reasoning_text) > 300 else reasoning_text
        self._vprint(f"{self.log_prefix}Reasoning-only response after tool calls — retrying ({self._empty_content_retries}/2). Reasoning: {reasoning_preview}")
    else:
        self._vprint(f"{self.log_prefix}Empty response after tool calls — retrying ({self._empty_content_retries}/2)")

    interim_msg = self._build_assistant_message(assistant_message, "incomplete")
    interim_msg["content"] = ""
    messages.append(interim_msg)

    continue_msg = {
        "role": "user",
        "content": (
            "[System: Your previous response contained only reasoning/thinking "
            "but no visible content. Please provide your actual response now, "
            "continuing the task from where you left off.]"
        ),
    }
    messages.append(continue_msg)
    self._session_messages = messages
    self._save_session_log(messages)
    continue

# Exhausted retries or no prior tool calls — accept as empty.
assistant_msg = self._build_assistant_message(assistant_message, finish_reason)
assistant_msg["content"] = "(empty)"
messages.append(assistant_msg)

if reasoning_text:
    reasoning_preview = reasoning_text[:500] + "..." if len(reasoning_text) > 500 else reasoning_text
    self._vprint(f"{self.log_prefix}Reasoning-only response (no visible content, retries exhausted). Reasoning: {reasoning_preview}")
else:
    self._vprint(f"{self.log_prefix}Empty response (no content or reasoning).")

final_response = "(empty)"
break
```

---

## 补丁 3: 工具循环中 API 调用间未清理死连接

**文件**: `run_agent.py`

**问题**: `_cleanup_dead_connections()` 只在 `run_conversation()` 开头调用一次。
在工具循环中多次 API 调用之间，HTTP 连接可能进入 CLOSE-WAIT 状态
（远端关闭但本地未关闭），导致下一次 API 调用挂在死连接上，agent 无响应。

**定位**: 搜索 `starting API call #`，找到 `api_call_count += 1` 后、`iteration_budget.consume()` 前。

**修复**: 在每次 API 调用计数后添加：
```python
# Clean up dead connections before each API call to prevent hangs
# on stale keep-alive sockets (CLOSE-WAIT from provider idle timeout).
if api_call_count > 1 and self.api_mode != "anthropic_messages":
    try:
        if self._cleanup_dead_connections():
            self._vprint(f"{self.log_prefix}Cleaned up stale connection before API call #{api_call_count}")
    except Exception:
        pass
```

---

## 补丁 4: API 429 重试次数过少

**文件**: `run_agent.py`

**问题**: 默认 `max_retries = 3`，遇到 429 限速时很快耗尽重试机会。

**修复**: 搜索 `max_retries = 3`，改为 `max_retries = 10`。

---

## 补丁 5: Stream 超时未考虑思考模型的推理时间

**文件**: `run_agent.py`

**问题**: 流式响应的 stale 超时默认 180s，只根据上下文大小缩放。
思考模型（如 GLM-5.1）即使上下文很小，也可能在推理阶段花费数分钟。
180s 超时会误杀正在思考的健康连接。

**定位**: 搜索 `HERMES_STREAM_STALE_TIMEOUT`，找到 `_est_tokens` 计算处。

**修复**: 增加 `max_tokens` 维度的缩放：
```python
_est_tokens = sum(len(str(v)) for v in api_kwargs.get("messages", [])) // 4
_output_budget = api_kwargs.get("max_tokens", 0) or 0
if _output_budget > 65536:
    _stream_stale_timeout = max(_stream_stale_timeout_base, 420.0)  # 7 min
elif _output_budget > 32768:
    _stream_stale_timeout = max(_stream_stale_timeout_base, 300.0)  # 5 min
elif _est_tokens > 100_000:
    _stream_stale_timeout = max(_stream_stale_timeout_base, 300.0)
elif _est_tokens > 50_000:
    _stream_stale_timeout = max(_stream_stale_timeout_base, 240.0)
else:
    _stream_stale_timeout = _stream_stale_timeout_base
```

**效果**: GLM-5.1 max_tokens=68266 → 300s（5分钟）超时

---

## 补丁 6: httpx 逐块读取超时未适配思考模型

**文件**: `run_agent.py`

**问题**: httpx 流式客户端的 socket 级 `read_timeout` 默认 60 秒。
思考模型在推理阶段可能超过 60 秒不发任何 chunk，
httpx 直接抛 `ReadTimeout` 异常，连接中断。

**定位**: 搜索 `HERMES_STREAM_READ_TIMEOUT`。

**修复**: 根据 `max_tokens` 缩放：
```python
_stream_read_timeout = float(os.getenv("HERMES_STREAM_READ_TIMEOUT", 60.0))
_output_budget = api_kwargs.get("max_tokens", 0) or 0
if _output_budget > 32768:
    _stream_read_timeout = max(_stream_read_timeout, 180.0)  # 3 min per-chunk
```

**注意**: 此超时与补丁 5 的 stale 超时是两个独立机制：
- stale 超时: 独立线程监控，全局无数据 N 秒后断开
- read timeout: httpx socket 级，两次 chunk 之间的最大等待

---

## 补丁 7: 凭证池 429 冷却时间过长

**文件**: `agent/credential_pool.py`

**问题**: 429 错误后冷却时间为 1 小时，导致用户被锁定无法使用。

**修复**: 搜索 `EXHAUSTED_TTL_429_SECONDS`，将 `60 * 60` 改为 `60 * 3`（3 分钟）。

---

## 补丁 8: Agent 对话无故中断（Gateway 模式专用）

**适用场景**: 仅在使用 `hermes gateway run`（API Server 模式）时需要。

### 修复 1: 生产端 — `gateway/run.py`

搜索 `already_sent`，找到设置 `response["already_sent"] = True` 的位置：

```python
# 修复前:
if _sc and _sc.already_sent and isinstance(response, dict):
    response["already_sent"] = True

# 修复后: 失败时不标记 already_sent，确保错误能传递
if _sc and _sc.already_sent and isinstance(response, dict):
    if not response.get("failed"):
        response["already_sent"] = True
```

### 修复 2: 消费端 — `gateway/run.py`

搜索 `agent_result.get("already_sent")`：

```python
# 修复前:
if agent_result.get("already_sent"):

# 修复后:
if agent_result.get("already_sent") and not agent_result.get("failed"):
```

### 修复 3: SSE 事件 — `gateway/platforms/api_server.py`

在 `assistant.completed` 和 `run.completed` 事件中增加失败字段：
```python
"failed": result.get("failed", False),
"error": result.get("error"),
```

### 修复 4: catch-all 异常 — `gateway/platforms/api_server.py`

在 SSE 流处理的外层添加：
```python
except Exception as _sse_err:
    logger.exception("Session SSE stream error for %s: %s", session_id, _sse_err)
    try:
        await response.write(_encode_sse("run.failed", {
            "session_id": session_id,
            "run_id": run_id,
            "error": str(_sse_err)[:500],
        }))
        await response.write(_encode_sse("done", {"session_id": session_id, "run_id": run_id, "state": "error"}))
    except Exception:
        pass
```

### 修复 5: 降低并发上限 — `gateway/platforms/api_server.py`

GLM API 限速严格，降低并发防止 429：

```python
# 修复前:
_MAX_CONCURRENT_RUNS = 10

# 修复后:
_MAX_CONCURRENT_RUNS = 3
```

---

## 验证清单

升级官方版后，按以下步骤确认：

| # | 检查项 | 验证方法 |
|---|--------|----------|
| 1 | max_tokens 生效 | agent 日志中搜索 `max_tokens`，确认值 > 4096 |
| 2 | 空内容重试 | 发送复杂工具调用任务，观察是否出现 "(empty)" |
| 3 | 死连接清理 | 执行多轮工具调用任务，确认不会卡住 |
| 4 | 429 恢复 | 触发限速后观察是否在 3 分钟内恢复 |
| 5 | 凭证池 | 检查 `~/.hermes/auth.json` 中凭证是否正常恢复 |
| 6 | Gateway 错误传递 | 通过 API 发起多轮 tool call 任务，中途制造 API 错误，确认有错误返回而非静默断开 |
