---
name: obsidian
description: Read, search, and create notes in the Obsidian vault.
---

# Obsidian Vault

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

## Using with Hermes Wiki

Hermes also has a persistent markdown wiki via the `kb` tool.

- Set `LLM_WIKI_PATH` to a directory inside the same vault if you want the wiki and your notes to live together.
- If `LLM_WIKI_PATH` is unset and `OBSIDIAN_VAULT_PATH` is configured, Hermes may default the wiki to `"$VAULT/Hermes/Wiki"`.
- Prefer the `/wiki` workflow for the disciplined loop:
  `/wiki init` -> `/wiki ingest` -> `/wiki review` -> `/wiki map` -> `/wiki file-query|compare|entity|concept` -> `/wiki lint`
- Use the `llm-wiki` skill when you need the deeper operating model behind that workflow.
- Use this Obsidian skill for ad hoc note browsing and editing around the wiki, not as a replacement for the structured wiki maintenance flow.
