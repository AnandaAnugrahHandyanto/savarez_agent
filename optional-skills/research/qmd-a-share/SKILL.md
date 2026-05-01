---
name: qmd-a-share
category: research
description: A股短线团队知识库检索增强包。用 qmd 把复盘、策略笔记、会议纪要沉淀为本地可搜索知识库，并给出 bootstrap 与验收流程。
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [A股, 短线, qmd, 复盘, 知识库, MCP]
    related_skills: [qmd, obsidian, siyuan]
---

# QMD A-Share

这是 `qmd` 的 A股短线团队增强层，目标不是替代行情工具，而是解决：

- 过去复盘写了很多，但找不回来
- 会议纪要、策略讨论、风险复核结论分散
- 想查“上次某个题材退潮时是怎么判断的”很慢

## 适用资产

推荐纳入 qmd collection 的资料：

- 每日复盘
- 盘前计划
- 情报官纪要
- 风控复核记录
- CIO 决策备忘
- 龙头股案例卡
- 题材切换复盘

---

## 推荐目录结构

```text
research/a_share_kb/
├── review-daily/
├── morning-plan/
├── catalysts/
├── risk-notes/
├── cio-memos/
└── playbooks/
```

目录含义：
- `review-daily/`：日复盘
- `morning-plan/`：盘前计划
- `catalysts/`：催化与题材观察
- `risk-notes/`：风险与失败案例
- `cio-memos/`：决策备忘
- `playbooks/`：固定战法与模板

---

## Bootstrap 流程

### 1. 安装与检查

先确保 `qmd` 按原始 skill 要求完成安装，并确认：

```bash
qmd --version
qmd status
```

### 2. 建目录 / 生成 bootstrap 计划

先生成可复用 bootstrap JSON：

```bash
python optional-skills/research/qmd-a-share/scripts/build_a_share_bootstrap.py \
  --output /tmp/qmd_a_share_bootstrap.json
```

再按计划建目录：

```bash
mkdir -p research/a_share_kb/{review-daily,morning-plan,catalysts,risk-notes,cio-memos,playbooks}
```

### 3. 注册 collection

```bash
qmd collection add research/a_share_kb/review-daily --name a-review-daily
qmd collection add research/a_share_kb/morning-plan --name a-morning-plan
qmd collection add research/a_share_kb/catalysts --name a-catalysts
qmd collection add research/a_share_kb/risk-notes --name a-risk-notes
qmd collection add research/a_share_kb/cio-memos --name a-cio-memos
qmd collection add research/a_share_kb/playbooks --name a-playbooks
```

### 4. 补 context 描述

```bash
qmd context add qmd://a-review-daily "A股短线每日复盘，关注情绪、连板、炸板、次日溢价"
qmd context add qmd://a-morning-plan "A股短线盘前计划，关注竞价、龙头、主板、非ST"
qmd context add qmd://a-catalysts "题材催化、公告与新闻线索"
qmd context add qmd://a-risk-notes "失败样本、风险复核、仓位与止损经验"
qmd context add qmd://a-cio-memos "CIO 决策备忘与关键取舍"
qmd context add qmd://a-playbooks "固定战法模板与案例"
```

### 5. 生成 embeddings

```bash
qmd embed
```

---

## 推荐查询模式

### 快速关键词检索

```bash
qmd search "炸板 次日溢价"
qmd search "竞价 弱转强"
```

### 高质量混合检索

```bash
qmd query "上一次主线切换时我们是如何识别退潮的"
qmd query "哪些复盘中提到高位分歧加剧但次日仍有修复"
```

### 指定 collection

```bash
qmd query "风险控制里如何处理一字板开板" --collection a-risk-notes
qmd search "连板梯队" --collection a-review-daily
```

---

## Verification

最小验收不是“装了 qmd”，而是：

1. `qmd status` 正常
2. 至少 1 个 A股 collection 已注册
3. `qmd search` 或 `qmd query` 能返回结果
4. bootstrap JSON 可以成功生成

推荐最小验收命令：

```bash
python optional-skills/research/qmd-a-share/scripts/build_a_share_bootstrap.py \
  --output /tmp/qmd_a_share_bootstrap.json

qmd status
qmd collection list
qmd search "竞价" --limit 3
python -m pytest -q tests/skills/test_stock_skill_helpers.py
```

通过标准：
- bootstrap JSON 成功生成
- `qmd status` 正常
- collection list 至少能看到 1 个 A股 collection
- `qmd search` 返回结构化结果或显式可执行错误
- 测试通过

## Pitfalls

1. qmd 是知识检索层，不是实时行情源。
2. 如果复盘文件质量差，qmd 检索质量也会差。
3. 先把资料按目录归位，再做 embed，收益最高。
4. 若只需要精确关键词，优先 `qmd search`；重要问题再用 `qmd query`。
5. 只生成 bootstrap JSON 不等于知识库可用，至少要验证 `qmd status` 和一次真实搜索。
