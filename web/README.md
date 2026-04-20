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

## Environment variables

Copy `web/.env.example` to a local `.env.local` if you want to override the defaults.

- `VITE_HERMES_API_BASE_URL` — production API base URL for the Hermes backend
- `VITE_HERMES_AUTH_BASE_URL` — origin that serves the SPA shell and token-injected HTML
- `VITE_HERMES_API_PROXY_URL` — local Vite proxy target for `/api`
- `HERMES_WEB_CORS_ORIGINS` — comma-separated backend allowlist for deployed frontend origins
- `HERMES_WEB_LOGIN_EMAIL` / `HERMES_WEB_LOGIN_PASSWORD` — optional public login gate for the studio UI
- `HERMES_WEB_LOGIN_SECRET` — optional signing secret for persisted login tokens

For local development, you usually do not need to set any of them.

## Build

```bash
npm run build
```

This builds the SPA into `dist/` and syncs the same assets into `../hermes_cli/web_dist/` when the Hermes CLI runs its web build step. The FastAPI server serves that packaged folder at runtime.

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
