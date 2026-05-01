# Skills Governance 落地执行结果（2026-04-13 · Round 2）

## 结论

本轮继续执行“持续吸收 → 持续验证 → 持续清洗”，已完成第二轮批量治理推进。当前体系已经从上一轮的 P0 吸收，进入 optional D1/D2 持续清洗阶段。

本轮完成：
1. **DuckDuckGo promotion 标记已对齐**：inventory 不再错误保留 promotion candidate。
2. **新增 4 个高价值 optional skills 治理升级**：
   - `gitnexus-explorer`
   - `qmd`
   - `siyuan`
   - `sherlock`
3. **新增 3 组测试文档回归**：
   - `tests/skills/test_gitnexus_skill.py`
   - `tests/skills/test_qmd_skill.py`
   - `tests/skills/test_siyuan_sherlock_skill_docs.py`
4. **全量本轮回归通过**：27 passed / 0 failed

---

## 本轮新增落地

### 1) DuckDuckGo promotion 对齐
已更新：
- `website/scripts/skills_inventory.py`
- `tests/skills/test_skills_inventory.py`

结果：
- `promotion_candidates` 现在为 **空列表**
- `duckduckgo-search` 不再被 inventory 误标

### 2) GitNexus Explorer 升级
已补：
- `## Verification`
- toolchain / analyzer / backend response 检查
- 新增测试：`tests/skills/test_gitnexus_skill.py`

结果：
- `gitnexus-explorer` 从 **D1 → D2**

### 3) QMD 升级
已补：
- `## Verification`
- `## Pitfalls`
- 新增测试：`tests/skills/test_qmd_skill.py`

结果：
- `qmd` 从 **D1 → D3**

### 4) SiYuan / Sherlock 升级
已补：
- `siyuan`
  - `## Verification`
  - acceptance ladder 与脚本验证闭环
- `sherlock`
  - `## Verification` 强化
  - 增补零结果显式判定标准
- 新增测试：`tests/skills/test_siyuan_sherlock_skill_docs.py`

结果：
- `siyuan` 仍是 **D1**，但验证闭环已补齐，后续可继续向 D2/D3 推进
- `sherlock` 保持 **D2**，验证标准更可靠

---

## 回归验证
已执行：
```bash
./.venv/bin/python -m pytest -q \
  tests/skills/test_skills_inventory.py \
  tests/skills/test_gitnexus_skill.py \
  tests/skills/test_qmd_skill.py \
  tests/skills/test_parallel_cli_skill.py \
  tests/skills/test_siyuan_sherlock_skill_docs.py \
  tests/skills/test_siyuan_skill.py \
  tests/skills/test_duckduckgo_search_skill.py \
  tests/skills/test_research_skill_helpers.py \
  tests/skills/test_stock_skill_helpers.py \
  --tb=short
```

结果：
- **27 passed**
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
- D1: **103**
- D2: **6**
- D3: **6**
- D4: **2**
- Skills with tests: **16**
- Runtime validated: **5**
- Promotion candidates: **0**

---

## 判断

### 已经达到的状态
- P0 吸收已经完成
- promotion candidate 残留已清零
- D3 池从上一轮 **5** 增长到 **6**
- 测试覆盖从 **15** 增长到 **16**
- D1 总量从 **105** 降到 **103**

### 当前仍然存在的缺口
1. **D1 总量依然高（103）**
   - 还远没到“全部过滤完毕”的终态。
2. **runtime validated 数量仍低（5）**
   - 当前主要是文档+测试治理，后续要逐步补 runtime smoke。
3. **部分 optional skills 已有单项成熟度，但没形成完整 D3 闭环**
   - 例如：`siyuan`、`meme-generation`、`agentmail` 周边还可继续清洗。

---

## 下一轮最优先

### P0
1. 继续扫 optional 中高价值 D1：
   - `meme-generation`
   - `bioinformatics`
   - `blogwatcher-a-share`
   - `qmd-a-share`
2. 对已有 D2 技能继续推 D3：
   - `gitnexus-explorer`
   - `sherlock`
3. 开始给一批 built-in D1 补 verification/pitfalls/testing，压缩 built-in 内部负债。

### P1
4. 为已成型的 D3/D4 技能补 runtime smoke。
5. 按 category 做批量清洗，而不是点状修补。

---

## 总结

这一轮新增价值不是“再盘一遍”，而是已经完成：
- **promotion 残留清零**
- **QMD 推到 D3**
- **GitNexus 推到 D2**
- **SiYuan / Sherlock 验证闭环补强**
- **27 个治理相关测试全通过**

Hermes 技能治理已经稳定进入：
**批量清洗 optional D1/D2 → 扩大 D3 池 → 再补 runtime 验证** 的持续执行阶段。
