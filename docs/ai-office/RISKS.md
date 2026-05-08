# Hermes AI Office — Risk Register

Last updated: 2026-05-08 11:32 KST
Status: Planning artifact. No implementation approved.

| ID | Risk | Severity | Likelihood | Mitigation |
|---|---|---:|---:|---|
| R001 | Building pixel UI before reliable data creates a beautiful but misleading dashboard | High | Medium | Build read-only observability and `OfficeState` first; pixel layer later. |
| R002 | Pixel Agents code is VS Code/Claude-specific | High | High | Treat as reference; design Hermes adapters instead of copying lifecycle code. |
| R003 | Asset licensing is unclear or separate from MIT code | High | Medium | Audit every visual asset before reuse; prefer original/simple placeholder assets. |
| R004 | Raw transcripts/prompts/tool args leak through dashboard APIs | Critical | Medium | Redaction-first serializers; no raw transcript in MVP. |
| R005 | Browser controls accidentally mutate tasks/services | Critical | Low if scoped | MVP read-only; mutation layer requires explicit approval and security review. |
| R006 | Parallel standalone server complicates Hermes runtime | Medium | Medium | Use existing Hermes dashboard backend; do not add Express sidecar. |
| R007 | Telegram provenance is missing for existing tasks | Medium | High | Show unknown; design capture/backfill separately; do not fabricate metadata. |
| R008 | Dashboard exposure beyond localhost leaks operational state | Critical | Low if scoped | Localhost-first; remote only through Tailscale/VPN/auth after review. |
| R009 | `/new` loses planning context | Medium | Medium | Maintain `STATUS.md` and `NEXT.md` before phase changes. |
| R010 | NAS/Obsidian sync failures block dashboard/runtime | Medium | Low if scoped | Read-only optional panel only; never startup dependency. |
| R011 | Cron prompts/scripts expose sensitive content | High | Medium | Show job name/status/schedule/delivery only; redact prompts/scripts by default. |
| R012 | UI over-indexes on novelty and hides exact details | Medium | Medium | Always provide table/card inspector fallback with exact safe metadata. |

## Current highest risks

1. Data/provenance gap.
2. Privacy/redaction.
3. Asset/license uncertainty.
4. Premature implementation.

## Risk decision gate

Before any implementation approval, Stage 5 architecture must include:

- redaction policy,
- data-source failure behavior,
- endpoint list,
- test plan,
- renderer/dependency decision if pixel work is in scope.
