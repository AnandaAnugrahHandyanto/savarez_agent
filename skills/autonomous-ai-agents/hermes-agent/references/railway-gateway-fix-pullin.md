# Railway gateway fix pull-in: lessons learned

When pulling a narrow set of upstream Hermes fixes into Gordon's Railway fork, prefer a conservative manual-patch workflow over broad cherry-pick batches.

## Useful upstream fix classes

Recent upstream commits contained small, relevant fixes in these areas:

- Telegram/gateway delivery: typing indicator after sends, Telegram-safe slash aliases, underscore-preserving markdown stripping, zsh-safe update wrapper, Telegram DM topic metadata for synthetic messages.
- Cron: collect parallel job futures independently so one exception does not drop all remaining job results.
- Provider fallback: pass custom providers into fallback context-length detection; reset fallback-chain index at turn start after exhausted fallback attempts.
- Memory/compression: ignore whitespace-only memory provider names; improve unavailable auxiliary compression provider warnings; isolate background review forks from external memory providers with `skip_memory=True`.

## Pitfalls

- Avoid batching many `git cherry-pick -n` operations. A conflict followed by `git cherry-pick --skip` can leave you believing prior staged changes survived when they may not have. Re-check each target hunk after any skip/abort/continue.
- Upstream may have refactored code into `agent/*` modules while Gordon's fork still keeps logic in `run_agent.py`; use original pre-refactor commits or manually translate hunks.
- Gateway `run.py` often diverges around i18n/reload/update handling. Resolve conflicts by preserving fork behavior unless the requested fix directly modifies that path.
- Do not call a rollout ready until: `git status` is clean or intentionally staged, conflict markers are absent, targeted pytest passes, syntax/lint checks pass, the commit is pushed, Railway deploy/restart finishes, and Telegram gateway delivery is tested live.

## Verification checklist

1. `git status --short` and search for unresolved merge-conflict marker strings.
2. Inspect target files to confirm the intended hunks are present.
3. Run targeted tests for changed areas: cron scheduler, Telegram/gateway, command registry, markdown stripping, fallback runtime, compression feasibility, background review memory isolation.
4. Run a syntax/lint gate on changed Python files before commit.
5. Commit and push through source watcher; if watcher blocks, inspect `/opt/data/logs/watcher-blocked.log` and fix before rollout.
6. Test Railway gateway delivery from Telegram before announcing rollout readiness.
