# Live Browser Auth Audit — 2026-04-21

## Purpose
Prove the real publish blocker from the live Hermes publish surface instead of trusting a stale readiness marker.

## Evidence checked
1. `~/.hermes/state/x-access.json`
   - reports `mode: browser-session`
   - reports `status: ready`
   - handle: `KelEvur`
2. `bash starter-kits/agent-launch-closeout-kit/scripts/publish-preflight.sh`
   - returns `Publish preflight OK`
   - returns `Publish path: browser-session ready (KelEvur)`
   - X API env vars still missing: `5/5`
3. Live browser inspection in the Hermes browser session
   - `https://x.com/` rendered the logged-out landing page
   - visible evidence included `Already have an account?` and `Sign in`
   - `https://x.com/compose/post` redirected into the login flow instead of reaching the composer

## Finding
`x-access.json` is only a local browser-session marker. It is not sufficient proof that the actual Hermes publish session is authenticated right now.

## Decision
Treat publish as blocked until the real publish session reaches a logged-in X surface (ideally the composer) in the same environment that will do the post.

## Required next proof
Before claiming publish is unblocked, capture all of the following in the same block:
- live browser session reaches `https://x.com/home` or the composer while signed in
- composer is available for `starter-kits/agentic-cron-orchestration-kit/launch/launch-thread.md`
- post URL and timestamp are recorded in `starter-kits/agent-launch-closeout-kit/launch-execution-log.md`

## Consequence for this MVP
The closeout kit should keep the browser-first publish path, but it must require a live browser auth check in addition to the `x-access.json` marker.
