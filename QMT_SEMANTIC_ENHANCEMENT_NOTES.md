# QMT 题材语义增强说明

## 已增强内容
在 `qmt_candidate_ranker.py` 中加入了题材语义层：
- 主线龙头候选
- 主线前排
- 跟风前排
- 非核心

## 当前规则
1. 先按候选池成交额统计 top sector
2. 候选属于 top sector 且板块内排名第1 → 主线龙头候选
3. 候选属于 top sector 且板块内排名前3 → 主线前排
4. 板块内排名前5但不在主线 → 跟风前排
5. 其他 → 非核心

## 已接入位置
- `qmt_candidate_ranker.py`
- `qmt_candidate_ranker_cn.py`
- `qmt_daily_report.py`

## 当前验证结果
真实 QMT JSON 下：
- 华友钴业 → 主线龙头候选
- 生益科技 → 主线前排
- 云赛智联 → 非核心
- 中天科技 → 跟风前排

## 当前价值
相比之前只看 sector_tags，当前输出已更接近主人真实交易口径：
- 不再只是板块名
- 开始区分主线 / 跟风 / 非核心
- 日报已能直接显示题材链路角色
