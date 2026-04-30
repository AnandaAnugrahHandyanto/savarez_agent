---
name: factory-droid-mission-mode
description: Use when running Factory Droid CLI as a mission-mode multi-agent coding orchestrator, especially with Stanislav's local BYOK models and safe macOS process hygiene.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [factory, droid, mission-mode, byok, acp, macos, coding-agents]
    related_skills: [hermes-agent, codex, claude-code]
---

# Factory Droid Mission Mode

## Overview

Factory Droid supports a `--mission` mode for complex multi-step coding tasks. Mission mode turns Droid into an orchestrator that can spawn worker sessions through Factory's daemon/factoryd path. It is powerful, but it is also the mode most likely to create many `droid exec --input-format stream-jsonrpc --output-format stream-jsonrpc` workers and consume memory.

On this setup, prefer local BYOK model IDs unless the task explicitly needs Factory cloud models:

- `custom:AEON-Qwen3.6-DFlash-[Local-BYOK]-0`
- `custom:Step3.5-Flash-GGUF-[Local-BYOK]-1`

Mission mode requires either `--auto high` or `--skip-permissions-unsafe`. Use `--auto high` by default. Reserve `--skip-permissions-unsafe` for isolated throwaway directories, containers, or CI sandboxes.

## When to Use

Use this skill when the user asks to:

- Run Droid in mission mode.
- Delegate a larger coding task to Droid with worker/validator agents.
- Compare Droid mission mode with Hermes `delegate_task`/ACP.
- Run a Droid mission using the local BYOK model.
- Diagnose worker buildup after mission-mode use.

Do not use mission mode for:

- Simple one-shot questions, log inspection, or small edits.
- Tasks where read-only analysis is enough.
- Running inside a valuable repo without checking git status first.
- Low-memory situations with many existing `stream-jsonrpc` workers.

## Preflight Checklist

Before starting a mission:

```sh
# Confirm version and available flags
droid --version
droid exec --help | sed -n '1,140p'

# Confirm working tree state if inside a repo
git status --short --branch 2>/dev/null || true

# Check existing Droid/Factory worker count
pgrep -fl 'droid exec --input-format stream-jsonrpc --output-format stream-jsonrpc' || true

# Check memory pressure on macOS
memory_pressure | sed -n '1,24p'
```

If many workers already exist, map parent chains before killing anything:

```sh
PID=<pid>
while ps -p "$PID" -o pid=,ppid=,command= >/tmp/droid-parent.$$ 2>/dev/null; do
  cat /tmp/droid-parent.$$
  PID=$(awk '{print $2}' /tmp/droid-parent.$$)
  [ "$PID" = "0" ] && break
done
rm -f /tmp/droid-parent.$$
```

Do not kill active `cmux`, TUI, or Factory.app sessions unless the user intends cleanup.

## Recommended Command Patterns

### Safe default: direct mission with local BYOK

```sh
droid exec --mission --auto high \
  --model 'custom:AEON-Qwen3.6-DFlash-[Local-BYOK]-0' \
  --worker-model 'custom:AEON-Qwen3.6-DFlash-[Local-BYOK]-0' \
  --validator-model 'custom:AEON-Qwen3.6-DFlash-[Local-BYOK]-0' \
  --cwd /path/to/repo \
  'Implement the planned change. Before editing, inspect the repo and make a concise plan. Run relevant tests. Do not push.'
```

### Mission with lower worker reasoning for local models

For local models, keep reasoning simple unless the model supports and benefits from Droid's reasoning values:

```sh
droid exec --mission --auto high \
  --model 'custom:AEON-Qwen3.6-DFlash-[Local-BYOK]-0' \
  --worker-model 'custom:AEON-Qwen3.6-DFlash-[Local-BYOK]-0' \
  --worker-reasoning-effort none \
  --validator-model 'custom:AEON-Qwen3.6-DFlash-[Local-BYOK]-0' \
  --validator-reasoning-effort none \
  --cwd /path/to/repo \
  'Do the task, run tests, and summarize files changed.'
```

If Droid rejects `none` for a specific model, omit the reasoning flags and let Droid choose defaults.

### Cloud primary with local worker/validator

Use only if local mission quality is insufficient:

```sh
droid exec --mission --auto high \
  --model gpt-5.5 \
  --worker-model 'custom:AEON-Qwen3.6-DFlash-[Local-BYOK]-0' \
  --validator-model 'custom:AEON-Qwen3.6-DFlash-[Local-BYOK]-0' \
  --cwd /path/to/repo \
  'Refactor the subsystem and run tests. Do not push.'
```

### Add a system prompt guardrail

```sh
droid exec --mission --auto high \
  --model 'custom:AEON-Qwen3.6-DFlash-[Local-BYOK]-0' \
  --append-system-prompt 'Never push to remote. Prefer minimal diffs. Ask before destructive operations.' \
  --cwd /path/to/repo \
  'Complete the task and report verification.'
```

