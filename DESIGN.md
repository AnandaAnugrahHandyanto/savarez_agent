---
version: alpha
name: Hermes Desktop Control Surface
description: Calm operational control surface for Hermes gateways, agents, projects, chats, workspaces, and sessions.
colors:
  background: "#F8FAFF"
  foreground: "#17171A"
  surface: "#FFFFFF"
  surface-muted: "#F3F7FF"
  surface-elevated: "#FCFCFC"
  primary: "#0053FD"
  primary-foreground: "#FFFFFF"
  text-secondary: "#555A66"
  text-muted: "#626A78"
  success: "#16664C"
  warning: "#75521A"
  danger: "#B21F45"
  info: "#245F6D"
typography:
  title:
    fontFamily: Inter, ui-sans-serif, system-ui, sans-serif
    fontSize: 1rem
    fontWeight: 650
    lineHeight: 1.25
    letterSpacing: "-0.01em"
  section-label:
    fontFamily: Inter, ui-sans-serif, system-ui, sans-serif
    fontSize: 0.6875rem
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "0.04em"
  row-label:
    fontFamily: Inter, ui-sans-serif, system-ui, sans-serif
    fontSize: 0.8125rem
    fontWeight: 560
    lineHeight: 1.25
  meta:
    fontFamily: Inter, ui-sans-serif, system-ui, sans-serif
    fontSize: 0.75rem
    fontWeight: 450
    lineHeight: 1.25
  mono-meta:
    fontFamily: ui-monospace, SFMono-Regular, Menlo, monospace
    fontSize: 0.75rem
    fontWeight: 500
    lineHeight: 1.25
spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  sidebar-gutter: 8px
  row-gap: 4px
  section-gap: 14px
rounded:
  sm: 6px
  md: 10px
  lg: 14px
components:
  sidebar-row:
    backgroundColor: "{colors.surface-muted}"
    textColor: "{colors.foreground}"
    typography: "{typography.row-label}"
    rounded: "{rounded.md}"
    padding: 8px
  sidebar-row-active:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-foreground}"
    typography: "{typography.row-label}"
    rounded: "{rounded.md}"
    padding: 8px
  health-badge-ok:
    backgroundColor: "{colors.surface-muted}"
    textColor: "{colors.success}"
    typography: "{typography.meta}"
    rounded: "{rounded.sm}"
    padding: 4px
  health-badge-degraded:
    backgroundColor: "#FFF4E5"
    textColor: "{colors.warning}"
    typography: "{typography.meta}"
    rounded: "{rounded.sm}"
    padding: 4px
  health-badge-offline:
    backgroundColor: "#FDEAF0"
    textColor: "{colors.danger}"
    typography: "{typography.meta}"
    rounded: "{rounded.sm}"
    padding: 4px
  health-badge-setup:
    backgroundColor: "{colors.surface-elevated}"
    textColor: "{colors.info}"
    typography: "{typography.meta}"
    rounded: "{rounded.sm}"
    padding: 4px
  sidebar-row-meta:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-muted}"
    typography: "{typography.meta}"
    rounded: "{rounded.sm}"
    padding: 4px
  empty-state:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-secondary}"
    typography: "{typography.meta}"
    rounded: "{rounded.lg}"
    padding: 16px
---

## Overview

Hermes Desktop is an internal operational control surface, not a decorative chat skin. It should help a user understand which gateway is connected, which agent/project/chat context is active, and why a session list is empty or degraded.

The mental model is Codex.app-like in density and hierarchy: calm chrome, compact rows, strong selection affordance, and visible runtime health. Do not copy private implementation details or screenshots; use the model as a usability benchmark only.

Primary job-to-be-done: route attention and future actions across gateways, agents, projects, Telegram conversations, workspaces, and recent sessions without falling back to raw cwd/session history as the dominant structure.

## Colors

