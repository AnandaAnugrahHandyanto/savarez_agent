# QMT 一进二智能推送系统

## 概述

完整的 A 股一进二（首板次日）智能推送系统，整合消息面分析、板块联动、历史趋势、风控管理。

## 核心功能

### P0: 风控自动化 ✅
- **虚拟持仓跟踪**: 记录每次推送的"虚拟买入"
- **实时盈亏跟踪**: 自动更新持仓价格和盈亏
- **止损止盈提醒**: 
  - 炸板立即止损 -3%
  - 封单不足 -2% 止损
  - 高开回落 -1.5% 止损
  - A1 主攻 8% 止盈
  - A2 备选 6% 止盈
  - B1 观察 4% 止盈
- **仓位管理建议**:
  - A1 主攻: 30% 仓位
  - A2 备选: 20% 仓位
  - B1 观察: 10% 仓位
  - B2 观察: 5% 仓位

### P1: 智能化提升 ✅
- **消息面 LLM 分析**:
  - 自动分析新闻标题和内容
  - 识别利好/利空强度 (1-10)
  - 提取相关个股和板块
  - 判断持续性（1日/3日/周级/月级）
  - 催化剂评分 (0-10)
- **早盘新闻抓取**:
  - 东方财富快讯
  - 财联社快讯
  - 新浪财经要闻
- **消息面增强打分**:
  - 消息催化剂占 15% 权重
  - 自动匹配候选票与新闻
  - 重新排序候选

### P2: 深度数据整合 ✅
- **分时数据接入**:
  - 9:30-15:00 每分钟分时数据
  - 实时计算承接强度
  - 量能趋势、买卖比、价格稳定性
- **板块联动分析**:
  - 同板块其他票的表现
  - 板块资金流向
  - 板块情绪指标
  - 板块情绪占 10% 权重
- **历史趋势分析**:
  - 过去 5 日涨跌幅
  - 过去 20 日成交额趋势
  - 历史同题材表现
  - 历史趋势占 10% 权重

## 文件结构

```
~/.hermes/runtime-hermes-agent/
├── qmt_risk_manager.py              # 风控管理核心
├── qmt_auto_track_positions.py      # 自动跟踪虚拟持仓
├── qmt_update_positions_price.py    # 实时更新持仓价格
├── qmt_fetch_morning_news.py        # 抓取早盘新闻
├── qmt_news_llm_analyzer.py         # LLM 分析新闻
├── qmt_news_enhanced_ranker.py      # 消息面增强打分
├── qmt_timeseries_monitor.py        # 分时数据监控
├── qmt_sector_analysis.py           # 板块联动分析
├── qmt_historical_analysis.py       # 历史趋势分析
├── qmt_smart_push_master.py         # 总控脚本
├── qmt_setup_cron.py                # Cron 配置
├── qmt_data_source.py               # 数据源适配器 ✨
├── llm_client.py                    # LLM 客户端适配器 ✨
├── qmt_install_deps.py              # 依赖安装脚本 ✨
├── QMT_SMART_PUSH_README.md         # 完整文档
└── QMT_CONFIG_GUIDE.md              # 配置指南 ✨

~/.hermes/state/
├── qmt_risk/                        # 风控数据
│   ├── virtual_positions.json       # 虚拟持仓
│   ├── risk_alerts.json             # 风控提醒
│   └── trade_history.json           # 交易历史
├── qmt_news/                        # 新闻数据
│   ├── morning_news_2026-04-21.json
│   └── analyzed_morning_news_2026-04-21.json
├── qmt_timeseries/                  # 分时数据
│   └── 300123_2026-04-21.jsonl
├── qmt_history/                     # 历史数据
└── qmt_smart_push/                  # 智能推送输出
    ├── candidates_2026-04-21.json
    ├── final_candidates_2026-04-21.json
    └── smart_push_report_2026-04-21.txt

~/.hermes/config/                    # 配置文件（可选）
├── tushare.json                     # Tushare token
├── openai.json                      # OpenAI API key
└── anthropic.json                   # Anthropic API key
```

