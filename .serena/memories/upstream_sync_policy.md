# Upstream Sync Policy

Keep the Hermes fork close to `NousResearch/hermes-agent@main`.

Preferred branch flow:

- `origin` points at the Leonidas-owned fork
- `upstream` points at `NousResearch/hermes-agent`
- rebase or replay fork changes onto `upstream/main`
- keep Leonidas-specific patches small and namespaced

Conflict policy:

- prefer upstream behavior when it does not affect Leonidas contract guarantees
- preserve Leonidas-specific gateway methods and versioned envelopes when conflicts touch the fork patch surface
- avoid broad drift into the TUI, desktop, or dashboard clients unless a protocol change truly needs it

Treat `tui_gateway/server.py` and its contract tests as the first place to look when evaluating fork sync impact.
