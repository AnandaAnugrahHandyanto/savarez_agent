# Project Overview

Hermes Agent is the upstream runtime that Leonidas forks for bounded gateway and planning work.

Use this checkout for Hermes-side implementation details, especially the shared TUI gateway in `tui_gateway/server.py`.

Core repo facts for this fork:

- upstream source: `NousResearch/hermes-agent`
- fork remote: `JoshMcCDev/hermes-agent`
- default upstream branch: `main`
- primary fork patch surface: `tui_gateway/server.py`
- primary contract tests: `tests/test_tui_gateway_server.py`

Keep the fork narrow. Add Leonidas-specific RPCs or envelopes instead of changing generic upstream methods unless the upstream contract needs to stay shared.
