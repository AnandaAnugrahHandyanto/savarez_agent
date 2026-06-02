# 2026-06-02 Upstream, CodeGraph, and Dependency Sync

## Scope

- Worktree: `C:\Users\downl\Documents\New project\hermes-agent`
- Branch: `main`
- Official upstream: `upstream/main` at `c6501c0f492c73313648df23417e9297cf91f868`
- Fork remote: `origin/main`
- User request:
  - Read and install `https://github.com/DannyMac180/skills`.
  - Follow official Hermes Agent latest features, vulnerability updates, bug fixes, and latest APIs.
  - Preserve fork-owned behavior and custom features.
  - Use Python sync scripts for inventory and merge investigation.
  - Enable `zapabob/Codegraph`.
  - Keep CI/CD and red-team PR selection evidence.
  - Select three serious, non-duplicate official PRs, excluding fork-only features and `_docs`.

## Inputs and Installed Tooling

- Installed `DannyMac180/skills` skill:
  - Source: `https://github.com/DannyMac180/skills`
  - Installed skill: `codex-dynamic-workflows`
  - Installed path: `C:\Users\downl\.codex\skills\codex-dynamic-workflows`
  - Note: Codex needs a restart before the new local skill is available in a fresh session context.
- Enabled CodeGraph:
  - Existing CLI: `codegraph 0.9.4`
  - Source checked: `https://github.com/zapabob/Codegraph`
  - Added MCP stanza to `C:\Users\downl\.codex\config.toml`:
    - command: `codegraph`
    - args: `serve --mcp`
  - The current Codex process must be restarted before the new MCP server is loaded.

## Upstream Sync

- Fetched remotes and confirmed the fork was behind official upstream after fetch.
- Ran inventory:
  - `python scripts/sync_all.py --inventory-only --skip-fetch`
  - Report: `_docs/merge-reports/sync-all-inventory-20260602T111737Z.json`
  - Inventory summary:
    - upstream paths: `180`
    - custom committed paths: `1696`
    - overlap paths: `29`
    - touched paths: `1847`
    - actions:
      - `manual_api_followup`: `26`
      - `official_with_overlay`: `4`
      - `preserve_custom`: `1662`
      - `upstream`: `155`
- Ran merge:
  - `python scripts/sync_all.py --merge --target main --skip-fetch --allow-preflight-blockers`
  - Report: `_docs/merge-reports/sync-all-ok-20260602T111803Z.json`
- Manual follow-up after merge:
  - Restored `hermes_cli.gateway._block_until_terminated()` compatibility for the s6 gateway dispatch test path while preserving the existing signal wait helper.
  - Restored `SessionDB.set_session_archived()` in `hermes_state.py` for archive behavior expected by session tests.

## Dependency Security Refresh

- Updated Python dependency pins and `uv.lock`:
  - `aiohttp 3.13.3 -> 3.13.4`
  - `anthropic 0.86.0 -> 0.87.0`
  - `pytest 9.0.2 -> 9.0.3`
  - `cbor2 5.8.0 -> 6.1.1`
- Updated npm lockfiles with `npm audit fix --package-lock-only`:
  - `package-lock.json`
  - `website/package-lock.json`
  - `web/package-lock.json`
  - `scripts/whatsapp-bridge/package-lock.json`
- WhatsApp bridge lock refresh specifically updated:
  - `protobufjs 7.5.6 -> 7.6.2`
  - `ws 8.20.0 -> 8.21.0`

## Commits

- `1ce1dc126` - `merge: sync upstream main through c6501c0f4`
- `ebdcbffcf` - `fix: refresh vulnerable dependency locks`
- `a4b34ae01` - `fix: refresh whatsapp bridge vulnerable locks`

## Verification

- Merge and publish:
  - `git status --short --branch --untracked-files=all`
    - clean after push.
  - `git rev-list --left-right --count origin/main...HEAD`
    - `0 0`
  - `git rev-list --left-right --count upstream/main...HEAD`
    - `0 167`
- CodeGraph:
  - `codegraph sync`
    - already up to date after final dependency-lock commit.
  - `codegraph status`
    - files: `3,039`
    - nodes: `84,410`
    - edges: `142,497`
    - status: OK, index up to date.
- Python:
  - `uv lock --check`
    - passed.
  - `uv run --extra dev ruff check hermes_cli/gateway.py hermes_state.py tests/hermes_cli/test_gateway_s6_dispatch.py tests/test_hermes_state.py`
    - passed.
  - `uv run --extra dev python -X utf8 -m pytest tests/hermes_cli/test_gateway_s6_dispatch.py tests/test_hermes_state.py tests/agent/test_runtime_cwd.py tests/agent/test_prompt_builder.py tests/tools/test_website_policy.py::TestWebToolPolicy::test_web_extract_blocks_firecrawl_unsafe_final_url tests/tools/test_website_policy.py::TestWebToolPolicy::test_web_extract_blocks_redirected_final_url tests/hermes_cli/test_web_server_host_header.py tests/gateway/test_platform_base.py::TestMediaDeliveryDefaultMode -q --timeout-method=thread`
    - `436 passed, 1 skipped`
- npm:
  - Ran `npm audit --package-lock-only --audit-level=moderate` for every repository `package-lock.json`.
  - Results:
    - `package-lock.json`: OK
    - `scripts/whatsapp-bridge/package-lock.json`: OK
    - `website/package-lock.json`: OK
    - `apps/desktop/package-lock.json`: OK
    - `ui-tui/packages/hermes-ink/package-lock.json`: OK
    - `ui-tui/package-lock.json`: OK
    - `web/package-lock.json`: OK
- Diff hygiene:
  - `git diff --check`
    - passed.
  - `git diff --check --cached`
    - passed before each commit.

## Official PR Candidates

Selected serious, non-duplicate, non-draft PRs for official `NousResearch/hermes-agent`.
Each PR excludes fork-only behavior and `_docs`.

1. `#35840` - `fix(web): re-check Firecrawl final URLs for SSRF`
   - URL: `https://github.com/NousResearch/hermes-agent/pull/35840`
   - Risk class: SSRF / unsafe redirect final URL handling.
   - CI: all checked jobs passing.
2. `#35852` - `fix(dashboard): validate websocket origin before tickets`
   - URL: `https://github.com/NousResearch/hermes-agent/pull/35852`
   - Risk class: dashboard WebSocket ticket misuse across origin and host validation order.
   - CI: all checked jobs passing.
3. `#35939` - `fix(gateway): block Hermes home media attachments`
   - URL: `https://github.com/NousResearch/hermes-agent/pull/35939`
   - Risk class: sensitive local Hermes state exposure via gateway media delivery.
   - CI: all checked jobs passing.

Not selected:

- `#35798` was not selected because it was draft and overlapped with an existing security-hardening line.

## Residual Risks and Follow-Up

- GitHub push output still reported 38 Dependabot alerts immediately after push. Local evidence showed all npm `package-lock.json` files pass `npm audit --package-lock-only --audit-level=moderate`; Dependabot can lag behind pushed lockfile updates.
- `PyNaCl` remains at `1.5.0` in `uv.lock` because `discord.py[voice] 2.7.1`, the latest available release at the time of this run, requires `PyNaCl >=1.5.0,<1.6`. Forcing `PyNaCl==1.6.2` makes the `messaging` extra unsatisfiable. This should be revisited when `discord.py` relaxes its upper bound or if Hermes decides to remove the voice extra from the default messaging extra.
- Broad full-repo pytest and frontend builds were not run in this closeout. The verification scope focused on merge fallout, security-relevant paths, dependency resolution, lockfile audit, and CodeGraph indexing.
