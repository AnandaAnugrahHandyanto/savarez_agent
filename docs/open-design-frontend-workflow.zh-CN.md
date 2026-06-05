# Open Design + Hermes 前端默认工作流

> 状态：本文件记录 QQ 对话中已确认的工作流约定。用于后续前端页面开发、修改、美化、重构时恢复上下文。

## 1. 默认适用范围

凡是涉及前端页面的开发、修改、美化、重构，默认使用本流程。

可跳过本流程的极小改动：

- 错别字
- 链接调整
- 极小文案修改
- 小 CSS bug
- 不改变页面结构、视觉方向、交互体验的微调

页面级、视觉级、体验级改动默认走 Open Design。

## 2. 总体路线

选择路线 B：

```text
Hermes → Open Design project/run API → Open Design 内部 Codex → HTML artifact → 审核 → 落地 brief → 明确批准后才实现
```

分工：

- Hermes：需求整理、结构化 prompt、流程编排、审核、落地 brief、验证。
- Open Design：设计沙盒、project/run 管理、预览、设计历史。
- Open Design 内部 Codex：生成前端设计稿、HTML artifact、收敛稿。
- 真实项目仓库：只在用户明确说“开始实现”后才修改。

## 3. 核心原则

```text
设计先冻结。
生成只进 Open Design。
预览给 URL。
审核过关后生成落地 brief。
用户明确开始实现前，不动真实 repo。
```

Open Design 是设计沙盒，不是生产仓库写入器。

## 4. 项目组织

Open Design project 映射真实 repo。

示例：

```text
/workspace/admissions-sales-workbench
→ Open Design project: admissions-sales-workbench

/workspace/tutoring-exam-analysis
→ Open Design project: tutoring-exam-analysis
```

命名方式：

```text
repo/page/task-name/v1
```

示例：

```text
admissions-sales-workbench/home/warm-parent-dashboard/v1
claude-code-oneclick/install/homepage-v1
```

## 5. 产物策略

先 HTML artifact，确认后再组件化。

探索阶段：

- 第一次生成 2–3 个方向。
- 不读真实 repo。
- 允许更大胆的视觉探索。
- 至少包含 1 个保守可落地方向 + 1–2 个大胆方向。

收敛阶段：

- 用户确认某个方向后才进入。
- 使用真实 repo 的只读上下文。
- 输出：
  - `index.html`：用于预览。
  - `components/` / `styles/`：作为落地参考。
  - `README.md`：说明设计结构和落地注意。

这些仍然属于 Open Design 草稿区，不直接写真实 repo。

## 6. 上下文策略

探索阶段：

```text
不看代码，只根据 Hermes 整理的设计 brief 生成方向。
```

收敛阶段：

```text
Hermes 先整理 repo 摘要 → Open Design/Codex 通过只读白名单查看细节。
```

收敛时需要对齐：

- 技术栈
- 路由结构
- 组件语言
- CSS / token 风格
- 真实实现边界
- 不扩张功能
- 不默认改 API

## 7. 只读 repo 安全边界

由 Hermes 按项目生成白名单。

默认允许：

```text
frontend/
src/
app/templates/
app/static/
README.md
docs/
```

默认禁止：

```text
.env
*.key
*.pem
auth.json
deploy/data/
database.sqlite
secrets/
```

Open Design/Codex 只能读白名单路径，不应读取密钥、数据、部署状态文件。

## 8. 自动化程度

采用半自动：

```text
探索阶段：必须用户选方向。
细化阶段：Hermes 可以自动让 Open Design 跑 1–2 轮。
落地前：必须用户确认。
```

审核决策：

```text
Hermes 排序推荐 + 说明理由，用户可接受或推翻。
```

## 9. 用户反馈处理

普通反馈先由 Hermes 结构化：

```text
保留：...
修改：...
不改：...
禁止：...
```

反馈确认规则：

- 小改不用确认。
- 大改必须确认。

小改：颜色、按钮强调、间距、轻微文案、局部视觉细节。

