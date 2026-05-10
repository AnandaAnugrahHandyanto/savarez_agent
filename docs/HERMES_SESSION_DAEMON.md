# Hermes Session Daemon Architecture

Status: MVP implemented behind explicit `hermes daemon ...` commands.

## Why

jcode's most useful architectural idea is not its full Rust implementation; it is
the separation of long-lived session runtime from thin client surfaces. Hermes can
use that pattern to support Mission Control / Agent Room, CLI, TUI, and future
mobile/web clients without making every surface spawn a separate independent
agent process.

## MVP Scope

The first slice is intentionally small and safe:

- one local daemon per Hermes profile
- Unix-domain socket only: `$HERMES_HOME/runtime/hermes-daemon.sock`
- PID file: `$HERMES_HOME/runtime/hermes-daemon.pid`
- log file: `$HERMES_HOME/runtime/hermes-daemon.log`
- JSON-lines protocol, one request and one response per line
- session registry operations only; no model calls or tool execution yet

Commands:

```bash
hermes daemon start
hermes daemon status [--json]
hermes daemon sessions [--limit N] [--json]
hermes daemon create-session [--title T] [--source S] [--model M]
hermes daemon stop
hermes daemon serve      # foreground/debug mode
```

Protocol methods:

- `ping`
- `session.list`
- `session.create`
- `session.get`
- `shutdown`

## Design Rules

1. Preserve current CLI behavior. The daemon is opt-in until it has enough
   runtime coverage to become the default.
2. Keep the socket local/profile-scoped. Do not expose a network API by default.
3. Keep sensitive operations approval-gated. The daemon should not become a way
   to bypass CLI/gateway safety checks.
4. Use existing `SessionDB` as the source of truth instead of creating a second
   session store.
5. Build toward `session != window/process`: clients are surfaces; sessions are
   durable server-owned records/runtimes.

## Next Slices

1. Add live runtime attachment: daemon-owned `AIAgent` workers keyed by session id.
2. Add `session.send` and event streaming with status states: idle, running,
   tool_wait, blocked, error.
3. Add read-only Mission Control panel consuming `ping` + `session.list`.
4. Add approval-gated controls: stop, fork, resume, attach.
5. Add memory graph retrieval as a separate local service path, not coupled to
   the daemon MVP.
