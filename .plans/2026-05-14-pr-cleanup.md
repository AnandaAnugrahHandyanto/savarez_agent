# 2026-05-14 PR cleanup handoff

## Completed PR sweep
- Reviewed today’s author PRs and closed overlapping/superseded ones.
- Kept open and in-progress lanes:
  - #25343 — Clear stale recovery state during model-switch transitions (ready for review)
  - #25332 — stop gateway memory leak on cached agent and session expiry
  - #25323 — Fix cron paths for runtime profile overrides
- Closed as duplicate/overlapping:
  - #25330 — superseded by #25332 (same problem space, broader fix in 25332)
  - #25334 — overlapping scope with #25324/#25326 and extra mixed changes
  - #25326 — mixed two separate fixes (proxy bypass + cron paths) already split elsewhere

## External feedback summary
- Only notable feedback was from `alt-glitch` comments on the closed PRs:
  - prefer one PR per fix area to avoid merge conflicts
  - #25326/#25334 overlap with #25324 (proxy bypass) and #25323 (cron paths)
  - #25330 overlaps with #25332 and existing PR #17276
- No formal review threads or inline review comments exist on remaining open PRs.

## Today’s actionable status
- #25343 comment-free after dedupe cleanup and marked open/ready.
- Next likely action: monitor #25324 (mentioned repeatedly as preferred standalone localhost proxy bypass PR) and continue with the three open PRs above.
