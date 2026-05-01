# QMT IFIND 题材增强接入说明

## 目标
把同花顺 iFind 的题材/概念维度数据接入 Hermes 的 QMT 候选排序，让系统不再只依赖：
- 名称关键词映射
- QMT 静态候选池金额聚合
- 涨停池代理分

## 当前 Hermes 已支持两种模式
1. **external**：读取真实 iFind/IFIND 题材增强 JSON
2. **proxy**：没有外部文件时，用当前 QMT payload 自动生成代理强度/资金/广度
3. **ifind-probe**：读取 `IFIND_REFRESH_TOKEN / IFIND_ACCESS_TOKEN / IFIND_BASE_URL` 并输出本地可用性探针信息，但在未确认真实 endpoint 前不盲打外部接口

## 已支持的加载方式
优先级如下：
1. 环境变量 `QMT_THEME_ENRICH_PATH`
2. 与 QMT payload 同目录下的：
   - `ifind_theme_enrichment.json`
   - `theme_enrichment.json`
   - `ifind_theme_snapshot.json`
3. 若都不存在，则自动回退到 `proxy`

## 标准输出格式
推荐最终写成：
- `examples/ifind_theme_enrichment.sample.json`

核心字段：
- `strength_score`
- `money_score`
- `breadth_score`
- `amount`
- `auction_amount`
- `limit_up_count`
- `highest_board`
- `member_count`
- `rising_count`
- `falling_count`
- `avg_pct`
- `avg_bid_ask_ratio`
- `leader_code`
- `leader_name`

## 自动导入脚本骨架
已提供：
- `scripts/build_ifind_theme_enrichment.py`
- `scripts/import_ifind_theme_table.py`

用途：
- `build_ifind_theme_enrichment.py`：把已有 JSON 导出归一化成 Hermes 标准增强文件。
- `import_ifind_theme_table.py`：把 iFind 导出的 Excel/CSV 表格直接转成 Hermes 标准增强文件。

示例：
```bash
python scripts/build_ifind_theme_enrichment.py \
  --input examples/ifind_theme_source.sample.json \
  --output qmt_sync/reports/20260414/ifind_theme_enrichment.json

python scripts/import_ifind_theme_table.py \
  --input examples/ifind_theme_table.sample.xlsx \
  --sheet 概念资金热度 \
  --output qmt_sync/reports/20260414/ifind_theme_enrichment.json
```

## 原始输入样例
已提供：
- `examples/ifind_theme_source.sample.json`

支持两种常见输入：
1. `{"themes": [...]}`
2. `{"themes": {"有色资源": {...}}}`

字段名兼容：
- `theme_strength` / `strength_score`
- `theme_money` / `money_score`
- `theme_breadth` / `breadth_score`
- `name` / `theme`

## 当前 Hermes 中的实际消费点
- `qmt_candidate_ranker.py`
- `qmt_candidate_ranker_cn.py`
- `qmt_daily_report.py`
- `qmt_theme_enrichment.py`

## 已提供样例与脚本
- `examples/ifind_theme_enrichment.sample.json`
- `examples/ifind_theme_source.sample.json`
- `examples/ifind_theme_table.sample.xlsx`
- `scripts/build_ifind_theme_enrichment.py`
- `scripts/import_ifind_theme_table.py`
- `scripts/windows_import_ifind_theme.ps1`
- `scripts/windows_import_ifind_theme.bat`

## 当前产出内容
报告中已新增：
- IFIND代理题材强度
- IFIND代理题材资金
- IFIND代理题材广度
- 单题材强度/资金/广度分
- 个股题材增强：强度 / 资金 / 广度

## 切到真实 IFIND 后的变化
当外部文件存在时：
- `market_map.theme_enrichment_meta.has_external = true`
- `market_map.theme_enrichment_meta.source = external+proxy`
- 每个题材优先采用外部值
- 缺失字段仍由 proxy 兜底

## 当前边界
当前脚本骨架只负责：
- 归一化已有 iFind 导出 JSON
- 生成 Hermes 标准增强文件
- 读取 `IFIND_REFRESH_TOKEN / IFIND_ACCESS_TOKEN / IFIND_BASE_URL`
- 对 refresh token 做本地结构解析与到期信息探针

它还没有负责：
- 直接调用 iFind SDK
- 直接连同花顺桌面客户端
- 在未确认 endpoint 的情况下盲打 refresh/access 接口
- 自动从未知格式网页/桌面缓存中提取真实接口地址

已提供最小探针脚本：
```bash
python scripts/inspect_ifind_config.py
```

当前已验证通过的真实认证形态：
- Base URL：`https://quantapi.51ifind.com/api/v1`
- 获取 access token：`POST /get_access_token`
- 刷新 access token：`POST /update_access_token`
- Header：`refresh_token: <token>`
- Body：`{}`
- 成功响应中：`data.access_token`
