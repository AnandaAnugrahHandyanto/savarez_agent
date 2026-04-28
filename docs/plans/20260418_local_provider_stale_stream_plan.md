# Plan: Local provider long-stream / stale watchdog hardening

**Date**: 2026-04-18  
**Base**: `main` @ mirror pull (HEAD `78a74bb0` in Beta_33)  
**Intel**: Issue #5889 class — provider appears silent while local compute continues; WSL / long vision preprocess stacks risk.

## 现状快照（避免重复造轮）

- **`run_agent.py` ~5887–5906**：已在默认 `HERMES_STREAM_STALE_TIMEOUT == 180` 且 `is_local_endpoint(self.base_url)` 时把流式 stale 阈值设为 `float("inf")`，并对非流式 `HERMES_API_CALL_STALE_TIMEOUT` 在本地默认 300 时同样放宽为 `inf`（~5174–5184）。
- **`run_agent.py` ~5479–5493**：本地 endpoint 下默认把 `HERMES_STREAM_READ_TIMEOUT` 从 120 抬到与 `HERMES_API_TIMEOUT` 一致。
- **`agent/model_metadata.py`：`is_local_endpoint()`** 已覆盖 localhost、RFC1918、部分容器 DNS、WSL 常见私网段。
- **缺口（规划动机）**：`base_url` 未被识别为 local（例如自定义域名反代、非标准 host）时仍会走 180s stale；`HERMES_STREAM_STALE_TIMEOUT` 被用户显式设为 `180` 时与「未设置」区分逻辑仅依赖 `== 180.0` 默认值分支；缺少「显式 local provider」配置与 **health 探针** 兜底；缺少 **长耗时本地流** 的集成级回归。

## 前置宪法动作（执行开发前必做）

1. 在 **`E:\MyPROJECT\NousPR\Master_Ledger.md`** 标题正下方、索引表之上插入免战牌（执行编码前，由实施者写入），目标文件建议写：`run_agent.py` / `agent/model_metadata.py` / 新增测试路径。
2. 若与账本 **#008**（`run_agent.py` 插件拦截回调）并行，优先 Rebase 或协作同一 PR，避免冲突。

---

## 原子任务清单（文件级）

**[Step 1]**: 收敛「本地 provider」判定源（单一真相）

- **File**: `agent/model_metadata.py`（或新建极薄模块 `agent/local_provider.py` 并由 `run_agent` 引用，避免单文件膨胀时拆分）
- **Action**: Modify / Create
- **Details**:
  - 增加显式 **`is_local_provider`** 语义：`(is_local_endpoint(base_url)) OR (config 白名单：如 `provider.local: true` / `HERMES_FORCE_LOCAL_PROVIDER=1`)`（具体键名与 `config.yaml` 现有 schema 对齐，优先复用已有 custom provider 字段）。
  - 将 `run_agent.py` 内重复的 `is_local_endpoint(self.base_url)` stale/read 分支改为调用单一 helper，避免一处改了另一处漏。
- **Verification**: `pytest tests/agent/test_local_stream_timeout.py -q -o addopts=` 全绿；新增单测覆盖「非公网 IP 但被标记为 local」的配置分支。

**[Step 2]**: 统一 stale 策略（流式 + 非流式 + 显式 env）

- **File**: `run_agent.py`（`_run_streaming_chat_completion` 外圈轮询 ~5887+；非流式 `_call` 轮询 ~5174+）
- **Action**: Modify
- **Details**:
  - 用 Step 1 的 **`is_local_provider`** 替换仅 `is_local_endpoint` 的分支。
  - 产品决策二选一（实施前在 PR 描述写清）：**A)** 本地仍用 `inf`（当前行为）；**B)** 改为上限 **3600s**（防止真死连接永不释放）。推荐 **B + env 覆盖**（`HERMES_LOCAL_STREAM_STALE_TIMEOUT`，默认 3600，`0` 表示 inf）。
  - 文档化：若用户显式设置 `HERMES_STREAM_STALE_TIMEOUT`，本地是否仍允许拉长 —— 建议「显式 local 标记优先于用户 180」，避免误杀。
