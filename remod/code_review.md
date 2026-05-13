# Code Review: remod/ Documentation

## Overview
6 files documenting an 8-step codebase analysis for forking Hermes Agent into "Jade". The analysis covers plugin architecture, skill format, config system, TUI/theme system, branding strings (95+ references), gateway adapters, and a phased customization roadmap. Content is accurate, well-organized, and actionable.

## Issues

### SUGGESTION: Incorrect file attribution for WhatsApp header
- **File:** `final_summary.md:565`
- **Problem:** Lists `gateway/config.py` as the source for the `"⚕ *Hermes Agent*"` WhatsApp default header. This string actually lives in `hermes_cli/config.py:1260` (inside the `whatsapp` config section). Gateway's own `config.py` models config structure (`PlatformConfig`, `HomeChannel`, etc.) and contains no branding strings.
- **Fix:** Change to `hermes_cli/config.py:1260` — the WhatsApp `# Default (None) uses the built-in "⚕ *Hermes Agent*" header.` comment is in the main config file's WhatsApp section.

### SUGGESTION: Env var rename table has vague location references
- **File:** `final_summary.md:402-422`
- **Problem:** 5 of 17 env var entries say only `"config reference"` for location — `HERMES_TUI_NO_CONFIRM`, `HERMES_TUI_RESUME`, `HERMES_KANBAN_BOARD`, `HERMES_BACKGROUND_NOTIFICATIONS`, `HERMES_HEAPDUMP_ON_START`. This is too vague for someone executing the rename who would need to grep all usage sites.
- **Fix:** Replace `"config reference"` with the specific module where each env var is consumed, e.g.:
  - `HERMES_TUI_NO_CONFIRM` → `appChrome.tsx` (opt-out flag)
  - `HERMES_TUI_RESUME` → `sessionPicker.tsx` (auto-resume override)
  - `HERMES_KANBAN_BOARD` → `plugins/kanban/worker.py` (pinned in subagent env)
  - `HERMES_BACKGROUND_NOTIFICATIONS` → `gateway/display_config.py` or `display.platforms` config section
  - `HERMES_HEAPDUMP_ON_START` → `entry.tsx:65` (already listed in TUI section, keep that reference)

### SUGGESTION: Package rename scope is understated
- **File:** `final_summary.md:537` (Phase 5: Source Fork)
- **Problem:** The section lists `hermes_cli/ → jade_cli/` and 7 other module renames without conveying the impact. Renaming the `hermes_cli` package alone would break `import` statements across ~80+ Python files in `hermes_cli/`, `gateway/`, `tools/`, `agent/`, `plugins/`, `tests/`, `cron/`, `environments/`, and `tui_gateway/`.
- **Fix:** Add a note like: "Package renames affect 80+ files — each renamed package requires updating all imports. Consider an automated migration pass (global sed) followed by manual review for name conflicts with third-party packages."

## Recommendation
**APPROVE WITH SUGGESTIONS** — Content is solid; the 3 issues above are minor documentation clarifications that would improve actionability.
