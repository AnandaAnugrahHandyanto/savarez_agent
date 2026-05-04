# Platform-Engineering Retrofit — Hermes → SRE/Platform Assistant

**Status:** rough draft for discussion (Drew + Trey).
**Goal:** retrofit the consumer-grade [`hermes-agent`](https://github.com/NousResearch/hermes-agent) codebase into an Abridge-internal, **Slack-only**, **Firebase-backed**, **GCP-hosted** platform-engineering / SRE assistant — sibling product to Apex (which targets app engineers; this one targets platform, infra, and on-call).

This is a *plan* document — no code lands with this PR. The four sections below were drafted by specialist agents (architecture, backend, security, UX) reviewing the current codebase, and are intended as the starting point for shaping the work, not the final answer.

## TL;DR

- **One channel: Slack.** Delete every other platform integration under `gateway/platforms/` and `plugins/platforms/`. ~25 files plus their tests and CLI surfaces go away.
- **One persistence layer: Firestore + GCS + Secret Manager.** Replace the SQLite + `~/.hermes/` + OS-keyring sprawl. Local SQLite stays as a dev option through a `StateStore` interface, then is dropped after migration.
- **One transport, many models.** Collapse the per-vendor adapters (Anthropic, Bedrock, Gemini-multiple, Codex, Copilot, LMStudio, Moonshot) onto the existing `chat_completions` transport pointed at an internal LLM gateway that routes between **Anthropic-on-Vertex**, **Vertex Gemini**, and **self-hosted Qwen / Gemma on GKE + vLLM**.
- **Two GCP projects** (`apex-sre-prod` runtime, `apex-sre-firebase` data) under a dedicated folder, behind VPC-SC, with WIF for service identity and Secret Manager for everything else.
- **Tiered approval for high-blast-radius actions** (T0 read → auto, T1 dev write → 1 approver, T2 prod write → 2-of-N, T3 destructive → 2-of-N + typed confirm). Hooks into the existing guardrail surface in `agent/tool_guardrails.py` + `agent/shell_hooks.py`.
- **HIPAA posture:** BAA-covered providers only (Vertex-Anthropic, Vertex-Gemini, self-hosted), routing layer enforces `phi_eligible` flag, audit logs sink to BigQuery with 6-year immutable retention.

---

> **Note on GCP service currency:** the architecture brief flags several GCP managed-service claims as `[VERIFY]` — WebSearch was unavailable during drafting, so before locking decisions on Agent Engine, Cloud Run GPU GA in our region, and any "managed LLM/MCP gateway" product, confirm against current GCP release notes.

---

## Architecture

This section drafts the target architecture for retrofitting `hermes-agent` into an enterprise platform-engineering / SRE assistant ("Apex's SRE sibling"), Slack-only, on a dedicated GCP project, with Firebase persistence and optional self-hosted models.

> **Note on GCP service currency:** WebSearch was unavailable in this drafting session, so claims about specific GCP GA dates below are flagged `[VERIFY]`. Drew/Trey should confirm against the GCP release notes before locking decisions.

### 1. Deployment Topology

**Project layout.** Two GCP projects under a dedicated folder, both in a single Org:
- `apex-sre-prod` — runtime (agent core, gateway, model proxies, MCP servers, secrets).
- `apex-sre-firebase` — Firebase project (Firestore, Auth, App Check). Firebase requires its own project; we link it to the runtime project via IAM rather than co-hosting.

A third sandbox project (`apex-sre-dev`) mirrors prod for staging. Production lives behind a **VPC Service Controls** perimeter that includes Firestore, Vertex AI, Secret Manager, Artifact Registry, and Cloud Logging. Slack ingress is the only public surface, fronted by a regional external HTTPS load balancer with Cloud Armor.

**Runtime.** The agent core today (`run_agent.py`, `agent/`, `gateway/run.py`) is a long-running Python process that holds Slack Socket-Mode/Events connections and drives multi-step tool loops. Recommendation:

- **GKE Autopilot** for the agent core + Slack ingress. Justification: persistent WebSocket to Slack, long agent loops (>60s common), and we want a single substrate that can also schedule GPU workloads when self-hosting models. Cloud Run's request-bound model is awkward for Socket Mode, and Agent Engine [VERIFY] is too prescriptive about agent shape (it expects ADK/LangChain-style graphs, not Hermes' bespoke loop in `agent/anthropic_adapter.py`).
- **Cloud Run** for stateless side-services only: cron tick, webhook receivers, batch eval runners (`batch_runner.py`).
- **Vertex AI Agent Engine** [VERIFY GA status] — *not* the home for the core agent. Reserve as a future option for spinning off subagents (e.g., a "diagnose-incident" graph) where managed runtime + tracing pays off.

### 2. Self-Hosted Model Serving

**Default recommendation: GKE Autopilot with GPU node pools running vLLM**, in the same cluster as the agent core, separate node pool. Models: Qwen3-Coder / Qwen3-VL and Gemma 3 served via vLLM with OpenAI-compatible endpoints, fronted internally by the LLM gateway (below).

- **A100 80GB or H100** node pool for the "primary" SRE-coding model (Qwen3-Coder-32B class). One replica warm, HPA on queue depth.
- **L4** node pool for embeddings + a cheap fallback chat model (Gemma 3 12B). L4 cold-start is the cheapest path to "always-on small model."
- **Cloud Run GPU (L4)** [VERIFY GA in our region] is attractive for *bursty* eval/batch jobs but not for the always-on inference path — its cold start and per-request scaling fight long agent loops. Use it for `batch_runner.py` eval sweeps.
- **Vertex AI custom endpoints** rejected as default: more expensive per GPU-hour, less control over vLLM internals, harder to swap quantizations.
- **On-prem Abridge hardware via GCP-side proxy** is viable but only worth the ops if Abridge already has spare H100s; otherwise GKE wins on operational simplicity.

Tradeoff to flag: GKE Autopilot has constraints on GPU-class node pools — we may need GKE Standard for the GPU pool and Autopilot for CPU services. Acceptable.

### 3. LLM and MCP Gateway

