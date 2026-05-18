# PM plugin import isolation and cross-tool semantic parity

## When this applies

Use this reference when `crypto_bot_pm_status --live-gitea-read` reports a local-import blocker such as `Gitea snapshot module is unavailable`, or when PM status recommends regenerating PM/Kanban context while another PM tool can still read live Gitea state.

## Session-derived root cause pattern

A false snapshot-unavailable report can occur when a PM status module groups core and optional imports in one `try/except ModuleNotFoundError` block. If an optional helper import fails, the exception handler can set core capabilities such as `capture_gitea_snapshot` or `build_work_state` to `None`, causing PM status to synthesize a misleading `<local-import>` blocker even though the actual snapshot module exists and works.

Concrete pattern observed:

- `project_status.py` imported `scripts.hermes_pm.gitea_readonly_snapshot`, issue lifecycle helpers, work-state helpers, and `scripts.hermes_operator.*` CI evidence helpers in one import block.
- Missing `scripts.hermes_operator.gitea_ci_evidence_contracts` / `policy_audit` caused the fallback path to null out `capture_gitea_snapshot`.
- `crypto_bot_pm_status` then returned `Gitea snapshot module is unavailable` and `Review the Gitea snapshot blockers and regenerate the Kanban packet`.
- Direct snapshot execution and `crypto_bot_pm_kanban_packet` still read live Gitea correctly, proving the failure was control-plane import isolation rather than Gitea availability.

## Diagnostic sequence

1. Run the exact failing PM tool path, not only the underlying script:
   - `crypto_bot_pm_status(output_format="json")`
   - Check `command`, `cwd`, `pythonpath`, `returncode`, and `stdout_json.gitea_pm_snapshot_summary.blockers`.
2. Run the direct snapshot module from the plugin scripts directory:
   - `python3 gitea_pm_snapshot.py --format json`
   - Verify `http_methods_used == ["GET"]`, base URL/owner/repo, and open issue/PR counts.
3. Run the Kanban packet tool:
   - `crypto_bot_pm_kanban_packet(output_format="json")`
   - Compare seed issue existence, open issue count, and repo identity against PM status.
4. Probe imports using the same `PYTHONPATH` shape as the plugin wrapper:
   - plugin root first, managed product repo second.
   - Import `scripts.hermes_pm.project_status` and print whether `capture_gitea_snapshot`, `build_work_state`, and optional CI helper imports are `None`.
5. Treat disagreement between PM status and Kanban as a Hermes control-plane bug until proven otherwise.

## Durable fix pattern

- Split imports by authority/capability. Core Gitea snapshot import, issue lifecycle import, work-state import, and optional CI evidence imports should have independent guarded fallbacks.
- Missing optional CI evidence helpers must degrade only `ci_locality_readiness`; they must not disable Gitea snapshot capture or work-state generation.
- Use a small provider-status structure per import group, with `available`, `module`, `error_type`, and redacted `error`, and surface it in PM status as `provider_import_status`.
- Do not use unqualified fallback imports such as `gitea_readonly_snapshot` or `work_state`; keep imports fully qualified under the plugin package path so a different current working directory cannot hijack module resolution.
- Catch `ImportError` as well as `ModuleNotFoundError`/attribute failures at the provider boundary. A dependency import failure inside one provider must become that provider's unavailable status, not abort PM status import.
- Error payloads should name the specific missing module/import, not the downstream capability that was nulled by grouped fallback, and should be redacted before returning through plugin output.
- Add regression checks for the exact runtime wrapper command/PYTHONPATH, not just direct module execution.
- After fixing the source plugin, synchronize the installed runtime plugin asset from `/Users/preston/.hermes/hermes-agent/plugins/crypto-bot-pm` to `/Users/preston/.hermes/plugins/crypto-bot-pm` using the guarded user-asset installer, then verify source/runtime parity before trusting live plugin tool output.

## Regression gates to add

- `crypto_bot_pm_status --live-gitea-read` has no blocker with `endpoint: <local-import>` when the snapshot module is present.
- PM status live summary has non-null `base_url`, `owner`, `repo`, and GET-only methods.
- PM status and Kanban agree on seed Issue #1 existence and open issue count when run against the same live Gitea instance.
- Optional CI evidence import failure leaves `ci_locality_readiness.available == false` but does not make `gitea_pm_snapshot_summary` unavailable.
- PM/Kanban semantic parity helper classifies mismatches as a control-plane regression instead of letting contradictory recommendations pass silently.
- Count parsing in parity checks is fail-closed: malformed or boolean count values produce an explicit blocker rather than raising or silently coercing.
- Provider import helper regression covers plain `ImportError` raised during import, proving provider dependency failures are isolated into provider status.
- Independent pre-commit review should explicitly check for import hijacking via unqualified fallback imports and for brittle `int(value or 0)` parsing.
- Live installed-plugin validation must run after source tests: call the actual `crypto_bot_pm_status` and `crypto_bot_pm_kanban_packet` tools, then verify source/runtime parity remains `matches_source: true`.
- Add focused provider-isolation regression tests that simulate failures in optional providers and verify core providers remain available: optional CI/provider import failures must not null out Gitea snapshot capture, work-state generation, or PM status baseline fields.

## Reporting rule

Do not report this as a Gitea outage when direct snapshot or Kanban can read live state. Report it as PM plugin/control-plane import isolation plus missing semantic parity coverage.