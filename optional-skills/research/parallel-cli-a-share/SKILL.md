---
name: parallel-cli-a-share
category: research
description: A股短线专题研究增强包。为 parallel-cli 补充 A股研究、富集、监控的模板命令与启用边界，避免把付费深研究链路误用为默认搜索。
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [A股, 短线, parallel-cli, 深研究, 富集, 监控]
    related_skills: [parallel-cli, duckduckgo-search, blogwatcher-a-share]
---

# Parallel CLI A-Share

`parallel-cli` 不适合作为 A股短线默认主链路。

它最适合：
- 高价值专题研究
- 公司/产业链结构化摸排
- 批量 enrichment
- 监控特定主题或事件

不适合：
- 普通网页搜索
- 简单公告确认
- 能用 RSS / DuckDuckGo / 交易所原文完成的工作

结论：

> **把 Parallel 当增强器，不当默认入口。**

---

## 何时启用

### 应启用
- 需要做题材链条深挖
- 需要批量 enrichment（公司、主营、催化、风险标签）
- 需要较长周期主题监控
- 需要研究报告级别输出

### 不应启用
- 只想查一条公告
- 只想验证一则消息真假
- 只需盘前快扫催化

这些场景优先：
- `blogwatcher-a-share`
- `duckduckgo-search`
- 官方公告源

---

## A股研究模板

### 1. 题材链专题研究

```bash
parallel-cli research run \
  "梳理某A股题材的核心催化、龙头、补涨、监管风险、历史持续性，并给出最可能的扩散路径" \
  --processor core \
  --json
```

### 2. 公司深挖

```bash
parallel-cli research run \
  "研究某上市公司最近三个月的公告、订单、扩产、并购、监管、产业链地位，并判断是否存在短线催化持续性" \
  --processor core \
  --json
```

### 3. 批量 enrichment

```bash
parallel-cli enrich run \
  --data '[{"company":"某公司A"},{"company":"某公司B"}]' \
  --goal "补充主营业务、题材标签、近期催化、主要风险" \
  --json
```

### 4. 主题监控

```bash
parallel-cli monitor create \
  --name "A股低空经济催化监控" \
  --query "A股 低空经济 催化 公告 订单 监管" \
  --json
```

---

## 推荐链路

1. 先用 `blogwatcher-a-share` / `duckduckgo-search` 做低成本初筛
2. 只有确认值得深挖时，再启 `parallel-cli`
3. 输出结论时必须回到原始来源，不要只复述供应商结果

---

## 风险与边界

1. 依赖认证与外部服务，不保证随时可用
2. 成本高于普通搜索，不能滥用
3. 对交易所原文、监管文书，仍应以原站内容为准
4. 不要把供应商摘要当成最终事实
