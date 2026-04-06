---
name: claude-code-migration
description: Migrate Claude Code settings, memories, rules, and MCP servers to Hermes Agent
version: 1.0.0
author: hernanqwz
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [Migration, Claude Code, Anthropic, Memory, Rules, Import]
    related_skills: [openclaw-migration]
    requires_toolsets: [terminal]
---

# Claude Code → Hermes Migration

Migrate your Claude Code configuration, memories, custom rules, and MCP server definitions into Hermes Agent.

## When to Use

Use this skill when:
- The user says "migrate from Claude Code" or "import my Claude settings"
- The user wants to bring over their Claude Code memories, rules, or MCP servers
- The user is switching from Claude Code to Hermes and wants to preserve their setup

## What Gets Migrated

| Category | Source | Destination | Default |
|----------|--------|-------------|---------|
| **Rules/Instructions** | `~/.claude/rules/*.md` | `SOUL.md` + `MEMORY.md` | Yes |
| **Project Memory** | `~/.claude/projects/*/memory/*.md` | `MEMORY.md` | Yes |
| **CLAUDE.md Files** | `CLAUDE.md` in project roots | Archived for reference | Yes |
| **MCP Servers** | `~/.claude/settings.json` | `~/.hermes/config.yaml` | Yes |
| **Custom Commands** | `~/.claude/commands/*.md` | `~/.hermes/skills/claude-imports/` | Yes |
| **API Keys** | `~/.claude/settings.json` | `~/.hermes/.env` | No |
| **Keybindings** | `~/.claude/keybindings.json` | Archived (different system) | No |

## Quick Reference

```bash
# Dry run (preview what would be migrated)
python3 ~/.hermes/skills/migration/claude-code-migration/scripts/claude_to_hermes.py

# Execute migration with user-data preset
python3 ~/.hermes/skills/migration/claude-code-migration/scripts/claude_to_hermes.py --execute --preset user-data

# Full migration including API keys
python3 ~/.hermes/skills/migration/claude-code-migration/scripts/claude_to_hermes.py --execute --preset full --migrate-secrets

# Select specific categories
python3 ~/.hermes/skills/migration/claude-code-migration/scripts/claude_to_hermes.py --execute --include rules,memory,mcp-servers
```

## Path Resolution

The migration script can be found at:
1. `~/.hermes/skills/migration/claude-code-migration/scripts/claude_to_hermes.py` (installed via hub)
2. `~/.hermes/hermes-agent/optional-skills/migration/claude-code-migration/scripts/claude_to_hermes.py` (bundled)

Always check both paths. Prefer the first if it exists.

## Default Workflow

1. **Always dry-run first.** Never execute without showing the user what will be migrated.
2. Present the dry-run summary clearly: how many rules, memories, MCP servers, etc.
3. Ask the user which preset they want: `user-data` (no secrets) or `full` (includes API keys).
4. If conflicts exist (e.g., existing MEMORY.md entries), present them and ask: skip, overwrite, or merge.
5. Execute with the chosen options.
6. Present the final report.

## User Interaction Protocol

When asking the user to make a decision, use the `clarify` tool with these rules:
- Present one decision at a time
- Offer 2-4 plain string options
- Map each option to the exact command flags

**Example:**
```
Options:
1. "User data only" → --preset user-data
2. "Everything including API keys" → --preset full --migrate-secrets
3. "Let me choose" → (show available categories)
```

## Post-Run Reporting

After execution, the script outputs a JSON report. Follow these rules:
1. Always show the summary counts (migrated, skipped, archived, conflicts, errors)
2. For merged memories, show how many entries were added vs duplicates
3. For overflow (entries that didn't fit in MEMORY.md), mention they're saved in the overflow directory
4. For MCP servers, list which ones were imported and their transport type
5. For archived items, explain they're saved for reference but need manual review
6. Never show raw JSON to the user — summarize in natural language

## Migration Categories

### rules (Claude Rules → SOUL.md + MEMORY.md)
- Global rules from `~/.claude/rules/*.md` are parsed by section
- Critical rules (workflow, gotchas) go into MEMORY.md entries
- Persona/behavioral rules go into SOUL.md
- Project-specific rules are archived with project context

### memory (Claude Memory → MEMORY.md)
- Files from `~/.claude/projects/*/memory/*.md` are parsed
- Each file becomes one or more MEMORY.md entries
- MEMORY.md index file is skipped (it's just pointers)
- Respects the 2,200 character limit; overflow saved separately

### mcp-servers (MCP Config → config.yaml)
- Reads `mcpServers` from `~/.claude/settings.json`
- Converts to Hermes MCP format in `config.yaml`
- Supports stdio, HTTP, and SSE transport types
- Environment variables and args are preserved

### custom-commands (Slash Commands → Skills)
- Custom commands from `~/.claude/commands/*.md` become Hermes skills
- Each command gets its own skill directory under `~/.hermes/skills/claude-imports/`
- Command name becomes skill name (kebab-case)

### api-keys (Settings → .env)
- Only migrated with `--migrate-secrets` flag
- Supported: ANTHROPIC_API_KEY, OPENAI_API_KEY
- Appended to `~/.hermes/.env` (never overwrites existing values)

## Pitfalls

- **MEMORY.md overflow**: Claude Code memories can be large. Entries that don't fit are saved to `overflow/` directory. Consider using mnemo (pgvector semantic search) for large knowledge bases.
- **MCP server paths**: Absolute paths in MCP server configs may differ between systems. Review imported configs.
- **Rules vs SOUL.md**: Not all rules belong in SOUL.md. The script uses heuristics to separate behavioral rules from factual knowledge.
- **Duplicate entries**: The script deduplicates by normalized text. Near-duplicates (slightly different wording) may still appear.

## Verification

After migration:
1. Check `~/.hermes/SOUL.md` — should contain persona and behavioral rules
2. Check `~/.hermes/memories/MEMORY.md` — should contain critical facts
3. Check `~/.hermes/memories/USER.md` — should contain user preferences
4. Run `hermes` and ask about something from your Claude Code rules
5. Check `~/.hermes/migration/claude-code/{timestamp}/report.json` for full details
