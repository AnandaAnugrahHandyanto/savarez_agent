# Frontend Visual QA Runbook

Use this runbook for meaningful UI changes, especially internal tools, dashboards, websites, and Penpot/reference-driven implementation.

## Required Checks

- Desktop viewport screenshot.
- Mobile or narrow viewport screenshot.
- Important interaction checked.
- Loading, empty, error, ready, disabled, success, and long-content states checked when relevant.
- Console errors checked.
- keyboard navigation or focus-visible basics checked.
- Accessibility basics checked: landmarks, labels, contrast risk, and button/link affordance.
- Responsive text and container overflow checked.
- screenshot comparison against Penpot, exported frame, or reference screenshot when available.

Do not report UI ready from code inspection alone.

## Quality Bar

- The first screen must be useful, not decorative.
- Operational tools should be dense, scannable, and calm.
- Visual hierarchy, spacing, and alignment must be intentional.
- Text must not overlap, clip, or resize unpredictably.
- Animation should clarify interaction, state change, or spatial orientation.
- Avoid generic AI UI: bland cards, one-note palettes, nested cards, decorative blobs, and marketing hero layouts for operator tools.

## Evidence

The handoff should include:

- changed files;
- reference used: Penpot link, screenshot, or written brief;
- desktop and mobile screenshot paths;
- interaction/state checks performed;
- console and accessibility notes;
- known limitations or follow-up approvals.

If browser automation cannot run, state the blocker and provide the strongest available fallback evidence.
