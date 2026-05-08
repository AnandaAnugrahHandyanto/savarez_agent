# Hermes AI Office — Pixel Agents Codex Fork Audit

Last updated: 2026-05-08 11:32 KST
Status: Stage 1 research artifact. Documentation-only; no code cloned, vendored, installed, or modified.

## Sources inspected

- https://github.com/MichaelMa907/pixel-agents-codex
- GitHub API metadata for `MichaelMa907/pixel-agents-codex`
- Root README, LICENSE, `package.json`, `webview-ui/package.json`
- Repository tree snippets for `src/` and `webview-ui/src/`
- Representative files inspected read-only:
  - `src/transcriptParser.ts`
  - `src/agentManager.ts`
  - `webview-ui/src/office/engine/officeState.ts`

## What it is

`pixel-agents-codex` appears to be a fork of the VS Code Pixel Agents project with some Codex-oriented positioning, but repository metadata and files inspected still largely resemble the original Claude-oriented Pixel Agents structure.

Observed facts:

- Description: “Pixel office.”
- License: MIT.
- Stars: 0 at inspection time.
- Forks: 1 at inspection time.
- Version observed in `package.json`: `1.0.2`.
- `package.json` includes `@anthropic-ai/sdk` among dev dependencies.
- Source still uses VS Code extension architecture and Claude-style project/transcript paths in inspected files.

## License and asset note

- Code license: MIT.
- README search snippet noted that some tileset/furniture assets may not be freely included because of their license and may require purchase/import pipeline.

This makes the asset question especially important. Even if code is MIT, visual assets may be unavailable or separately licensed.

## Architecture relevance

The Codex fork does not currently appear to solve the main Hermes integration problem. It remains closer to a VS Code extension and transcript-parser model than to a Hermes-native dashboard.

Potentially useful:

- It may reveal minimal changes needed to adapt Pixel Agents from Claude-specific messaging to another agent provider.
- Its reduced/older codebase may be easier to read than the original.

Not useful for MVP:

- Does not provide a Hermes adapter.
- Does not remove VS Code coupling.
- Does not solve Kanban/cron/gateway provenance.

## Hermes adoption matrix

| Area | Direct reuse? | Adapt conceptually? | Notes |
|---|---:|---:|---|
| Codex adaptation | Unknown | Maybe | Needs deeper audit only if Codex-specific changes are real. |
| Renderer | Maybe later | Yes | Similar to original Pixel Agents. |
| VS Code extension host | No | No | Same mismatch. |
| Asset pipeline warnings | No | Yes | Reinforces need for asset license audit. |

## Risks

1. Low signal: small fork with limited activity and no stars at inspection time.
2. Possible stale fork: may lag original Pixel Agents architecture.
3. Asset licensing complexity: direct visual reuse may require paid/external assets.
4. Still not Hermes-native.

## MVP implications for Hermes

- Do not prioritize this fork over original Pixel Agents or standalone fork.
- Keep as a secondary reference if later adapting Codex/Hermes session activity into pixel-office events.
- Treat asset licensing as a formal Stage 5/8 review item.

## Recommendation

Use this only as a secondary reference. Primary references should be `pablodelucca/pixel-agents` for UX/renderer concepts and `rolandal/pixel-agents-standalone` for browser separation.
