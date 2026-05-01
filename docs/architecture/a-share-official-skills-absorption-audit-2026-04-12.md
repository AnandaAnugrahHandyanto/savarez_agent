# A股短线高价值官方技能吸收盘查（2026-04-12）

## 结论

本轮围绕官方 Skills Hub 候选中对 **A股短线情报、研究、知识检索、持续监控** 最有价值的能力做了盘查，并补了动态验收证据。当前 Hermes 自有体系状态：

- **已吸收并可直接复用**：`blogwatcher`
- **已吸收为 optional skill，可按需安装**：`duckduckgo-search`、`qmd`、`parallel-cli`
- **已补本地增强资产**：`optional-skills/research/blogwatcher/scripts/build_a_share_watchlist.py`、`optional-skills/research/blogwatcher-a-share/scripts/build_cron_closure.py`、`optional-skills/research/blogwatcher-a-share/scripts/build_scrapling_supplement.py`、`optional-skills/research/qmd-a-share/scripts/build_a_share_bootstrap.py`、`optional-skills/productivity/siyuan/scripts/build_a_share_workspace.py`
- **已补 Hermes 自有增强层**：`blogwatcher-a-share`、`qmd-a-share`、`parallel-cli-a-share`
- **本轮新增验收结论**：`qmd`、`parallel-cli` 与 `siyuan` 已完成“真实运行环境缺失或未接入”下的动态边界验收——增强脚本与测试可运行，但当前机器缺少 `qmd` / `parallel-cli` CLI，且未提供可用 `SIYUAN_TOKEN`，因此仍不能宣称已在真环境跑通

因此判断：

> **基础吸收已完成；A股短线化增强已基本成型；剩余缺口已从“文档/脚本缺失”收敛到“等待具备 qmd / parallel-cli 真实环境的最终动态验收”。**

下一阶段应优先把这些能力从“通用技能目录存在”推进到“短线团队可直接拿来跑”。

---

## 盘查范围

重点反复对照官方 Skills 文档目录与本仓库现状，锁定以下高价值候选：

1. `blogwatcher` — RSS / 博客 / 资讯源监控，适合盘前、盘中、盘后情报轮询
2. `duckduckgo-search` — 免费网页/新闻检索，适合公告、题材、传闻快速补证
3. `qmd` — 本地知识库混合检索，适合沉淀复盘、会议纪要、策略笔记
4. `parallel-cli` — 深度研究 / 网页抽取 / 富集 / 监控，适合高价值专题研究与结构化情报扩展

---

## 逐项盘查

### 1) blogwatcher

**现状**
- 内置 skill 已存在：`skills/research/blogwatcher/SKILL.md`
- 说明完整，覆盖安装、扫描、OPML 导入、分类筛选、数据库路径
- 本轮新增 A股辅助脚本：
  - `optional-skills/research/blogwatcher/scripts/build_a_share_watchlist.py`

**适配价值**
- 可承接交易所公告、媒体快讯、监管新闻等轮询需求
- 可与 `cronjob` 串联，形成盘前/盘中监控
- 可与后续 scrapling / DuckDuckGo / Parallel 联动做二跳抽取

**当前问题**
- 还没有形成 A股短线专用 skill 包装与文档入口
- 当前 watchlist 脚本仅产出候选 feed JSON，未直接附带 blogwatcher-cli 导入流程
- 深交所 / 巨潮 / 证监会等关键源仍包含非 RSS 页面，需二次抓取链路

**判断**
- **可吸收度：高**
- **当前状态：已部分场景化吸收**

---

### 2) duckduckgo-search

**现状**
- optional skill 已存在：`optional-skills/research/duckduckgo-search/SKILL.md`
- 已带辅助脚本：`optional-skills/research/duckduckgo-search/scripts/duckduckgo.sh`
- 文档已强调 CLI 与 Python runtime 分离、`ddgs` 安装与验证方法、`max_results` keyword-only 陷阱