- **Verification**: 扩展 `tests/agent/test_local_stream_timeout.py` 或并列新文件，mock 时间/线程，断言本地在 N 秒内不触发 `stale_stream_kill`。

**[Step 3]**: Per-stream 活动信号与「token 回调」对齐（可选增强）

- **File**: `run_agent.py`（`last_chunk_time` 更新点：OpenAI chunk 循环 ~5533；Anthropic event 循环 ~5700+）
- **Action**: Modify
- **Details**:
  - 确保 **任意** 会阻断 `delta.content` 但仍推进推理的路径（如仅 `usage`、`ping` chunk）也更新 `last_chunk_time` 或单独的 **`_stream_progress_time`**，避免「有 SSE 无 token」误判；若 Issue 根因是 ping-only，则改为：仅当「无内容类事件」超过 T1 才计入 stale，有内容类事件重置 T2（文档中写清状态机）。
- **Verification**: 新增单元测试：模拟「仅空 choices / usage chunk」与「无 chunk」两种序列，期望行为与注释一致。

**[Step 4]**: 集成测试 `test_local_stream_long`（或并入现有命名）

- **File**: `tests/run_agent/test_local_stream_long.py`（新建）或 `tests/agent/test_local_stream_timeout.py`（扩展）
- **Action**: Create / Modify
- **Details**:
  - 使用 `httpx`/`respx` 或进程内 mock stream，使 **首个 token 延迟 > 200s**（快测可用 monkeypatch `time.time` 缩放或调低阈值 env）。
  - 断言：不触发重连、不调用 `_close_request_openai_client(..., reason="stale_stream_kill")`（可用 spy/mock）。
- **Verification**: `python "C:\Users\Administrator\.cursor\skills\test-sentinel\scripts\test_runner.py"` 或 `pytest <file> -q -o addopts=`。

**[Step 5]**: Provider health probe（`/healthz` / `/health` fallback）

- **File**: `agent/model_metadata.py` 或新 `agent/provider_health.py`；调用点：`run_agent.py` 在首次建连前或 stale 触发前（限频，如每会话一次）
- **Action**: Create / Modify
- **Details**:
  - 对 **local** base_url：`GET {base}/healthz`，失败则 `GET {base}/health`、`GET {base}/v1/models`（与 `detect_local_server_type` 探针风格一致，复用超时常量）。
  - 仅作 **fallback 信号**（日志 + 可选延长 stale），避免阻塞主路径；失败不阻断请求。
- **Verification**: `pytest` 使用 `httpx.MockTransport` 覆盖 200/404/timeout 分支。

**[Step 6]**: 配置与文档

- **File**: `.env.example`（若存在相关 HERMES_* 说明）、`website/docs` 或现有 env 文档（仅当仓库已有对应章节时增量一行，避免无请求的大文档改动）
- **Action**: Modify
- **Details**: 记录 `HERMES_STREAM_STALE_TIMEOUT`、`HERMES_LOCAL_STREAM_STALE_TIMEOUT`、local 标记配置键。
- **Verification**: 文档构建非强制；至少 grep 确认新 env 在 `.env.example` 可发现。

---

## 风险与依赖

- **`run_agent.py` 体量**：若单文件修改超过工作区「150 行」红线，将 **Step 1 helper** 与 **Step 5 probe** 抽到 `agent/` 下新模块，保持 `run_agent` 仅接线。
- **与 OPEN PR 关系**：雷达上 gateway / provider 类 PR 较多；本改动聚焦 **agent 流式轮询**，与 **#008** 文件重叠需注意 rebase。

---

## Plan Master 闭环确认

> 以上是精确到文件级别的原子化任务拆解。是否合理？如果无误，请回复「按计划执行」，实施方将按步骤逐一击破并运行 `test-sentinel` 验证。
