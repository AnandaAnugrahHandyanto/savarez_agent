# 模型上下文显示/运行时对齐修复进度日志

日期：2026-04-17
状态：执行中
关联方案：`docs/plans/2026-04-17-model-context-alignment-fix-plan.md`

## 当前阶段
- Phase 1：建立基线、冻结方案、准备实施

## 基线状态
- 当前分支：`main`
- 初始工作区非本任务脏改动：
  - `M gateway/config.py`
  - `M package-lock.json`
  - `?? docs/plans/2026-04-16-get-web-router-design-plan.md`
  - `?? docs/plans/2026-04-16-get-web-router-implementation-plan.md`
  - `?? docs/plans/2026-04-16-pr-10885-followup-plan.md`
  - `?? docs/plans/2026-04-16-skill-publishing-guide-publish-plan.md`
  - `?? docs/progress/`
- 当前已确认问题：
  - 显示层 fallback 到 `128000`
  - 运行时/LCM 实际使用 `200000`
  - 配置声明值为 `524288`

## 本轮待办
- [x] 建立计划文档
- [x] 建立进度日志
- [ ] 实现显示层统一展示值
- [ ] 实现运行时 context 优先级修复
- [ ] 补测试并运行验证
- [ ] 核对 git 影响面并准备提交/PR

## 执行日志

### 2026-04-17 / Step 1
- 动作：完成只读分析，确认显示层 / 运行时 / LCM 三层问题边界。
- 结果：锁定最小修复范围为 `hermes_cli/model_switch.py`、`cli.py`、`gateway/run.py`、`run_agent.py` 及定向测试。
- 影响文件：
  - `docs/plans/2026-04-17-model-context-alignment-fix-plan.md`
  - `docs/progress/2026-04-17-model-context-alignment-fix-progress.md`
- 备注：本轮明确不改 `config.yaml` workaround，不改 LCM 阈值语义。

### 2026-04-17 / Step 2
- 动作：实现显示层统一展示值与 gateway/CLI 回显对齐。
- 结果：
  - `hermes_cli/model_switch.py` 新增 `ModelSwitchResult.display_context_length`。
  - 新增 custom provider 匹配与 `context_length` 解析 helper，优先读取 matching custom provider per-model 值。
  - `cli.py` 与 `gateway/run.py` 两条 `/model` 成功回显路径改为优先显示 `display_context_length`，避免 custom provider 走错误的 128K fallback。
- 影响文件：
  - `hermes_cli/model_switch.py`
  - `cli.py`
  - `gateway/run.py`
- 备注：gateway picker 回调和普通 `/model ...` 文本路径都已覆盖。

### 2026-04-17 / Step 3
- 动作：实现运行时 `context_length` 优先级修复与热切换刷新。
- 结果：
  - `run_agent.py` 新增共享 helper：
    - `_resolve_custom_provider_model_context_length()`
    - `_resolve_runtime_config_context_length()`
  - 初始化路径改为：matching custom provider per-model override > 全局 `model.context_length` > auto-detect。
  - `AIAgent.switch_model()` 在切模型后重新 `load_config()` 并刷新 `self._config_context_length`，再更新 context engine。
- 影响文件：
  - `run_agent.py`
- 备注：保持 LCM 阈值语义不变，只修其吃到的 `context_length` 值。

### 2026-04-17 / Step 4
- 动作：补定向回归测试并执行验证。
- 结果：
  - 新增 `tests/hermes_cli/test_model_switch_context_alignment.py`：覆盖 display context、runtime 优先级、热切换刷新。
  - 更新 `tests/gateway/test_model_command_custom_providers.py`：覆盖 gateway `/model` 回显使用 `display_context_length`。
  - 保持并复跑 `tests/hermes_cli/test_model_switch_opencode_anthropic.py`，确保本轮没有破坏既有 `/model` 切换修复。
- 影响文件：
  - `tests/hermes_cli/test_model_switch_context_alignment.py`
  - `tests/gateway/test_model_command_custom_providers.py`
- 最近一次验证：
  - `pytest -q tests/hermes_cli/test_model_switch_context_alignment.py tests/hermes_cli/test_model_switch_opencode_anthropic.py tests/gateway/test_model_command_custom_providers.py`
  - 结果：`15 passed, 6 warnings in 4.22s`
  - warning 判断：来自 `tests/conftest.py` 的既有 `DeprecationWarning: There is no current event loop`，与本次修复无关。

### 2026-04-17 / Step 5
- 动作：执行 git / GitHub PR 预检，确认最小提交面与推送路径。
- 结果：
  - 当前仓库存在无关脏改动：`gateway/config.py`、`package-lock.json`、以及多份 2026-04-16 文档草稿；本任务提交时必须隔离。
  - 本任务最小提交面：
    - `cli.py`
    - `gateway/run.py`
    - `hermes_cli/model_switch.py`
    - `run_agent.py`
    - `tests/gateway/test_model_command_custom_providers.py`
    - `tests/hermes_cli/test_model_switch_context_alignment.py`
    - `docs/plans/2026-04-17-model-context-alignment-fix-plan.md`
    - `docs/progress/2026-04-17-model-context-alignment-fix-progress.md`
  - GitHub 权限预检：
    - `origin = NousResearch/hermes-agent`，`viewerPermission = READ`，直推 dry-run 返回 `403`（符合预期，不能直接推 upstream）。
    - `fork-leavrcn = leavrcn/hermes-agent`，`viewerPermission = ADMIN`。
    - `git push --dry-run fork-leavrcn HEAD:refs/heads/fix/context-alignment-preflight` 成功，说明后续可走 fork 分支 + PR 到 upstream。
- 最近一次验证：
  - `git status --short -- <task files>` → 仅本任务文件处于 modified/untracked。
  - `gh repo view NousResearch/hermes-agent --json ...` → `viewerPermission=READ`
  - `gh repo view leavrcn/hermes-agent --json ...` → `viewerPermission=ADMIN`
  - `git push --dry-run origin HEAD:refs/heads/fix/context-alignment-preflight` → `403`
  - `git push --dry-run fork-leavrcn HEAD:refs/heads/fix/context-alignment-preflight` → success

## 当前断点
- 已完成：代码修复、定向测试、文档留痕、GitHub 推送路径预检。
- 下一步：若主人批准，可进入“创建本地分支 → 按最小提交面暂存 → 提交 → 推送 fork → 创建 PR”。

## 最近一次验证
- `git status --short -- cli.py gateway/run.py hermes_cli/model_switch.py run_agent.py tests/hermes_cli/test_model_switch_context_alignment.py tests/gateway/test_model_command_custom_providers.py docs/plans/2026-04-17-model-context-alignment-fix-plan.md docs/progress/2026-04-17-model-context-alignment-fix-progress.md` → 仅本任务文件处于 modified/untracked
- `git push --dry-run fork-leavrcn HEAD:refs/heads/fix/context-alignment-preflight` → success
