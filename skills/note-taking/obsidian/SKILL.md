---
name: obsidian
description: Read, search, and create notes in the Obsidian vault.
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [obsidian, note-taking, vault, markdown]
    related_skills: [obsidian-markdown, obsidian-cli, obsidian-bases, json-canvas]
---

# Obsidian Vault

This is Hermes's broad, generic entry point for Obsidian work. Keep using it for straightforward filesystem-first vault tasks such as locating the vault, listing notes, searching note files, creating notes, and appending content.

When the task is format-specific or app-specific, route to the specialized skills instead:
- `.md` note authoring with wikilinks, properties/frontmatter, callouts, embeds, or Obsidian-specific Markdown semantics -> `obsidian-markdown`
- running Obsidian app workflows, Obsidian CLI usage, plugin development, or theme development -> `obsidian-cli`
- editing `.base` files or working with Bases filters, views, and formulas -> `obsidian-bases`
- editing `.canvas` files or visual canvases -> `json-canvas`

**Location:** Set via `OBSIDIAN_VAULT_PATH` environment variable (e.g. in `~/.hermes/.env`).

If unset, defaults to `~/Documents/Obsidian Vault`.

Note: Vault paths may contain spaces - always quote them.

## Read a note

```bash
VAULT="${OBSIDIAN_VAULT_PATH:-$HOME/Documents/Obsidian Vault}"
cat "$VAULT/Note Name.md"
```

## List notes

```bash
VAULT="${OBSIDIAN_VAULT_PATH:-$HOME/Documents/Obsidian Vault}"

# All notes
find "$VAULT" -name "*.md" -type f

# In a specific folder
ls "$VAULT/Subfolder/"
```

## Search

```bash
VAULT="${OBSIDIAN_VAULT_PATH:-$HOME/Documents/Obsidian Vault}"

# By filename
find "$VAULT" -name "*.md" -iname "*keyword*"

# By content
grep -rli "keyword" "$VAULT" --include="*.md"
```

## Create a note

```bash
VAULT="${OBSIDIAN_VAULT_PATH:-$HOME/Documents/Obsidian Vault}"
cat > "$VAULT/New Note.md" << 'ENDNOTE'
# Title

Content here.
ENDNOTE
```

## Append to a note

```bash
VAULT="${OBSIDIAN_VAULT_PATH:-$HOME/Documents/Obsidian Vault}"
echo "
New content here." >> "$VAULT/Existing Note.md"
```

## Wikilinks

Obsidian links notes with `[[Note Name]]` syntax. When creating notes, use these to link related content.
