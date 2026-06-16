---
title: "Stripe Projects — Provision SaaS services + sync creds via Stripe Projects"
sidebar_label: "Stripe Projects"
description: "Provision SaaS services + sync creds via Stripe Projects"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Stripe Projects

Provision SaaS services + sync creds via Stripe Projects.

## Skill metadata

| | |
|---|---|
| Source | Optional — install with `hermes skills install official/payments/stripe-projects` |
| Path | `optional-skills/payments/stripe-projects` |
| Version | `0.1.0` |
| Author | Teknium (teknium1), Hermes Agent |
| License | MIT |
| Platforms | linux, macos |
| Tags | `Payments`, `Stripe`, `Projects`, `Provisioning`, `Infrastructure` |
| Related skills | [`stripe-link-cli`](/docs/user-guide/skills/optional/payments/payments-stripe-link-cli), [`mpp-agent`](/docs/user-guide/skills/optional/payments/payments-mpp-agent) |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Stripe Projects Skill

Wraps the [Stripe Projects](https://projects.dev) CLI plugin so Hermes can provision and manage third-party services such as databases, hosting, auth, AI, analytics, messaging, and observability from the terminal.

Stripe Projects can create or connect provider accounts, provision resources, sync credentials into local environment files, manage named environments, rotate keys, upgrade plans, and centralize billing through Stripe.

Gated `[linux, macos]` while the broader payments cluster matures on Windows. The Stripe CLI itself is cross-platform; this gate is a posture for the cluster, not a hard limit.

## When to Use

Trigger phrases:

- "set up &lt;provider>", "provision &lt;Neon|Supabase|Vercel|PostHog|...>", "create a database"
- "give me a &lt;Postgres|Redis|Twilio number|LLM API key|...> for this project"
- "manage my stack credentials", "rotate this key", "upgrade my plan"
- "what providers can I add?", "browse the catalog", "show project status"
- "set up development/staging/production environment variables"

Use Stripe Projects when the user asks to provision, connect, or manage a cloud service. Do not tell the user to sign up manually for a supported provider until you have checked the Projects catalog.

If the user already has the service set up manually and only wants application code to consume existing credentials, this skill is not the right entry point.

## Prerequisites

- Stripe CLI installed. Verify with `stripe --version`. If missing, use Homebrew on macOS or the platform-specific install guide at https://docs.stripe.com/stripe-cli/install.
- Stripe Projects plugin installed with `stripe plugin install projects`.
- A Stripe account. The CLI may open a browser for `stripe login`, `stripe projects init`, `stripe projects link`, or provider authentication.

## Install

macOS:

```
brew install stripe/stripe-cli/stripe
stripe plugin install projects
```

Linux: follow the platform-specific install at https://docs.stripe.com/stripe-cli/install, then:

```
stripe plugin install projects
```

## How to Run

Run all commands through the `terminal` tool from inside the user's project directory.

The CLI manages `.projects/` and local environment output files such as `.env`, `.env.dev`, or `.env.production`. Do not hand-edit `.projects/` or generated credential files. Never print environment variable values; show names only.

Prefer `--json` for structured commands when you need to parse output. Do not use `--json` with `stripe projects init`.

## Procedure

### 1. Verify the CLI and plugin

```
stripe --version
stripe plugin install projects
```

If the plugin is already installed, the install command is safe to report as already satisfied.

### 2. Check whether the project is initialized

```
cd <project-root>
stripe projects status --json
```

If the command reports that no project exists, initialize one:

```
stripe projects init
```

If the CLI opens a browser for authentication, stop and tell the user to complete sign-in or provider authorization before continuing.

`stripe projects init` creates `.projects/state.json`, `.projects/state.local.json`, and ignore rules for credential files. The encrypted credential cache is written under `.projects/vault/` after provisioning or `env --pull`.

### 3. Discover available providers and services

For a specific request, search first:

```
stripe projects search <query> --json
```

For a vague request or browsing:

```
stripe projects catalog --json
stripe projects catalog <provider> --json
stripe projects catalog <category> --json
```

Copy the exact `<provider>/<service>` slug from catalog output. Never guess provider or service slugs.

### 4. Add a service

```
stripe projects add <provider>/<service>
```

Examples:

- `stripe projects add neon/postgres`
- `stripe projects add supabase/project`
- `stripe projects add vercel/project`

Use `--name <resource-name>` when the project needs a stable local resource name:

```
stripe projects add neon/postgres --name app-db
```

The CLI provisions the resource in the user's provider account, generates credentials, stores them in the vault, writes them to the active environment's output file, and records the resource in project state. The user may need to confirm provider authorization, terms, tier selection, or pricing prompts.

### 5. Verify status and credentials

```
stripe projects status
stripe projects env
```

`status` shows the project, connected providers, provisioned resources, tiers, health, and active environment. `env` lists environment variable names with values redacted.

Run `env --pull` when setting up a new checkout, after a teammate changes resources, after switching environments, or when a local output file needs to be restored:

```
stripe projects env --pull
```

`env --pull` runs automatically after provisioning, rotating credentials, or upgrading a resource.

### 6. Manage named environments

Use project environments for separate local, staging, and production credential sets.

```
stripe projects env list
stripe projects env show
stripe projects env create development --output .env.dev
stripe projects env use development
stripe projects env use default
```

After switching environments, `stripe projects add` provisions into the active environment and `stripe projects env --pull` writes that environment's credentials to its configured output file.

Manage which existing resources belong to the active environment:

```
stripe projects env add <resource_name>
stripe projects env remove <resource_name>
```

These commands only change environment membership. They do not provision or deprovision provider resources.

### 7. Manage / upgrade / remove

```
stripe projects upgrade <provider>/<service>
stripe projects upgrade <resource_name>
stripe projects rotate <provider>/<service>
stripe projects rotate <resource_name>
stripe projects remove <provider>/<service>
stripe projects remove <resource_name>
stripe projects open <provider>
```

Use `stripe projects billing show`, `stripe projects billing add`, and `stripe projects spend` for payment method and spend management.

## Pitfalls

- **`.env` writes are real writes.** The CLI writes credentials to the active environment's output file. Check that `.env` and `.env.*` are ignored before pulling credentials.
- **Do not hand-edit CLI-managed state.** `.projects/state.json` and `.projects/state.local.json` are project state. `.projects/vault/` and `.env*` files contain local credential material. Use CLI commands instead of editing them directly.
- **Commit project state deliberately.** Stripe's docs expect `.projects/state.json` and `.projects/state.local.json` to be shared with teammates, while `.projects/vault/`, `.projects/cache/`, `.env`, and `.env.*` stay ignored.
- **Billing happens on Stripe's side.** Tier prompts during `add` or `upgrade` can create real charges. Surface pricing and confirmation prompts to the user before accepting them.
- **Provider availability changes.** The catalog grows. If a provider or service is absent, report that and suggest browsing the catalog instead of fabricating a command.
- **Environment variable values are sensitive.** `stripe projects env` redacts values. Do not reveal values from `.env`, provider dashboards, logs, or shell output.
- **Removing membership is not deprovisioning.** `stripe projects env remove <resource>` only removes a resource from the active environment. Use `stripe projects remove <resource>` to deprovision.
- **Production hosts are separate.** `stripe projects env --pull` writes local files only. Users still need to add credentials to Vercel, Render, Fly.io, or other production host environment settings.

## Verification

```
stripe projects status
stripe projects env
```

Exit code 0 inside an initialized project means the plugin is healthy. Confirm that expected resource names and environment variable names appear, but do not display credential values.
