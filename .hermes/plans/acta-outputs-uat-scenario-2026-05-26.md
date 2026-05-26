# Acta Outputs UAT Scenario Slice — 2026-05-26

## CEO feature bet selection

1. **Obvious but necessary — extend browser UAT from feed/jobs to Outputs shelf.**
   - Why P: Outputs are the durable artifact library; if they leak raw logs or become unreadable on phone, Acta stops being trustworthy.
   - Moment: P opens `/outputs`, taps the newest artifact, checks provenance/read state, and expects no prompt/tool/path leakage.
   - Payoff: Each future renderer change can be gated by an actual operator acceptance scenario, not just unit tests.
   - Risk: Low; harness-only plus tests, no production data/model changes.
   - MVP: Add `--scenario outputs` to `scripts/acta_browser_uat.py`, with fixture tests for readable signed rows, raw-log leakage sentinels, mobile overflow/console checks, and metadata in JSON report.
   - CEO rating: 8/10.

2. **High-leverage personal workflow — persisted output importance/routing preference memory.**
   - Why P: Acta could learn which output types deserve lead vs background.
   - Moment: P repeatedly ignores dev sprint noise but opens daily briefing outputs.
   - Payoff: Compounding rank/routing intelligence.
   - Risk: Medium/high; touches preference architecture and needs product taste calibration.
   - MVP: Spike only.
   - CEO rating: 7/10.

3. **Weird/magical — Telegram follow-up prep cards from output provenance.**
   - Why P: Acta could draft the exact ASK/FOLLOW-UP prompt for a source object.
   - Moment: P sees a report and wants to challenge/extend it without composing context.
   - Payoff: Moves Acta from display to agency.
   - Risk: Overbuild/fake-AI unless backed by real Telegram/source context.
   - MVP: Later spike.
   - CEO rating: 7/10.

## Decision
BUILD NOW: Outputs browser UAT scenario. It is small, safe, verifiable, and protects a high-value operator moment.

## Scope
- Update `scripts/acta_browser_uat.py` to support `--scenario outputs`.
- Validate Outputs shelf identity, rows, signed/openable rows, read-state/toggle affordances, provenance/confidence/freshness copy, and absence of raw prompt/tool/path leakage.
- Add tests in `tests/cron/test_acta_browser_uat.py`.

## Out of scope
- No cron job changes.
- No production deploy.
- No authentication changes.
- No new fake data or fake metrics.

## Verification
- Targeted pytest for Acta browser UAT tests.
- Run harness against a generated local Outputs fixture at 390x844 if browser CLI is available.
- Git diff/status review and stale leakage sentinel scan.
