# A股短线官方技能能力矩阵（2026-04-12）

## 结论

本轮对官方 Skills Hub 中与 **A股短线** 直接相关的高价值研究型能力做了再次吸收盘查后，当前矩阵如下：

- **已可直接用于生产辅助**：`blogwatcher`、`duckduckgo-search`
- **已吸收且增强层已验收，但最终落地仍需环境准备**：`qmd`、`siyuan`
- **已吸收且边界已验收，但真实运行仍应视作增强链路**：`parallel-cli`
- **本轮新增的 Hermes 自有增强层**：`blogwatcher-a-share`、`qmd-a-share`、`parallel-cli-a-share`

整体判断：

> **A股短线研究/情报侧的通用技能底座已吸收，可直接进入团队工作流的主要是 blogwatcher + DuckDuckGo；qmd 与 parallel-cli 属于高阶增强，需按场景启用。**

---

## 能力矩阵

| 技能 | 类型 | 对A股短线核心价值 | 当前可用级别 | 主要依赖/门槛 | 本轮动作 | 剩余缺口 |
|---|---|---|---|---|---|---|
| blogwatcher | built-in | 盘前/盘中/盘后资讯源轮询、公告/快讯跟踪 | 高 | `blogwatcher-cli` | 新增 A股 watchlist 脚本 | 需补 feed 导入流程与非 RSS 联动说明 |
| blogwatcher-a-share | Hermes 自有增强 | 把 blogwatcher 场景化为 A股短线情报监控链路 | 高 | 依赖 blogwatcher + 可选 cronjob | 新增 skill 文档 | 需后续补更多源模板 |
| duckduckgo-search | optional | 快速检索公告解读、题材催化、监管/媒体补证 | 高 | `ddgs` CLI | 已补 A股查询模板、辅助脚本测试 | 仍需与 cron/监控链路继续串联 |
| siyuan | optional | A股复盘/题材/风险笔记可落到可搜索知识库容器 | 中 | `SIYUAN_TOKEN` + 本地/远程实例 | 已补 workspace 模板脚本、自检脚本、pytest | 需在真实 SiYuan 实例做导入与检索验收 |
| qmd | optional | 本地复盘/纪要/策略知识库检索 | 中 | Node.js>=22、本地模型下载 | 已补 bootstrap 动态边界验收 | 运行吸收仍依赖真实 qmd 环境 |
| qmd-a-share | Hermes 自有增强 | 为 A股团队知识库提供 bootstrap、collection/context 规划与验收口径 | 中高 | 依赖 qmd 运行环境 | 新增 bootstrap 脚本与测试 | 需在真实知识库环境做一次动态验收 |
| parallel-cli | optional | 深度研究、结构化富集、监控、专题摸排 | 中 | 认证 + 外部服务 | 已补当前机器边界验收 | 缺少已认证环境下运行证据 |
| parallel-cli-a-share | Hermes 自有增强 | 固化 A股专题研究、富集、监控模板与启用边界 | 中高 | 依赖 parallel-cli 认证 | 新增 skill 文档 | 需在已认证环境做动态验收 |

---

## 映射到团队链路

### 1. 事件链

情报官 + 数据员（并行）→ 风控官 → CIO

- `blogwatcher-a-share`：负责已知高价值源持续扫描
- `duckduckgo-search`：负责异动事件补证、消息交叉确认

### 2. 研究链

情报官 → 数据员 → 量化员 → 风控官 → CIO

- `parallel-cli`：用于专题调研、公司/产业链深挖、结构化 enrichment
- `qmd`：用于回看历史研究结论与复盘知识

### 3. 复盘链

数据员 + 情报官（并行）→ 量化员 → 风控官 → CIO

- `blogwatcher-a-share`：保留盘后资讯与公告流
- `qmd`：沉淀为可复检知识资产

---

## 吸收完成度定义

| 等级 | 定义 |
|---|---|
| 高 | 技能已存在 + 文档可用 + 当前有辅助脚本/测试，可直接纳入工作流 |
| 中 | 技能已存在，但依赖或场景化不足，需补环境或模板 |
| 低 | 技能虽在目录中，但尚未形成可稳定执行的链路 |

---

## 本轮新增/确认资产

1. `optional-skills/research/blogwatcher/scripts/build_a_share_watchlist.py`
2. `optional-skills/research/blogwatcher-a-share/SKILL.md`
3. `optional-skills/research/qmd-a-share/SKILL.md`
4. `optional-skills/research/qmd-a-share/scripts/build_a_share_bootstrap.py`
5. `optional-skills/research/parallel-cli-a-share/SKILL.md`
6. `optional-skills/productivity/siyuan/scripts/build_a_share_workspace.py`
7. `tests/skills/test_stock_skill_helpers.py`
8. `tests/skills/test_siyuan_skill.py`
9. `docs/architecture/a-share-official-skills-absorption-audit-2026-04-12.md`

---

## P0 / P1

### P0
1. 用 `blogwatcher-a-share` 固化盘前/盘中/盘后监控链路
2. 继续把 `duckduckgo-search` 与监控/复盘链路串联
3. 运行 extract-skills + pytest，形成正式验收证据
4. 将上述文档补入 `docs/README.md` 与 `README.md` 索引

### P1
5. 用 `qmd-a-share` 在具备 qmd 的真实知识库目录完成最终动态验收
6. 用 `parallel-cli-a-share` 在已认证环境补一轮真实深研究/监控验收
