# 高价值剩余可吸收能力审计（2026-04-12）

## 结论

本轮再次对官方 Skills Hub 与仓库现状交叉盘查后，针对 **A股短线 / 团队知识沉淀 / 深研究补链**，当前最值得继续吸收但尚未闭环的高价值项重新收敛为三类：

1. **`qmd` 的真实动态验收链路**
2. **`parallel-cli` 的真实认证环境动态验收链路**
3. **`siyuan` 的 A股短线知识库模板化落地**（本轮已补 Hermes-native workspace 生成脚本与测试，剩余是真实实例导入验收）

其余本轮重点目标已完成 Hermes-native 吸收或增强包装：

- `blogwatcher-a-share`
- `duckduckgo-search` A股模板化
- `qmd-a-share`
- `parallel-cli-a-share`
- `siyuan` A股 workspace 模板化

因此当前判断：

> **值得继续吸收的，已经不是泛泛再搬更多 skill，而是把“知识沉淀 + 监控补链 + 深研究”三类高价值增强层逐个跑到真实环境验收通过。**

---

## 盘查依据

### 1. 官方 Skills Hub 再盘查结果

在 `https://hermes-agent.nousresearch.com/docs/skills` 再次盘查后，研究类中对 A股短线最相关的候选主要仍集中于：

- `blogwatcher`
- `duckduckgo-search`
- `qmd`
- `parallel-cli`
- `llm-wiki`
- `youtube-content`
- `polymarket`

其中：

- `blogwatcher` / `duckduckgo-search` / `qmd` / `parallel-cli` 直接对应情报监控、知识检索、深研究补链，价值最高
- `llm-wiki` 更偏通用长期知识编纂，和当前 A股短线日常工作流相比，不如 `qmd` 轻量直接
- `youtube-content` 对 A股短线日常决策链路不是高频核心
- `polymarket` 与当前 A股短线主链路关联较弱，暂不优先

### 2. 仓库现状再核对结果

已存在或已新增：

- `skills/research/blogwatcher/SKILL.md`
- `optional-skills/research/duckduckgo-search/SKILL.md`
- `optional-skills/research/qmd/SKILL.md`
- `optional-skills/research/parallel-cli/SKILL.md`
- `optional-skills/research/blogwatcher-a-share/SKILL.md`
- `optional-skills/research/qmd-a-share/SKILL.md`
- `optional-skills/research/qmd-a-share/scripts/build_a_share_bootstrap.py`
- `optional-skills/research/parallel-cli-a-share/SKILL.md`
- `optional-skills/productivity/siyuan/SKILL.md`
- `optional-skills/productivity/siyuan/scripts/check_siyuan.py`
- `optional-skills/productivity/siyuan/scripts/build_a_share_workspace.py`
- `tests/skills/test_stock_skill_helpers.py`
- `tests/skills/test_siyuan_skill.py`

验证结果：

```bash
./.venv/bin/python -m pytest -q tests/skills/test_stock_skill_helpers.py
# 7 passed

python3 website/scripts/extract-skills.py
# Extracted 649 skills to website/src/data/skills.json

python3 optional-skills/research/qmd-a-share/scripts/build_a_share_bootstrap.py --output /tmp/qmd_a_share_bootstrap.json
# ok=true, collection_count=6

python3 optional-skills/productivity/siyuan/scripts/build_a_share_workspace.py --output /tmp/siyuan_a_share_workspace.json
# ok=true, notebook_count=3

python3 optional-skills/research/blogwatcher-a-share/scripts/build_scrapling_supplement.py --output /tmp/a_share_scrapling_supplement.json
# ok=true, job_count=3

python3 -m pytest -q tests/skills/test_stock_skill_helpers.py tests/skills/test_siyuan_skill.py
# 15 passed

python3 - <<'PY'
import shutil, json
print(json.dumps({'qmd_path': shutil.which('qmd'), 'parallel_cli_path': shutil.which('parallel-cli')}))
PY
# {"qmd_path": null, "parallel_cli_path": null}
```

---

## 剩余高价值吸收机会

| 能力 | 当前状态 | 已完成 | 仍缺什么 | 优先级 |
|---|---|---|---|---|
| qmd 动态落地 | 已有通用 skill + A股增强 skill + bootstrap 脚本 + 测试 | 文档、脚本、测试、当前机器边界验收 | 真实安装环境下 `qmd status / collection list / search` 动态验收 | P0 |
| parallel-cli 动态落地 | 已有通用 skill + A股增强 skill | 场景模板、启用边界文档、当前机器边界验收 | 已认证环境下真实 `research/enrich/monitor` 运行证据 | P0 |
| duckduckgo-search 监控闭环 | 已补查询模板与测试 | 模板、脚本测试 | 和 cron / blogwatcher 形成更完整闭环示例 | P1 |
| blogwatcher 源模板扩充 | 已有 watchlist + A股 skill | 基础监控底座 | 更多稳定源模板与导入自动化 | P1 |

---

## 为什么这轮不优先吸收其他官方 skill

### `llm-wiki`
不优先原因：
- 更适合长期知识工程，而不是短线团队“快搜-快复盘-快回看”主链路
- 当前 `qmd` 已更贴合“本地文档检索 + 复盘召回”需求

### `youtube-content`
不优先原因：
- 更偏内容转录和摘要
- 对盘前、盘中、盘后核心决策链路不是高频基础设施

### `polymarket`
不优先原因：
- 与 A股主板短线工作流耦合度低
- 对当前团队日常执行收益不如 qmd / parallel-cli / blogwatcher / duckduckgo-search

---

## 正式判断

当前剩余“最值得继续吸收”的能力，不是新增更多通用官方 skills，而是把以下三条链路做成真正可验收：

1. `qmd-a-share` → 真机动态跑通
2. `parallel-cli-a-share` → 真认证环境动态跑通
3. `siyuan` A股 workspace → 真实例导入与检索跑通

如果这些高价值增强链路没补齐，再继续广撒网吸收更多 skill，收益会明显下降。

---

## 下一步建议

### P0
1. 在有 `qmd` 的机器上执行：
   - `qmd --version`
   - `qmd status`
   - `qmd collection add ...`
   - `qmd search "竞价" --limit 3`
2. 在已认证的 `parallel-cli` 环境执行：
   - `parallel-cli auth`
   - `parallel-cli research run ... --json`
   - `parallel-cli monitor create ... --json`

### P1
3. 给 `duckduckgo-search` + `blogwatcher-a-share` 补一份 cron 闭环示例
4. 给 `blogwatcher-a-share` 继续扩充交易所/监管/媒体源模板
5. 在可用 `SIYUAN_TOKEN` 的实例执行：
   - `python optional-skills/productivity/siyuan/scripts/build_a_share_workspace.py --output /tmp/siyuan_a_share_workspace.json`
   - 用 `createNotebook` / `createDocWithMd` 导入模板
   - 用 SiYuan 全文检索验证“竞价 / 龙头 / 风险”关键词可召回
