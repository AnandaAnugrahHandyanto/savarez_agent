# QMT 当日真实数据题材增强验收

日期：2026-04-14

## 已执行
1. 从 Windows VM 拉取真实候选池：
   - `qmt_sync/reports/20260414/auction_candidates_main_board_non_st.json`
2. 使用当前 Hermes 本地增强版脚本重跑：
   - `qmt_daily_report.py`
   - `qmt_candidate_ranker_cn.py`
3. 生成新结果：
   - `qmt_sync/reports/20260414/daily_report_trade_theme.txt`
   - `qmt_sync/reports/20260414/cn_trade_theme_report.txt`

## 真实数据现状
- VM 导出的 `sector_tags` 仍然只有：
  - 上证A股
  - 沪深A股
  - 深证A股
- 这说明上游导出尚未提供细题材标签。
- 因此本轮真实交易题材识别，主要依赖 Hermes 本地名称/关键词映射。

## 真实数据重跑后的结果
### 日报结论
- 今日无主攻，仅保留备选观察：`600010.SH 包钢股份（有色资源）`

### 备选
- `600010.SH 包钢股份` → 主线前排 / 有色资源
- `600183.SH 生益科技` → 主线前排 / 半导体

### 回避样本
- `603799.SH 华友钴业` → 主线前排 / 有色资源
- `600522.SH 中天科技` → 跟风前排 / 铜缆高速连接
- `601318.SH 中国平安` → 非核心 / 泛市场

## 关键发现
1. 真实题材增强已经真正跑进当天数据，不再只是样例。
2. 但由于上游 `sector_tags` 太粗，`top_trade_themes_by_amount` 里仍有大量 `泛市场`。
3. 这意味着当前最好用法是：
   - 用本地映射辅助交易语义
   - 不把它误当成完备题材库

## 当前边界
- 已完成：真实数据重跑 + 本地题材增强落地
- 未完成：上游细题材标签补齐、盘中动态刷新、题材数据库接入
