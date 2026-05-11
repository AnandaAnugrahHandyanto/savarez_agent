# Artifact Runtime API

Current Hermes Canvas/Artifacts runtime surface for the `artifact-builder` skill.

## Tool: `artifact_present`

Registers generated content or an existing local file as a versioned Hermes artifact under `$HERMES_HOME/artifacts` and returns structured metadata for the Artifacts Dashboard.

Call with exactly one of:

- `content`: string content to write into the artifact version directory.
- `source_path`: existing local regular file to copy into the artifact version directory.

Common arguments:

```json
{
  "title": "Revenue Dashboard",
  "artifact_id": "revenue-dashboard",
  "content": "<html>...</html>",
  "filename": "index.html",
  "content_type": "text/html",
  "description": "Interactive revenue dashboard prototype"
}
```

Successful result:

```json
{
  "success": true,
  "artifact": {
    "id": "revenue-dashboard",
    "version": 1,
    "title": "Revenue Dashboard",
    "contentType": "text/html",
    "path": "$HERMES_HOME/artifacts/revenue-dashboard/versions/1/index.html",
    "url": "/api/plugins/artifacts/preview/revenue-dashboard/versions/1/index.html",
    "createdAt": "2026-05-11T00:00:00Z"
  }
}
```

Failure result:

```json
{
  "success": false,
  "error": "Provide exactly one of content or source_path"
}
```

Failures must be reported as structured error notes. Do not paste the artifact source into chat as a fallback unless the user explicitly asks for source.

## Structured artifact event

Rich clients can render artifact cards from this optional event envelope:

```json
{
  "type": "artifact",
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

Use `agent.artifacts.artifact_event_from_tool_result(...)` to convert a successful `artifact_present` JSON result into this envelope. Plain clients can ignore the event and render `agent.artifacts.render_artifact_fallback_text(...)`, e.g. `Artifact ready: Revenue Dashboard (text/html, v1)` plus the preview URL. This keeps the response backward compatible while avoiding prose scraping.

The event carries preview metadata only. It must not contain raw HTML/source content, external preview URLs, dotfile/secret fields, or bridge instructions.

## Supported content types

The current tool accepts caller-provided MIME/content types. Preferred types for Dashboard artifacts:

| Type | Filename | Use |
| --- | --- | --- |
| `text/html` | `index.html` | Standalone HTML artifact, prototype, dashboard, deck |
| `image/svg+xml` | `index.svg` or source filename | SVG diagrams and visualizations |
| `text/markdown` | `index.md` or source filename | Markdown reports and docs |
| `application/vnd.mermaid` | `diagram.mmd` | Mermaid diagrams |
| `application/json` | `data.json` | JSON data artifacts |
| `text/plain` | `artifact.txt` | Plain text outputs |

If `filename` is omitted for generated `content`, the tool chooses defaults such as `index.html`, `index.svg`, `index.md`, `diagram.mmd`, `data.json`, or `artifact.txt` based on `content_type`.

## Preview URLs

Artifacts are previewed through the Dashboard plugin API:

```text
/api/plugins/artifacts/preview/<artifact_id>/versions/<version>/<filename>
```

Example:

```text
/api/plugins/artifacts/preview/revenue-dashboard/versions/1/index.html
```

The Dashboard viewer should load preview URLs in a sandboxed iframe. The MVP default is `sandbox="allow-scripts"` without `allow-same-origin`.

## Storage layout

```text
$HERMES_HOME/artifacts/
└── revenue-dashboard/
    ├── manifest.json
    └── versions/
        └── 1/
            └── index.html
```

The manifest tracks `id`, `title`, `description`, `contentType`, `latestVersion`, timestamps, and version entries.

## Safety constraints

`artifact_present` rejects or should reject:

- calls with both `content` and `source_path`, or neither;
- unsafe output filenames such as absolute paths, `..`, dotfiles, and secret-looking names;
- source files that are dotfiles, symlinks, non-regular files, or secret-looking files;
- attempts to expose `.env`, keys, PEM files, or token dumps.

The preview resolver separately blocks traversal, dotfiles, secret-looking files, invalid artifact ids, and path escapes from the artifact root.

## Builder responsibilities

Before calling `artifact_present`, the builder should:

1. choose the content type and filename;
2. produce substantive content or a source file;
3. run syntax/visual checks where practical;
4. register the artifact;
5. return only structured artifact metadata and a short summary.

Main chat never receives raw HTML dumps by default.
