# QMT 真实交易题材映射增强说明

## 本轮已完成
1. 在 `qmt_candidate_ranker.py` 增加了 `trade_theme` 交易题材映射层。
2. 基于股票名称 + `sector_tags` 做关键词归因，不再只输出“上证A股/沪深A股”这类粗标签。
3. 将题材映射结果接入：
   - `qmt_candidate_ranker_cn.py`
   - `qmt_daily_report.py`
4. 输出字段新增：
   - `semantics.trade_theme`
   - `semantics.theme_hits`
   - `semantics.is_main_theme`
   - `top_trade_themes_by_amount`

## 当前支持的真实题材
- AI算力
- 铜缆高速连接
- 半导体
- 消费电子
- 机器人
- 固态电池
- 新能源汽车
- 医药
- 军工
- 有色资源

## 当前规则
1. 先从股票名称与 `sector_tags` 中抽取文本。
2. 用关键词命中映射到交易题材。
3. 再按题材成交额统计 `top_trade_themes_by_amount`。
4. `chain_role` 由“板块主线”升级为“交易题材主线”。
5. 若只落到 `泛市场/未知题材`，额外加入风控项：`交易题材不清晰`。

## 当前边界
- 这是 Hermes 本地规则映射，不是外部题材数据库。
- 题材归因质量取决于导出名称与标签质量。
- 若后续接入更细题材源，可继续替换这层规则而不改日报接口。

## 价值
- 日报开始更接近交易员口径，而不是仅有交易所级粗分类。
- 主攻/备选/回避现在会直接带出题材语义。
- 后续可继续扩展到题材强度、盘中切换、题材链条前后排。
