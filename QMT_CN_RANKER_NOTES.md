# QMT 中文结论版输出器

## 文件
- `qmt_candidate_ranker_cn.py`

## 作用
把 `auction_candidates_main_board_non_st.json` 转成主人可直接看的中文结论输出：
- 状态
- 结论
- 主攻 / 备选 / 禁追观察
- 依据
- 下一步

## 当前验证结果
基于真实 QMT JSON：
- 环境 = 分歧日
- 主攻 = 无
- 备选 = 华友钴业
- 输出格式已符合“先判断、再依据、再动作”的口径

## 与原始 ranker 的区别
- `qmt_candidate_ranker.py`：结构化 JSON 结果，适合程序接入
- `qmt_candidate_ranker_cn.py`：中文结论版，适合主人直接看

## 下一步增强建议
1. 把 sector_tags 升级成主线题材标签
2. 增加竞价尾段承接因子
3. 支持盘中二次刷新同一票的结论变化
