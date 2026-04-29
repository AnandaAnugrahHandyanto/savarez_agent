# Rule: web-dashboard

Paths: `web/`, `hermes_cli/web_server.py`.

DO NOT:
- Never commit `web/dist/`.
- Never edit `web/package-lock.json` by hand.

Architecture Notes: backend `:9119`, frontend `:5173`; dashboard chat embeds the real TUI.

Thresholds: UI changes require `cd web && npm run build`.

Key Files: `hermes_cli/web_server.py`, `web/src/`, `web/package.json`.