- Use the existing Desktop light control palette as the default: cool near-white chrome, blue primary, restrained operational status colors.
- `colors.primary` is reserved for active selection, primary action, and strong focus affordance. Do not use it as a decorative wash across every section.
- Gateway health tones are semantic: success means connected and websocket-ready; warning means partial/degraded; danger means offline or unreachable. Do not encode health with color alone.
- Borders should be visible enough to separate chrome from content, but never louder than active selection or warning/error states.
- Raw connection tokens, dashboard secrets, and private session text must never appear in UI, logs, examples, screenshots, or DESIGN.md updates. Token UI may show redacted preview only.

## Typography

- Keep sidebar labels compact and scannable. Row titles should fit common profile/topic/project names without forcing the sidebar wider.
- Use `section-label` for uppercase or small section headers only. Do not use all-caps for row names or explanatory copy.
- Use `meta` for counts, platform names, gateway states, and short degraded hints.
- Use `mono-meta` only for technical identifiers that must be compared exactly, and prefer human labels first.

## Layout

### Desktop shell

- Primary left sidebar order is fixed for the control-surface slice:
  1. New session and top-level nav actions
  2. Gateways
  3. Agents
  4. Projects
  5. Chats
  6. Workspaces
  7. Recent Sessions
- Projects and chats outrank workspaces. Workspace grouping is a fallback, not the product's main IA.
- Sidebar sections use compact rhythm: 8px outer gutter, 4px row gap, about 14px between semantic sections.
- Keep rows one-line by default with optional one-line meta. Use truncation with accessible title/tooltip for long topic/project names.
- Counts are loaded-session counts unless explicitly labeled otherwise. Do not imply unloaded history is absent.

### Control-surface semantics

- Gateway rows represent backend connections. They can filter or scope the view, but their first job is health and origin clarity.
- Agent rows represent live Hermes profiles/gateway actors. If agents do not have a real session mapping yet, render them as display/status rows, not clickable filters that lead to a generic empty session state.
- Project rows represent durable work objects, usually Telegram topic plus knowledge/project page. They should remain useful without expanding every session.
- Chat rows represent platform conversations not promoted to projects.
- Workspace rows represent cwd fallback for raw sessions. They must not visually outrank named project/topic context.
- Recent Sessions is a safety net for history, not the primary navigation model.

## Elevation & Depth

- Prefer flat, layered desktop chrome over cards everywhere. Use surface shifts, borders, and row states before heavy shadows.
- Sidebar rows should feel like native control rows: quiet default, clear hover, unmistakable active, and keyboard-visible focus.
- Elevated panels, menus, and dialogs may use shadow, but the sidebar control hierarchy should remain readable without elevation tricks.

## Shapes

- Use 6px radius for compact badges/chips, 10px for sidebar rows and controls, 14px for empty/degraded panels.
- Do not mix pill badges, square rows, and oversized rounded cards in the same sidebar section.
- Status dots must be small and paired with text or aria labels where status matters.

## Components

### Sidebar sections

- Section headers: small label, optional count, no large icons unless the section is collapsed.
- Section order and labels must stay stable: Gateways, Agents, Projects, Chats, Workspaces, Recent Sessions.
- Empty sections should usually be hidden unless their absence communicates an actionable setup/degraded state.
- Avoid icon soup. Icons may distinguish top-level routes or entity families, but row meaning should come from label, section, status, and meta.

### Sidebar rows

- Default row: label first, optional meta second, no more than one status badge/dot.
- Hover row: subtle background shift using tokenized row hover color, not a new hardcoded accent.
- Active row: high-contrast background/text using `sidebar-row-active` or equivalent CSS tokens.
- Focus row: visible 2px ring/outline with enough contrast on both active and inactive rows. Keyboard focus must not rely on hover styling.
- Disabled/display-only row: reduced interaction affordance, no pointer cursor, and microcopy/meta that explains why it is not selectable when needed.

### Gateway health