## 使用方法

### 0. 安装依赖

```bash
cd ~/.hermes/runtime-hermes-agent
python3 qmt_install_deps.py
```

### 1. 配置数据源和 LLM（可选）

参考 `QMT_CONFIG_GUIDE.md` 配置：
- Tushare token（推荐，用于历史数据）
- OpenAI/Anthropic API key（推荐，用于智能分析）
- Ollama（可选，本地免费 LLM）

最小配置（免费）：无需配置，自动使用 Akshare + 规则引擎

### 2. 手动运行完整流程

```bash
cd ~/.hermes/runtime-hermes-agent
python3 qmt_smart_push_master.py
```

### 2. 单独运行各模块

#### 数据源测试
```bash
# 测试数据源
python3 qmt_data_source.py test --source auto

# 获取实时行情
python3 qmt_data_source.py quote --code 600519 --source akshare

# 获取历史数据
python3 qmt_data_source.py history --code 600519 --days 20 --source akshare
```

#### LLM 测试
```bash
# 测试 LLM
python3 llm_client.py test --client auto

# 分析新闻
python3 llm_client.py analyze \
  --title "工信部发布AI算力支持政策" \
  --content "..." \
  --client auto
```

#### 风控管理
```bash
# 添加虚拟持仓
python3 qmt_risk_manager.py add \
  --code 300123 --name 太阳鸟 --grade A1 \
  --price 12.34 --time "2026-04-21 09:30:00" \
  --reason "低空经济 | 高开3.2% + 量能1.5亿" \
  --news "低空经济政策利好"

# 更新持仓价格
python3 qmt_risk_manager.py update \
  --code 300123 --price 12.80 --time "2026-04-21 10:00:00"

# 查看持仓摘要
python3 qmt_risk_manager.py summary

# 查看活跃持仓
python3 qmt_risk_manager.py positions

# 查看风控提醒
python3 qmt_risk_manager.py alerts

# 平仓
python3 qmt_risk_manager.py close \
  --position-id "300123_2026-04-21 09:30:00" \
  --price 13.20 --time "2026-04-21 15:00:00" \
  --reason "止盈"
```

#### 消息面分析
```bash
# 抓取早盘新闻
python3 qmt_fetch_morning_news.py

# LLM 分析单条新闻
python3 qmt_news_llm_analyzer.py \
  --title "工信部发布AI算力支持政策" \
  --content "..."

# 批量分析新闻
python3 qmt_news_llm_analyzer.py \
  --batch ~/.hermes/state/qmt_news/morning_news_2026-04-21.json \
  --min-score 7.0

# 消息面增强候选
python3 qmt_news_enhanced_ranker.py \
  --input candidates.json \
  --output news_enhanced_candidates.json
```

#### 分时监控
```bash
# 实时监控候选票（30分钟）
python3 qmt_timeseries_monitor.py monitor \
  --codes 300123 600123 000123 \
  --duration 30

# 获取承接强度报告
python3 qmt_timeseries_monitor.py report \
  --codes 300123 600123 000123
```

#### 板块分析
```bash
python3 qmt_sector_analysis.py \
  --candidates candidates.json \
  --all-stocks all_stocks.json \
  --output sector_enhanced_candidates.json
```

#### 历史趋势
```bash
python3 qmt_historical_analysis.py \
  --candidates candidates.json \
  --output historical_enhanced_candidates.json
```

### 3. 设置定时任务

每天早上 9:00 自动运行：

```bash
# 方式1: 使用 Hermes cron
python3 qmt_setup_cron.py

# 方式2: 使用系统 crontab
crontab -e
# 添加：
0 9 * * 1-5 cd ~/.hermes/runtime-hermes-agent && python3 qmt_smart_push_master.py
```

## 评分体系

### 原始评分（qmt_candidate_ranker.py）
- 买卖比: 25%
- 开盘位置: 20%
- 量能: 20%
- 相对量能: 15%
- 竞价金额: 10%
- 题材热度: 10%

