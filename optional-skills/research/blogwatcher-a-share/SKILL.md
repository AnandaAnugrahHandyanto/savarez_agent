---
name: blogwatcher-a-share
category: research
description: A股短线情报监控增强包。基于 blogwatcher 的 RSS/资讯轮询，配合 DuckDuckGo / Scrapling / cronjob 形成盘前、盘中、盘后持续监控链路。
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [A股, 短线, RSS, 资讯监控, blogwatcher, cron]
    related_skills: [blogwatcher, duckduckgo-search, scrapling, morning-briefing]
---

# Blogwatcher A-Share

把官方 `blogwatcher` 能力场景化为 **A股短线情报监控链路**。

适用场景：
- 盘前盯公告、交易所动态、监管消息、媒体快讯
- 盘中轮询题材催化、公告异动、快讯更新
- 盘后沉淀次日关注情报源

## 核心定位

`blogwatcher` 适合处理 **稳定 RSS / Atom feed**。

但 A股关键情报源并不全是 RSS，因此本 skill 采用三层组合：

1. **blogwatcher**：接稳定 feed
2. **duckduckgo-search**：补免费检索与快速二跳确认
3. **scrapling / parallel-cli**：处理非 RSS 页面、专题抓取、深研究

因此不要把它理解成“只靠 RSS 就能覆盖全部 A股情报”。正确理解是：

> **用 blogwatcher 做稳定监控底座，再用搜索/抓取工具补全非 RSS 缺口。**

---

## 已提供资产

### 1. A股监控源生成脚本

脚本：

```bash
python optional-skills/research/blogwatcher/scripts/build_a_share_watchlist.py \
  --output /tmp/a_share_watchlist.json
```

输出内容：
- 监控用途说明
- 候选 feeds 列表
- 哪些源属于 RSS / 哪些属于非 RSS 候选
- 后续补链建议

当前候选覆盖：
- 上交所上市公司公告
- 深交所上市公司公告（待定制抓取）
- 巨潮资讯公告检索（待定制抓取）
- 证券时报快讯
- 财联社
- 证监会新闻发布（待定制抓取）

### 2. 场景化运行边界

- **稳定 RSS**：直接接入 `blogwatcher-cli`
- **非 RSS 页面**：不要硬塞给 blogwatcher，改走 `scrapling` / `parallel-cli` / DuckDuckGo 检索
- **定时轮询**：交给 `cronjob`
- **本轮新增补链脚本**：`optional-skills/research/blogwatcher-a-share/scripts/build_scrapling_supplement.py`，用于生成深交所 / 巨潮 / 证监会这类非 RSS 页面的 Scrapling 抓取模板

### 3. 非 RSS 页面补链模板

脚本：

```bash
python optional-skills/research/blogwatcher-a-share/scripts/build_scrapling_supplement.py \
  --output /tmp/a_share_scrapling_supplement.json
```

输出内容：
- 深交所公告页 / 巨潮资讯检索页 / 证监会新闻页的抓取模板
- 对应 DuckDuckGo → Scrapling 的推荐顺序
- 示例 `scrapling extract get ...` 命令
- 动态验收与注意事项

---

## 推荐工作流

### 工作流 A：先生成监控源清单

```bash
python optional-skills/research/blogwatcher/scripts/build_a_share_watchlist.py \
  --output /tmp/a_share_watchlist.json
```

查看 JSON 后，先挑出稳定 RSS 源用于 `blogwatcher-cli add`。

### 工作流 B：把稳定 RSS 源接进 blogwatcher

示例：

```bash
blogwatcher-cli add "上交所上市公司公告" https://www.sse.com.cn/disclosure/listedinfo/announcement/ \
  --feed-url https://www.sse.com.cn/disclosure/listedinfo/announcement/rss.xml

blogwatcher-cli add "证券时报-快讯" https://www.stcn.com/ \
  --feed-url https://www.stcn.com/rss/rss.xml

blogwatcher-cli add "财联社" https://www.cls.cn/ \
  --feed-url https://www.cls.cn/rss.xml
```

然后：

```bash
blogwatcher-cli scan
blogwatcher-cli articles --all
```

### 工作流 C：对非 RSS 源做补链

适合：
- 深交所公告页
- 巨潮资讯检索页
- 证监会新闻发布页

先生成 Scrapling 补链模板：

```bash
python optional-skills/research/blogwatcher-a-share/scripts/build_scrapling_supplement.py \
  --output /tmp/a_share_scrapling_supplement.json
```

推荐顺序：

1. 先用 `duckduckgo-search` 补快速检索
2. 再用 `scrapling` 处理页面抓取
3. 高价值专题才用 `parallel-cli` 做深研究 / 富集 / 监控

---

## 与 cronjob 串联

适合定时任务：
- 08:30 盘前公告与快讯扫描
- 11:35 午间增量扫描
- 14:30 盘中异动扫描
- 20:30 盘后整理与次日关注点输出

### 先生成 cron 闭环模板

```bash
python optional-skills/research/blogwatcher-a-share/scripts/build_cron_closure.py \
  --output /tmp/a_share_cron_closure.json
```

### 推荐 prompt 结构

```text
扫描 blogwatcher 未读文章；聚焦 A股主板、非 ST、短线龙头、次日溢价相关催化；
把结果按【公告/监管/媒体快讯/题材催化】分类，输出最值得次日跟踪的事项。
对非 RSS 关键线索，追加用 duckduckgo-search 做二跳补证。
```

---

## 注意事项

1. **不要假设所有 A股源都有 RSS。**
2. **不要把非 RSS 页面直接当成稳定 feed。**
3. **blogwatcher 更适合监控“已知来源”，不是全网搜索替代品。**
4. **短线价值不在信息量，而在筛掉无关源后留下催化信号。**
5. **交易所 / 监管 / 权威媒体优先级高于泛财经搬运站。**

---

## Verification

最小验收：

```bash
python optional-skills/research/blogwatcher/scripts/build_a_share_watchlist.py \
  --output /tmp/a_share_watchlist.json

python optional-skills/research/blogwatcher-a-share/scripts/build_scrapling_supplement.py \
  --output /tmp/a_share_scrapling_supplement.json

python optional-skills/research/blogwatcher-a-share/scripts/build_cron_closure.py \
  --output /tmp/a_share_cron_closure.json

python -m pytest -q tests/skills/test_stock_skill_helpers.py
```

通过标准：
- watchlist / scrapling supplement / cron closure 三个 JSON 都成功生成
- 至少包含交易所公告源与主流财经快讯源
- 非 RSS 补链模板包含深交所 / 巨潮 / 证监会三类页面
- 测试通过
