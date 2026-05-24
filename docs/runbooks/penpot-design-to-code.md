# Penpot Design-To-Code Runbook

Use this runbook when Hermes/Codex turns a Penpot concept, design system, or reference screen into a frontend implementation.

## Default Flow

1. Confirm the target workflow, audience, app framework, and existing component system.
2. Use Penpot as the primary design canvas when available. A written brief or reference screenshot is acceptable when Penpot is not connected.
3. Start with a read-only MCP prompt:
   - list pages, components, styles, tokens, and the focused page;
   - summarize the visible structure and likely implementation concerns;
   - do not create, rename, restyle, move, or delete anything yet.
4. If write actions are needed, produce an intended-change summary first, then apply small reversible changes.
5. Export or save the reference output: a Penpot screenshot/exported frame plus a short implementation brief.
6. Implement in code using the app's existing design system first. For new web apps, prefer shadcn/Radix/Tailwind unless the project already uses another stack.
7. Run browser QA with `docs/runbooks/frontend-visual-qa.md`.

## MCP Modes

Remote MCP is the default when available. Add the Penpot server URL through the Codex or MCP client UI. Do not commit MCP keys, remote URLs containing `userToken`, local session tokens, or screenshots showing tokens.

Local MCP is the fallback for local control:

```powershell
scripts/start_penpot_mcp.ps1
```

On platforms where the package runs cleanly through the registry, the direct command is still valid:

```powershell
npx -y @penpot/mcp@stable
```

The local MCP endpoint is:

```text
http://localhost:4401/mcp
```

Load the Penpot plugin from:

```text
http://localhost:4400/manifest.json
```

Keep the plugin connected to the intended Penpot file/page while agents work. MCP follows the active focused page, so verify the active tab/page before running prompts.

## File And Design-System Rules

- Use small libraries instead of one huge design file.
- Use meaningful page, board, layer, component, and token names.
- Prefer CSS-friendly token names such as `bg-surface`, `text-muted`, `border-danger`, and `radius-panel`.
- Use Flex/Grid layouts so the design maps to real responsive CSS.
- Annotate components when usage rules matter.
- Keep primitive, semantic, and component tokens small enough to understand.
- Avoid detached component sprawl; create variants or new components deliberately.
- Keep concept art, moodboards, and production UI frames separated.

## Safety Rules

- First MCP operation is read-only.
- Write actions require an intended-change summary.
- Do not commit MCP keys, tokens, generated secret URLs, or private Penpot exports.
- Do not let design tooling change live customer behavior.
- If Penpot MCP is unavailable, continue with screenshots/briefs and state the limitation.

## Output Contract

A frontend card using this runbook should hand off:

- Penpot file/page/frame reference or reference screenshot path;
- implementation brief with target workflow and chosen direction;
- token/component assumptions;
- screenshots from the final browser QA;
- unresolved design or backend-contract risks.