### Use a prompt file

```sh
cat > /tmp/droid-mission.md <<'EOF'
Goal: ...
Constraints:
- Do not push.
- Keep changes minimal.
- Run tests and show results.
EOF

droid exec --mission --auto high \
  --model 'custom:AEON-Qwen3.6-DFlash-[Local-BYOK]-0' \
  --cwd /path/to/repo \
  -f /tmp/droid-mission.md
```

## Hermes / ACP Guidance

Droid has native ACP via:

```sh
droid exec --output-format acp --model 'custom:AEON-Qwen3.6-DFlash-[Local-BYOK]-0'
```

But Droid slash commands do not route through ACP; `/help`, `/model`, etc. arrive as normal text. Use CLI flags instead.

For mission mode, prefer direct `droid exec --mission ...` in the terminal rather than Hermes `delegate_task` ACP, because mission mode itself spawns workers and can be long-running. If using Hermes tooling, start it as a tracked background terminal process rather than a synchronous `delegate_task`:

```sh
droid exec --mission --auto high --model 'custom:AEON-Qwen3.6-DFlash-[Local-BYOK]-0' --cwd /path/to/repo '...'
```

## Verification After a Mission

After completion:

```sh
# Inspect repo changes
git status --short
git diff --stat
git diff --check

# Check lingering Droid workers
pgrep -fl 'droid exec --input-format stream-jsonrpc --output-format stream-jsonrpc' || true

# Check relevant logs if something felt unstable
tail -n 30 ~/.factory/logs/desktop-startups.log
tail -n 200 ~/.factory/logs/droid-log-single.log | grep -E 'ERROR|WARN|Transport error|SIGKILL|Unknown/custom|falling back' || true
```

Verify BYOK routing through session files, not log warnings alone:

```sh
python3 - <<'PY'
from pathlib import Path
import json, time
roots=[Path.home()/'.factory/sessions/-Users-stanislavwolf', Path.home()/'.factory/sessions/-Users-stanislavwolf-.hermes-hermes-agent']
files=[]
for r in roots:
    files += list(r.glob('*.settings.json'))
for p in sorted(files, key=lambda p:p.stat().st_mtime, reverse=True)[:10]:
    j=json.loads(p.read_text())
    print(time.strftime('%F %T', time.localtime(p.stat().st_mtime)), p)
    print('  model=', j.get('model'), 'providerLock=', j.get('providerLock'), 'autonomy=', j.get('autonomyMode') or j.get('autonomyLevel'))
PY
```

## Cleanup Pattern

If mission mode leaves stale workers and the user wants cleanup:

```sh
# First inspect
pgrep -fl 'droid exec --input-format stream-jsonrpc --output-format stream-jsonrpc' || true

# Kill only stream-jsonrpc helper workers, not every droid process
pkill -f 'droid exec --input-format stream-jsonrpc --output-format stream-jsonrpc'

# Verify
pgrep -fl 'droid exec --input-format stream-jsonrpc --output-format stream-jsonrpc' || true
memory_pressure | sed -n '1,24p'
```

If Factory.app daemon itself is crash-looping, inspect `~/.factory/logs/desktop-startups.log` before restarting. A `daemon_crash` with `exitSignal: SIGKILL` and very low `freeMemoryMb` points to memory pressure or external kill rather than an application exception.

## Common Pitfalls

1. **Using mission mode for small work.** Mission mode is expensive and spawns workers. Use plain `droid exec` or Hermes `delegate_task` for small tasks.

2. **Forgetting `--auto high`.** Droid requires `--auto high` or `--skip-permissions-unsafe` for `--mission`.

3. **Using `--skip-permissions-unsafe` on a real repo.** This bypasses all checks. Default to `--auto high` and add prompt guardrails instead.

4. **Assuming ACP supports Droid slash commands.** It does not. Use flags like `--model`, `--auto`, `--mission`, and `--cwd`.

5. **Believing BYOK fallback warnings blindly.** Logs may say `Unknown/custom model, defaulting to FIREWORKS` even when session settings and transcript show local BYOK. Inspect `*.settings.json`.

6. **Leaving worker buildup unattended.** Mission mode may create many stream-jsonrpc helpers; check processes and memory afterward.

7. **Running from `$HOME` accidentally.** Always pass `--cwd /path/to/repo` for repo work.

## Verification Checklist

- [ ] `droid --version` and `droid exec --help` confirm expected version/flags.
- [ ] Target repo path passed with `--cwd`.
- [ ] Git status inspected before edits.
- [ ] Mission uses `--auto high`, not `--skip-permissions-unsafe`, unless isolated.
- [ ] BYOK model IDs use exact `custom:...` values from `droid exec --help`.
- [ ] Tests or equivalent verification ran after changes.
- [ ] Session settings inspected if BYOK routing matters.
- [ ] Lingering workers and memory pressure checked after completion.
