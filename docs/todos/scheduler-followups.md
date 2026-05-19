# Scheduler followups (deferred from the 2026-05-19 wedge fix)

These were identified during the wedge investigation but are
**not** implemented in the `fix/scheduler-wedge` branch — they
need separate design / operator sign-off before landing.

## 1. LaunchAgent supervision for the gateway

**Observation.** The Hermes gateway on the incident host had no
launchd registration (`launchctl list | grep hermes` returned
nothing). Process PPID was 1 (orphan inherited by init via a
`nohup ... & disown` startup). Net effect: if the process dies,
it stays dead. No auto-respawn.

**Recommendation.**
- Ship a sample LaunchAgent plist at `packaging/launchd/
  com.nousresearch.hermes-gateway.plist` (path TBD per repo
  layout).
- `KeepAlive` should be `Crashed`-only (dict-form), not the
  blanket boolean `true` — we don't want a clean operator-
  initiated stop (e.g. `hermes stop`) to be re-spawned.
  ```xml
  <key>KeepAlive</key>
  <dict>
      <key>SuccessfulExit</key>
      <false/>
  </dict>
  ```
- `ThrottleInterval` ≥ `60` so a crash loop can't burn the CPU.
- `StandardOutPath` / `StandardErrorPath` should point at
  `~/Library/Logs/hermes/gateway.out` / `gateway.err` (separate
  from the in-app `~/.hermes/logs/gateway.log` rotation).
- Installer step: `bin/setup-launchd` (or similar) that copies
  the plist into `~/Library/LaunchAgents/`, runs
  `launchctl bootstrap gui/<uid>` and `launchctl enable`.

**Why deferred.** The wedge fix already prevents the gateway from
getting stuck inside `tick()`. Auto-respawn is a separate failure
mode (process crash) that we have not seen in the wild on this
host yet; the supervision design needs a sign-off from the
operator on the KeepAlive policy + logging destinations before
landing.

## 2. Per-job stream timeout overrides

**Observation.** `HERMES_LLM_STREAM_TIMEOUT_SECONDS` and
`HERMES_LLM_STREAM_CHUNK_TIMEOUT_SECONDS` are process-wide. Some
classes of cron job legitimately need longer windows:

- Compliance / regulatory web-search jobs (current default in
  this repo: ~5–10 minutes with up to 10 sequential searches).
- Deep-research / agentic-research jobs that iterate over a
  large tool surface.
- Long-form report generation against slow local models.

Pushing the global default up to accommodate them would also
loosen the bound on every other job in the same process.

**Recommendation.**
- Add an optional `stream_timeout_seconds` / `stream_chunk_timeout_seconds`
  field on the cron job record (set via the `cronjob` create / update
  tool, mirroring the existing `enabled_toolsets` plumbing).
- At job-run time, push the per-job values into the process via
  `ContextVar` so the per-stream watchdog inside
  `_call_chat_completions` reads the job-scoped value instead of
  the global env-var default.
- Validate: per-job total must be ≤ some hard ceiling (e.g.
  3600s) to prevent a misconfigured job from re-introducing the
  wedge pattern at a longer time scale.

**Why deferred.** Adds new schema, new tool surface, and
operator-facing config UX — needs a separate design pass. The
env-var defaults plus the documented "set to 0 to disable" knob
cover the immediate need for the algotrader workload.
