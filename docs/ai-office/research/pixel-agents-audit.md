# Hermes AI Office — Pixel Agents Repository Audit

Last updated: 2026-05-08 11:32 KST
Status: Stage 1 research artifact. Documentation-only; no code cloned, vendored, installed, or modified.

## Sources inspected

- https://github.com/pablodelucca/pixel-agents
- GitHub API metadata for `pablodelucca/pixel-agents`
- Root README, LICENSE, `package.json`, `webview-ui/package.json`
- Repository tree snippets for `src/`, `server/`, `shared/`, `webview-ui/src/`
- Representative files inspected read-only:
  - `src/transcriptParser.ts`
  - `src/agentManager.ts`
  - `server/src/hookEventHandler.ts`
  - `webview-ui/src/office/engine/officeState.ts`
  - `webview-ui/src/office/types.ts`

## What it is

Pixel Agents is a VS Code extension that turns AI coding-agent sessions into animated pixel-office characters. The repository describes itself as “The game interface where AI agents build real things” and “Pixel office.”

It is highly relevant as a UX reference, especially for:

- one agent/session = one character
- visual status transitions for active, waiting, permission-needed, idle, and tool-use states
- office layout, seats, furniture, sprites, and character animations
- mapping coding-agent terminal/session events into an office metaphor

## License and reuse posture

- Repository license: MIT.
- `package.json` license: MIT.
- LICENSE copyright: Pablo De Lucca.

MIT is generally compatible with reuse, but Hermes should still avoid direct vendoring until:

1. asset licensing is checked separately,
2. attribution requirements are planned,
3. architecture mismatch is reviewed,
4. user explicitly approves code adoption.

## Stack and architecture

Observed stack:

- VS Code extension host TypeScript.
- React webview UI.
- Canvas/pixel-office renderer under `webview-ui/src/office/`.
- Esbuild/Vite/TypeScript tooling.
- Server/hook layer added for agent hooks and event routing.

Important directories:

- `src/`: VS Code extension host integration, terminal/session launch, file watching, transcript parsing, webview bridge.
- `server/`: hook/event provider layer, tests, provider abstractions.
- `shared/`: asset loader/build helpers.
- `webview-ui/src/office/`: pixel office renderer, game loop, office state, layout/furniture/sprites.

## Relevant implementation concepts

### Agent state from transcripts/hooks

`src/transcriptParser.ts` reads agent transcript records and maps tool-use/message events into statuses. It contains tool-specific status formatting and permission heuristics.

Key observed concepts:

- `processTranscriptLine(agentId, line, agents, ...)`
- tool status formatting by tool name
- permission-exempt tools
- active tool IDs/names/statuses
- waiting/permission timers
- subagent/team metadata support in newer version

### Agent lifecycle / launch integration

`src/agentManager.ts` is VS Code-specific. It creates terminals, starts Claude commands, tracks expected JSONL transcript paths under `~/.claude/projects`, and posts webview messages such as `agentCreated`.

This is not directly reusable for Hermes because Hermes has its own CLI/gateway/session/Kanban model.

### Hook server/event routing

`server/src/hookEventHandler.ts` maps external hook events to the correct agent using session IDs and buffers early events. This concept is relevant to Hermes if future office state is event-driven, but the provider implementation is Claude/VS Code oriented.

### Pixel office renderer

`webview-ui/src/office/engine/officeState.ts` and `webview-ui/src/office/types.ts` are the most reusable conceptual pieces:

- `OfficeState` owns characters, seats, layout, walkable tiles, and subagent mappings.
- `Character` tracks visual state, current tool, activity, bubble type, parent/subagent status, team/agent names.
- Status bubbles include permission/waiting concepts.
- Characters pick seats, walk, sit, and animate based on work state.

## Hermes adoption matrix

| Area | Direct reuse? | Adapt conceptually? | Notes |
|---|---:|---:|---|
| Pixel office visual metaphor | Maybe later | Yes | Strong UX inspiration. Keep behind Stage 8. |
| React office components | Maybe later | Yes | Could inspire `/office/pixel`, but current UI must fit Hermes dashboard stack. |
| OfficeState model | Maybe later | Yes | Useful after a Hermes-native `OfficeState` DTO exists. |
| Transcript parser | No | Partially | Hermes sessions/tool events differ from Claude JSONL. |
| VS Code terminal launcher | No | No | Hermes dashboard must not depend on VS Code extension APIs. |
| Claude hooks | No | Partially | Event-routing idea useful, implementation not. |
| Assets/sprites | Unknown | Maybe | Asset license must be checked separately before reuse. |

## Risks

1. VS Code coupling: core lifecycle assumptions are VS Code terminal/webview centric.
2. Claude coupling: transcript paths and tool names assume Claude Code-style JSONL.
3. Asset licensing: MIT code does not automatically mean all art assets are freely reusable; verify each asset source.
4. Product risk: pixel animation can distract from operational truth.
5. Integration risk: Hermes dashboard already embeds `hermes --tui`; do not rebuild chat in React.

## MVP implications for Hermes

- Do not begin with Pixel Agents renderer.
- First create a Hermes-native read-only `OfficeState` model from Kanban/cron/gateway/session state.
- Later, adapt the office-state-to-character mapping from Pixel Agents concepts.
- If code reuse is considered, isolate it to renderer/state modules and preserve attribution.

## Recommendation

Treat `pablodelucca/pixel-agents` as the primary UX and architecture reference for the pixel-office layer, but not as the first implementation base. Hermes should build read-only observability and provenance first, then revisit renderer reuse after Stage 5 architecture review.
