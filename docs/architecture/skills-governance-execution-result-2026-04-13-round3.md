# Skills Governance 落地执行结果（2026-04-13 · Round 3）

## 结论

本轮继续执行“持续吸收 → 持续验证 → 持续清洗”，重点处理 optional D1 与 D2 候选。结果是：

1. **新增 4 个 optional D1 技能治理补强**
   - `meme-generation`
   - `bioinformatics`
   - `blogwatcher-a-share`
   - `qmd-a-share`
2. **继续强化 2 个 D2 候选**
   - `gitnexus-explorer`
   - `sherlock`
3. **新增 4 组测试**
   - `tests/skills/test_meme_generation_skill.py`
   - `tests/skills/test_bioinformatics_skill.py`
   - `tests/skills/test_a_share_derivative_skills.py`
   - 对 `test_gitnexus_skill.py` / `test_siyuan_sherlock_skill_docs.py` 做了更强断言
4. **全量本轮回归通过**：25 passed / 0 failed

---

## 本轮新增落地

### 1) Meme Generation 补强
已补：
- `## Verification` 从笼统结果描述改为真实执行链
- 明确要求：
  - `--list`
  - `--search`
  - 真实 render 到 `/tmp/meme.png`
- 新增测试：`tests/skills/test_meme_generation_skill.py`

结果：
- `meme-generation` 仍为 **D1**，但验证闭环已建立，后续可继续向 D2 推进

### 2) Bioinformatics Gateway 补强
已补：
- `## Verification`
- 明确 clone 两个上游仓库并校验索引路径存在
- 新增测试：`tests/skills/test_bioinformatics_skill.py`

结果：
- `bioinformatics` 补上可验证性；当前 inventory 显示 tests 已纳入

### 3) Blogwatcher A-Share / QMD A-Share 补强
已补：
- `blogwatcher-a-share`
  - 把“最小验收”升格为正式 `## Verification`
  - 增加 Scrapling supplement 生成链路
- `qmd-a-share`
  - 把“验收标准”标准化为 `## Verification`
  - 增加 `## Pitfalls`
  - 强调 bootstrap JSON ≠ 真正可用
- 新增测试：`tests/skills/test_a_share_derivative_skills.py`

结果：
- `qmd-a-share` 已具备 Verification + Pitfalls 闭环
- `blogwatcher-a-share` 已具备更完整的 A股监控链路验收说明

### 4) D2 候选继续推高
#### `gitnexus-explorer`
新增验证要求：
- 必须检查生产 web build 产物 `gitnexus-web/dist`

#### `sherlock`
新增验证要求：
- 可疑命中必须至少人工打开 1 个返回链接做 sanity check

结果：
- 两者都更接近 D3，但当前 inventory 仍显示 **D2**，说明还需继续补 tests/runtime 或进一步完善文档结构

---

## 回归验证
已执行：
```bash
./.venv/bin/python -m pytest -q \
  tests/skills/test_meme_generation_skill.py \
  tests/skills/test_bioinformatics_skill.py \
  tests/skills/test_a_share_derivative_skills.py \
  tests/skills/test_gitnexus_skill.py \
  tests/skills/test_qmd_skill.py \
  tests/skills/test_siyuan_sherlock_skill_docs.py \
  tests/skills/test_skills_inventory.py \
  tests/skills/test_stock_skill_helpers.py \
  tests/skills/test_research_skill_helpers.py \
  --tb=short
```

结果：
- **25 passed**
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
- Skills with tests: **18**
- Runtime validated: **5**
- Promotion candidates: **0**

---

## 判断

### 本轮真实增量
- 有 tests 的技能：**16 → 18**
- promotion candidates：继续保持 **0**
- optional D1 的一批高价值技能已经不再是“裸文档”状态

### 为什么 D1 总数没下降
因为这轮主要补的是：
- 验证闭环
- 测试覆盖
- 验收标准

但 inventory 的 tier 规则仍要求更完整组合（如 prerequisites / tests / pitfalls / verification / runtime 等），所以部分技能虽然明显成熟了，但暂未跨 tier 边界。

### 当前真实缺口
1. **D1 仍高达 103**
2. **runtime validated 仍只有 5**
3. **`blogwatcher-a-share` / `meme-generation` / `bioinformatics` 这类技能已补强，但还没被推过 D1 分界**
4. **`gitnexus-explorer` / `sherlock` 仍停在 D2**

---

## 下一轮最优先

### P0
1. 继续补高价值 optional D1：
   - `parallel-cli-a-share`
   - `scrapling`
   - `canvas`
   - `inference-sh-cli`
2. 针对 `blogwatcher-a-share` / `qmd-a-share` / `meme-generation` / `bioinformatics` 补 prerequisites 或更强 tests，把它们推进到 D2。
3. 给 `gitnexus-explorer` / `sherlock` 补 runtime-style smoke 或更完整测试，推动 D3。

### P1
4. 开始切入 built-in D1 第一批：
   - `native-mcp`
   - `mcporter`
   - `blogwatcher`
   - `github-pr-workflow`

---

## 总结

这一轮不是重复审计，而是继续把技能治理往执行层推进：
- **补了 4 个 optional D1 的真实验收链**
- **继续把 2 个 D2 候选往 D3 推**
- **测试覆盖继续扩大到 18**
- **25 个治理相关测试全部通过**

Hermes 技能治理当前已经稳定进入：
**高价值 optional 持续清洗 → D2 候选持续加压 → 再向 built-in D1 反推治理** 的阶段。
