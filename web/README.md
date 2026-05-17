# Hermes Agent — Web UI

Browser-based dashboard for managing Hermes Agent configuration, API keys, and monitoring active sessions.

## Stack

- **Vite** + **React 19** + **TypeScript**
- **Tailwind CSS v4** with custom dark theme
- **shadcn/ui**-style components (hand-rolled, no CLI dependency)

## Development

```bash
# Start the backend API server
cd ../
python -m hermes_cli.main web --no-open

# In another terminal, start the Vite dev server (with HMR + API proxy)
cd web/
npm run dev
```

The Vite dev server proxies `/api` requests to `http://127.0.0.1:9119` (the FastAPI backend).

## Build

```bash
npm run build
```

This outputs to `../hermes_cli/web_dist/`, which the FastAPI server serves as a static SPA. The built assets are included in the Python package via `pyproject.toml` package-data.

## Profile Runtime UI Notes

The Profiles page surfaces non-secret runtime metadata for each Hermes profile.
Local Magic Moment operating policy for Shiori/Ritz/default belongs in the
Phantom Factory SSOT, not in this UI package README.

Current data flow:

- Backend profile discovery lives in `hermes_cli/profiles.py`.
- The dashboard REST payload is serialized by `hermes_cli/web_server.py`
  through `GET /api/profiles`.
- Frontend types live in `web/src/lib/api.ts`.
- The UI is rendered by `web/src/pages/ProfilesPage.tsx`.

`/api/profiles` currently returns non-secret runtime metadata:

- profile name and `config.yaml` path
- gateway running state and PID
- main `model`, `provider`, and `agent.reasoning_effort`
- subagent delegation model/provider/reasoning settings
- auth method summary: `oauth`, `api_key`, `mixed`, `external_process`, or
  `aws_sdk`
- auth source labels such as `profile auth.json`, `global auth.json`, or
  `.env:ANTHROPIC_API_KEY`

Security rule: never return or render token values, key previews, refresh
tokens, full env values, or raw `auth.json` entries from profile runtime UI.
Only expose method and source labels. Profile credential lookup should mirror
Hermes runtime semantics: profile `auth.json` wins for a provider, and global
`~/.hermes/auth.json` is only a read-only fallback when the profile has no
entries for that provider.

When adding another runtime field, update all four touchpoints above and verify
with:

```bash
python -m py_compile hermes_cli/profiles.py hermes_cli/web_server.py
cd web && npm run build
```

If an agent sandbox cannot empty `hermes_cli/web_dist/`, build to a temporary
directory and copy the generated `index.html` plus new assets into
`hermes_cli/web_dist/` without deleting existing assets:

```bash
cd web
npm run build -- --outDir /private/tmp/hermes-web-dist-check --emptyOutDir
cp /private/tmp/hermes-web-dist-check/index.html ../hermes_cli/web_dist/index.html
cp /private/tmp/hermes-web-dist-check/assets/* ../hermes_cli/web_dist/assets/
```

The local Mac mini dashboard is managed by the `ai.hermes.dashboard`
LaunchAgent and serves prebuilt assets with `--skip-build`. After changing
served assets or backend code, restart only the dashboard service:

```bash
launchctl kickstart -k gui/501/ai.hermes.dashboard
```

Do not restart Hermes profile gateways for UI-only changes.

## Structure

```
src/
├── components/ui/   # Reusable UI primitives (Card, Badge, Button, Input, etc.)
├── lib/
│   ├── api.ts       # API client — typed fetch wrappers for all backend endpoints
│   └── utils.ts     # cn() helper for Tailwind class merging
├── pages/
│   ├── StatusPage   # Agent status, active/recent sessions
│   ├── ConfigPage   # Dynamic config editor (reads schema from backend)
│   └── EnvPage      # API key management with save/clear
├── App.tsx          # Main layout and navigation
├── main.tsx         # React entry point
└── index.css        # Tailwind imports and theme variables
```
