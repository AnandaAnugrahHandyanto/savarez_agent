# 模型上下文显示/运行时对齐修复计划

日期：2026-04-17
状态：已批准，实施中

## 背景
主人已批准对 Hermes Agent 中“模型切换回显 / 运行时上下文 / LCM 实际窗口”三层不一致问题做最小范围修复，并要求：
1. 记录完整改动过程，确保中断后可恢复。
2. 改完后做好提交与 PR 到 Hermes-Agent 官方库的准备。
3. 优先控制改动面，不在本轮顺手改大范围配置/插件语义。

当前已确认现象：
- `yunfeiplus:gpt-5.4` 的配置声明窗口是 `524288`。
- `/model` 切换后的显示会回退成 `128000`。
- 运行中的 `AIAgent` / `LCMEngine` 实际仍吃到全局 `model.context_length=200000`。
- LCM 当前阈值 `0.75` 来自插件默认，不应与内置 `compression.threshold` 混改。

## 目标
1. 修复模型切换成功回显，使其优先显示 custom provider per-model 的 `context_length`，不再错误显示 `128000`。
2. 修复运行时 `AIAgent` 初始化与热切换时的 context_length 解析优先级，使 `custom_providers[].models[model].context_length` 优先于全局 `model.context_length`。
3. 让 LCM 在当前模型为 `yunfeiplus:gpt-5.4` 时实际吃到 `524288`，阈值随之按 LCM 自身 `0.75` 规则计算。
4. 补充定向测试与文档记录，为后续 git commit / PR 做准备。

## 非目标
- 本轮不修改 `~/.hermes/config.yaml` 作为临时 workaround。
- 本轮不修改 LCM 插件阈值语义，不把其与内置 `compression.threshold` 对齐。
- 本轮不扩大到无关 provider / gateway 其它信息展示重构，除非为共享修复所必需。
- 本轮不直接重启 gateway；如需线上验证，待代码与测试完成后再单独决定。

## 证据链
- `~/.hermes/config.yaml`：
  - `model.context_length: 200000`
  - `context.engine: lcm`
  - `custom_providers.yunfeiplus.models.gpt-5.4.context_length: 524288`
- `cli.py`：模型切换回显 fallback 调 `get_model_context_length(...)` 时未传 config override。
- `run_agent.py`：初始化时优先读取顶层 `model.context_length`，仅在其为 `None` 时才看 custom provider per-model 值。
- `lcm_status()`：当前会话 `context_length=200000`，`threshold_tokens=150000`。

## 实施步骤（冻结版）
1. 建立计划/进度文档，记录基线与范围。
2. 在 `hermes_cli/model_switch.py` 设计并实现统一展示值字段（如 `display_context_length`）。
3. 在 `cli.py`（必要时含共享调用方）优先使用统一展示字段，消除 128K 显示回退。
4. 在 `run_agent.py` 抽取共享 runtime context override 解析逻辑，并调整优先级为：custom provider per-model > 顶层 `model.context_length` > auto-detect。
5. 修复 `switch_model()` 热切换路径，使其在切换后重新解析并刷新 `self._config_context_length` 与 context engine 的窗口值。
6. 补充/更新定向测试，覆盖：
   - custom provider 展示值正确
   - runtime context 优先级正确
   - 热切换后 context engine 上下文值正确
7. 运行定向测试与最小脚本验证。
8. 更新 progress 文档，核对 git 影响面，为 commit / PR 做准备。

## Definition of Done
- `/model gpt-5.4 --provider yunfeiplus` 的成功回显显示 `524,288`，不再错误回退到 `128,000`。
- `AIAgent(model='gpt-5.4', provider='yunfeiplus', ...)` 初始化后 `context_compressor.context_length == 524288`。
- 从其他模型热切换到 `yunfeiplus:gpt-5.4` 后，`context_compressor.context_length == 524288`。
- 在 LCM 下，阈值按 `524288 * 0.75 = 393216` 计算。
- 改动文件范围清晰、测试结果有记录、仓库可进入提交/PR 准备阶段。

## 断点恢复入口
- 本计划：`docs/plans/2026-04-17-model-context-alignment-fix-plan.md`
- 本任务进度：`docs/progress/2026-04-17-model-context-alignment-fix-progress.md`
- 关键代码：
  - `hermes_cli/model_switch.py`
  - `cli.py`
  - `run_agent.py`
  - `tests/...`（待补）