### 增强评分
- **消息催化**: +0 ~ +1.5 分（15% 权重）
- **板块情绪**: +0 ~ +1.0 分（10% 权重）
- **历史趋势**: +0 ~ +1.0 分（10% 权重）

### 最终评分
原始评分 + 消息催化 + 板块情绪 + 历史趋势

## 风控规则

### 止损
- 炸板: -3%
- 封单不足（< 1亿）: -2%
- 高开回落（高开 > 7% 后回落）: -1.5%
- 单票最大亏损: -5%
- 总仓位最大亏损: -10%

### 止盈
- A1 主攻: 8%
- A2 备选: 6%
- B1 观察: 4%

### 回撤提醒
从最高点回撤 > 3%，触发减仓提醒

## 数据源

### 新闻源
- 东方财富快讯
- 财联社快讯
- 新浪财经要闻

### 行情数据（多源支持）
- **本地快照**: QMT 快照数据（最快）
- **Akshare**: 免费实时行情 + 历史数据（无需配置）
- **Tushare**: 专业历史数据（需要 token）
- **远程 VM**: QMT Windows VM 同步（需要 SSH）

### LLM 支持（多模型）
- **Ollama**: 本地免费（qwen2.5:14b 等）
- **OpenAI**: GPT-4o-mini / GPT-4（推荐）
- **Anthropic**: Claude 3.5 Sonnet（备选）
- **规则引擎**: Fallback（无需配置）

### 题材数据
- stock_theme_library.py
- ifind_board_enrichment.py
- tushare_theme_enrichment.py

## 输出格式

### 智能推送报告
```
============================================================
QMT 一进二智能推送报告
生成时间: 2026-04-21 09:00:00
============================================================

## 持仓摘要
活跃持仓: 3 (仓位 60.0%)
总盈亏: +2.5%
胜率: 65.0%

## A1 主攻 (30% 仓位)

太阳鸟 (300123) | 评分 8.5
  题材: 低空经济
  原因: 高开3.2% | 量能1.5亿 | 买卖比1.8
  消息催化 (8.5):
    - [8.5] 工信部发布低空经济支持政策
    - [7.0] 多地出台低空经济规划
  板块情绪: 强势 (7.5)
  历史趋势: 上升 | 5日 +12.3%
  建议仓位: 30%
  止盈: 8% | 止损: -5%

## A2 备选 (20% 仓位)
...

## B1 观察 (10% 仓位)
...

============================================================
风险提示: 虚拟持仓仅供参考，实盘操作需谨慎
============================================================
```

## 优化效果预期

### P0 风控自动化
- 回撤降低: 30-40%
- 避免追高: 减少高开 > 7% 的失败案例
- 及时止损: 炸板立即提醒

### P1 智能化提升
- 准确率提升: 10-15%
- 消息面命中率: 提升 20%
- 减少无催化剂的盲目追涨

### P2 深度数据整合
- 准确率提升: 15-20%
- 板块联动识别: 提升 30%
- 历史趋势过滤: 减少弱势票

### 综合效果
- 总准确率提升: 35-50%
- 总回撤降低: 30-40%
- 胜率提升: 15-20%

## 后续优化方向

1. **实时数据接入**
   - 对接 QMT 实时行情 API
   - 对接 tushare/akshare 历史数据
   - 对接同花顺/东方财富板块数据

2. **LLM 能力增强**
   - 用真实 LLM API 替代规则引擎
   - 增加多模态分析（图表、K线）
   - 增加情绪分析（社交媒体、论坛）

3. **策略优化**
   - 动态调整权重（根据历史准确率）
   - 增加机器学习模型
   - 增加回测系统

4. **风控增强**
   - 增加实盘对接（自动下单）
   - 增加仓位动态调整
   - 增加组合风险管理

## 注意事项

1. **虚拟持仓**: 当前为虚拟持仓，不涉及真实交易
2. **数据源**: 部分数据源需要 API key 或付费订阅
3. **LLM 调用**: 当前用规则引擎 fallback，需要对接真实 LLM API
4. **风险提示**: 股市有风险，投资需谨慎

## 联系方式

如有问题或建议，请联系开发者。
