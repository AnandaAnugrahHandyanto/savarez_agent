# MES 智能巡检系统

基于 hermes-agent 平台的 MES 生产环境智能巡检系统。脚本直接检测指标，仅在发现异常时触发 LLM 诊断，降低运营成本。

## 架构

```
Cron 定时调度
  ├─ heartbeat (每 2 分钟) — upstream 节点轻量存活检查
  ├─ full_check (每 5 分钟) — 6 大组件全量巡检
  ├─ deep_analysis (每 30 分钟) — Oracle 慢查询 + ELK 异常模式
  ├─ daily_report (每天 8:00) — 全量巡检报告（纯脚本，无 LLM）
  ├─ weekly_trend (每周一 9:00) — 周度趋势分析（LLM）
  └─ evolution (每周日 2:00) — 技能自动进化（DSPy）
```

**核心原则：** 脚本检测 → 指标正常？→ `{"wakeAgent": false}`（无 LLM 成本）；异常？→ 报告 + `{"wakeAgent": true}` → LLM 诊断 + 自愈。

## 巡检组件

| 组件 | 脚本 | 检查方式 | 频率 |
|------|------|----------|------|
| Nginx | `nginx_check.py` | HTTP `/status` 端点 | 5 分钟 |
| JVM/Tomcat | `jvm_check.py` | SSH (jstat/jmap) + HTTP | 5 分钟 |
| RabbitMQ | `rabbitmq_check.py` | HTTP Management API | 5 分钟 |
| Oracle | `oracle_check.py` | JDBC/SSH | 5/30 分钟 |
| ELK | `elk_check.py` | HTTP ES API | 5/30 分钟 |
| SkyWalking | `skywalking_check.py` | HTTP GraphQL API | 5 分钟 |
| Upstream | `upstream_check.py` | HTTP nginx_upstream_check_module | 2 分钟 |

## 快速开始

### 1. 安装依赖

```bash
cd mes-inspection
pip install -r setup/requirements.txt
```

### 2. 配置

```bash
cp config/mes_inspection.yaml.example ~/.mes-inspection/config.yaml
# 编辑配置：目标主机、SSH 凭据、阈值、飞书 Webhook
```

### 3. 运行巡检

```bash
# 心跳检查（upstream 节点存活）
python scripts/heartbeat.py

# 全组件巡检
python scripts/full_check.py

# 深度分析（Oracle + ELK）
python scripts/deep_analysis.py
```

### 4. 调试工具

```bash
# GC 日志截取（按时间段）
python scripts/debug_tools.py gc --host 10.0.0.1 --start 2026-06-05T01:00:00 --end 2026-06-05T02:00:00

# 线程堆栈分析（关键字过滤 + ±10 行上下文）
python scripts/debug_tools.py stack --host 10.0.0.1 --keyword DataRecordServiceImpl

# ES 日志检索（按主机 + 时间 + 关键字 + 级别）
python scripts/debug_tools.py log --host-name 39QEMES-Tomcat-Crontab01 --start 2026-06-05T01:00:00 --end 2026-06-05T02:00:00 --keyword Exception --level ERROR
```

## 目录结构

