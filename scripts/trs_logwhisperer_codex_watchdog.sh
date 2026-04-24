#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/zl/ai/TRS-LogWhisperer-v2
QUEUE=/root/.hermes/hermes-agent/scripts/run_codex_queue.sh
PROMPT=/root/.hermes/workspace/tmp/codex_trs_v2_prompt.txt
START=/root/.hermes/scripts/start_trs_logwhisperer.sh
HEALTH_URL=http://127.0.0.1:8000/health
PLAN_SRC=/home/zl/ai/TRS-LogWhisperer-v2/plans/trs-logwhisperer-v2
PLAN_LINK=$ROOT/plans/trs-logwhisperer-v2
RUN_LOG=/root/.hermes/workspace/tmp/codex_trs_v2_run.log
START_LOG=/root/.hermes/workspace/tmp/start_trs_logwhisperer_from_hermes.log

mkdir -p /root/.hermes/codex_queue /root/.hermes/workspace/tmp "$ROOT/plans"
ln -sfn "$PLAN_SRC" "$PLAN_LINK"

if ! curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
  bash "$START" >"$START_LOG" 2>&1 || true
fi

if pgrep -af '(^|/)(codex)( |$)|codex exec|codex_queue_runner.py|run_codex_trs_v2.py' >/dev/null 2>&1; then
  echo "Codex already running; skip enqueue"
  exit 0
fi

set +e
python3 - <<'PY'
import json
from pathlib import Path
state_file = Path('/root/.hermes/codex_queue/state.json')
if state_file.exists():
    state = json.loads(state_file.read_text(encoding='utf-8'))
    queued = [t for t in state.get('queue', []) if t.get('status') in {'queued', 'running'}]
    if queued:
        print(f'queue_pending={len(queued)}')
        raise SystemExit(10)
PY
status=$?
set -e
if [ "$status" -eq 10 ]; then
  echo "Queue already has pending Codex task; skip enqueue"
  exit 0
elif [ "$status" -ne 0 ]; then
  exit "$status"
fi

python3 - <<'PY'
from pathlib import Path
src = Path('/home/zl/ai/TRS-LogWhisperer-v2/plans/trs-logwhisperer-v2/CODEX_LONG_SESSION_PROMPT.md')
out = Path('/root/.hermes/workspace/tmp/codex_trs_v2_prompt.txt')
text = src.read_text(encoding='utf-8').strip()
extra = '''\n\n补充执行要求（Hermes cron 版）：\n- 默认认为项目仍未达到“真实项目现场可稳定使用”的最终目标，除非你能基于运行结果明确证明已经达到。\n- 优先推进：任务稳定性/恢复、超大日志处理、进度与可观测性、跨链路分析可信度、以及面向现场实施/交付人员的中文化与易用性。\n- 每轮结束前，至少执行与你改动直接相关的验证；不要只改代码不验证。\n- 若服务未运行或健康检查失败，优先修复并恢复到可本机访问。\n- 若确实没有值得继续推进的内容，才允许停止，并在最终说明里写清阻塞证据。\n- 每轮结束时，必须覆盖写入 `plans/trs-logwhisperer-v2/LATEST_ROUND_SUMMARY.md`，不能沿用旧内容。\n- `LATEST_ROUND_SUMMARY.md` 顶部必须包含 `# 任务标识` 小节，并逐行写入当前环境变量中的以下字段原值：\n  - `CODEX_QUEUE_TASK_ID`\n  - `CODEX_QUEUE_TASK_STARTED_AT`\n  - `CODEX_QUEUE_TASK_WORKDIR`\n  - `finished_at`（若结束时还不知道最终值，先写占位；但文件中必须有这一行，供 runner 收尾回填）\n- 若上述任务标识任一缺失，视为本轮未完成交付，必须在收尾前补齐后再结束。\n- 写完 `LATEST_ROUND_SUMMARY.md` 后，务必再次读取该文件，自检其中的 `CODEX_QUEUE_TASK_ID`、`CODEX_QUEUE_TASK_STARTED_AT`、`CODEX_QUEUE_TASK_WORKDIR` 是否与当前环境变量一致；不一致就继续改到一致。\n'''
out.write_text(text + extra, encoding='utf-8')
print(f'prompt_written={out}')
PY

CMD="codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check -m gpt-5.5 -C $ROOT - < $PROMPT >> $RUN_LOG 2>&1"
$QUEUE add "$CMD" --workdir "$ROOT" --name "TRS-LogWhisperer-v2 auto-continue" \
  --env CODEX_AUTO_GIT_PUSH=1 \
  --env CODEX_AUTO_GIT_BRANCH=master \
  --env 'CODEX_AUTO_GIT_COMMIT_MESSAGE=自动推进LogWhisperer-v2本轮任务'
