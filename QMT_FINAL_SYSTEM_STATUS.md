# QMT 系统最终状态（含题材语义增强）

## 当前已完成
1. QMT VM 自动导出主板非ST候选池
2. QMT VM 自动生成日报
3. Hermes 本机自动同步日报
4. 盘中多时点快照自动落盘
5. 盘中二快照刷新报告自动生成
6. 盘中全日轨迹报告自动生成
7. 自动状态迁移决策引擎已接入
8. 本机已具备盘中同步脚本与验收脚本
9. 盘中自动推送 cron 已创建，并带 post-deliver 去重提交
10. 题材语义增强已接入：
   - 主线龙头候选
   - 主线前排
   - 跟风前排
   - 非核心

## 关键脚本
- `qmt_candidate_ranker.py`
- `qmt_candidate_ranker_cn.py`
- `qmt_daily_report.py`
- `qmt_sync_report.py`
- `qmt_sync_intraday.py`
- `qmt_intraday_acceptance.py`
- `qmt_intraday_push_change_guard.py`
- `qmt_intraday_snapshot_and_refresh.py`
- `qmt_intraday_timeline.py`
- `qmt_intraday_state_matrix.py`

## 当前效果
系统现在不只给日报，还能直接给：
- 主线标签
- 链路角色
- 回避样本的语义分类
- 盘中最强切换 / 焦点切换
- 单票升级 / 降级 / 重排 / 重评
- 自动动作（继续主攻 / 重写主攻 / 仅留备选 / 仅观察 / 全部回避）
- 当前聊天的盘中自动推送（仅变化时推送，成功投递后才提交基线）

## 当前仍可继续增强
1. 真实交易题材名替换掉“上证A股/沪深A股”这种粗标签
2. 将快照序列事件层升级为更高频成交/逐笔级盘中流
3. 修 VM 控制台显示乱码（文件本身、同步结果与验收已正常）
