# Skills Governance 落地执行结果（2026-04-13）

## 结论

本轮已把 P0 全部落地，并完成一轮新的 P1 治理推进。Hermes 技能体系已经从“候选评估”进入“实际吸收 + 持续清洗”阶段。

本轮完成：

1. **4 个高价值 optional skills 已迁入 built-in**
   - `domain-intel`
   - `fastmcp`
   - `honcho`
   - `docker-management`
2. **`duckduckgo-search` 已推进到 D3**
3. **新增一轮 D1 清洗**：补强 `parallel-cli`
4. **回归通过，索引与 inventory 已更新**

---

## 本轮新增落地

### 1) Built-in 晋升落地
已完成目录迁移：
- `skills/domain/domain-intel/`
- `skills/mcp/fastmcp/`
- `skills/autonomous-ai-agents/honcho/`
- `skills/devops/docker-management/`

已同步更新：
- `tests/skills/test_extract_skills_index.py`
- `tests/skills/test_skills_inventory.py`
- `website/scripts/skills_inventory.py`
- `tests/skills/test_research_skill_helpers.py`
- `tests/skills/test_stock_skill_helpers.py`
- `tests/skills/test_honcho_skill.py`
- `tests/skills/test_docker_management_skill.py`
- `skills/devops/DESCRIPTION.md`

并已清理对应 optional 源目录，避免 built-in / optional 双重来源冲突。

### 2) DuckDuckGo Search 推进到 D3
已完成：
- 新增测试 `tests/skills/test_duckduckgo_search_skill.py`
- 把 helper 脚本同步到 built-in 路径：
  - `skills/research/duckduckgo-search/scripts/build_a_share_queries.py`
  - `skills/research/duckduckgo-search/scripts/duckduckgo.sh`
- 更新测试与 skill 文档中的脚本路径引用
- 补齐 Verification / Pitfalls 闭环

结果：`duckduckgo-search` 进入 **D3**，并已不再是 promotion candidate。

### 3) 新一轮 D1 清洗：parallel-cli
已补：
- `## Prerequisites`
- `## Verification`
- `## Pitfalls`
- 新增测试：`tests/skills/test_parallel_cli_skill.py`

说明：本轮优先处理 research 类高价值 D1 技能，`parallel-cli` 已从“仅使用说明”升级为“可前置检查、可验证、可规避误用”的治理状态。

---

## 回归验证
已执行：
```bash
./.venv/bin/python -m pytest -q \
  tests/skills/test_parallel_cli_skill.py \
  tests/skills/test_extract_skills_index.py \
  tests/skills/test_skills_inventory.py \
  tests/skills/test_research_skill_helpers.py \
  tests/skills/test_stock_skill_helpers.py \
  tests/skills/test_honcho_skill.py \
  tests/skills/test_docker_management_skill.py \
  tests/skills/test_duckduckgo_search_skill.py \
  --tb=short
```

结果：
- **23 passed**
- **0 failed**

并已重新生成：
```bash
python3 website/scripts/extract-skills.py
python3 website/scripts/skills_inventory.py \
  --json website/src/data/skills-inventory.json \
  --markdown docs/architecture/skills-inventory-report.md
```

---

## 当前盘点结果（最新）

### Source Summary
- Local total: **128**
- built-in: **84**
- optional: **44**

### Quality Summary
- D0: **11**
- D1: **106**
- D2: **5**
- D3: **4**
- D4: **2**
- Skills with tests: **14**
- Runtime validated: **5**

### Promotion Candidates
- `duckduckgo-search`

> 注：当前 inventory 仍把 `duckduckgo-search` 列为 promotion candidate，说明下一步应把它也按 built-in 晋升链路处理，或调整 inventory 规则以匹配当前治理判断。

---

## 判断

### 已完成吸收
P0 已全部落地，不再是候选讨论：
- `domain-intel`：已 built-in
- `fastmcp`：已 built-in
- `honcho`：已 built-in
- `docker-management`：已 built-in

### 已完成推进
- `duckduckgo-search`：已 D3 化
- `parallel-cli`：已完成新一轮高价值 D1 补强

### 当前残余缺口
1. **inventory 规则与治理判断还有一处未对齐**
   - `duckduckgo-search` 文档/测试成熟度已显著提升，但 inventory 仍把它保留为 promotion candidate。
2. **D1 总量仍高（106）**
   - 说明下一阶段应继续按高价值 optional skills 做批量治理，而不是停在单点修复。

---

## 下一步最优先

### P0.5
1. 处理 `duckduckgo-search` 的 built-in 晋升或 inventory 规则对齐。

### P1
2. 继续扫 research / productivity / security 中高价值 D1：
   - `gitnexus-explorer`
   - `qmd`
   - `siyuan`
   - `sherlock`
3. 为新 built-in 候选补更强 runtime smoke。
4. 继续把 D3 池扩大，再做下一轮 built-in 吸收。

---

## 总结

这一轮不是“再看一遍”，而是已经完成：
- **4 个技能正式吸收进 built-in**
- **DuckDuckGo Search 推到 D3**
- **新增 parallel-cli 治理补强**
- **索引 / inventory / 测试全部回归通过**

Hermes 技能吸收链路现在已经进入：
**持续吸收 → 持续验证 → 持续清洗 D1** 的执行阶段。
