# 官方 Skills 吸收盘查（本轮）

## 目标
- 比对线上 Skills Hub、仓库内置 skills/optional-skills、以及外部 index-cache。
- 找出已吸收但文档/站点未对齐的项。
- 找出值得继续吸收的高价值外部能力。
- 产出一轮可落地的 Hermes 自有优化建议，且不改 openclaw 工作区本体。

## 证据来源
- 线上 Skills Hub: https://hermes-agent.nousresearch.com/docs/skills
- 本地文档: `website/docs/reference/skills-catalog.md`
- 可选技能目录: `website/docs/reference/optional-skills-catalog.md`
- 本地索引脚本: `website/scripts/extract-skills.py`
- 站点数据: `website/src/data/skills.json`
- 本地 skills 树: `skills/`, `optional-skills/`
- 外部缓存: `skills/index-cache/anthropics_skills_skills_.json`, `skills/index-cache/openai_skills_skills_.json`
- 本轮实机验证：
  - `python3 website/scripts/extract-skills.py`
  - `python3 optional-skills/email/agentmail/scripts/check_agentmail.py`
  - `python3 optional-skills/productivity/siyuan/scripts/check_siyuan.py`
  - `python3 skills/productivity/ocr-and-documents/scripts/build_pdf_workflow_map.py`
  - `python3 - <<'PY' ... python-docx/openpyxl reopen 验收 ... PY`
  - `./.venv/bin/python -m pytest -q tests/skills/test_agentmail_skill.py tests/skills/test_siyuan_skill.py tests/skills/test_stock_skill_helpers.py`

## 当前盘查结论

### A. Hermes 已吸收且站点/目录已对齐
以下高价值 optional skills 当前已完成“本地存在 + 文档可见 + Skills Hub 数据可索引”的闭环：

| 能力 | 本地状态 | 文档状态 | 数据状态 | 结论 |
|---|---|---|---|---|
| `canvas` | `optional-skills/productivity/canvas` | `skills-catalog.md` / `optional-skills-catalog.md` 已收录 | `website/src/data/skills.json` 已生成 | 已吸收并编目 |
| `memento-flashcards` | `optional-skills/productivity/memento-flashcards` | 双目录已收录 | `skills.json` 已生成 | 已吸收并编目 |
| `siyuan` | `optional-skills/productivity/siyuan` | 双目录已收录 | `skills.json` 已生成 | 已吸收并编目 |
| `telephony` | `optional-skills/productivity/telephony` | 双目录已收录 | `skills.json` 已生成 | 已吸收并编目 |
| `agentmail` | `optional-skills/email/agentmail` | 双目录已收录 | `skills.json` 已生成 | 已吸收并编目 |
| `honcho` | `optional-skills/autonomous-ai-agents/honcho` | 双目录已收录 | `skills.json` 已生成 | 已吸收并编目 |

### A.1 本轮已完成验证
本轮已执行并确认：

| 验证项 | 动作 | 结果 |
|---|---|---|
| Skills Hub 数据重建 | `python3 website/scripts/extract-skills.py` | 成功生成 `website/src/data/skills.json`，共 649 条 skills（128 本地，521 外部） |
| optional productivity / telephony 可用性 | `pytest -q tests/skills/test_telephony_skill.py tests/skills/test_memento_cards.py tests/skills/test_youtube_quiz.py` | `54 passed, 10 warnings` |
| optional skills 搜索闭环 | 检查 `skills.json` 中 `canvas` / `memento-flashcards` / `siyuan` / `telephony` | 均已出现 |
| 本轮新增自检与索引测试 | `pytest -q tests/skills/test_extract_skills_index.py tests/skills/test_siyuan_skill.py tests/skills/test_telephony_skill.py tests/skills/test_memento_cards.py tests/skills/test_youtube_quiz.py` | `58 passed, 10 warnings` |
| SiYuan 自检脚本 | 新增 `optional-skills/productivity/siyuan/scripts/check_siyuan.py` | 已支持 `SIYUAN_TOKEN`/`SIYUAN_URL` 预检与 `/api/notebook/lsNotebooks` smoke |
| AgentMail 自检脚本 | `python3 optional-skills/email/agentmail/scripts/check_agentmail.py` | 当前机器 `npx_found=true`，脚本有效；live 配置状态以运行时配置为准 |
| SiYuan 当前机器边界验收 | `python3 optional-skills/productivity/siyuan/scripts/check_siyuan.py` | 返回 `missing_siyuan_token`，说明脚本有效、当前环境未注入凭据 |
| PDF 工作流地图 | `python3 skills/productivity/ocr-and-documents/scripts/build_pdf_workflow_map.py` | 成功输出 `/tmp/hermes_pdf_workflow_map.json`，`entrypoint_count=4`，`gap_count=6` |
| DOCX 最小 reopen 验收 | `python-docx` 创建并重新打开 `/tmp/hermes_office_verify/sample.docx` | `docx_exists=True`、`docx_paragraphs=2`、`docx_tables=1` |
| XLSX 最小 reopen 验收 | `openpyxl` 创建并重新打开 `/tmp/hermes_office_verify/sample.xlsx` | `xlsx_exists=True`、sheet=`Data`、`A1=metric`、`B2=7` |
| 本轮技能回归测试 | `./.venv/bin/python -m pytest -q tests/skills/test_agentmail_skill.py tests/skills/test_siyuan_skill.py tests/skills/test_stock_skill_helpers.py` | `19 passed, 10 warnings` |

