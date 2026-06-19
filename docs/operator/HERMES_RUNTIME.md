# Hermes Runtime Handoff

Canonical current-state handoff for Hermes on Studio. Update this file whenever
runtime shape, active integrations, blockers, or next steps change in a
meaningful way. New Codex threads should start here before relying on chat
history.

## Current Runtime Shape

- Primary local model: `omlx` `qwen3-30b-a3b-instruct-2507-4bit`
- Telegram/gateway primary: OpenRouter `deepseek/deepseek-v4-flash`
- Telegram/gateway fallback: OpenRouter `deepseek/deepseek-v4-pro`
- Gateway local failover: enabled with 25s no-first-chunk and stale-chunk cutoffs
- Global CLI/default model: local `qwen3-30b-a3b-instruct-2507-4bit`
- Telegram tool exposure: `computer_use` removed; core messaging, memory, web, music, and media tools remain
- Memory: Studio family/karate operational memory migrated and verified

## Active Integrations

- Telegram gateway is the main daily chat surface
- Fantastical MCP is configured but still under reliability scrutiny for calendar reads
- Raindrop integration is configured in Hermes MCP, but auth still needs a valid accepted token flow before it is usable
- Apple Music and Spotify integrations are active in the current Studio setup
- Vapi outbound calling is active, but call quality and confirmation-safe handling still need work

## Blockers

- Raindrop MCP auth is not yet accepted by the service; config reaches the endpoint, but the current token flow returns `401 Unauthorized`
- Fantastical remains a reliability follow-up for live schedule reads in agent-driven turns
- Telegram tool surfaces still need further hardening for cost and context size

## Done

- Telegram MVP backhaul is working
- `computer_use` is no longer exposed to Telegram
- Family/karate memory migrated into Studio Hermes
- Apple Music Telegram playlist create/add works
- Hermes runtime docs and action-item workflow are now anchored in the repo

## Next

1. Finish Raindrop auth so bookmark search/add/tag flows work from Hermes
2. Continue Telegram hardening on tool exposure and prompt/context size
3. Resolve Fantastical reliability so schedule lookups are trustworthy again
4. Keep Linear as the issue tracker and update issue comments whenever runtime state changes

## Active Hermes Links

- [HERMES-9](https://linear.app/agents-n-such/issue/HERMES-9/implement-confirmation-safe-vapi-outbound-calling-for-hermes-telegram)
- [HERMES-10](https://linear.app/agents-n-such/issue/HERMES-10/track-studio-hermes-spotify-and-apple-music-integrations)
- [HERMES-19](https://linear.app/agents-n-such/issue/HERMES-19/evaluate-and-enable-hermes-web-uicontrol-surfaces)
- [HERMES-31](https://linear.app/agents-n-such/issue/HERMES-31/telegram-e2e-harness-final-reply-detection-after-tool-progress)

## Handoff Format

Use this shape in Linear comments, repo notes, and thread summaries:

- Current state
- Blockers
- Next action
- Action items for you
- Links