- Health must be visible but low-noise: one compact strip/badge per gateway or one aggregate strip when only one gateway is configured.
- Status vocabulary:
  - `Connected`: `/api/status` and `/api/ws` are usable.
  - `Degraded`: partial data or one required endpoint failed; healthy gateways still work.
  - `Offline`: backend unreachable or websocket unavailable.
  - `Setup needed`: no usable gateway is configured.
- `/api/status` alone is not enough for Desktop readiness. The Desktop remote backend requires Dashboard HTTP plus `/api/ws`.
- Degraded health must explain the affected source: agents, conversations, projects, sessions, websocket, or token/config. Do not collapse API failures into empty arrays that look like normal empty states.
- Never expose raw tokens. Token copy must use redacted preview and settings affordance, not inline secret text.

### Empty and degraded states

- Empty copy must name the scope: `No sessions loaded for this project yet`, not `No sessions`.
- Project empty state must distinguish:
  - no known project history
  - known history not loaded yet
  - backend data degraded or unavailable
- A selected Agent with no session mapping should not send the Recent Sessions pane into a generic empty state. Either show the agent as display-only or provide a real agent activity/session scope.
- Degraded state copy should include a next check when useful: `Gateway connected, but /api/projects failed. Recent sessions are still available.`
- Loading and empty states must preserve layout stability so the sidebar does not jump when data arrives.

### Token and usage data

- Token counts are usage metrics, not credentials. They can be shown only as aggregate input/output/total counts tied to a session or model.
- Do not label connection secrets as tokens without context. Use `credential`, `dashboard token`, or `redacted token preview` when referring to auth.
- Never render raw dashboard/session tokens in rows, logs, examples, test fixtures, or screenshots.
- If a metric is stale or partial, label it as such; do not present stale counts with live authority.

## Do's and Don'ts

Do:
- Preserve the control-surface IA: Gateways → Agents → Projects → Chats → Workspaces → Recent Sessions.
- Make gateway health legible without turning the sidebar into an alarm panel.
- Prefer named Telegram topic/project context above cwd fallback.
- Use design tokens or existing CSS variables for color, spacing, radius, and focus styling.
- Provide explicit states for loading, empty, degraded, disabled/display-only, hover, active, and focus.
- Keep copy concise, operational, and specific to the selected scope.

Don't:
- Do not ship generic SaaS cards inside the sidebar.
- Do not create clickable rows that only lead to unexplained empty results.
- Do not hide backend/API failures by returning empty UI with no degraded explanation.
- Do not introduce hardcoded one-off colors when a token or semantic status color exists.
- Do not make Workspaces the primary hierarchy when project/topic context exists.
- Do not print, store, screenshot, or document raw tokens/secrets.

## Accessibility and Review Acceptance

Target WCAG 2.2 AA for text, controls, and focus indicators.

Acceptance notes for this control surface:

- Sidebar hierarchy: Gateways, Agents, Projects, Chats, Workspaces, and Recent Sessions are visually distinct, in that order, with Workspaces clearly treated as fallback.
- Gateway health: connected/degraded/offline/setup-needed states are visible, low-noise, and based on Dashboard HTTP plus `/api/ws` readiness where relevant.
- Empty/degraded states: copy names the selected scope and distinguishes no data, not-yet-loaded data, and failed/partial backend data.
- Token usage: auth tokens are redacted and never logged/rendered raw; usage token counts are aggregate metrics only and labeled when stale/partial.
- States: every sidebar row or control has default, hover, active, focus, disabled/display-only, loading, empty, and degraded behavior defined or intentionally not applicable.
- Visual evidence: final design sign-off needs approved screenshot/browser/electron evidence or an explicit note that review was code-contract-only.
- Implementation evidence: run focused sidebar tests and Desktop typecheck/build where a UI implementation changes; this contract-only edit may be validated with `npx -y @google/design.md lint DESIGN.md`.
