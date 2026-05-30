# Hermes ↔ OpenClaw A2A v2.5.0 cron monitor race hardening

## 结论

v2.5.0 修正了 v2.4.0 手动触发验证中的监测竞态：旧 monitor 在启动时重新采集 baseline，如果 cronjob 已经快速完成并落盘 evidence，它会把新 evidence 当成初始状态，导致诊断为 `no running process and no new evidence`。

新 monitor 支持显式 baseline、since timestamp、post cron job 状态和 completed evidence 识别，可以区分：

1. run request accepted
2. process still running
3. execution evidence observed
4. cron job reports ok but matching evidence was not identified
5. no running process and no new evidence

## 修改文件

- `scripts/hermes_openclaw_cron_monitor.py`

## 新增能力

### 1. Baseline file

新增参数：

```bash
--baseline-file examples/v2.2.0/baseline.json
```

baseline JSON 可包含：

```json
{
  "created_epoch": 1780062850.0,
  "evidence": {
    "cron-run-...": {
      "dir": "...",
      "mtime": 1780061761.0,
      "summary_exists": true,
      "summary_size": 2213,
      "raw_exists": true,
      "raw_size": 2214
    }
  }
}
```

### 2. Since timestamp

新增参数：

```bash
--since-epoch 1780062850.0
```

用于识别触发时间之后生成的 evidence，即使 monitor 启动较晚也能关联完成结果。

### 3. Cron job status correlation

新增参数：

```bash
--job-id 170596628792
--post-cron-list-json path/to/cron-list-after-run.json
```

如果 post cron list 中 `last_status=ok`，monitor 会把它作为执行完成信号之一，但仍优先寻找 evidence。

### 4. Detection fields

输出新增关键字段：

- `execution_observed`
- `detected_summary`
- `post_since_summary`
- `evidence_after_job_last_run`
- `post_job`
- `diagnosis`

## 无副作用验证

### Synthetic baseline replay

用 v2.4.0 手动 run 的既有 evidence 构造旧 baseline，不触发 OpenClaw、不运行 cronjob。

命令：

```bash
cd /.hermes/hermes-agent
python3 scripts/hermes_openclaw_cron_monitor.py \
  --timeout 1 \
  --interval 1 \
  --expect-new \
  --job-id 170596628792 \
  --baseline-file examples/v2.2.0/v250-synthetic-baseline-before-manual-run.json \
  > examples/v2.2.0/v250-monitor-synthetic-baseline-result.json
```

结果：

```text
ok=True
diagnosis=execution evidence observed
execution_observed=True
new_evidence=['cron-run-20260529T135437Z']
detected_dir=/.hermes/hermes-agent/examples/v2.2.0/cron-run-20260529T135437Z
run_id=v2.2.0-20260529T135519Z-27714df9
```

### Idle monitor verification

命令：

```bash
cd /.hermes/hermes-agent
python3 scripts/hermes_openclaw_cron_monitor.py --timeout 1 --interval 1 \
  > examples/v2.2.0/v250-monitor-idle-result.json
```

结果：

```text
ok=True
diagnosis=no running process and no new evidence; stop waiting
execution_observed=False
new_evidence=[]
```

这保留了 v2.3.2 的安全边界：没有进程、没有新 evidence 时不继续空等。

## Evidence

- `examples/v2.2.0/v250-synthetic-baseline-before-manual-run.json`
- `examples/v2.2.0/v250-monitor-synthetic-baseline-result.json`
- `examples/v2.2.0/v250-monitor-idle-result.json`

## Recommended future manual run sequence

1. Capture baseline before `cronjob run`.
2. Resume job if paused.
3. Trigger `cronjob run`.
4. Monitor with `--baseline-file` and `--job-id`.
5. Read post-run cron state.
6. Pause recurring job.
7. Report: request accepted / evidence observed / cron last_status / callback boundary.

## Side effects boundary

v2.5.0 did not:

- run OpenClaw queue
- resume cronjob
- trigger cronjob
- restart Hermes gateway
- restart OpenClaw
- modify OpenClaw config

Only local monitor script and docs/evidence files were changed.