**LLM gateway: thin internal proxy, OpenAI-shape, written in Python and co-located with the agent.** Replaces the current per-vendor sprawl in `agent/transports/anthropic.py`, `agent/transports/bedrock.py`, `agent/anthropic_adapter.py`, `agent/bedrock_adapter.py`, `agent/gemini_native_adapter.py`, etc. Routes:

- Anthropic → **Anthropic on Vertex AI** (keeps traffic in-VPC, single billing).
- Google models → **Vertex AI Model Garden**.
- Self-hosted Qwen/Gemma → in-cluster vLLM service.
- OpenAI/Azure → kept only if a specific capability (e.g., realtime audio) requires it.

The gateway owns: per-tenant rate limits, prompt-caching policy (preserve `agent/prompt_caching.py` semantics), redaction (`agent/redact.py`), cost accounting (`agent/usage_pricing.py`, `agent/account_usage.py`), and routing rules ("SRE incident triage → Claude Opus; code edit → self-hosted Qwen; embeddings → Gemma"). LiteLLM is a reasonable starting library but we should not depend on its routing UI — own the policy layer ourselves.

A "GCP-managed LLM gateway" product [VERIFY — unclear if GA] is *not* a blocker; if/when it ships and supports our routing requirements, the internal gateway becomes a thin client to it without changing the agent.

**MCP gateway: self-hosted MCP registry inside the cluster.** Hermes already speaks MCP (`mcp_serve.py`, `optional-skills/mcp/`). Run a registry service that the agent queries to discover tenant-scoped MCP servers (GitHub, Datadog, PagerDuty, ArgoCD, internal Backstage/IDP). Use Cloud Run for each MCP server (stateless, per-tenant scaling). A managed GCP MCP gateway [VERIFY] should be adopted only after it supports per-tenant auth scoping; until then, our registry plus Workload Identity is sufficient.

### 4. Persistence Retrofit

Today's storage surface (`hermes_state.py` SQLite + WAL, `~/.hermes/` filesystem, `hermes_cli/kanban_db.py` SQLite, `plugins/memory/*` various local stores, `agent/credential_pool.py` keyring) is single-tenant by construction. Mapping to Firestore:

