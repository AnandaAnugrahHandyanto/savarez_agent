---
name: mes-upstream-check
description: MES 上游端点 HTTP 存活检查。
version: "1.0"
license: MIT
metadata:
  hermes:
    tags: [mes, inspection, upstream, heartbeat]
    category: devops
---

# MES Upstream Check Skill

轻量 HTTP 上游端点存活检查，用于高频心跳巡检（2 分钟间隔）。

## When to Use

- 心跳巡检：快速确认所有上游 HTTP 端点是否可达
- 端点健康验证：检查 HTTP 状态码和响应时间
- 不需要 SSH、不解析日志、不检查 JVM

## How to Run

```bash
python scripts/upstream_check.py
```

## 检查项

| 检查项 | 数据源 | 判定逻辑 |
|--------|--------|----------|
| 端点存活 | HTTP GET url | 非 2xx → CRITICAL |
| 响应时间 | curl 耗时 | ≥critical → CRITICAL，≥warn → WARNING |

## 配置

```yaml
upstream:
  targets:
    - name: "mes-app-1"
      url: "http://10.0.0.1:8080/health"
    - name: "mes-app-2"
      url: "http://10.0.0.2:8080/health"
  timeout: 5
  response_time_warn: 2.0
  response_time_critical: 5.0
```