### B. 已吸收但仍需继续优化的点
这些项已经“存在并可见”，但仍有继续吸收/优化空间：

| 能力 | 当前状态 | 可继续优化点 | 优先级 |
|---|---|---|---|
| `agentmail` | 文档已收录，能力以 MCP 配置为主；本轮已补 `check_agentmail.py` 与 pytest | 下一步是在真实 API key 环境补 inbox create/list/send 动态验收 | P1 |
| `siyuan` | 已补最小 smoke 脚本、A股 workspace 模板与测试 | 可继续补更多常用 API 封装（例如 search/create/update 助手） | P1 |
| `honcho` | skill 完整，Hermes 内核已深度吸收 | 继续反哺 observer / workspace peer state / 自动迁移验收 | P1 |
| `telephony` | skill + 脚本 + 测试齐全 | 可继续补 provider 配置健康检查与更明确的安全边界验证 | P2 |
| `canvas` | skill + 脚本齐全 | 可补最小只读 smoke（mock 或无网自检） | P2 |
| `memento-flashcards` | skill + 脚本 + 测试齐全 | 可补与 `youtube-content` 的联动验收样例 | P2 |
| `docx` | Hermes-native skill 已落地，站点目录可见，最小 reopen 验收已通过 | 可继续补 pytest 样例文件与低层 Office XML 回包验证 | P1 |
| `xlsx` | Hermes-native skill 已落地，站点目录可见，最小 reopen 验收已通过 | 可继续补 pytest 样例文件、公式缓存与 CSV 导出验证 | P1 |
| `pdf` 组合链 | `ocr-and-documents` + `nano-pdf` + workflow map 已覆盖主链 | 继续补 watermark / forms / rotate / signing / batch normalization | P1 |

### C. 高价值可继续吸收的外部能力（基于现有缺口重排）
优先级按 Hermes 当前复用价值、官方 Skills Hub 当前可见项，以及“能否落成 Hermes-native 工作流”排序：

| 优先级 | 外部能力 | 吸收价值 | 与现有能力关系 |
|---|---|---|---|
| P0 | `docx` | 已落地为 Hermes-native skill，补齐 Word 文件工作流 | 已吸收 + 最小动态验收通过 |
| P0 | `xlsx` | 已落地为 Hermes-native skill，补齐本地 Excel 文件工作流 | 已吸收 + 最小动态验收通过 |
| P1 | `agentmail` 真实动态验收 | 官方站点已出现，本地也已吸收，但当前机器是否真正可用仍取决于 runtime 配置与凭据 | 下一步是补真实 inbox create/list/send 证据 |
| P1 | `siyuan` 真实动态验收 | 官方站点已出现，本地也已吸收，但当前机器缺 `SIYUAN_TOKEN` | 下一步是补真实 notebook/search/create 证据 |
| P1 | `pdf` 完整工作流 | 外部索引存在 `pdf`，本地当前采用组合式覆盖；主链已清晰但高级能力未吸收 | 适合后续按 merge/split/forms/watermark/signing 补全 |
| P1 | `mcp-builder` | 外部 Anthropic 索引中明确存在，且与 Hermes 的 MCP 生态高度契合 | 可优先以 `fastmcp` + `native-mcp` + `mcporter` 经验沉淀成 Hermes-native builder/playbook |
| P2 | `doc-coauthoring` | 外部 Anthropic 索引中明确存在，对提案/规格文档质量有价值 | 更适合先沉淀为写作/协作流程 skill，而非立即做大型实现 |
| P2 | `webapp-testing` | 外部 Anthropic 索引中明确存在，但 Hermes 已有 `dogfood` 覆盖主链 | 以增量吸收 checklist / evidence schema 为主，非重新造轮子 |
| P2 | `frontend-design` | 对前端生成质量有价值，但当前仓库已有 `popular-web-designs` / `p5js` 等 | 紧迫度较低 |
| P3 | `algorithmic-art` / `canvas-design` / `theme-factory` / `web-artifacts-builder` | 偏创作增强，收益低于工程/文档/QA链路 | 后续再看 |

## 本轮判断
1. **本轮不是“还没吸收”问题，而是“已吸收项正在进入验证与优化阶段”。**
2. `canvas / memento-flashcards / siyuan / telephony / agentmail / honcho` 已完成目录与 Skills Hub 数据闭环。
3. `docx` / `xlsx` 已作为 Hermes-native productivity skills 落地，且最小 reopen 动态验收已通过，不再只是口头吸收。
4. `pdf` 当前采用 `ocr-and-documents` + `nano-pdf` 的组合式覆盖，并通过 workflow map 固化了入口与缺口，当前无需重复造薄壳 `pdf` skill。
5. 当前最值得继续吸收的，不是再机械搬运同类 skill，而是继续补：
   - `agentmail` 的真实 API key 环境动态验收
   - `siyuan` 的真实 token 环境动态验收
   - `mcp-builder` 这类与 Hermes-native MCP 基建强相关的工程型能力
   - `doc-coauthoring` 这类可显著提升文档产出质量的流程型能力
   - `webapp-testing` 对 `dogfood` 的反哺式增强

## 下一步默认建议
1. **P1：给 `agentmail` 与 `siyuan` 补 live runtime 验收证据。**
2. **P1：继续盘查线上 Skills Hub 新增项，优先盯 `mcp-builder` / `doc-coauthoring` / `webapp-testing` / `pdf` 完整工作流。**
3. **P1：把本轮最小动态验收结果补进正式验收文档与 docs 索引。**
