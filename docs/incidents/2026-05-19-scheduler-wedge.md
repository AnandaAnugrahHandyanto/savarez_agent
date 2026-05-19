# 2026-05-19 — Cron scheduler wedged for 32 minutes

## Symptom

The algotrader operator running on this Hermes instance saw the
`algotrader-catalysts-scan` and `algotrader-catalysts-evaluate`
crons (both `*/5 * * * *`, `no_agent=True`) stop firing for
roughly 25 minutes (15:25 → 15:50 EDT). During the same window:

- The Telegram chat thread spent 32 minutes processing a single
  inbound message (gateway log: `response ready: ... time=1962.8s
  api_calls=3 response=1177 chars`).
- `~/.hermes/cron/.tick.lock` was held continuously across the
  whole window.
- Other cron jobs (analyst-batch, polymarket, fear-greed) also
  missed their schedule, but the operator-visible pain was
  concentrated on the 5-minute catalysts because they were the
  shortest-cadence jobs in the gap.

Manual `rm ~/.hermes/cron/.tick.lock` followed by the next minute
boundary restored normal firing immediately.

## Mechanism

`cron/scheduler.py:tick()` (the function the gateway calls every
60 s from a background thread) acquires the file lock, then runs
**every due job to completion inside the `try:` block** before
releasing in `finally:` (lines 1447–1590 of the file at incident
time).

When at least one due job in a tick is an LLM-backed job (not
`no_agent=True`), `run_job()` calls
`agent.run_conversation(prompt)` which internally streams from
the model provider via `chat.completions.create(stream=True)` and
iterates synchronously over chunks (`run_agent.py:6907-6933`).

There is no enforced end-to-end deadline on that stream:

- `HERMES_STREAM_READ_TIMEOUT` (default 120 s) is an httpx-level
  per-chunk read timeout — it resets on every byte received, so a
  stream that emits one token every 119 s never trips.
- `HERMES_STREAM_STALE_TIMEOUT` (default 180 s) is a stale-stream
  detector inside the chunk loop; same per-chunk semantics.
- `HERMES_CRON_TIMEOUT` (default 600 s) is *inactivity*-based —
  it's reset by `_touch_activity("receiving stream response")`
  on every chunk, so an active-but-slow stream keeps it pinned at
  zero indefinitely.
- `max_iterations` (default 90) is a *tool-loop* ceiling, not a
  wall-clock ceiling — each iteration can itself be an
  arbitrarily long stream.

So in pathological cases (provider degradation, retry storm with
keepalive pings, agent stuck in a tool/think/answer cycle that
makes progress slowly), a single LLM job can sit inside `tick()`
for minutes-to-hours while holding the file lock.

Every subsequent tick attempt during that window logs
`"Tick skipped — another instance holds the lock"` and returns 0
without firing any cron — including unrelated `no_agent` cron
that wouldn't touch the LLM at all.

## Lock-scope audit

A repo-wide grep (`tick.lock | tick_lock | _get_lock_paths`)
shows only `cron/scheduler.py` and its tests touch the lock.
The lock has exactly one purpose: prevent two concurrent
`tick()` calls from picking up the same due job twice (the
gateway's background ticker and a standalone `python -m
cron.scheduler` daemon running in parallel — explicitly called
out in the module docstring).

It does **not** serialize:

- LLM provider concurrency (each job constructs its own
  `AIAgent`, its own httpx client, its own credential pool).
- Job output storage (`save_job_output` is fd-per-write,
  independent per `job_id`).
- Per-job state (jobs have independent SessionDB rows keyed by
  `cron_session_id`).
- Shared adapters (delivery uses live adapters via
  `asyncio.run_coroutine_threadsafe`, no lock).

Conclusion: the lock's purpose is *single-flight on cron-job
dispatch*, nothing else. There is no second purpose to preserve;
narrowing the lock to dispatch-only is safe.

## Fix plan (branch `fix/scheduler-wedge`)

A. **LLM stream deadline.** Add two env vars —
   `HERMES_LLM_STREAM_TIMEOUT_SECONDS` (default 300 s, total
   wall-clock budget for one stream) and
   `HERMES_LLM_STREAM_CHUNK_TIMEOUT_SECONDS` (default 60 s, max
   gap between chunks). Both enforced inside the chunk loop with
   a new `StreamTimeoutError`. On breach: close the stream
   cleanly, raise, surface to the agent loop's existing retry /
   error-propagation paths.

   **Deviation note**: the spec says "wrap LLM stream in
   `asyncio.wait_for`", but the OpenAI SDK stream path here is
   synchronous (`for chunk in stream:`) and the cron caller
   wraps it in a `ThreadPoolExecutor`. Bolting `asyncio.wait_for`
   on would require rewriting the whole sync path into async,
   which is a much bigger change than the wedge fix needs. The
   deadline + per-chunk watchdog inside the existing sync loop
   gives the same end-to-end guarantee: stream cannot exceed the
   total budget; stream cannot stall longer than the per-chunk
   budget; on breach, raise `StreamTimeoutError` and close.

B. **Narrow lock scope.** Hold `.tick.lock` only across
   `get_due_jobs()` + `advance_next_run()` (the actual dispatch
   step). Release before job execution. Subsequent ticks during
   the LLM run land with an empty due-job list (already advanced)
   and become a fast no-op. Single-flight semantics preserved
   because `advance_next_run()` happens under the lock.

C. **Guaranteed release.** Wrap the lock acquisition in an
   explicit `try/finally` that covers `asyncio.CancelledError`,
   `KeyboardInterrupt`, and arbitrary `BaseException` —
   currently the `try` block has bare `Exception` only.

5 regression tests pin the new invariants
(`tests/scheduler/test_wedge_recovery.py`):

1. Total-timeout abort — slow stream over budget raises
   `StreamTimeoutError`.
2. Per-chunk-timeout abort — stream stall over per-chunk budget
   raises `StreamTimeoutError`.
3. Lock released during stream — concurrent tick fires while the
   first tick's LLM job is mid-stream.
4. Lock released on cancellation — `CancelledError` mid-tick
   releases the lock.
5. Lock released on exception — uncaught exception mid-tick
   releases the lock.

## What this does NOT fix

- LaunchAgent supervision. The Hermes gateway on this machine is
  not registered with launchd (`launchctl list | grep hermes`
  returns nothing); the process was started with PPID 1 and has
  no auto-respawn. Filed in `docs/todos/scheduler-followups.md`.
- Per-job timeout overrides. `HERMES_LLM_STREAM_TIMEOUT_SECONDS`
  is process-wide. Some long-form jobs (compliance check, deep
  research) genuinely need >300 s. Filed in
  `docs/todos/scheduler-followups.md`.