**适配价值**
- 免费、无需 API key，适合作为广覆盖情报检索 fallback
- 可快速补证：公司公告解读、题材催化、监管消息、媒体二次确认
- 可作为 `blogwatcher` 非 RSS 源的补位检索器

**当前问题**
- 已补 A股短线预置查询模板
- 已补 `duckduckgo.sh` 基本行为测试
- 仍需继续形成与 cron / watchlist / 复盘文档的串联说明

**判断**
- **可吸收度：高**
- **当前状态：通用吸收已完成，短线模板与测试已补齐**

---

### 3) qmd

**现状**
- optional skill 已存在：`optional-skills/research/qmd/SKILL.md`
- 文档完整，覆盖 collection / context / embed / query / MCP 接入
- 非常适合把复盘、纪要、策略文档沉淀为本地知识库检索层

**适配价值**
- 能承接“找过去某次复盘怎么判断题材切换”“查询龙头战法笔记”“回看某次风险会结论”等需求
- 可把团队复盘与会议纪要转为长期可检索资产
- 可与 Hermes MCP 体系自然集成

**当前问题**
- 依赖 Node.js >= 22 + 本地模型下载，接入门槛较高
- 已新增 A股团队专用目录规范与 bootstrap 脚本：`optional-skills/research/qmd-a-share/`
- 已有脚本/测试证明 bootstrap JSON 可直接生成
- 本轮已在当前机器完成边界验收：`qmd` CLI 不存在，但 bootstrap 计划生成成功、样例知识库目录与文档已成功落盘，说明 Hermes 自有增强层可用，阻塞点仅剩真实 qmd 安装环境

**判断**
- **可吸收度：中高**
- **当前状态：文档吸收完成，A股 bootstrap 已补，运行吸收待环境验收**

---

### 4) parallel-cli

**现状**
- optional skill 已存在：`optional-skills/research/parallel-cli/SKILL.md`
- 覆盖安装、认证、search/extract/research/enrich/findall/monitor 的命令模式
- 明确标注为 optional、付费服务、不是 Hermes 默认能力

**适配价值**
- 适合高价值专题研究、公司/产业链深度摸排、结构化富集
- monitor / enrichment / findall 对跟踪题材扩散、公司关联图谱有潜在价值
- 对普通检索外的“深研究 + 结构化输出”有补强作用

**当前问题**
- 强依赖认证与外部服务，不适合作为默认链路
- 已新增 A股研究场景 best practice / 模板命令：`optional-skills/research/parallel-cli-a-share/SKILL.md`
- 本轮已在当前机器完成边界验收：`parallel-cli` CLI 不存在，且未发现相关认证环境变量；因此当前缺口被精确收敛为“等待已认证环境的真实运行证据”

**判断**
- **可吸收度：中**
- **当前状态：通用 optional 吸收完成，A股模板与边界已补，动态验收待补**

---

### 5) siyuan

**现状**
- optional skill 已存在：`optional-skills/productivity/siyuan/SKILL.md`
- 本轮前已补最小自检脚本：`optional-skills/productivity/siyuan/scripts/check_siyuan.py`
- 本轮新增 A股短线知识库模板脚本：`optional-skills/productivity/siyuan/scripts/build_a_share_workspace.py`
- 已新增 pytest 覆盖：`tests/skills/test_siyuan_skill.py`

**适配价值**
- 适合把盘前计划、午间观察、盘后复盘沉淀进可检索的结构化笔记系统
- 适合把题材库、龙头映射、风险信号库拆分成独立 notebook，降低知识混杂
- 可作为 `qmd` 之外更偏“编辑优先”的 A股团队知识容器

**当前问题**
- 真实运行依赖 `SIYUAN_TOKEN` 与可访问实例
- 当前机器未提供可用 token，因此只能完成模板/脚本/测试级验收
- 仍需在真实实例完成 notebook/document 导入与关键词检索验证

**判断**
- **可吸收度：中高**
- **当前状态：已完成 Hermes-native A股模板化吸收，动态导入验收待补**

