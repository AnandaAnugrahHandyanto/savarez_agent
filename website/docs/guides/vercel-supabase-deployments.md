---
title: "Deploy with Vercel and Supabase"
description: "How to wire the Hermes site/dashboard deployment to Vercel with a Supabase backend."
---

# Deploy with Vercel and Supabase

Hermes can use two separate deployment paths:

1. **The docs site** (`website/`) builds as a static Docusaurus site and is published to GitHub Pages.
2. **The Vercel deployment** is triggered by the `Deploy Site` GitHub Actions workflow through `VERCEL_DEPLOY_HOOK`. Vercel owns the build command, output directory, and runtime environment for the connected project.

When you add Supabase, keep the responsibility split clear:

- GitHub Actions only needs the Vercel deploy hook URL when using the deploy-hook path.
- Vercel needs the Supabase environment variables because Vercel runs the production build and any serverless functions.
- Browser-exposed variables must use the `VITE_` prefix and must only contain public Supabase values.
- Service-role credentials must stay server-side. Never expose them through `VITE_*`, `NEXT_PUBLIC_*`, static files, or client code.

## Required GitHub secret

Set this in **GitHub → Settings → Secrets and variables → Actions** for `NousResearch/hermes-agent`:

```bash
VERCEL_DEPLOY_HOOK=https://api.vercel.com/v1/integrations/deploy/...
```

The workflow checks this value explicitly. If it is missing, the Vercel deploy job fails with a clear `VERCEL_DEPLOY_HOOK secret is not configured` error instead of silently posting an empty URL.

## Vercel environment variables

Set these in **Vercel → Project → Settings → Environment Variables**.

Current required public browser variables for the Vite dashboard Supabase client:

```bash
VITE_SUPABASE_URL=https://<project-ref>.supabase.co
VITE_SUPABASE_ANON_KEY=<public-anon-key>
```

Optional server-only variables for future API routes, serverless functions, or backend jobs:

```bash
SUPABASE_SERVICE_ROLE_KEY=<server-only-service-role-key>
SUPABASE_DB_URL=postgresql://...
```

Only add `SUPABASE_SERVICE_ROLE_KEY` when there is server-side code that needs elevated Supabase access. Keep it server-side only. Do not set it as `VITE_SUPABASE_SERVICE_ROLE_KEY`; that would publish it to every browser that loads the app.

## Local dashboard development

Copy the Vite example env file and fill only public values:

```bash
cd web
cp .env.example .env.local
```

The dashboard exposes a small helper at `web/src/lib/supabase.ts`:

```ts
import { getSupabaseClient, requireSupabaseClient } from "@/lib/supabase";

const supabase = getSupabaseClient();
if (supabase) {
  const { data, error } = await supabase.from("example_table").select("*");
}
```

Use `getSupabaseClient()` when Supabase is optional and `requireSupabaseClient()` when the feature cannot run without Supabase configuration.

## Deploy-hook behavior

The GitHub workflow triggers the Vercel deploy hook for:

- published releases,
- qualifying pushes to `main`, and
- manual `workflow_dispatch` runs.

It also skips the GitHub Pages job on release events so release workflows do not fail because the Pages deployment path ran when only the Vercel hook was needed.

## Moving to Vercel-native PR previews later

Deploy hooks trigger production deployments but do not provide Vercel GitHub App PR previews/checks/comments by themselves. For full Vercel-native preview behavior, connect the repository in the Vercel dashboard or add a Vercel CLI workflow with:

```bash
VERCEL_TOKEN=
VERCEL_ORG_ID=
VERCEL_PROJECT_ID=
```

The Supabase variables above still belong in Vercel project environment variables unless a GitHub Action is doing the build directly.
