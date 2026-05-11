---
name: artifact-builder
description: Use when building Hermes Canvas/Artifacts deliverables out-of-band, especially HTML/SVG/Markdown/Mermaid artifacts that should be registered with artifact_present instead of pasted into main chat.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [artifacts, canvas, html, svg, mermaid, dashboard, preview, design, sandbox]
    related_skills: [claude-design, sketch, popular-web-designs, architecture-diagram, excalidraw, verification-before-completion]
---

# Artifact Builder

## Overview

Use this skill to act as a focused artifact builder for Hermes Canvas/Artifacts. The builder creates a concrete artifact file or generated content, registers it through `artifact_present`, and returns only structured artifact metadata plus a short human note.

This is the Hermes-native version of the useful part of OpenClaw Canvas: build something visual or reusable, put it into a controlled artifact store, and let the Dashboard render it in a sandboxed preview. It is not a browser bridge, not a native WebView controller, and not a permission slip for tiny browser demons to touch the agent runtime.

## When to Use

Use this skill when the user asks for:

- a rendered HTML artifact, dashboard, prototype, report, slide/deck, or component board;
- an SVG, Mermaid, Markdown, JSON, or text artifact that should be browsed later;
- a Canvas/Artifacts-style deliverable rather than prose in chat;
- multiple visual variants where the final output should be previewable in the Artifacts Dashboard;
- a subagent/profile that builds artifacts while the main chat stays compact.

Do not use this skill for:

- ordinary prose answers that fit in chat;
- production app changes in an existing repo, unless the artifact is a separate preview/report;
- bidirectional UI bridges or agent-control surfaces;
- `canvas.eval`, arbitrary iframe JS control, or raw HTML injection into Dashboard DOM.

## Contract

Main chat never receives raw HTML dumps by default. The builder writes or generates the artifact out-of-band and calls `artifact_present`. Return structured artifact metadata, not the whole file body.

Minimum success payload after `artifact_present`:

```json
{
  "success": true,
  "artifact": {
    "id": "revenue-dashboard",
    "version": 1,
    "title": "Revenue Dashboard",
    "contentType": "text/html",
    "path": "$HERMES_HOME/artifacts/revenue-dashboard/versions/1/index.html",
    "url": "/api/plugins/artifacts/preview/revenue-dashboard/versions/1/index.html"
  }
}
```

If registration fails, return a concise timeout/failure object or note with:

- what was attempted;
- the exact failed check or tool error;
- whether a local source file exists;
- the safe next action.

Do not silently fall back to pasting the artifact into chat. That defeats the point and makes token budgets cry quietly in a corner.

## Workflow

1. **Intake**
   - Identify artifact type: `text/html`, `image/svg+xml`, `text/markdown`, `application/vnd.mermaid`, `application/json`, or `text/plain`.
   - Decide whether the artifact is generated from `content` or first written as a local `source_path`.
   - Pick a stable, lowercase artifact id when persistence/versioning matters.

2. **Build**
   - Prefer a complete, portable file with local CSS/JS for HTML artifacts.
   - Keep assets under the artifact source directory before registration.
   - For standalone HTML, use semantic markup, accessible contrast, responsive layout, and no secrets or private env data.
   - For Mermaid/Markdown/SVG, ensure the content is valid enough for preview/download.

3. **Verify before registration**
   - Confirm the source file exists and has substantive content.
   - For HTML/SVG/JSON/Mermaid, run a cheap syntax or structural check where available.
   - For visual artifacts, use browser/snapshot/vision verification when available.
   - Fix visible broken layout, console errors, or missing data before presentation.

4. **Register**
   - Call `artifact_present` with exactly one of `content` or `source_path`.
   - Pass `title`, optional `artifact_id`, `content_type`, and a safe `filename`.
   - Let the tool copy the file into `$HERMES_HOME/artifacts/<id>/versions/<n>/` and create the manifest.

5. **Return**
   - Return the JSON metadata or its key fields: id, version, title, contentType, path, url.
   - Add one short note about what was built and any caveat.
   - Do not include raw HTML/CSS/JS unless the user explicitly asks for source.

## Tool Use Pattern

For generated content:

```python
artifact_present(
    title="Revenue Dashboard",
    artifact_id="revenue-dashboard",
    content=html,
    filename="index.html",
    content_type="text/html",
    description="Interactive revenue dashboard prototype"
)
```

For an existing file:

```python
artifact_present(
    title="Architecture Diagram",
    artifact_id="architecture-diagram",
    source_path="/absolute/path/to/diagram.svg",
    content_type="image/svg+xml",
    description="System architecture diagram"
)
```

Use `source_path` for anything large, multi-step, or visually verified from disk. Use `content` for small generated artifacts where keeping a separate source file adds no value.

## Runtime and Safety Constraints

- Preview must use the Artifacts Dashboard sandboxed preview path.
- No `allow-same-origin` by default.
- No `canvas.eval`.
- No direct JS bridge from artifact iframe to agent runtime.
- No rendering generated HTML directly in Dashboard DOM.
- No LAN exposure or public bind changes.
- No copying dotfiles, `.env`, private keys, tokens, or secret-looking files.
- No symlink tricks, path traversal, or absolute output filenames.
- Avoid external CDNs unless the user explicitly accepts network dependencies; default to local/self-contained artifacts.

## Design Quality Bar

For HTML and visual artifacts:

- Use real copy and realistic data, not lorem ipsum confetti.
- Make layout responsive enough for desktop and narrow viewports.
- Include meaningful empty/error/loading states when the artifact represents a product UI.
- Prefer a coherent visual stance over generic gradient-card soup.
- Keep JavaScript minimal and local to the artifact.

When the assignment is primarily design, combine this with `claude-design`, `sketch`, or `popular-web-designs`. Those skills drive taste; this one drives artifact lifecycle and registration.

## Verification Checklist

- [ ] Artifact type and filename are explicit.
- [ ] Source file or generated content exists and is substantive.
- [ ] Visual/syntax verification ran where practical.
- [ ] `artifact_present` returned `success: true`.
- [ ] Returned metadata includes `id`, `version`, `title`, `contentType`, `path`, and `url`.
- [ ] Preview URL starts with `/api/plugins/artifacts/preview/`.
- [ ] Main response does not paste raw HTML by default.
- [ ] No secrets, dotfiles, symlinks, path traversal, or unsafe iframe privileges are involved.

## Common Pitfalls

1. **Pasting the full artifact into chat.** Use `artifact_present`; chat gets the handle.
2. **Skipping visual verification.** HTML that technically exists can still look like a ransom note generated by CSS.
3. **Using unsafe iframe privileges.** `allow-same-origin` and bridges are later-phase decisions, not MVP defaults.
4. **Treating OpenClaw Canvas SKILL.md as the implementation.** OpenClaw relies on a broader Canvas plugin/host/native surface. Hermes needs plugin + store + sandbox + tool.
5. **Registering secrets by accident.** Never pass `.env`, keys, cookies, token dumps, or hidden files as source artifacts.

## Reference

See `references/artifact-runtime-api.md` for the current `artifact_present` payload shape, supported content types, preview URLs, and failure contract.