```
mes-inspection/
├── scripts/                  # 巡检脚本（核心代码）
│   ├── base_checker.py       # BaseChecker 基类 — 多节点、JSON 输出、exit code
│   ├── ssh_executor.py       # SSH/本地执行器抽象
│   ├── inspection_runner.py  # 统一执行入口
│   ├── heartbeat.py          # 心跳入口（upstream，每 2 分钟）
│   ├── full_check.py         # 全量巡检入口（6 组件，每 5 分钟）
│   ├── deep_analysis.py      # 深度分析入口（Oracle+ELK，每 30 分钟）
│   ├── debug_tools.py        # 调试工具 CLI（gc/stack/log）
│   ├── gc_log_analyzer.py    # GC 日志分析器
│   ├── thread_stack_analyzer.py  # 线程堆栈分析器
│   ├── es_log_search.py      # ES 日志检索器
│   ├── nginx_check.py        # Nginx 巡检
│   ├── jvm_check.py          # JVM/Tomcat 巡检
│   ├── rabbitmq_check.py     # RabbitMQ 巡检
│   ├── oracle_check.py       # Oracle 巡检
│   ├── elk_check.py          # ELK 巡检
│   ├── skywalking_check.py   # SkyWalking 巡检
│   └── upstream_check.py     # Upstream 节点存活检查
├── config/
│   ├── default_thresholds.py # 默认阈值配置
│   ├── config_manager.py     # 配置管理器（YAML 加载 + 深度合并）
│   ├── cron_jobs.json        # 6 个 Cron 作业定义
│   └── mes_inspection.yaml.example  # 配置模板
├── alerter/
│   ├── feishu_alerter.py     # 飞书告警（卡片 + 文本）
│   └── formatter.py          # 飞书格式化器（节点分组）
├── self_healing/             # 自愈引擎
│   ├── decision_matrix.py    # 五维评分矩阵
│   ├── self_healer.py        # 自愈执行器
│   └── code_analyzer.py      # 日志代码分析
├── memory/                   # 巡检记忆
├── evolution/                # 技能进化（DSPy）
├── gitlab/                   # GitLab 集成（自动 MR）
├── skills/                   # 9 个 Hermes Skills
├── tests/                    # 测试套件（~172 个测试）
└── vendor/                   # 第三方依赖
```

## 多节点巡检模型

- **集中式：** 所有巡检从一个控制节点发起
- **HTTP 检查**（Nginx 状态、RabbitMQ API、ES 健康、Tomcat HTTP）：使用 `target.url`
- **命令检查**（jstat、jstack、jmap、日志文件）：使用 `SSHExecutor` 远程执行
- `BaseChecker.check()` → `check_all_targets()` → `check_node(target)` → `_merge_node_reports()`
- `create_executor(target)` 自动选择 `LocalExecutor`（localhost）或 `SSHExecutor`（远程）

## 脚本输出规范

所有脚本输出 JSON 到 stdout，使用退出码：

- `0` = NORMAL（全部健康）
- `1` = WARNING（降级）
- `2` = CRITICAL（故障/不可达）

```
===INSPECTION_REPORT===
{"component":"nginx","status":"CRITICAL","checks":[...]}
===END===
{"wakeAgent": true}
```

`===INSPECTION_REPORT===` / `===END===` 分隔人类可读报告与 `{"wakeAgent": true/false}` 门控。

## 飞书告警

- P0/P1: 红色卡片 + @所有人
- P2: 橙色卡片
- P3: 蓝色卡片
- 防风暴：5 分钟内相同检查项不重复告警
- 节点分组：相同节点的异常合并显示

## 测试

```bash
# 全量测试（必须加 -o "addopts=" 覆盖超时设置）
python -m pytest tests/ -v --no-header -o "addopts="

# 单个测试文件
python -m pytest tests/test_gc_log_analyzer.py -v --no-header -o "addopts="

# 单个测试
python -m pytest tests/test_gc_log_analyzer.py::TestGcLogParsing::test_parse_g1_young -v -o "addopts="
```

## Cron 作业

| 作业 | 调度 | 脚本 | LLM | 技能 |
|------|------|------|-----|------|
| mes-heartbeat | 每 2 分钟 | heartbeat.py | 异常时 | mes-upstream-check |
| mes-full-check | 每 5 分钟 | full_check.py | 异常时 | 6 个 mes-*-check |
| mes-deep-analysis | 每 30 分钟 | deep_analysis.py | 异常时 | mes-oracle-check, mes-elk-check |
| mes-daily-report | 每天 8:00 | full_check.py | 否 | - |
| mes-weekly-trend | 每周一 9:00 | full_check.py | 是 | 6 个 mes-*-check |
| mes-evolution | 每周日 2:00 | - | 是 | mes-evolution |

## 自愈级别

五维评分矩阵（数据风险×0.30 + 可逆性×0.25 + 影响范围×0.25 + (1-成功率)×0.15 + 配置变更×0.05）：

- **L1（<30 分）：** 自动执行修复命令（重启服务等）
- **L2（30-70 分）：** 推送修复方案到飞书，等待人工确认
- **L3（≥70 分）：** 推送详细诊断报告到飞书，通知运维人员
