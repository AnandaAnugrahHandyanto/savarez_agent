# Hermes AI Office — Pixel Agents Standalone Fork Audit

Last updated: 2026-05-08 11:32 KST
Status: Stage 1 research artifact. Documentation-only; no code cloned, vendored, installed, or modified.

## Sources inspected

- https://github.com/rolandal/pixel-agents-standalone
- GitHub API metadata for `rolandal/pixel-agents-standalone`
- Root README, LICENSE, `package.json`, `webview-ui/package.json`
- Repository tree snippets for `server/` and `webview-ui/src/`
- Representative files inspected read-only:
  - `server/index.ts`
  - `server/parser.ts`
  - `server/watcher.ts`
  - `webview-ui/src/wsApi.ts`
  - `webview-ui/src/office/engine/officeState.ts`

## What it is

`pixel-agents-standalone` is a standalone browser app fork of Pixel Agents. Its README states that it visualizes Claude Code sessions as pixel-art characters in a virtual office and removes the VS Code requirement.

This fork is highly relevant to Hermes because Hermes already has a browser dashboard. It shows how the original VS Code webview model can be separated into:

- a local HTTP/WebSocket server,
- a browser UI,
- file/session watchers,
- persistent layout/seating state.

## License and reuse posture

- Repository license: MIT.
- LICENSE credits both Pablo De Lucca and Roland Ligtenberg.
- README says it is based on Pixel Agents by Pablo De Lucca under MIT.

MIT makes it a plausible implementation reference, but direct reuse still requires explicit approval and attribution planning.

## Stack and architecture

Observed stack:

- Node/TypeScript server.
- Express HTTP server.
- `ws` WebSocket server.
- `chokidar`/filesystem watcher style dependencies.
- React/Vite web UI.
- Pixel office renderer carried over from original Pixel Agents.

Important observed behavior:

- Default port from source: `PORT || 3456`.
- Server keeps `agents = new Map<string, TrackedAgent>()` and `clients = new Set<WebSocket>()`.
- Persistence under `~/.pixel-agents` for layout and agent seats.
- WebSocket broadcasts messages to browser clients.
- Watches `~/.claude/projects` for Claude JSONL sessions.

## Relevant implementation concepts for Hermes

### Browser/server separation

The standalone fork proves that Pixel Agents-style UI does not require VS Code. For Hermes, this supports a dashboard-native design:

- Hermes web server exposes read-only office APIs.
- React dashboard consumes those APIs.
- Optional SSE/WebSocket updates can follow later.

### WebSocket message model

`webview-ui/src/wsApi.ts` replaces VS Code `postMessage` with a browser WebSocket bridge. Hermes could use existing dashboard HTTP/SSE/WebSocket conventions instead of this exact bridge.

### Watcher/parser pattern

`server/watcher.ts` and `server/parser.ts` are Claude-specific, but they demonstrate useful state transitions:

- active session discovered
- tool start
- tool done
- waiting timer
- permission-needed timer
- idle timeout

Hermes should map these from its own sources:

- Kanban task status/runs/events,
- current session/tool-call events if exposed,
- cron job state,
- gateway pending approvals/clarifications.

## Hermes adoption matrix

| Area | Direct reuse? | Adapt conceptually? | Notes |
|---|---:|---:|---|
| Standalone architecture | No | Yes | Hermes already has dashboard server; use as reference only. |
| Express/WebSocket server | No | Yes | Avoid adding parallel Node server. Use Hermes dashboard backend. |
| React office UI | Maybe later | Yes | Candidate for Stage 8 pixel renderer study. |
| Claude watcher/parser | No | Partially | Replace with Hermes adapters. |
| Layout/seat persistence | Maybe later | Yes | Could be profile-local config after design. |

## Risks

1. Parallel-server trap: do not add a second standalone server beside Hermes dashboard.
2. Claude-path assumption: watcher reads `~/.claude/projects`, irrelevant to Hermes source of truth.
3. Data mismatch: Hermes work may be Kanban/cron/gateway-originated, not always a terminal JSONL session.
4. Asset licensing remains separate.

## MVP implications for Hermes

- Strong support for browser-dashboard feasibility.
- Use Hermes dashboard server, not Express.
- Create normalized office-state API first.
- If live updates are necessary, add SSE/WebSocket after the read-only API is stable.

## Recommendation

Use `pixel-agents-standalone` as the strongest architecture reference for making a Pixel Agents-style UI run outside VS Code. Do not copy the server. Instead, adapt the browser/server separation pattern into Hermes' existing dashboard architecture.
