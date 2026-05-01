# Windows / QMT 机 IFIND 导入简明说明

## 目标
把 iFind 导出的题材热度/资金表，直接落到：
- `C:\Users\mac\Desktop\qmt_runtime\exports\YYYYMMDD\ifind_theme_enrichment.json`

这样 Hermes 在读取当天 QMT 候选池时，会自动优先加载这份增强文件。

## 已提供脚本
- `scripts\windows_import_ifind_theme.ps1`
- `scripts\windows_import_ifind_theme.bat`

## 用法
### 方式 1：bat
```bat
windows_import_ifind_theme.bat C:\path\to\ifind_export.xlsx 概念资金热度 20260415
```

### 方式 2：PowerShell
```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows_import_ifind_theme.ps1 \
  -InputPath C:\path\to\ifind_export.xlsx \
  -Sheet 概念资金热度 \
  -DateTag 20260415
```

## 输出位置
默认输出：
```text
C:\Users\mac\Desktop\qmt_runtime\exports\YYYYMMDD\ifind_theme_enrichment.json
```

## 支持输入
- `.xlsx`
- `.xls`
- `.csv`

参考样例：
- `examples/ifind_theme_source.sample.json`
- `examples/ifind_theme_table.sample.xlsx`

## 推荐表头
导入器支持宽松映射，但推荐尽量包含：
- 题材名称
- 题材强度
- 题材资金
- 题材广度
- 题材成交额
- 竞价额
- 涨停家数
- 最高板
- 成分股数
- 上涨家数
- 下跌家数
- 平均涨幅
- 平均承接比
- 龙头代码
- 龙头名称

## 接入后效果
当天目录中若同时存在：
- `auction_candidates_main_board_non_st.json`
- `ifind_theme_enrichment.json`

则 Hermes 在运行：
- `qmt_candidate_ranker.py`
- `qmt_candidate_ranker_cn.py`
- `qmt_daily_report.py`

时会自动优先使用真实 IFIND 数据，而不是仅用 proxy 代理。
