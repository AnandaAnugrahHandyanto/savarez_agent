# Infisical Credential Foundation Design

Date: 2026-05-28
Status: approved design direction, pending written-spec review

## Goal

Implement Hermes issue [#22791](https://github.com/NousResearch/hermes-agent/issues/22791) as a native Infisical external-vault backend, expanded into a complete credential foundation for a personal Hermes deployment.

Hermes must be able to use a local self-hosted Infisical instance on this device, secured for remote access by Tailscale, resolve secrets from multiple Infisical projects, store Infisical bootstrap credentials in the operating system credential store, and migrate existing plaintext `~/.hermes/.env` secrets into Infisical.

The design must support future SimpleX, Gmail, Calendar, inbox-rules, and model-router work without forcing each feature to know Infisical-specific details.

## Scope

In scope:

- Native `infisical` secret backend for Hermes.
- Self-hosted Infisical on the current device as the primary setup target.
- Tailscale-secured access to the local Infisical service for any same-user remote device access.
- A generic Infisical host URL so the backend is not hardcoded to one deployment shape.
- Universal Auth for machine identity.
- Cross-platform OS credential stores for Infisical bootstrap credentials:
  - macOS Keychain.
  - Windows Credential Manager.
  - Linux Secret Service/libsecret.
- Multiple Infisical projects addressed by aliases such as `mail`, `chat`, `models`, and `gateway`.
- Guided setup flow for host, environment, project aliases, and machine identity.
- Full `.env` migration into Infisical, including write, read-back verification, timestamped backup, and plaintext cleanup.
- Runtime secret resolution that preserves existing Hermes code paths as much as practical.
- Redaction and logging rules that prevent secret leakage.
- Tests for backend resolution, bootstrap storage, migration, and error handling.

Out of scope for this credential-foundation goal:

- Building or forking Infisical itself.
- Replacing Infisical with OS credential stores as the main vault.
- Full password/passphrase encrypted local keystore from issue [#3629](https://github.com/NousResearch/hermes-agent/issues/3629).
- SimpleX calling, Gmail assistant behavior, inbox rules, or model-router optimization.
- Public internet exposure of the local Infisical server.
- Tailscale Funnel exposure for Infisical.
- Optimized setup flows for Infisical Cloud or remote self-hosted Infisical.

## Research Findings

There is already an open Hermes feature issue for the exact native-vault direction:

- [#22791: Add Infisical as an External Vault backend](https://github.com/NousResearch/hermes-agent/issues/22791)

That issue proposes an `infisical` backend with Universal Auth, multiple projects, aliases, token refresh, integration tests against an Infisical dev image, documentation, and redaction checks.

Adjacent Hermes work exists but should not replace this design:

- [#3629: Encrypted Keystore + OS Credential Store + .env Migration](https://github.com/NousResearch/hermes-agent/issues/3629) covers a broader encrypted local keystore and password/passphrase model.
- [#1583: Mitigate plaintext secret .env exfiltration risk by adopting Varlock](https://github.com/NousResearch/hermes-agent/issues/1583) discusses launcher-based secret mitigation, including Infisical through Varlock.

Infisical supports the needed deployment and auth model:

- [Infisical deployment models](https://infisical.com/docs/documentation/getting-started/concepts/deployment-models) cover self-hosted and cloud options.
- [Infisical Universal Auth](https://infisical.com/docs/documentation/platform/identities/universal-auth) provides machine-identity authentication.
- [Infisical Agent](https://infisical.com/docs/integrations/platforms/infisical-agent) exists, but the chosen Hermes direction is native resolver support.
- [Agent Vault](https://infisical.com/blog/agent-vault-the-open-source-credential-proxy-and-vault-for-agents) and Infisical credential-brokering work are relevant future directions, but not the first implementation target.

Tailscale supports the desired private-network posture:

- [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve) routes traffic from devices on the private tailnet to a service running locally on this device.
- [Tailscale access controls](https://tailscale.com/docs/features/access-control) provide policy-based least-privilege access between tailnet devices.
- [MagicDNS](https://tailscale.com/docs/features/magicdns/) and [Tailscale HTTPS certificates](https://tailscale.com/docs/how-to/set-up-https-certificates) can provide stable tailnet names and browser-friendly HTTPS when enabled.

Local repo context:

- Hermes already has `~/.hermes/config.yaml` for non-secret settings and `~/.hermes/.env` for API keys and tokens.
- Existing config contains `smart_model_routing`, `auxiliary`, provider, gateway, and skill settings that should eventually consume resolved secrets.
- The current checkout does not appear to have a general `agent/secrets` backend package or existing Infisical implementation.
- The active worktree had unrelated local edits before this design; this spec must not depend on reverting them.

## Recommended Approach

Use Infisical as the source of truth for Hermes secrets. Use OS credential stores only as the bootstrap trust root that protects the Infisical machine identity.

```text
Hermes config.yaml
  -> backend type, host, environment, and project aliases

OS credential store
  -> Infisical Universal Auth client ID and client secret only

Infisical
  -> Gmail, SimpleX, model provider, gateway, skill, and assistant secrets

~/.hermes/.env
  -> migration source and emergency override path only
```

This keeps the security boundary simple. The OS credential store answers one question: how does Hermes authenticate to Infisical? Infisical answers the broader question: where do Hermes secrets live?

## Architecture

Suggested new packages and modules:

```text
agent/secrets/
  __init__.py
  resolver.py
  references.py
  redaction.py
  errors.py
  backends/
    __init__.py
    base.py
    env.py
    infisical.py
  bootstrap/
    __init__.py
    base.py
    keyring_store.py
    memory_store.py

hermes_cli/
  secrets_commands.py
  secrets_setup.py
  secrets_migration.py
```

`agent/secrets/resolver.py`

- Owns runtime resolution order.
- Provides a narrow interface such as `resolve_secret(name)` and `resolve_secret_ref(ref)`.
- Keeps providers, tools, skills, and gateway adapters from importing Infisical-specific code.

`agent/secrets/references.py`

- Parses secret references.
- Supports explicit references such as `models:OPENAI_API_KEY`.
- Supports unqualified names such as `OPENAI_API_KEY` through configured defaults and backward-compatible fallback.

`agent/secrets/backends/infisical.py`

- Implements the Infisical backend.
- Authenticates with Universal Auth.
- Resolves project aliases.
- Reads and writes secrets.
- Performs token refresh.
- Produces redacted structured errors.

`agent/secrets/bootstrap/keyring_store.py`

- Wraps cross-platform credential storage.
- Uses macOS Keychain, Windows Credential Manager, or Linux Secret Service/libsecret through a single interface.
- Stores only Infisical bootstrap identity material.
- Provides a fake or in-memory adapter for tests.

`hermes_cli/secrets_setup.py`

- Implements the guided setup flow.
- Handles local self-host defaults.
- Stores bootstrap credentials in the OS credential store.
- Validates Infisical connectivity and project aliases.

`hermes_cli/secrets_migration.py`

- Scans `~/.hermes/.env`.
- Suggests alias mappings.
- Writes selected secrets to Infisical.
- Verifies read-back.
- Backs up `.env`.
- Removes active plaintext secret values after successful verification.

## Local Self-Hosted Infisical

This device should be the primary deployment target for the first personal Hermes setup, and Tailscale should be the only supported remote-access path.

Hermes should not vendor Infisical or fork its deployment stack. Instead, it should provide a local-first setup path that assumes Infisical is running on the same machine, validates it before migration, and verifies that any remote access is limited to the user's tailnet.

Default local posture:

- Host URL defaults to a local address such as `http://127.0.0.1:<port>` when the user chooses local self-hosted Infisical.
- Infisical should bind to localhost by default for Hermes on the same device.
- If access from another user-owned device is needed, expose Infisical through Tailscale Serve or an equivalent tailnet-only reverse proxy.
- Tailscale Funnel must not be used for Infisical.
- Tailnet policy should restrict Infisical access to explicitly approved user devices or device tags.
- MagicDNS and Tailscale HTTPS should be preferred when the user wants a stable browser URL for Infisical from other tailnet devices.
- Public internet exposure is out of scope.
- The setup wizard should check the local health endpoint or equivalent API reachability before accepting the host.
- The setup wizard should optionally check the Tailscale route or Serve URL when the user enables tailnet access.
- The documentation should point to the official Infisical self-hosting docs instead of copying a stale compose file into Hermes.

Local setup behavior:

- `hermes secrets setup infisical` must offer a local-hosted profile.
- If Docker or another supported local runtime is present, Hermes should print the exact next command or docs link needed to start Infisical.
- The local-hosted profile must include a Tailscale-secured option for users who need to reach Infisical from a phone, laptop, or other tailnet device.
- Hermes should not silently install or start privileged services.
- Generated local Infisical passwords, database credentials, and encryption keys are Infisical deployment secrets, not Hermes runtime secrets. The first implementation should document where those live and avoid copying them into Hermes `.env`.

For this goal, success means Hermes can connect to and use a self-hosted Infisical instance running on this device, with setup docs and preflight checks that make the local and Tailscale-secured paths reproducible. Fully automating Infisical installation is out of scope for the first implementation because it would require Hermes to own third-party service lifecycle, database lifecycle, and upgrade behavior.

## Config Shape

Add a `secrets` section to `config.yaml`.

```yaml
secrets:
  active_backend: infisical
  backends:
    infisical:
      type: infisical
      host: http://127.0.0.1:8080
      remote_access:
        mode: tailscale
        tailnet_url: https://hermes-infisical.example-tailnet.ts.net
        public_funnel_allowed: false
      environment: prod
      auth:
        method: universal_auth
        bootstrap_store: os_keyring
        identity_name: hermes-agent-default
      projects:
        mail:
          project_id: 00000000-0000-0000-0000-000000000001
          path: /hermes/mail
        chat:
          project_id: 00000000-0000-0000-0000-000000000002
          path: /hermes/chat
        models:
          project_id: 00000000-0000-0000-0000-000000000003
          path: /hermes/models
        gateway:
          project_id: 00000000-0000-0000-0000-000000000004
          path: /hermes/gateway
```

The config contains host, optional Tailscale remote-access metadata, environment, alias metadata, and the OS credential-store identity name. It must not contain Universal Auth client secrets or resolved application secrets.

Secret references:

```text
mail:GMAIL_CLIENT_SECRET
mail:GOOGLE_REFRESH_TOKEN
chat:SIMPLEX_PRIVATE_KEY
gateway:TELEGRAM_BOT_TOKEN
models:OPENAI_API_KEY
models:ANTHROPIC_API_KEY
```

Resolution precedence:

1. Explicit runtime environment variable, for emergency override and CI.
2. Active secret backend.
3. Legacy `~/.hermes/.env`, only while plaintext secrets still exist.

Unqualified secret names can resolve through configured default mappings. Explicit `alias:KEY` references must never search unrelated projects.

## Setup Flow

Primary command:

```bash
hermes secrets setup infisical
```

Expected flow:

1. Ask whether Infisical is local self-hosted on this device or an advanced custom host URL. The recommended path is local self-hosted on this device.
2. For local self-hosted mode, default the host to a local address and validate that Infisical is reachable on this device.
3. Ask whether to configure Tailscale-secured access for other user-owned devices.
4. If Tailscale access is enabled, validate that Tailscale is installed, the device is joined to the tailnet, and the configured Serve or reverse-proxy URL reaches the local Infisical service.
5. Refuse setup if the URL appears to use public Tailscale Funnel or another public exposure path.
6. Prompt for Infisical environment.
7. Prompt for Hermes identity name.
8. Prompt for Universal Auth client ID and client secret.
9. Store the Universal Auth bootstrap credentials in the OS credential store.
10. Prompt for project aliases.
11. Validate each alias against Infisical.
12. Write and read a temporary verification secret per project alias, then delete it.
13. Offer `.env` migration.
14. Save `config.yaml` with the backend enabled only after validation succeeds.

Credential-store behavior:

- macOS uses Keychain.
- Windows uses Credential Manager.
- Linux uses Secret Service/libsecret.
- Headless Linux without a usable Secret Service should fail clearly in interactive setup and explain the supported alternatives.
- Tests and CI may use an in-memory or fake bootstrap store.
- Non-interactive bootstrap through env vars remains available for automation, but setup should guide production users to OS credential storage.

## Migration Flow

Migration is part of this goal.

Primary command shape:

```bash
hermes secrets migrate infisical
```

The setup wizard may call the same migration code after backend validation.

Expected flow:

1. Load `~/.hermes/.env`.
2. Identify secret-looking keys using the existing optional env metadata and Hermes provider/tool categories.
3. Suggest project mappings:
   - Gmail, Google, and OAuth keys -> `mail`.
   - SimpleX and chat platform secrets -> `chat`.
   - Gateway platform tokens -> `gateway`.
   - Model provider API keys -> `models`.
   - Unknown secrets -> ask for an alias.
4. Show a dry-run summary with key names, destination aliases, and whether the destination already has a value.
5. Require explicit confirmation before writing.
6. Write selected secrets to Infisical.
7. Read the written values back and compare.
8. Create a timestamped backup of `~/.hermes/.env`.
9. Remove plaintext values for successfully migrated secrets from the active `.env`.
10. Preserve comments and non-secret settings where practical.
11. Report any values that were skipped, failed, or still require manual cleanup.

Cleanup rule:

No plaintext cleanup happens until all selected writes and read-back verification succeed. If migration partially writes to Infisical and then fails, Hermes reports the written keys and leaves the active `.env` untouched.

## Runtime Behavior

Hermes should initialize the active secrets resolver early in CLI and gateway startup.

Provider setup, tool availability checks, gateway adapters, and skills should eventually use the resolver rather than direct `os.getenv()` calls for secrets. To reduce blast radius, the first implementation can bridge resolved values into process environment for legacy call sites while adding direct resolver usage at high-value boundaries.

Resolution examples:

```text
resolve_secret("OPENAI_API_KEY")
  -> runtime env override
  -> configured default alias, usually models:OPENAI_API_KEY
  -> legacy .env while present

resolve_secret("models:OPENAI_API_KEY")
  -> Infisical project alias models
  -> no search in mail, chat, or gateway

resolve_secret("mail:GMAIL_CLIENT_SECRET")
  -> Infisical project alias mail
```

Universal Auth behavior:

- Load client ID and client secret from the OS credential store.
- Exchange them for an Infisical access token.
- Cache access tokens in memory by default.
- Refresh on expiry.
- Retry once for refreshable auth failures.
- Never log tokens, client secrets, or secret values.

## Error Handling

Errors should be explicit and redacted.

Required cases:

- Missing OS credential entry: tell the user to rerun `hermes secrets setup infisical`.
- Local Infisical not reachable: report the configured local host and suggest checking the local service.
- Tailscale access not reachable: report the configured tailnet URL and suggest checking Tailscale status, Serve or reverse-proxy state, and tailnet policy.
- Public exposure detected: fail setup unless the user changes to a local or tailnet-only URL.
- Unknown project alias: fail fast and name the alias.
- Permission denied: report the alias, project, and path where possible without exposing secret values.
- Secret not found: report the reference name, not the value.
- Infisical unavailable: do not silently fall back to stale plaintext unless an explicit emergency fallback is configured.
- Token expired: refresh once, then fail with a setup/auth message.
- Migration interrupted: leave active `.env` untouched unless backup and cleanup had already completed successfully.
- Linux Secret Service unavailable: fail setup with a platform-specific explanation rather than writing plaintext bootstrap credentials.

Redaction requirements:

- Secret values returned by Infisical must enter the same redaction pipeline as `.env` secrets.
- Logs must redact Universal Auth client secret, access tokens, refresh tokens, provider API keys, OAuth tokens, and migrated values.
- Dry-run migration output may show key names and destinations, but not values.

## Testing

Unit tests:

- Config parsing for `secrets.backends.infisical`.
- Alias parsing for `alias:KEY`.
- Resolution precedence.
- Bootstrap credential-store abstraction with fake stores.
- Infisical Universal Auth token exchange.
- Token refresh and retry behavior.
- Redaction of backend-returned values.
- `.env` scanning and category suggestion.
- Migration dry-run output.
- Write/read-back verification behavior.
- Backup and plaintext cleanup behavior.

Integration tests:

- Mocked HTTP Infisical API for deterministic CI.
- Optional Infisical dev container test for local development.
- Setup flow against fake OS credential store.
- Migration from a temporary Hermes home.
- Runtime provider/tool secret lookup through the resolver path.

Platform tests:

- Fake bootstrap store in ordinary CI.
- macOS Keychain smoke test when running on macOS with user approval.
- Windows Credential Manager smoke test when running on Windows.
- Linux Secret Service smoke test when a session bus and keyring backend are available.

Manual verification:

- Local self-hosted Infisical on this device.
- Tailscale-secured access to the local Infisical service from another approved tailnet device.
- Migration from a populated `.env`.
- Restart Hermes after migration and confirm secrets still resolve.

## Acceptance Criteria

- `hermes secrets setup infisical` can configure a local self-hosted Infisical instance running on this device.
- Any remote access to the local Infisical service is through Tailscale, not public internet exposure.
- Tailscale Funnel is not used for Infisical.
- The backend remains host-URL based, but the guided setup and manual verification target local self-hosted Infisical secured by Tailscale.
- Universal Auth bootstrap credentials are stored in the OS credential store, not plaintext config.
- macOS, Windows, and Linux have equivalent credential-store adapter support.
- Multiple project aliases work.
- Explicit `alias:KEY` references resolve only through the selected alias.
- Existing `.env` secrets can be migrated into selected Infisical projects.
- Migration writes secrets, verifies reads, backs up `.env`, and removes plaintext active values.
- Existing Hermes features can obtain secrets without each feature becoming Infisical-aware.
- Infisical outage, missing credentials, unknown aliases, and permission failures produce clear redacted errors.
- Logs do not leak secret values, Universal Auth credentials, or Infisical tokens.

## Implementation Notes

The implementation plan should deliver this in vertical slices:

1. Secret reference parser, backend interface, resolver, and tests.
2. OS credential-store abstraction and fake store tests.
3. Infisical backend with Universal Auth and mocked HTTP tests.
4. Config loading and CLI command skeleton.
5. Local self-hosted setup validation path.
6. Multi-project alias validation.
7. `.env` migration dry run.
8. Infisical write/read-back migration.
9. `.env` backup and plaintext cleanup.
10. Runtime integration for provider/tool/gateway secret resolution.
11. Documentation and manual verification.

New dependencies must follow the repository dependency pinning policy. If using Python `keyring` or Infisical client libraries, add upper bounds and regenerate the lockfile. If a direct HTTP client is sufficient and already available, prefer that over adding a new Infisical SDK dependency.