大改：整体布局、风格方向、模块增删、目标用户变化、信息优先级大调整。

## 10. 过程汇报

过程只汇报关键节点，不刷屏。

示例：

```text
1. 已创建/复用 Open Design project
2. 已启动探索 run
3. Codex 正在生成
4. artifact 已生成
5. Hermes 审核完成
6. 等用户选择方向
```

失败时给精简错误和可追踪信息。

## 11. 失败策略

采用 A + 小兜底：

- 技术失败自动重试 1 次。
- 仍失败就停下汇报。
- 不擅自换路线。
- 预览保存失败时保留生成内容和失败原因。

## 12. 视觉资产策略

用户确认：允许少量本地视觉资产，关键页面可以更大胆使用视觉资产。

默认理解：

- 后台 / CRM：少量、克制、功能优先。
- 落地页 / 品牌页 / 家长端：可以更大胆，更有视觉记忆点。

当前实测结果：Open Design 内部 Codex 当前没有拿到 `image2` 工具，不能自动生成真实 PNG/WEBP 图片。它可以写 SVG/CSS fallback，但不能声称 image2 成功。

实测记录：

```text
project: od-image2-smoke-481452fe
run: 2ae621f3-84e3-4ed5-8ec8-1a8fbf8a6faa
result: image2 unavailable in Open Design Codex environment
files: README.md, index.html
no png/webp/jpg/jpeg produced
```

当前推荐分工：

```text
Open Design：决定页面风格、图片位置、用途、尺寸、风格约束、图片 prompt。
Hermes：调用 image_generate/image2 生成真实图片资产，本地化后交给 Open Design 引用。
```

如果以后 Open Design 内部 image2 打通，则默认改为：

```text
页面强绑定的一次性图片 → Open Design 生成。
全局/复用/高价值资产包 → Hermes 生成或统一管理。
失败/占位/不满意 → Hermes 兜底。
```

## 13. 响应式默认

按项目类型判断：

- 后台 / CRM / 管理台 / 工作台：桌面优先。
- 落地页 / 家长端 / 微信入口：移动端优先。
- 不确定时 Hermes 先判断并说明。

## 14. 设计记录

默认在 Hermes / Open Design 侧保存轻量记录。

内容：

- 设计目标
- 选中方案
- 选择理由
- 淘汰方案
- artifact URL
- Hermes 审核结论
- 落地注意事项

淘汰方案简单记录：

- 方案名
- 预览 URL
- 为什么没选

只有用户确认后，才写入真实 repo 的 `docs/`。

## 15. 落地权限

默认只生成 Codex 执行版落地 brief，不动真实 repo。

只有用户明确说：

```text
开始实现
开始落地
按这个改代码
```

才进入真实项目实现。

落地 brief 采用 Codex 执行版，包含：

- 严格范围
- 参考 artifact URL
- 涉及页面/组件
- 候选文件
- 禁止改动范围
- 组件迁移步骤
- CSS/token 变更建议
- 状态/交互要求
- 测试命令
- 验收标准
- 回滚注意
- 审核清单

## 16. 任务结束标准

分阶段结束。

设计阶段结束：

- 用户确认选中 artifact。
- Hermes 审核通过。
- 生成 Codex 执行版落地 brief。
- 不动真实 repo。

实现阶段结束：

- 用户明确说“开始实现”。
- Codex/Hermes 在真实 repo 落地。
- 验证通过。
- 用户确认。
- 记录落地状态。

## 17. 落地后回写 Open Design

默认记录落地状态，可选保存最终实现快照 artifact。

记录内容：

- 已落地 repo / branch
- commit / PR
- 实现差异
- 最终预览 / 截图
- 是否偏离原设计

这只是记录，不是把真实项目代码同步回 Open Design。

## 18. 后续待细聊

- Open Design 内部如何正式接入 `image2`。
- Open Design image2 打通后的素材路由策略。
- Open Design project/run API 的稳定封装脚本。
- 真实 repo 只读白名单的项目级模板。
- 前端默认工作流是否需要做成 Hermes skill。
