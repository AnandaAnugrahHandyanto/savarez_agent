# BMad + Rosetta setup for contributors

This repository contains BMad Method scaffolding and Rosetta-equivalent AS-IS docs so contributors can plan future Hermes Agent source changes with a real BMad + Rosetta workflow.

## What is committed

- `_bmad/` — BMad Method core/BMM configuration and helper scripts.
- `.claude/skills/` — BMad-generated Claude Code skills.
- `_bmad-output/project-context.md` — bridge from BMad agents to Rosetta AS-IS docs.
- Root AS-IS docs:
  - `TECHSTACK.md`
  - `CODEMAP.md`
  - `DEPENDENCIES.md`
  - `ARCHITECTURE.md`
  - `CONTEXT.md`

## What is intentionally not committed

Personal installer answers and project-level external plugin activation are not committed as shared source defaults.

Each contributor can keep local overrides in:

- `_bmad/custom/config.user.toml`

That file is ignored by `_bmad/custom/.gitignore` and is not touched by the installer.

## Optional Rosetta plugin activation for Claude Code

If you use Claude Code and want to enable the Rosetta plugin locally, create `.claude/settings.json` in your checkout with:

```json
{
  "extraKnownMarketplaces": {
    "rosetta": {
      "source": {
        "source": "github",
        "repo": "griddynamics/rosetta"
      }
    }
  },
  "enabledPlugins": {
    "rosetta@rosetta": true
  }
}
```

Review the plugin source and your organization's tool policy before enabling external Claude Code plugins.

## Refreshing BMad

To refresh the generated BMad assets, run from the repository root:

```bash
npx bmad-method install --directory . --modules core,bmm --tools claude-code --user-name Contributor --communication-language English --document-output-language English --output-folder _bmad-output --set core.project_name=Hermes-Agent --set bmm.user_skill_level=intermediate -y
```

After refreshing, remove or generalize any user-specific installer answers before committing.

## Boundary

Rosetta AS-IS docs describe the current repository. BMad PRDs, architectures, stories, and sprint artifacts describe future TO-BE work and should link back to the AS-IS docs instead of copying or overwriting them.