| Today | Target |
|---|---|
| `hermes_state.py` sessions, messages, tool calls | Firestore: `tenants/{ws}/sessions/{id}` with subcollection `messages` |
| FTS5 message search | Vertex AI Search index over a Firestore→BigQuery export (FTS5 doesn't translate) |
| `cron/jobs.py` schedules | Firestore `tenants/{ws}/cron_jobs` driven by Cloud Scheduler ticking the agent |
| `plugins/kanban/dashboard/plugin_api.py` SQLite kanban | Firestore `tenants/{ws}/kanban/{board}/cards` |
| `plugins/memory/*` stores | One canonical store backed by Firestore + Vertex AI Vector Search; deprecate the long tail (byterover, hindsight, holographic, honcho, mem0, openviking, retaindb, supermemory) |
| `skills/` filesystem skills | Stay on disk (read-only, baked into image); tenant overrides go in Firestore |
| `agent/credential_pool.py` + keyring | **Removed.** Human auth → Firebase Auth (Google SSO via Abridge IdP). Service creds → Secret Manager via Workload Identity |
| Trajectory compressor scratch (`trajectory_compressor.py`, `agent/context_compressor.py`) | Stay in-memory / local tmpfs |
| Sticker cache, HTTP caches | Local tmpfs / Memorystore |

Migration shape: introduce a `StateStore` interface, give it two implementations (`SqliteStateStore` = current, `FirestoreStateStore` = new), feature-flag per session source. Strangler-fig over 2–3 milestones; SQLite path remains for local dev.

### 5. Identity and Multi-Tenancy

- **Tenant = Slack workspace** (`team_id`). All Firestore docs are namespaced under `tenants/{team_id}/...` and Firestore Security Rules enforce it.
- **Users = Firebase Auth identities.** Slack `user_id` → Firebase custom claim mapping table; first interaction triggers an enrollment DM that links Slack → Google SSO.
- **Agent permissions** are scoped via a per-tenant service account with Workload Identity. Cross-tenant tool calls are structurally impossible because the agent process loads its tenant context from the Slack event and never holds cross-tenant credentials in memory.
- **App Check** on all Firebase calls; **Cloud Armor** + Slack signing-secret verification on ingress.

### 6. Open Questions / Decision Points

- **Agent runtime vs. Agent Engine:** commit to GKE Autopilot now, or pilot Agent Engine for a single subagent first? Decision gates the deployment work.
- **Self-hosted vs. hosted default:** which workloads route to Qwen/Gemma by default vs. Claude/Gemini? Need a cost+quality SLO before writing routing rules.
- **GPU sourcing:** GKE GPU node pool in `us-central1` vs. reusing existing Abridge on-prem capacity. Affects capex and the gateway's egress story.
- **Firestore vs. AlloyDB for session history:** Firestore is the easier fit but FTS and analytics are weak. Are we OK with a Firestore→BigQuery mirror for search, or do we want AlloyDB from day one?
- **Keep SQLite path for local dev?** Yes is my default, but it doubles store-interface surface area; confirm the team values offline dev enough to pay that tax.
- **Scope of channel strip:** confirm we delete `gateway/platforms/{telegram,discord,whatsapp,signal,sms,email,matrix,feishu,dingtalk,wecom,weixin,bluebubbles,homeassistant,mattermost,webhook,yuanbao,qqbot}.py` outright (my recommendation) versus moving them to an archived branch. Affects test surface and contributor messaging.

---

## Backend Retrofit

Goal: convert `hermes-agent` (Nous consumer multi-platform agent) into an internal Slack-only Abridge platform-engineering / SRE assistant, swapping local SQLite/JSON state for Firestore and Anthropic/Bedrock/Gemini/Codex bias for self-hosted vLLM serving Qwen / Gemma. Plan only — no code in this PR.

### 1. Removal manifest

**(a) Non-Slack platforms — `gateway/platforms/`.** Delete: `discord.py`, `telegram.py`, `telegram_network.py`, `whatsapp.py`, `signal.py`, `signal_rate_limit.py`, `sms.py`, `email.py`, `matrix.py`, `mattermost.py`, `bluebubbles.py`, `dingtalk.py`, `feishu.py`, `feishu_comment.py`, `feishu_comment_rules.py`, `homeassistant.py`, `webhook.py`, `wecom.py`, `wecom_callback.py`, `wecom_crypto.py`, `weixin.py`, `yuanbao.py`, `yuanbao_media.py`, `yuanbao_proto.py`, `yuanbao_sticker.py`, `qqbot/`. Plus `plugins/platforms/{irc,teams}/`. **Keep:** `slack.py`, `base.py` (3382 lines — shared `Platform` ABC, `cache_audio_from_bytes`, `cache_image_from_bytes`, `resolve_channel_prompt`, `resolve_channel_skills`, all referenced from `slack.py:2111,2833,2836`), `helpers.py` (`MessageDeduplicator` — slack.py:38), `_http_client_limits.py`, `api_server.py`, `__init__.py`, `ADDING_A_PLATFORM.md`. Audit `gateway/platform_registry.py`, `gateway/config.py` (`Platform` enum), `gateway/whatsapp_identity.py`, `gateway/sticker_cache.py`, `gateway/channel_directory.py`, `gateway/mirror.py`, `gateway/pairing.py` for cross-platform dispatch tables — many will collapse to single-branch logic and should be flattened, not just stub-imported.

**(b) Consumer plugins — `plugins/`.** Cut: `spotify/`, `image_gen/{openai,openai-codex,xai}/`, `hermes-achievements/`, `google_meet/` (incl. `node/`, `realtime/`, `audio_bridge.py`, `meet_bot.py`), `strike-freedom-cockpit/`, `disk-cleanup/`, `example-dashboard/`. In `plugins/memory/` keep one canonical store (recommend `honcho/` or a new `firestore/`); delete `byterover/`, `hindsight/`, `holographic/`, `mem0/`, `openviking/`, `retaindb/`, `supermemory/`. Keep: `context_engine/`, `observability/langfuse/`, `kanban/` (data layer needs Firestore rewrite — see §2). Verify `plugins/__init__.py` and any `entry_points` in `pyproject.toml` are updated.

**(c) Consumer CLI — `hermes_cli/`.** Delete: `voice.py`, `dingtalk_auth.py`, `vercel_auth.py`, `nous_subscription.py`, `slack_cli.py` (consumer-style pairing CLI; replace with admin-oriented install flow), `webhook.py`, `pairing.py`, `clipboard.py`, `pty_bridge.py`, `browser_connect.py`, `claw.py`, `relaunch.py`, `tips.py`, `banner.py`, `default_soul.py`, `skin_engine.py`, `skins_*` references, `azure_detect.py` (consumer onboarding), `copilot_auth.py` (Codex/Copilot is gone in §3). Audit `hermes_cli/platforms.py`, `cron.py`, `kanban.py`, `kanban_db.py`, `setup.py`, `models.py`, `model_*.py` after the model-adapter cut. Non-obvious: `agent/credential_pool.py:18-34` imports a large surface of `hermes_cli.auth`; pruning provider auth (Codex, Kimi, ZAI, Anthropic OAuth) means `hermes_cli/auth.py:149` `PROVIDER_REGISTRY` shrinks dramatically and most of `agent/credential_pool.py` (1584 lines) becomes dead.

**Skill catalogue.** `skills/` includes `apple/`, `gaming/`, `gifs/`, `social-media/`, `smart-home/`, `creative/`, `media/`, `yuanbao/`, `dogfood/` — all consumer or vendor-specific. Delete or move to `optional-skills/`. Keep `devops/`, `mlops/`, `software-development/`, `data-science/`, `research/`, `domain/`, `note-taking/`, `email/` (if SRE runbooks live there), `github/`, `mcp/`, `productivity/`. Re-curate after §6 phase 2.

### 2. Firestore persistence migration

Each store, current location, proposed Firestore shape. All paths assume a single Firestore database scoped per-Abridge-tenant; multi-workspace cleanly maps to a top-level `workspaces/{workspaceId}` parent.

| Store | Current | Firestore shape | Indexes / risk |
|---|---|---|---|
| Sessions + messages + FTS | `hermes_state.py` (SQLite, `state.db`, schema v11, FTS5 unicode + trigram) | `workspaces/{ws}/sessions/{sessionId}` doc; `…/sessions/{sessionId}/messages/{autoId}` subcollection | Composite indexes on `(source, started_at desc)`, `(parent_session_id, started_at)`. **FTS5 has no Firestore equivalent — keep a local SQLite read-replica or stand up Vertex AI Search / Elasticsearch for full-text.** Trigram CJK index (`hermes_state.py:132`) is dead weight for English-only Abridge use; drop. |
| Cron jobs + run output | `cron/jobs.py` (`~/.hermes/cron/jobs.json`), output md files in `~/.hermes/cron/output/{job_id}/` | `workspaces/{ws}/cronJobs/{jobId}`; runs as `…/cronJobs/{jobId}/runs/{runId}` with `output_gcs_uri` pointing at GCS | Multi-process file lock (`jobs.py:43`) becomes Firestore transactions. Run output > 1 MB → GCS, not Firestore. |
| Kanban | `hermes_cli/kanban_db.py` (3326 LOC SQLite) | `workspaces/{ws}/boards/{boardId}`, `…/boards/{boardId}/cards/{cardId}`, `…/cards/{cardId}/comments/{id}` | Indexes on `(board_id, status, updated_at desc)`. Highest migration complexity — write a one-shot exporter and freeze SQLite schema. |
| Memory | `agent/memory_manager.py` + `plugins/memory/*` | `workspaces/{ws}/memory/{kind}/items/{id}` with vector embeddings stored alongside; consider Firestore Vector Search (in GA on multi-region DBs) or Vertex Vector Search if recall matters | Pick **one** memory backend before migrating; current tree has 8 implementations. |
| Skills metadata + usage | `tools/skill_usage.py`, skills_hub state under `~/.hermes/` | `workspaces/{ws}/skillUsage/{userId}/events/{id}` (TTL 90d) | Hot write path — batch writes, consider BigQuery export for analytics. |
| Account / usage tracking | `agent/account_usage.py`, `~/.hermes/usage.json` | `workspaces/{ws}/usage/{providerId}/windows/{windowId}` | Most consumer providers are deleted in §3, so this collapses to one doc per vLLM endpoint. |
| Credential pool | `agent/credential_pool.py` (1584 lines), `hermes_cli/auth.py:read_credential_pool` | `workspaces/{ws}/secrets/{providerId}` — **but** real secrets go in **GCP Secret Manager**; Firestore stores only metadata (rotation timestamps, status, last-used). | Never put raw API keys in Firestore. |
| Pairing tokens | `gateway/pairing.py`, `feishu_comment_pairing.json` | Slack-only: `workspaces/{ws}/slackInstalls/{teamId}` storing bot/user tokens (again with secrets in Secret Manager) | TTL on ephemeral install nonces. |
| Channel directory / dedup | `gateway/channel_directory.py`, `gateway/platforms/helpers.py:MessageDeduplicator` | Dedup stays in-memory or **Memorystore Redis** (low TTL, hot path) — do not put per-message dedup in Firestore | Latency + cost. |
| Trajectory / run logs | `trajectory_compressor.py`, JSONL on disk | GCS bucket `gs://abridge-hermes-trajectories/{ws}/{date}/{sessionId}.jsonl.zst` | Large blobs; Firestore document size limit (1 MiB) is hostile here. |
| FTS / search index | `hermes_state.py` FTS5 | **Local cache** or Elastic/Vertex Search | Genuinely stays out of Firestore. |
| Model catalog disk cache | `hermes_cli/model_catalog.py:108` (`~/.hermes/cache/model_catalog.json`) | **Stays local** — it is a cache fronting an HTTP fetch. | None. |

Migration risk is dominated by (a) Kanban schema breadth, (b) FTS replacement decision, and (c) sessions table schema-version 11 evolution requiring an explicit one-shot exporter. Build a `scripts/sqlite_to_firestore.py` per-table importer guarded by `--dry-run`.

### 3. Self-hosted model adapter (vLLM / Qwen / Gemma)

The transport layer (`agent/transports/`) is already cleanly factored: `ProviderTransport` ABC (`base.py`) with implementations for `chat_completions.py`, `anthropic.py`, `bedrock.py`, `codex.py`. `chat_completions.py` (529 LOC) is already used for ~16 OpenAI-compatible providers (Ollama, DeepSeek, NVIDIA, Qwen, Kimi, etc., per its docstring), so vLLM/TGI fit natively.

**Recommendation: do _not_ add `agent/vllm_adapter.py`.** Add a thin `selfhosted` provider entry in `hermes_cli/auth.py:PROVIDER_REGISTRY` (`api_mode='chat_completions'`, configurable `base_url`, no auth or bearer-from-env), and let routing flow through the existing `chat_completions` transport. Quirks (Qwen tool-call format, Gemma's lack of tool calling, vLLM's non-standard `extra_body` for guided decoding) belong in small `if model.startswith("qwen")` / `if "gemma" in model` branches inside `chat_completions.build_kwargs` — the file already has analogous Moonshot/LMStudio/Gemini branches (see `chat_completions.py:15-17,22-60`).

**Do not add LiteLLM in front.** Reasons: (i) Hermes already _is_ a multi-provider router; LiteLLM duplicates that; (ii) it adds an ops surface (proxy deploy, version skew); (iii) the transport ABC is the right seam. If we ever need cross-cloud failover (Bedrock fallback for Anthropic outage), build it at the `auxiliary_client.py:923` layer where `api_mode` is already a parameter.

**Delete adapters:** `agent/anthropic_adapter.py` (1970 LOC), `agent/bedrock_adapter.py` (1264 LOC), `agent/codex_responses_adapter.py`, `agent/copilot_acp_client.py`, `agent/gemini_cloudcode_adapter.py`, `agent/gemini_native_adapter.py`, `agent/gemini_schema.py`, `agent/google_code_assist.py`, `agent/google_oauth.py`, `agent/lmstudio_reasoning.py`, `agent/moonshot_schema.py`, `agent/nous_rate_guard.py`, `agent/image_gen_provider.py`, `agent/image_gen_registry.py`, `agent/image_routing.py`. Keep: `agent/auxiliary_client.py` (collapse provider switch), `agent/prompt_caching.py` (vLLM has prefix caching — repurpose), `agent/context_compressor.py`, `agent/retry_utils.py`, `agent/error_classifier.py`, `agent/rate_limit_tracker.py`, `agent/redact.py`, `agent/usage_pricing.py` (rewrite for self-hosted GPU $/hr math, not $/Mtoken). Also drop transports `agent/transports/{anthropic,bedrock,codex}.py`.

**Routing decision lives per-tenant + per-tool**, not per-workspace. Concretely: a Firestore `workspaces/{ws}/modelPolicy` doc maps `(toolClass, urgency) → vllmEndpoint`. Tool classes: `code_edit` → Qwen3-Coder; `summarize/triage` → Gemma-3-27B; `cheap_classify` → Gemma-3-4B. Workspaces inherit a tenant default. The picker hooks in at `agent/auxiliary_client.py:1854` (`runtime_api_mode`) — add a `resolve_endpoint(tool_class, workspace)` step before the existing runtime resolution.

`hermes_cli/model_catalog.py` is a remote-fetch from `hermes-agent.nousresearch.com`; either point its `DEFAULT_CATALOG_URL` (line 64) at an internal Abridge-hosted manifest or rip the fetcher out and ship a static `agent/model_metadata.py` table. Recommend the latter — the catalog drift problem doesn't apply when we own the inference stack.

### 4. Slack hardening

`gateway/platforms/slack.py` is 2926 lines of consumer-grade logic (per-user pairing, sticker caches, voice). Concrete enterprise items:

- **Install model**: switch to a Slack App with org-level install (Enterprise Grid `enterprise_install: true` in manifest), distribute via the workspace's Slack admin. Drop the `slack_cli` user-pairing flow entirely — auth is the bot token issued at install, stored in Secret Manager keyed by `team_id` + `enterprise_id`.
- **Transport**: prefer **HTTP Events API** behind Cloud Run / GKE Ingress over Socket Mode. Socket Mode is nice for dev but couples uptime to a long-lived WebSocket and complicates horizontal scaling. Keep Socket Mode as a dev-loop opt-in only.
- **Permission model**: introduce a `WorkspaceRole` (admin / responder / observer) materialized in Firestore `workspaces/{ws}/members/{userId}`, checked before any tool that touches prod (kubectl exec, terraform apply, PagerDuty ack). Tie to Slack `user_id`; no separate identity store.
- **Audit logging**: every tool invocation writes to `workspaces/{ws}/auditLog/{eventId}` (immutable, TTL 400d) and mirrors to BigQuery via Pub/Sub for SOC2 retention. Hook in at the existing `tools/approval.py` boundary.
- **Rate limits**: respect Slack's tier-2/3 web API limits; the existing `MessageDeduplicator` (`helpers.py`) handles inbound retries but outbound posting needs a token-bucket per channel. There's nothing useful here today.
- **Threading model**: enforce that all bot replies thread under the trigger message (no channel spam) and that `chat:write.customize` is _not_ requested — admins reject custom usernames in Grid.

### 5. Test / CI surgery

Tests under `tests/gateway/` reference deleted platforms directly: `test_bluebubbles.py`, `test_dingtalk.py`, `test_discord_*.py`, plus all `test_yuanbao_*.py` at the repo root. Delete those plus `tests/plugins/test_achievements_plugin.py`, `test_disk_cleanup_plugin.py`, `test_google_meet_*.py` (4 files), `tests/plugins/image_gen/`, `tests/plugins/memory/` for cut providers, `tests/e2e/matrix_xsign_bootstrap/`, `tests/test_minimax_*`, `tests/test_yuanbao_*`. `tests/conftest.py` likely fixtures SQLite paths — needs a Firestore emulator fixture (`firebase emulators:start --only firestore`) wired up. Stress tests (`tests/stress/test_concurrency*.py`) target SQLite WAL contention; replace with Firestore transaction-contention tests or delete. Expect to remove ~30–40% of the test count.

CI: add a Firestore emulator service container; drop matrix entries for non-Slack platform integration suites; add a vLLM mock (`responses` lib or a fake httpx transport returning OpenAI-shaped JSON) so unit tests don't need a real GPU.

### 6. Migration sequencing (PR order, repo stays green at every step)

1. **Phase 0 — Removal + green CI.** Delete non-Slack platforms, consumer plugins, consumer CLI surfaces, and their tests. No behavioral changes for Slack users. Land as a series of small per-platform PRs (one per delete) so revert is cheap.
2. **Phase 1 — Provider trim.** Delete Anthropic/Bedrock/Gemini/Codex/Copilot/LMStudio/Moonshot adapters and `PROVIDER_REGISTRY` entries; collapse `credential_pool.py` and `auxiliary_client.py`; default to `chat_completions` transport pointing at a placeholder OpenAI-compatible URL. Tests stay green via fake transport.
3. **Phase 2 — vLLM provider entry + per-tool routing.** Add `selfhosted` provider, the Qwen/Gemma branches in `chat_completions.build_kwargs`, and the `resolve_endpoint(tool_class, workspace)` hook with a static in-memory policy. Still SQLite-backed.
4. **Phase 3 — Firestore behind a `StateStore` interface.** Introduce an interface over `hermes_state.py` so callers depend on it, with two implementations (SQLite + Firestore). Run dual-write in dev, single-source in tests. Migrate sessions/messages first (highest blast radius), then cron, then kanban.
5. **Phase 4 — Secrets + Slack Enterprise install.** Move credentials to Secret Manager, switch Slack auth to org-install, wire audit logging.
6. **Phase 5 — Skill curation + memory consolidation + remove SQLite path.** Pick one memory backend, delete the rest, drop SQLite implementation of `StateStore`, freeze schema, ship.

### 7. Risks / unknowns

- **FTS replacement is unscoped.** Sessions search is a real product feature; Firestore has no native FTS. Decide between local SQLite cache, Elastic, or Vertex Search before phase 3 — this gates session UX.
- **Firestore document-size and write-rate limits.** Long agent runs produce >1 MiB `messages` arrays and bursty per-second writes against a single doc. Subcollections and per-message docs avoid both, but cost (per-document read/write billing) needs a back-of-envelope before commitment.
- **vLLM tool-calling fidelity for Qwen / Gemma.** Gemma has no first-class tool-calling; Qwen's varies by version. Either constrain to grammar-guided JSON via vLLM's `guided_json` (in `extra_body`) or keep an Anthropic fallback for tool-heavy flows — but that contradicts §3.
- **`gateway/platforms/base.py` (3382 LOC) coupling.** It mixes ABC contract with platform-agnostic helpers (audio cache, channel prompt resolution). Splitting cleanly so we can shrink it after the platform deletes is non-trivial — budget a dedicated refactor PR.
- **Credential-pool blast radius.** `agent/credential_pool.py` (1584 LOC) has many transitive consumers; deleting providers will surface unobvious dead branches that need careful review, not a mass delete.
- **Kanban migration scope.** `hermes_cli/kanban_db.py` is 3326 LOC of schema and queries. Decide early whether kanban is a keeper for SRE workflows or a candidate for cut; if kept, it dominates phase 3.

---

## Security & Compliance

This section turns the consumer-grade Hermes agent (multi-platform, local keyring, single-tenant) into a HIPAA-aligned platform-engineering assistant for Abridge. Scope is Slack-only, single GCP project, Firebase persistence, mixed managed + self-hosted models, with high-blast-radius tooling (kubectl, terraform, gcloud, AWS, prod DB).

### 1. Identity & access

- **Slack as IDP, Okta as truth.** Use Slack OIDC (`openid`, `email`, `profile`) wired through Firebase Auth's OIDC provider. Reject any Slack workspace ID that is not the Abridge corp workspace; reject any user whose `email` claim does not resolve to an active Okta principal (nightly reconciliation job). The current `gateway/platforms/slack.py` adapter authenticates the *bot* via xoxb token but does **not** identify the human user beyond `event.user`; we need to add a `resolve_user(slack_user_id) -> CorpPrincipal` shim that hits Slack `users.info` + Okta SCIM and caches in Firestore.
- **Workspace = tenant.** Even though we expect one workspace today, encode `tenant_id = team_id` on every audit event and Firestore document so the data model is multi-tenant-ready (Apex sister product, future BU split).
- **Per-user scoping.** Every agent session is scoped to the resolved corp principal; memories, transcripts, and approved-action history keyed by `(tenant_id, user_id)`. No shared memory pool.
- **Agent service identity = WIF, not SA keys.** The agent's own GCP/AWS access (for runbook execution) must use Workload Identity Federation from the Cloud Run / GKE workload identity pool. Replace any SA-key flow in `agent/credential_pool.py` and `agent/credential_sources.py`. SA keys are explicitly disallowed by policy; CI must fail on `*.json` key files.

### 2. Authorization for high-blast-radius actions

Tier every tool call. Hook the tiering into the existing pre-tool-call guardrail surface in `agent/tool_guardrails.py` (the `before_call` decision path) and the shell-hook bridge in `agent/shell_hooks.py` (the `pre_tool_call` event), and extend the write-denylist in `agent/file_safety.py` to cover infra paths (`~/.kube`, `~/.aws`, terraform state).

| Tier | Examples | Gate |
|------|----------|------|
| T0 read | `kubectl get`, `gcloud … describe`, `terraform plan` | allow, audit only |
| T1 non-prod write | `kubectl apply` in dev/staging, `gcloud … create` in sandbox | Slack interactive approval from invoker |
| T2 prod write | `kubectl apply` in prod, `terraform apply`, IAM mutations, secret rotation | Slack two-party approval (invoker + second on-call) with 5-min TTL |
| T3 destructive | `kubectl delete`, DB drop, force-push, `gcloud … delete` of stateful resources | T2 gate **plus** typed-confirmation challenge of the resource name |

Tier classification lives next to `MUTATING_TOOL_NAMES` in `tool_guardrails.py`; the approval state machine (request → pending → approved/denied/expired) is persisted in Firestore so restart doesn't lose context.

### 3. Audit logging

- **Every** tool call, model call, prompt, completion, approval grant/deny, identity resolution, and credential fetch emits a structured Cloud Logging record with: `tenant_id`, `user_id`, `session_id`, `turn_id`, `tool_name`, `tool_args_hash` (the `ToolCallSignature.args_hash` already in `tool_guardrails.py`), `model_id`, `route_decision`, `phi_eligible` flag, `request_id`.
- **Sink to BigQuery** with a dedicated dataset (`hermes_audit_<env>`), partitioned by day, **Object Versioning + bucket lock** on the GCS export, retention 6 years (HIPAA §164.530(j)(2)).
- **Redaction before logging.** `agent/redact.py` is well-built for vendor-prefixed tokens, JWTs, DB conn strings, URL userinfo, and form bodies — keep it. **Gaps** to close before relying on it for HIPAA logs:
  - It is OFF by default (`HERMES_REDACT_SECRETS`); the platform deploy must force `redact_sensitive_text(..., force=True)` at every audit-emit site, not rely on the env var.
  - No PII/PHI patterns (MRN, name, DOB, addresses, ICD codes). For an SRE tool we should not see PHI, but add a defense-in-depth pass that strips anything that looks like an MRN or 9-digit SSN before write.
  - Add allowlist-based field redaction for known prompt fields rather than relying solely on regex.
- Audit records are **immutable** — no Firestore mutability, write-once via the BigQuery sink. Engineers querying audit data go through a separate IAM role with `dataViewer`-only.

### 4. HIPAA posture

This is an SRE tool, not a clinical tool, but it sits adjacent to PHI infrastructure, so we treat it as a HIPAA workforce-access system.

- **BAA-covered model providers only.** Allowed: Anthropic via Vertex (Google BAA covers Vertex), Vertex-native Gemini, self-hosted Qwen/Gemma. Disallowed without explicit BAA on file: Anthropic direct API, OpenAI direct, OpenRouter, Together, Groq, any consumer provider currently configured in `agent/credential_pool.py` / `auxiliary_client.py`.
- **Routing enforcement.** Add a `phi_eligible` boolean on every route decision; the model router refuses to dispatch to a non-BAA endpoint when the flag is true, and logs a deny event. Default the flag to true (fail-closed) until the request is classified as obviously non-PHI (e.g., "list pods in namespace foo").
- **No PHI in prompts.** Engineers should never paste PHI into Slack, but we add a heuristic pre-prompt scrubber and a Slack message-level warning banner when patterns matching PHI appear.
- **Vertex regionalization.** Pin Vertex calls to `us-central1` (or another in-scope region) and disable cross-region failover; document in the BAA addendum.

### 5. Self-hosted Qwen/Gemma security

- **Network isolation.** GPU hosts in a dedicated VPC, no default internet egress, only Cloud NAT for explicit allowlisted destinations (model registry pulls only). Inbound restricted to the gateway via PSC / internal LB; no public IP.
- **No prompt/response logging on the inference host** beyond what Cloud Logging already captures via the gateway. Local model server logs scrubbed and retained 7 days.
- **Model supply chain.** Pin model weights by SHA-256, mirror to a private GCS bucket with bucket lock, scan for known-bad model fingerprints (model-scan / `picklescan`), and reject any weights file not signed by an approved key. No live HF Hub pulls in production.
- **Tenant-isolated GPU memory.** Single-tenant inference processes; no batched inference across tenants until KV-cache isolation is verified.

### 6. Secrets

- **Replace `agent/credential_pool.py` + `agent/credential_sources.py`.** The current design persists credentials to a local JSON pool keyed off `~/.hermes` and uses local OS keyring as a "secure" backend — unacceptable for a hosted multi-user service. Migrate to GCP Secret Manager:
  - Slack bot token, signing secret, app token → Secret Manager, accessed by Cloud Run via WIF.
  - Model provider keys (Anthropic, Vertex SAs are WIF, others) → Secret Manager, with rotation policy (90-day for static keys, automatic for federated).
  - Customer cloud creds for runbook execution → short-lived STS / WIF tokens minted per-action, never stored.
- **Per-tenant secret namespacing.** Secret Manager labels: `tenant=<team_id>`, `env=<prod|staging>`, `purpose=<slack|model|runbook>`. IAM bindings restrict the agent service account to its own tenant prefix.
- **Forbid env-var secret pass-through** for anything beyond bootstrap config. The `_SECRET_ENV_NAMES` regex in `redact.py` is a redaction safety net, not an architectural justification for env-var secrets.

### 7. Data classification & retention

| Asset | Class | Default retention | Right-to-delete |
|------|------|------|------|
| Audit logs | Restricted (HIPAA-relevant access logs) | 6 years, immutable | No (regulatory hold) |
| Session transcripts (prompts + completions) | Confidential | 90 days | Yes — soft-delete + hard-delete after 30d |
| Long-term memories | Confidential | 1 year, user-purgeable | Yes |
| Approval records | Restricted | 6 years | No |
| Model routing telemetry (no content) | Internal | 1 year | N/A |

Right-to-delete is implemented as a tenant-admin Slack command that triggers a tombstone in Firestore + BigQuery DML; audit log entries are never deleted but PII fields inside them are tokenized at write time so deletion of the user mapping table effectively renders them unlinkable.

### 8. OWASP / agent-specific risks — top 3 mitigations

1. **Prompt injection from Slack messages and tool outputs.** Untrusted text from Slack (especially forwarded/quoted content rendered by `_extract_text_from_slack_blocks` in `gateway/platforms/slack.py`) and tool output (especially `kubectl` describe of user-controlled annotations, or web content) can carry instructions. Mitigations: (a) wrap all untrusted text in clearly-delimited spans the system prompt instructs the model to treat as data; (b) **never** auto-execute mutating tools from text alone — the T1/T2/T3 human-approval gates from §2 are the actual defense; (c) strip ANSI / zero-width / homoglyph control chars before prompt assembly.
2. **Tool-output feedback loops.** A poisoned tool result (e.g., a Confluence page or runbook MCP server returning "now run `rm -rf …`") could chain into a destructive call. Mitigations: separate tool-output channel in the prompt, signed runbook sources only, and the existing `ToolCallGuardrailController` repeat-failure circuit breaker (already in `tool_guardrails.py`) extended to flag suspicious instruction-shaped tool output.
3. **MCP server supply chain.** Each MCP server is effectively arbitrary code with our credentials. Mitigations: allowlist of approved MCP servers (manifest pinned to git SHA), network egress restricted, no MCP server may call Secret Manager directly, all MCP tool calls flow through the same Tier-classification gate as native tools.

### 9. Open compliance questions (for legal / GRC)

- BAA scope: do we need a BAA with Anthropic directly or is the Google Vertex BAA sufficient for Anthropic-on-Vertex (Claude on Vertex)?
- Are self-hosted Qwen/Gemma deployments subject to model-card / FDA-adjacent disclosure requirements given Abridge's clinical product, even though this tool is non-clinical?
- FedRAMP: is this system in or out of the Abridge FedRAMP boundary? If in, what's the inheritance story for the Cloud Run + Firebase + Vertex stack vs. our existing ATO?
- Audit-log retention: confirm 6 years is correct for HIPAA workforce-access logs in our jurisdiction; some states require longer.
- Cross-border: any restriction on routing prompts to Vertex regions outside the US? Do we need data-residency pinning for non-US engineers?
- Acceptable-use policy: do platform engineers need to sign an addendum acknowledging that Slack messages to the bot are recorded, retained, and reviewable by Security?

---

## UX & Slack Interaction Design

Hermes today already exposes a sophisticated Slack surface: native slash commands generated from `COMMAND_REGISTRY` (`/btw`, `/stop`, `/model`, `/help`, …), Block Kit exec-approval with three-tier buttons (Approve Once / Session / Always), assistant-thread lifecycle, ephemeral slash responses scoped per-user via a `ContextVar`, and reaction-based processing signals. The retrofit is mostly *curation and reframing*, not new plumbing.

### 1. Interaction patterns: DM, mention, slash, workflow

- **DM with the bot = personal incident scratchpad.** The on-call SRE pages from their phone, opens the DM, asks "what's burning?" Use the existing assistant-thread surface (`assistant_thread_started`) — already wired — as the canonical 1:1 mode. Default to terse output.
- **Channel mention = team-visible incident coordination.** `@hermes` in `#incident-payments-2026-05-04` is the canonical multi-person flow. **Discipline: one incident = one Slack thread**, scoped by `thread_ts`. The agent should refuse to answer top-level in incident channels (post an ephemeral nudge: "open a thread or DM me"), to keep channel signal high.
- **Slash commands = verbs, not chat.** Keep `/stop`, `/model`, `/help`, `/sync`. Add SRE verbs: `/oncall`, `/runbook <name>`, `/k <kubectl args>`, `/incident open|close|status`, `/spend`, `/tfplan <repo>`, `/page <service>`. Cut consumer verbs: `/btw` (Hermes' fun-fact command), `/personality`, `/voice`, `/imagine`, achievement/kanban entry points unless we keep them deliberately (see §7).
- **Workflow Builder buttons = "the big red one" entrypoints.** A pinned message in `#sre` with buttons: "Start Incident", "Page Owner", "Open Runbook". This is the 3am-from-phone path — no typing required.

### 2. Approval & confirmation UX

The existing `send_exec_approval` Block Kit pattern is a strong base, but its three buttons (Once / Session / Always) are wrong for prod blast radius. Replace with **risk-tiered approval**:

- **Tier 0 (read-only):** auto-execute, no prompt. `kubectl get`, `gcloud … describe`, log tails.
- **Tier 1 (mutating, low blast):** Approve Once / Reject / Edit-and-retry. Single approver from an allowlist (reuses today's exec-approval allowlist check at `slack.py:2316`).
- **Tier 2 (prod / multi-tenant impact):** **two-of-N approval**. Block Kit message shows `⚠️ Prod write — needs 2 SREs`. Each click adds a ✅ reaction with the user's name; the second qualifying click resolves the approval. Show the pending command in a code block, the inferred blast radius ("affects 14 pods, 3 namespaces"), and a 10-minute timeout banner that ticks down via message edits.
- Always post the **executed result** as a reply in the same thread, never as a new top-level message. Disable the buttons (atomic `_approval_resolved.pop`, already implemented) so a stale phone tap can't double-fire.

### 3. Persona-specific surfaces

- **3am on-call from phone:** default to a "triage card" — one Block Kit message with: severity, affected service, last 3 alerts, top suspect (LLM-summarized), and three buttons: *Ack page*, *Show graph*, *Open runbook*. No prose dump. Long output collapses to a "Show details" button that posts a snippet file on tap.
- **Platform engineer at desk during planned change:** verbose mode by default — full terraform plan in a snippet, diff highlighting, link to the PR, link to the runbook step list. They have a 27" monitor; use it.
- Toggle controlled by a per-user preference (`/prefs verbose=on`) and auto-detected from device (Slack delivers `client_msg_id` context; mobile defaults to terse).

### 4. Output formatting for SRE workloads

Hermes already has `format_message` and file-upload helpers — use them as a tiered ladder:

- **<20 lines:** inline triple-backtick code block.
- **20–200 lines:** Slack `files.upload` as a `.log`/`.yaml` snippet so syntax highlighting and "Expand" work.
- **>200 lines or binary diffs:** upload as a file with a 1-line summary and a "Top 5 changes" bullet list above it. Never paste a full `kubectl describe` inline — it nukes the channel.
- **Terraform plans:** always snippet, never inline; pre-summarize ("12 to add, 3 to change, 1 to destroy — destroy is `aws_rds_instance.payments_replica`, expand the file for full diff").
- **Multi-step output:** stream as edits to a single message with a checklist (`✅ fetched pods` / `⏳ describing deploy` / `⬜ tailing logs`), not N new messages.

### 5. Discoverability

The TUI's autocomplete is gone in Slack; replace it with three layers:

- **`/help` lands a Block Kit menu** grouped by job (Incidents, Runbooks, Cluster Ops, Spend, Admin), not alphabetically. Each group expands inline.
- **First-DM onboarding card** when a new user opens the assistant thread: "I'm Hermes. Ask me 'what's broken in prod-east?' or try a button below." Three example buttons that pre-fill the composer.
- **`/runbook` and `/k` accept partial input** and respond with an ephemeral picker (Block Kit `static_select`) when ambiguous. This recovers the autocomplete affordance.
- **Pinned canvas in `#sre`** (Slack Canvas) maintained by the agent listing top 10 commands with examples — auto-updated from `COMMAND_REGISTRY`.

### 6. Multi-tenant / multi-workspace

Abridge runs corp + customer-support + eng-only workspaces. Recommendations:

- **Install only in eng-relevant workspaces.** Customer-support workspace gets a *read-only* Hermes (status queries, no exec). Enforce by workspace ID at the slash dispatcher, not by trust.
- **Per-workspace allowlists** for approval and exec, stored alongside today's exec-approval list. Display the active workspace in `/help` header so engineers know which scope they're in.
- **No org-wide deploy** (`org_deploy_enabled: false` is already correct in the manifest).
- **Channel scoping:** Hermes responds in `#sre`, `#incident-*`, `#platform`, and DMs. Other channels: silent unless explicitly mentioned, and even then return an ephemeral "I'm scoped to platform/SRE work — try Apex for app questions."

### 7. Deliberate cuts

- **Voice memos, image gen, personality picker, fun-facts (`/btw`), achievements** — cut. Wrong persona; an SRE at 3am does not want a personality.
- **Kanban: keep, but reframe.** Repurpose as an *incident task tracker* tied to the incident thread, not a personal todo board. Each incident gets an ephemeral checklist the agent maintains.
- **Image upload handling: keep.** SREs paste Grafana screenshots constantly; OCR + chart description is high-leverage.
- **Free-form chat in arbitrary channels: cut.** Force mention or slash. Reduces noise and accidental costs.

### 8. Open UX questions for Drew & Trey

- Is there an existing Abridge incident-channel naming convention (`#inc-*` vs `#incident-*`) we should auto-detect to enable elevated mode?
- Do we want Hermes and Apex to be *visibly distinct* bots (different avatars, different mention names) or a single `@abridge-agent` that routes? The persona separation is cleaner if distinct.
- For Tier-2 prod approvals, is "any 2 SREs" sufficient, or do we need role-specific quorum (e.g., 1 SRE + 1 service owner)?
- Phone-first defaults: do we trust device detection from Slack metadata, or require an explicit `/oncall on` toggle that the pager integration sets automatically?
- Runbook execution surface: inline Block Kit step-by-step (one message per step, agent walks the human through), or fire-and-monitor with a single status card? Trade-off is engagement vs. noise.

---

## Cross-cutting open questions

A consolidated list of decisions that block forward motion. Each maps back to the section that raised it.

1. **Agent runtime substrate** — GKE Autopilot (recommended) vs. Vertex AI Agent Engine pilot. *(Architecture §6)*
2. **GPU sourcing** — GKE GPU node pool vs. on-prem Abridge hardware. *(Architecture §6, Backend §7)*
3. **Default routing policy** — which tool classes route to self-hosted Qwen/Gemma vs. Anthropic-on-Vertex / Vertex Gemini. *(Architecture §3, Backend §3)*
4. **FTS replacement** — local SQLite read-replica, Vertex AI Search, or Elasticsearch. *(Backend §2, §7)*
5. **Channel-strip scope** — delete files outright vs. archive on a branch. *(Architecture §6, Backend §1)*
6. **Tier-2 quorum** — any 2 SREs vs. role-specific (SRE + service owner). *(Security §2, UX §8)*
7. **Bot identity** — single `@abridge-agent` that routes to Apex/Hermes vs. two visibly distinct bots. *(UX §8)*
8. **BAA scope** — Vertex BAA sufficient for Anthropic-on-Vertex, or separate Anthropic BAA needed. *(Security §9)*
9. **FedRAMP boundary** — is the SRE assistant inside Abridge's existing ATO? *(Security §9)*
10. **Kanban fate** — keep and rewrite for Firestore-backed incident task tracking, or cut. *(Backend §2, UX §7)*

## Suggested next step

Land this plan, then schedule a 60-minute review with Drew + Trey + a security partner to walk the open-questions list above. After that meeting, the plan splits into the six-phase PR sequence in *Backend §6*, with phase 0 (removal + green CI) being the first concrete code PR.
