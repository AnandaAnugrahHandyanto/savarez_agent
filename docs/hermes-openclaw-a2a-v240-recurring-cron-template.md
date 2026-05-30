# Hermes ↔ OpenClaw A2A v2.4.0 recurring compact cron template

## 结论

已创建一个可复用的 Hermes cronjob 模板，用于按固定周期触发 OpenClaw A2A queue，并把最终结果以短 Markdown 摘要回流到当前 origin 通道。

当前状态：模板已创建但保持 paused，不会自动执行，不会打扰当前通道。

## Cronjob

- job_id: `170596628792`
- name: `openclaw-a2a-queue-v2.4.0-compact-recurring-paused`
- schedule: `0 */6 * * *`
- repeat: `forever`
- deliver: `origin`
- no_agent: `true`
- script: `openclaw_queue_cron_v220.sh`
- workdir: `/.hermes/hermes-agent`
- verified state: `paused`

## Side effects boundary

This version only created and paused the cronjob template.

It did not:

- restart Hermes gateway
- restart OpenClaw
- modify OpenClaw config
- run the A2A queue
- send an automatic platform callback
- enable daemon/background loop

## Script paths

Required files verified:

- `/root/.hermes/scripts/openclaw_queue_cron_v220.sh`
- `/.hermes/hermes-agent/scripts/hermes_openclaw_queue_cron_v220.sh`
- `/.hermes/hermes-agent/scripts/hermes_openclaw_cron_monitor.py`

The wrapper is intentionally compact-output only:

1. full queue JSON is written to evidence files
2. stdout prints only short Markdown summary
3. `no_agent=true` cron delivery sends stdout verbatim to `origin`

## Enable / manual-run / pause commands

Use the job id from `hermes cron list` or the current verified id `170596628792`.

### 1. Check current state

```bash
hermes cron list
```

Expected when idle-safe:

- `enabled=false`
- `state=paused`

### 2. Enable the recurring schedule

```bash
hermes cron resume 170596628792
```

Effect:

- future automatic runs every 6 hours
- each run posts a compact summary back to the origin channel

### 3. Trigger one manual run for verification

Do not immediately pause after triggering; first watch runtime evidence.

```bash
hermes cron run 170596628792
```

Then monitor:

```bash
cd /.hermes/hermes-agent
python3 scripts/hermes_openclaw_cron_monitor.py --timeout 120 --interval 10
```

Interpretation:

- `cronjob run` success only means scheduler accepted the request
- real completion requires new evidence or a delivered compact callback
- if monitor reports no running process and no new evidence, stop waiting; nothing is currently executing

### 4. Pause again after verification

```bash
hermes cron pause 170596628792
```

## Verification evidence

Created during v2.4.0 verification:

- `examples/v2.2.0/v240-monitor-paused-template.json`

Observed monitor result for paused template:

- `ok=true`
- `diagnosis=no running process and no new evidence; stop waiting`
- `new_evidence=[]`
- `process_running_at_end=false`

This proves the monitor can correctly stop waiting when the recurring template is paused and no queue execution is active.

## Reporting contract for future runs

Every callback to the user channel must stay short and include only:

- conclusion
- run_id
- success_count / failure_count
- per-item task_id / state / ok / marker
- duplicate guard status
- secret scan status
- `external_message_sent`
- evidence_dir

Full raw JSON must remain on disk under evidence directories, not in the user channel.

## Safety rules

- Keep `external_message_sent=false` unless a specific guarded sender version is intentionally enabled.
- Do not leak `Bearer` / `Authorization` / token material into stdout, docs, receipts, or summary files.
- Do not treat paused cronjob as failure.
- Do not treat `cronjob run accepted` as execution proof.
- Always monitor evidence + process + cron state together after manual trigger.
