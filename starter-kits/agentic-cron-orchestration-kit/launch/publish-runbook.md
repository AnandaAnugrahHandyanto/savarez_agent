# Publish Runbook — Agentic Cron Orchestration Kit

## Purpose
Execute the shipped launch line without reopening scope.

The product is already shippable on the **starter-workflow claim**. This runbook exists to remove the last launch-execution friction: posting the thread and pairing it with the right proof/demo assets.

## Honest launch line
Only claim what is already proved:
- from a fresh notes context
- after injecting the exact note paths and workspace path into the prompt templates
- an operator can run preflight, schedule one recurring workflow, and execute the evening-doc-sync loop
- recorded clean-room proof time: **1.74 minutes**

Do **not** claim full four-job-pack end-to-end proof.

## Required source files
- `launch/launch-thread.md`
- `launch/demo-outline.md`
- `launch/demo-capture-runbook.md`
- `launch/demo-captions.srt`
- `qa/clean-room-proof-run-2026-04-17.md`
- `launch/ship-note.md`

## Publish order
1. Run `bash starter-kits/agent-launch-closeout-kit/scripts/publish-preflight.sh`.
2. If the preflight uses the browser-first path, verify the real publish session is actually signed into X before proceeding. `~/.hermes/state/x-access.json` and `Publish path: browser-session marker ready` are not enough by themselves. If `https://x.com/` shows the logged-out landing page or `compose/post` redirects to login, stop and treat publish as blocked.
3. Re-open `launch/launch-thread.md` and post it with no broader claim edits.
4. Attach or link the strongest supporting proof artifact available:
   - primary: short demo using the shot list + captions
   - fallback: screenshot/snippet of `qa/clean-room-proof-run-2026-04-17.md` showing **1.74 minutes**
5. Keep the CTA narrow: this is the fastest honest path to one recurring workflow, not a control plane.
6. After posting, record the post URL and timestamp in the weekly notes and ship checklist.

## Ready-to-post thread payload
```text
Most "autonomous" agent setups are fake autonomy. They only move when you remember to prompt them again.

I packaged the recurring operator loop we use inside Hermes into a starter kit: the Agentic Cron Orchestration Kit.

Proof-backed outcome so far: from a fresh notes context, one recurring evening-doc-sync workflow was scheduled and run in 1.74 minutes once the exact note/workspace paths were injected.

It ships one opinionated weekly operating system:
- Monday kickoff
- Daily CEO review
- Evening doc sync
- Friday ship review

The kit includes:
- cron job prompts
- project-note templates
- ship checklist template
- a local preflight script

This is intentionally not a dashboard or control plane. It is the fastest path to keeping one project moving without babysitting your agent.

The real setup contract is now clear: you still have to inject the exact note paths and workspace path into each prompt before the loop is runnable from a fresh context.

If you run Hermes/Codex/Claude/OpenCode-style agents and want them to keep advancing while you sleep, this is the starter system.
```

## Attachment priority
1. Short walkthrough cut using `demo-captions.srt`
2. Still image from the proof artifact showing the 1.74-minute run
3. Screenshot of `Preflight OK`

## Launch guardrails
- Never imply that unpublished demo capture blocks the product ship decision.
- Never widen the claim to "full autonomous operating system" without fresh proof.
- Never hide the explicit path-injection requirement.
- If demo capture is still pending, publish the thread anyway against the proved starter-workflow line.
- If the browser-first marker and the live browser session disagree, trust the live browser session and treat auth as still blocked.

## Completion record
After publish, update:
- `launch/launch-execution-log.md`
- weekly factory note current-week focus
- `MVP Pipeline — Week of 2026-04-13.md`
- `Agentic Cron Orchestration Kit — CEO Note.md`
- `Agentic Cron Orchestration Kit — Ship Checklist.md`
with the post URL, timestamp, and whether demo media was attached.
