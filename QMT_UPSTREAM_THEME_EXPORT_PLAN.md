# QMT 上游细题材导出改造方案

## 目标
把当前 VM 导出的粗标签：
- 上证A股
- 沪深A股
- 深证A股

升级成更接近交易使用的细题材标签，减少 Hermes 端依赖名称猜测。

## 当前真实问题
- `auction_candidates_main_board_non_st.json` 中 `sector_tags` 只有交易所级标签。
- 导致 Hermes 端即使补了题材映射，也只能做到部分识别。
- `top_trade_themes_by_amount` 中仍会大量出现 `泛市场`。

## 建议改造顺序
### P0：导出端补细题材字段
在 VM 导出 JSON 时，新增至少一个字段：
- `theme_tags`: ["有色资源", "稀土", "锂电"]
- 或 `concept_tags`: [...]

最低要求：
1. 每只股票至少给 1~3 个细题材标签
2. 保留现有 `sector_tags` 向后兼容
3. 不要覆盖原字段，新增字段即可

### P0：Hermes 端兼容优先级
Hermes 端读取优先级建议：
1. `theme_tags`
2. `concept_tags`
3. `sector_tags`
4. 最后才 fallback 到名称关键词映射

### P1：补题材强度统计
如果导出端能给：
- 题材内成交额
- 涨停家数
- 连板家数
- 高标/龙头标识

则 Hermes 可进一步输出：
- 主线题材
- 次主线题材
- 题材内龙一/龙二/跟风

### P1：盘中多次导出
建议导出频率：
- 09:26
- 09:32
- 09:45
- 10:15
- 11:00
- 13:15
- 14:00
- 14:40

这样 Hermes 端的 `qmt_intraday_refresh.py` 可直接消费多版本 JSON，生成升级/降级报告。

## Hermes 已完成的配套
- `qmt_candidate_ranker.py`：已支持交易题材映射
- `qmt_daily_report.py`：已支持题材语义日报
- `qmt_candidate_ranker_cn.py`：已支持中文结论
- `qmt_intraday_refresh.py`：已支持两版快照对比

## 结论
真正的精度瓶颈已经明确在导出端，而不是 Hermes 展示层。