---

## 吸收完成度矩阵

| 能力 | 仓库存在 | A股短线价值 | 运行门槛 | 场景化文档 | 验收测试 | 当前结论 |
|---|---|---:|---:|---:|---:|---|
| blogwatcher | 是 | 很高 | 中 | 中 | 有 | 已吸收，已完成场景化增强 |
| duckduckgo-search | 是 | 很高 | 低 | 中 | 有 | 已吸收，模板与测试已补 |
| siyuan | 是 | 高 | 中 | 中 | 有 | 已吸收，A股 workspace 模板与自检已补，待真实实例导入验收 |
| qmd | 是 | 高 | 高 | 中 | 有（bootstrap 级） | 已吸收，增强层可运行，待真实环境动态验收 |
| parallel-cli | 是 | 中高 | 高 | 中 | 有（边界验收级） | 已吸收，适合作为增强链路，待已认证环境动态验收 |

---

## 建议吸收顺序（按 A股短线收益 / 成本比）

### P0
1. **blogwatcher A股短线化**
   - 补 skill 包装 / 文档
   - 把 watchlist JSON 生成流程纳入正式说明
   - 明确哪些源走 RSS，哪些源走二跳抓取

2. **duckduckgo-search 场景模板化**
   - 补 A股短线查询模板与 shell helper 用法
   - 补脚本级测试

### P1
3. **qmd 团队知识库落地化**
   - 已补 A股团队知识库目录建议
   - 已补 bootstrap / 测试
   - 已完成当前机器边界验收，待在真实 qmd 环境做最终动态验收

4. **parallel-cli 高价值增强化**
   - 已补“仅在深研究/富集/监控时启用”的边界文档
   - 已补 A股研究示例命令
   - 已完成当前机器边界验收，待在已认证环境补最终运行证据

5. **siyuan A股知识库容器化**
   - 已补自检脚本与 A股 workspace 模板脚本
   - 已补 pytest 验证生成 payload
   - 待在真实 SiYuan 实例完成 notebook 导入与关键词检索验收

---

## 本轮已落地资产

- 新增：`optional-skills/research/blogwatcher/scripts/build_a_share_watchlist.py`
  - 输出 A股短线监控 feed 候选 JSON
  - 标记了 RSS / 非 RSS 源与后续动作
- 新增：`optional-skills/research/blogwatcher-a-share/scripts/build_scrapling_supplement.py`
  - 输出深交所 / 巨潮 / 证监会等非 RSS 页面补链模板
- 新增：`optional-skills/research/qmd-a-share/SKILL.md`
  - 给出 A股团队知识库目录约定、bootstrap 和验收口径
- 新增：`optional-skills/research/qmd-a-share/scripts/build_a_share_bootstrap.py`
  - 输出 collection/context/bootstrap JSON 计划
- 新增：`optional-skills/research/parallel-cli-a-share/SKILL.md`
  - 固化 A股专题研究 / enrichment / monitor 模板与启用边界
- 新增：`optional-skills/productivity/siyuan/scripts/build_a_share_workspace.py`
  - 输出 A股日复盘 / 题材 / 风险知识库模板
- 更新：`optional-skills/research/duckduckgo-search/SKILL.md`
  - 补 A股短线查询模板
- 更新：`tests/skills/test_stock_skill_helpers.py`
  - 新增 watchlist / duckduckgo / qmd bootstrap / scrapling supplement 辅助脚本测试
- 更新：`tests/skills/test_siyuan_skill.py`
  - 新增 SiYuan workspace 模板脚本测试

---

## 下一步执行要求

本盘查结束后，应继续直接推进：

1. 把 `blogwatcher` 做成 A股短线可直接使用的 optional/built-in 辅助方案
2. 为 `duckduckgo-search` / `qmd` / `parallel-cli` 持续补场景文档与最小测试
3. 已更新 `docs/README.md` 与 `README.md` 索引
4. 继续在具备真实 qmd / parallel-cli 环境时补最终动态运行证据
