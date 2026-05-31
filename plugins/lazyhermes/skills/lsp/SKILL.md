---
name: lsp
description: Use Hermes' native LSP diagnostics and symbols instead of launching a separate Codex LSP service.
---

# LazyHermes LSP

Use Hermes' existing LSP support for code intelligence. Prefer the repo's
native diagnostics, symbol lookup, and file operation tools before adding
new parsing scripts.

For a LazyHermes retrofit, this skill means:

1. Reuse `agent/lsp` and Hermes file operations.
2. Run targeted diagnostics for files you change when the project supports it.
3. Treat LSP findings as evidence to combine with tests, not as a replacement
   for behavioral verification.
